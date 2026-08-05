"""Environment diagnostics for first-run setup (`open-frame doctor`)."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "skip"]

# Optional extras: absent → skip (informational), not a failure.
_EXTRA_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("extra_ocr", ("PIL", "pytesseract"), "pip install -e '.[ocr]'"),
    ("extra_act", ("pyautogui",), "pip install -e '.[act]'"),
    ("extra_flow", ("yaml",), "pip install -e '.[flow]'"),
    ("extra_agent", ("anthropic",), "pip install -e '.[agent]'"),
    ("extra_mcp", ("mcp",), "pip install -e '.[mcp]'"),
    ("extra_template", ("PIL", "numpy"), "pip install -e '.[template]'"),
)


@dataclass(frozen=True)
class CheckResult:
    """One doctor check row."""

    id: str
    status: CheckStatus
    detail: str
    hint: str | None = None
    required: bool = True


def run_doctor() -> list[CheckResult]:
    """Run all environment checks and return results in display order."""
    checks: list[CheckResult] = [
        _check_platform(),
        _check_python(),
        _check_tesseract(),
    ]
    checks.extend(_check_extras())
    checks.append(_check_screen_recording())
    checks.append(_check_accessibility())
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


def _check_screen_recording() -> CheckResult:
    if sys.platform != "darwin":
        return CheckResult(
            id="screen_recording",
            status="skip",
            detail="skipped on non-macOS",
            required=False,
        )

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
            hint=(
                "System Settings → Privacy & Security → Screen Recording — "
                "enable your terminal/IDE host, then restart it"
            ),
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

    hint = (
        "System Settings → Privacy & Security → Accessibility — "
        "enable your terminal/IDE host, then restart it"
    )
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
