"""Environment diagnostics for first-run setup (`open-frame doctor`)."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from openframe.desktop_access import (
    permission_denied_message,
    read_display_power,
    screen_unavailable_message,
)

CheckStatus = Literal["pass", "fail", "skip"]

_PACKAGE = "off-camber-open-frame"
_MCP_REQUIRED_EXTRAS = ("extra_ocr", "extra_act", "extra_mcp")
MCP_CLIENT_PERMISSION_NOTE = (
    "Screen Recording and Accessibility must be granted to the MCP client app "
    "(Cursor or Claude Desktop), not the terminal that ran doctor."
)


def _extra_hint(extra: str) -> str:
    return f'pip install "{_PACKAGE}[{extra}]"'


# Optional extras: absent → skip (informational), not a failure.
_EXTRA_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("extra_ocr", ("PIL", "pytesseract"), _extra_hint("ocr")),
    ("extra_act", ("pyautogui",), _extra_hint("act")),
    ("extra_flow", ("yaml",), _extra_hint("flow")),
    ("extra_agent", ("anthropic",), _extra_hint("agent")),
    ("extra_mcp", ("mcp",), _extra_hint("mcp")),
    ("extra_template", ("PIL", "numpy"), _extra_hint("template")),
)


@dataclass(frozen=True)
class CheckResult:
    """One doctor check row."""

    id: str
    status: CheckStatus
    detail: str
    hint: str | None = None
    required: bool = True


def mcp_client_config() -> dict[str, Any]:
    """Ready-to-paste MCP client config using this interpreter."""
    return {
        "mcpServers": {
            "open-frame": {
                "command": sys.executable,
                "args": ["-m", "openframe.cli", "mcp", "serve"],
            }
        }
    }


def run_doctor(*, mcp: bool = False) -> list[CheckResult]:
    """Run all environment checks and return results in display order."""
    checks: list[CheckResult] = [
        _check_platform(),
        _check_python(),
        _check_tesseract(),
        _check_ocr(),
    ]
    checks.extend(_check_extras())
    checks.append(_check_display_power())
    checks.append(_check_screen_recording())
    checks.append(_check_accessibility())
    checks.append(_check_displays())
    if mcp:
        checks = _require_mcp_extras(checks)
        checks.append(_check_mcp_server(checks))
    return checks


def doctor_ok(checks: list[CheckResult]) -> bool:
    """True when every required check passed."""
    return all(item.status == "pass" for item in checks if item.required)


def format_doctor_text(checks: list[CheckResult]) -> str:
    """Human-readable doctor report."""
    lines = ["Open Frame doctor"]
    width = max(len(item.id) for item in checks)
    for item in checks:
        lines.append(f"  [{item.status:<4}] {item.id:<{width}}  {item.detail}")
        if item.hint and item.status != "pass":
            lines.append(f"         hint: {item.hint}")
    overall = "ok" if doctor_ok(checks) else "not ready"
    lines.append(f"overall: {overall}")
    return "\n".join(lines)


def format_doctor_json(checks: list[CheckResult]) -> dict[str, Any]:
    """Machine-readable doctor report."""
    return {
        "ok": doctor_ok(checks),
        "checks": [asdict(item) for item in checks],
    }


def _check_platform() -> CheckResult:
    system = platform.system()
    if system != "Darwin":
        return CheckResult(
            id="platform",
            status="fail",
            detail=f"macOS required; got {system}",
            hint="Open Frame currently supports macOS only.",
            required=True,
        )
    version = platform.mac_ver()[0] or "unknown"
    return CheckResult(
        id="platform",
        status="pass",
        detail=f"Darwin {version}",
        required=True,
    )


def _check_python() -> CheckResult:
    major, minor, micro = _python_version()
    detail = f"{major}.{minor}.{micro}"
    if (major, minor) < (3, 11):
        return CheckResult(
            id="python",
            status="fail",
            detail=f"Python {detail} (need >= 3.11)",
            hint="Install Python 3.11+ and recreate your virtualenv.",
            required=True,
        )
    return CheckResult(id="python", status="pass", detail=f"Python {detail}", required=True)


def _python_version() -> tuple[int, int, int]:
    version = sys.version_info
    return version.major, version.minor, version.micro


def _check_tesseract() -> CheckResult:
    binary = shutil.which("tesseract")
    if binary is None:
        return CheckResult(
            id="tesseract",
            status="fail",
            detail="tesseract binary not found on PATH",
            hint="brew install tesseract",
            required=True,
        )
    version = _tesseract_version_line(binary) or "version unknown"
    return CheckResult(
        id="tesseract",
        status="pass",
        detail=f"{binary} ({version})",
        required=True,
    )


def _check_ocr() -> CheckResult:
    """Read a generated image. This fails when Tesseract cannot open its input."""
    if shutil.which("tesseract") is None:
        return CheckResult(
            id="ocr",
            status="skip",
            detail="tesseract is not installed",
            required=False,
        )
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return CheckResult(
            id="ocr",
            status="skip",
            detail="ocr extra is not installed",
            hint=_extra_hint("ocr"),
            required=False,
        )
    from openframe.recognize.ocr.tesseract import OcrError, TesseractRecognizer

    probe_fd, probe_name = tempfile.mkstemp(prefix="openframe-doctor-ocr-", suffix=".png")
    os.close(probe_fd)
    probe = Path(probe_name)
    try:
        _write_ocr_probe(probe, Image, ImageDraw, ImageFont)
        frame_width, frame_height = 600, 160
        from openframe.types import Frame

        result = TesseractRecognizer().find(
            frame=Frame(
                width=frame_width,
                height=frame_height,
                scale_factor=1.0,
                source="doctor:ocr",
                image_path=str(probe),
            ),
            query="HELLO",
        )
    except (OcrError, OSError, RuntimeError, ValueError) as exc:
        return CheckResult(
            id="ocr",
            status="fail",
            detail=str(exc),
            required=True,
        )
    finally:
        probe.unlink(missing_ok=True)
    if not any("HELLO".casefold() in (target.text or "").casefold() for target in result.targets):
        return CheckResult(
            id="ocr",
            status="fail",
            detail="tesseract did not read the generated text",
            required=True,
        )
    return CheckResult(
        id="ocr",
        status="pass",
        detail="read HELLO from a generated image",
        required=True,
    )


def _write_ocr_probe(path: Path, image_cls: Any, draw_cls: Any, font_cls: Any) -> None:
    image = image_cls.new("L", (600, 160), 255)
    draw = draw_cls.Draw(image)
    try:
        font = font_cls.load_default(size=72)
    except TypeError:
        font = font_cls.load_default()
    draw.text((20, 30), "HELLO", fill=0, font=font)
    image.save(path)


def _check_extras() -> list[CheckResult]:
    results: list[CheckResult] = []
    for check_id, modules, install_hint in _EXTRA_CHECKS:
        missing = [name for name in modules if importlib.util.find_spec(name) is None]
        if missing:
            results.append(
                CheckResult(
                    id=check_id,
                    status="skip",
                    detail=f"not installed ({', '.join(missing)})",
                    hint=install_hint,
                    required=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    id=check_id,
                    status="pass",
                    detail="installed",
                    required=False,
                )
            )
    return results


def _check_display_power() -> CheckResult:
    """Fail when the screen is locked or the display is asleep.

    That state is not a missing privacy grant. The permission probes are skipped
    until the display is awake and unlocked.
    """
    if sys.platform != "darwin":
        return CheckResult(
            id="display_power",
            status="skip",
            detail="skipped on non-macOS",
            required=False,
        )
    state = read_display_power()
    if not state.known:
        return CheckResult(
            id="display_power",
            status="skip",
            detail="could not read whether the display is awake",
            required=False,
        )
    if state.unavailable:
        return CheckResult(
            id="display_power",
            status="fail",
            detail=screen_unavailable_message(state),
            required=True,
        )
    return CheckResult(
        id="display_power",
        status="pass",
        detail="awake and unlocked",
        required=True,
    )


def _permission_probe_blocked(check_id: str) -> CheckResult | None:
    if sys.platform != "darwin":
        return None
    state = read_display_power()
    if not state.unavailable:
        return None
    return CheckResult(
        id=check_id,
        status="skip",
        detail="not checked while the screen is locked or the display is asleep",
        required=False,
    )


def _check_screen_recording() -> CheckResult:
    if sys.platform != "darwin":
        return CheckResult(
            id="screen_recording",
            status="skip",
            detail="skipped on non-macOS",
            required=False,
        )
    blocked = _permission_probe_blocked("screen_recording")
    if blocked is not None:
        return blocked

    try:
        from openframe.capture import CaptureError, region
    except ImportError as exc:  # pragma: no cover
        return CheckResult(
            id="screen_recording",
            status="fail",
            detail=f"capture module unavailable: {exc}",
            hint="Reinstall open-frame and retry.",
            required=True,
        )

    try:
        with tempfile.TemporaryDirectory(prefix="openframe-doctor-") as tmp:
            out = Path(tmp) / "probe.png"
            frame = region(x=0, y=0, width=64, height=64, out_path=out)
            path = Path(frame.image_path or out)
            if not path.exists() or path.stat().st_size <= 0:
                raise CaptureError("capture wrote an empty image")
    except (CaptureError, OSError, RuntimeError, ValueError) as exc:
        return CheckResult(
            id="screen_recording",
            status="fail",
            detail=str(exc),
            hint=permission_denied_message("Screen Recording"),
            required=True,
        )

    return CheckResult(
        id="screen_recording",
        status="pass",
        detail="region capture succeeded",
        required=True,
    )


def _check_accessibility() -> CheckResult:
    if sys.platform != "darwin":
        return CheckResult(
            id="accessibility",
            status="skip",
            detail="skipped on non-macOS",
            required=False,
        )
    blocked = _permission_probe_blocked("accessibility")
    if blocked is not None:
        return blocked

    try:
        from openframe.recognize.a11y.macos import _list_frontmost_elements
    except ImportError as exc:  # pragma: no cover
        return CheckResult(
            id="accessibility",
            status="fail",
            detail=f"a11y module unavailable: {exc}",
            hint="Reinstall open-frame and retry.",
            required=True,
        )

    hint = permission_denied_message("Accessibility")
    try:
        elements = _list_frontmost_elements()
    except (RuntimeError, TypeError, ValueError) as exc:
        return CheckResult(
            id="accessibility",
            status="fail",
            detail=str(exc),
            hint=hint,
            required=True,
        )

    valid = [
        item
        for item in elements
        if float(item.get("width") or 0) > 0 and float(item.get("height") or 0) > 0
    ]
    if not valid:
        return CheckResult(
            id="accessibility",
            status="fail",
            detail=f"no elements with usable bounds (seen={len(elements)})",
            hint=hint,
            required=True,
        )

    return CheckResult(
        id="accessibility",
        status="pass",
        detail=f"{len(valid)} elements with bounds (seen={len(elements)})",
        required=True,
    )


def _require_mcp_extras(checks: list[CheckResult]) -> list[CheckResult]:
    """MCP onboarding fails when ocr, act, or mcp is not installed."""
    updated: list[CheckResult] = []
    for item in checks:
        if item.id in _MCP_REQUIRED_EXTRAS and item.status != "pass":
            updated.append(
                CheckResult(
                    id=item.id,
                    status="fail",
                    detail=item.detail,
                    hint=item.hint,
                    required=True,
                )
            )
        else:
            updated.append(item)
    return updated


def _check_displays() -> CheckResult:
    """Warn when more than one display is online. Capture stays on the primary display."""
    if sys.platform != "darwin":
        return CheckResult(
            id="displays",
            status="skip",
            detail="skipped on non-macOS",
            required=False,
        )
    try:
        from openframe.capture import CaptureError, list_displays
    except ImportError as exc:  # pragma: no cover
        return CheckResult(
            id="displays",
            status="skip",
            detail=f"capture module unavailable: {exc}",
            required=False,
        )
    try:
        displays = list_displays()
    except (CaptureError, OSError, RuntimeError, ValueError) as exc:
        return CheckResult(
            id="displays",
            status="skip",
            detail=str(exc),
            required=False,
        )
    online = [item for item in displays if item.get("online")]
    if len(online) > 1:
        return CheckResult(
            id="displays",
            status="pass",
            detail=(
                f"warning: {len(online)} displays online; only the primary display is supported"
            ),
            required=False,
        )
    noun = "display" if len(online) == 1 else "displays"
    return CheckResult(
        id="displays",
        status="pass",
        detail=f"{len(online)} {noun} online",
        required=False,
    )


def _check_mcp_server(checks: list[CheckResult]) -> CheckResult:
    """Start the MCP server in-process and require the full tool list."""
    missing = [
        item.id for item in checks if item.id in _MCP_REQUIRED_EXTRAS and item.status != "pass"
    ]
    if missing:
        return CheckResult(
            id="mcp_server",
            status="fail",
            detail="server not started because " + ", ".join(missing) + " is missing",
            hint=_extra_hint("mcp,ocr,act"),
            required=True,
        )
    try:
        from mcp.shared.memory import (
            create_connected_server_and_client_session as connect_session,
        )

        from openframe.integrations.mcp.adapter import MCP_TOOLS
        from openframe.integrations.mcp.server import create_mcp_server
    except ImportError as exc:
        return CheckResult(
            id="mcp_server",
            status="fail",
            detail=f"MCP server did not start: {exc}",
            hint=_extra_hint("mcp"),
            required=True,
        )

    expected = {str(tool["name"]) for tool in MCP_TOOLS}

    async def _list() -> set[str]:
        server = create_mcp_server()
        async with connect_session(server) as session:
            listed = await session.list_tools()
            return {item.name for item in listed.tools}

    try:
        names = asyncio.run(_list())
    except Exception as exc:  # noqa: BLE001 - doctor reports any startup failure
        return CheckResult(
            id="mcp_server",
            status="fail",
            detail=f"MCP server did not start: {exc}",
            hint=_extra_hint("mcp"),
            required=True,
        )
    missing_tools = expected - names
    if missing_tools:
        return CheckResult(
            id="mcp_server",
            status="fail",
            detail="MCP server is missing tools: " + ", ".join(sorted(missing_tools)),
            required=True,
        )
    return CheckResult(
        id="mcp_server",
        status="pass",
        detail=f"started and listed {len(names)} tools",
        required=True,
    )


def _tesseract_version_line(binary: str) -> str | None:
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    if not text:
        return None
    return text.splitlines()[0].strip()
