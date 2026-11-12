"""Tests for open-frame doctor diagnostics."""

from __future__ import annotations

import json
from typing import Any

import pytest

from openframe.doctor import (
    CheckResult,
    doctor_ok,
    format_doctor_json,
    format_doctor_text,
    run_doctor,
)


def test_doctor_ok_requires_only_required_passes() -> None:
    checks = [
        CheckResult(id="platform", status="pass", detail="ok", required=True),
        CheckResult(id="extra_agent", status="skip", detail="missing", required=False),
    ]
    assert doctor_ok(checks) is True

    checks_fail = [
        CheckResult(id="platform", status="fail", detail="nope", required=True),
        CheckResult(id="extra_agent", status="pass", detail="ok", required=False),
    ]
    assert doctor_ok(checks_fail) is False


def test_format_doctor_json_shape() -> None:
    checks = [
        CheckResult(
            id="tesseract",
            status="fail",
            detail="missing",
            hint="brew install tesseract",
            required=True,
        ),
        CheckResult(id="extra_mcp", status="skip", detail="not installed", required=False),
    ]
    payload = format_doctor_json(checks)
    assert payload["ok"] is False
    assert payload["checks"][0]["id"] == "tesseract"
    assert payload["checks"][0]["hint"] == "brew install tesseract"
    assert payload["checks"][1]["status"] == "skip"


def test_format_doctor_text_includes_hints_for_non_pass() -> None:
    text = format_doctor_text(
        [
            CheckResult(id="platform", status="pass", detail="Darwin", required=True),
            CheckResult(
                id="tesseract",
                status="fail",
                detail="missing",
                hint="brew install tesseract",
                required=True,
            ),
        ]
    )
    assert "[pass]" in text
    assert "[fail]" in text
    assert "hint: brew install tesseract" in text
    assert "overall: not ready" in text


def test_run_doctor_monkeypatched_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openframe.doctor._check_platform", lambda: CheckResult("platform", "pass", "Darwin")
    )
    monkeypatch.setattr(
        "openframe.doctor._check_python", lambda: CheckResult("python", "pass", "Python 3.11")
    )
    monkeypatch.setattr(
        "openframe.doctor._check_tesseract",
        lambda: CheckResult("tesseract", "fail", "missing", hint="brew install tesseract"),
    )
    monkeypatch.setattr(
        "openframe.doctor._check_extras",
        lambda: [
            CheckResult("extra_agent", "skip", "not installed (anthropic)", required=False),
            CheckResult("extra_mcp", "pass", "installed", required=False),
        ],
    )
    monkeypatch.setattr(
        "openframe.doctor._check_screen_recording",
        lambda: CheckResult("screen_recording", "pass", "ok"),
    )
    monkeypatch.setattr(
        "openframe.doctor._check_accessibility",
        lambda: CheckResult("accessibility", "pass", "ok"),
    )

    checks = run_doctor()
    by_id = {item.id: item for item in checks}
    assert by_id["tesseract"].status == "fail"
    assert by_id["extra_agent"].status == "skip"
    assert by_id["extra_agent"].required is False
    assert doctor_ok(checks) is False


def test_check_tesseract_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.shutil, "which", lambda _name: None)
    result = doctor_mod._check_tesseract()
    assert result.status == "fail"
    assert result.hint == "brew install tesseract"


def test_check_tesseract_present(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.shutil, "which", lambda _name: "/opt/homebrew/bin/tesseract")
    monkeypatch.setattr(doctor_mod, "_tesseract_version_line", lambda _binary: "tesseract 5.5.0")
    result = doctor_mod._check_tesseract()
    assert result.status == "pass"
    assert "tesseract 5.5.0" in result.detail


def test_check_python_too_old(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_python_version", lambda: (3, 10, 0))
    result = doctor_mod._check_python()
    assert result.status == "fail"
    assert "3.11" in (result.hint or "")


def test_check_extras_skip_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    def fake_find_spec(name: str) -> Any:
        if name in {"anthropic", "mcp"}:
            return None
        return object()

    monkeypatch.setattr(doctor_mod.importlib.util, "find_spec", fake_find_spec)
    results = {item.id: item for item in doctor_mod._check_extras()}
    assert results["extra_agent"].status == "skip"
    assert results["extra_agent"].required is False
    assert results["extra_mcp"].status == "skip"
    assert results["extra_ocr"].status == "pass"
    assert results["extra_mcp"].hint == 'pip install "off-camber-open-frame[mcp]"'
    hints = {check_id: hint for check_id, _modules, hint in doctor_mod._EXTRA_CHECKS}
    assert hints["extra_ocr"] == 'pip install "off-camber-open-frame[ocr]"'
    assert "pip install -e" not in " ".join(hints.values())


def test_check_screen_recording_fail_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod
    from openframe.capture import CaptureError

    monkeypatch.setattr(doctor_mod.sys, "platform", "darwin")

    def boom(**_kwargs: Any) -> None:
        raise CaptureError("Capture command failed")

    monkeypatch.setattr("openframe.capture.region", boom)
    # Re-import path used inside the check
    import openframe.capture as capture_mod

    monkeypatch.setattr(capture_mod, "region", boom)

    result = doctor_mod._check_screen_recording()
    assert result.status == "fail"
    assert "Screen Recording" in (result.hint or "")


def test_check_accessibility_fail_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.sys, "platform", "darwin")

    def boom() -> list[dict[str, Any]]:
        raise RuntimeError("macOS accessibility query failed: not allowed")

    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        boom,
    )
    result = doctor_mod._check_accessibility()
    assert result.status == "fail"
    assert "Accessibility" in (result.hint or "")


def test_cli_doctor_json_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    checks = [
        CheckResult(id="platform", status="pass", detail="Darwin", required=True),
        CheckResult(
            id="tesseract",
            status="fail",
            detail="missing",
            hint="brew install tesseract",
            required=True,
        ),
    ]
    monkeypatch.setattr("openframe.cli.run_doctor", lambda **_kwargs: checks)
    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--json"])

    from openframe.cli import main

    code = main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["checks"][1]["id"] == "tesseract"

    monkeypatch.setattr(
        "openframe.cli.run_doctor",
        lambda **_kwargs: [
            CheckResult(id="platform", status="pass", detail="Darwin", required=True)
        ],
    )
    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--json"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_displays_warns_when_more_than_one_is_online(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        "openframe.capture.list_displays",
        lambda: [
            {"name": "Built-in", "online": True, "main": True},
            {"name": "External", "online": True, "main": False},
            {"name": "Offline", "online": False, "main": False},
        ],
    )
    result = doctor_mod._check_displays()
    assert result.status == "pass"
    assert result.required is False
    assert result.detail.startswith("warning: 2 displays online")
    assert doctor_ok([result]) is True


def test_displays_pass_for_one_online_display(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        "openframe.capture.list_displays",
        lambda: [{"name": "Built-in", "online": True, "main": True}],
    )
    result = doctor_mod._check_displays()
    assert result.status == "pass"
    assert result.detail == "1 display online"


def test_displays_skip_when_the_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod
    from openframe.capture import CaptureError

    monkeypatch.setattr(doctor_mod.sys, "platform", "darwin")

    def boom() -> list[dict[str, Any]]:
        raise CaptureError("display probe failed")

    monkeypatch.setattr("openframe.capture.list_displays", boom)
    result = doctor_mod._check_displays()
    assert result.status == "skip"
    assert "display probe failed" in result.detail


def test_displays_skip_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod.sys, "platform", "linux")
    result = doctor_mod._check_displays()
    assert result.status == "skip"
    assert result.required is False


def test_doctor_mcp_fails_when_required_extras_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openframe import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_check_platform", lambda: _pass("platform"))
    monkeypatch.setattr(doctor_mod, "_check_python", lambda: _pass("python"))
    monkeypatch.setattr(doctor_mod, "_check_tesseract", lambda: _pass("tesseract"))
    monkeypatch.setattr(doctor_mod, "_check_screen_recording", lambda: _pass("screen_recording"))
    monkeypatch.setattr(doctor_mod, "_check_accessibility", lambda: _pass("accessibility"))
    monkeypatch.setattr(doctor_mod, "_check_displays", lambda: _pass("displays", required=False))

    def fake_find_spec(name: str) -> Any:
        if name == "mcp":
            return None
        return object()

    monkeypatch.setattr(doctor_mod.importlib.util, "find_spec", fake_find_spec)
    checks = {item.id: item for item in doctor_mod.run_doctor(mcp=True)}
    assert checks["extra_mcp"].status == "fail"
    assert checks["extra_mcp"].required is True
    assert checks["mcp_server"].status == "fail"
    assert "extra_mcp" in checks["mcp_server"].detail
    assert doctor_ok(list(checks.values())) is False


def test_doctor_mcp_lists_tools_and_prints_client_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("mcp")
    from openframe import doctor as doctor_mod
    from openframe.integrations.mcp.adapter import MCP_TOOLS

    monkeypatch.setattr(doctor_mod, "_check_platform", lambda: _pass("platform"))
    monkeypatch.setattr(doctor_mod, "_check_python", lambda: _pass("python"))
    monkeypatch.setattr(doctor_mod, "_check_tesseract", lambda: _pass("tesseract"))
    monkeypatch.setattr(doctor_mod, "_check_screen_recording", lambda: _pass("screen_recording"))
    monkeypatch.setattr(doctor_mod, "_check_accessibility", lambda: _pass("accessibility"))
    monkeypatch.setattr(doctor_mod, "_check_displays", lambda: _pass("displays", required=False))
    monkeypatch.setattr(
        doctor_mod,
        "_check_extras",
        lambda: [
            _pass("extra_ocr"),
            _pass("extra_act"),
            _pass("extra_mcp"),
        ],
    )

    checks = {item.id: item for item in doctor_mod.run_doctor(mcp=True)}
    assert checks["mcp_server"].status == "pass"
    assert str(len(MCP_TOOLS)) in checks["mcp_server"].detail

    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--mcp", "--json"])
    monkeypatch.setattr("openframe.cli.run_doctor", lambda **_kwargs: list(checks.values()))
    from openframe.cli import main

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    command = payload["client_config"]["mcpServers"]["open-frame"]["command"]
    assert command.startswith("/")
    assert payload["client_config"]["mcpServers"]["open-frame"]["args"] == [
        "-m",
        "openframe.cli",
        "mcp",
        "serve",
    ]
    assert "Cursor" in payload["permissions"]
    assert "Claude Desktop" in payload["permissions"]
    assert "not the terminal" in payload["permissions"]


def test_doctor_mcp_text_prints_the_client_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--mcp"])
    monkeypatch.setattr(
        "openframe.cli.run_doctor",
        lambda **_kwargs: [_pass("platform")],
    )
    from openframe.cli import main

    assert main() == 0
    output = capsys.readouterr().out
    assert "Cursor" in output
    assert "Claude Desktop" in output
    assert "mcpServers" in output


def test_mcp_server_reports_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    def boom(coro: Any) -> set[str]:
        coro.close()
        raise RuntimeError("server crashed")

    monkeypatch.setattr(doctor_mod.asyncio, "run", boom)
    result = doctor_mod._check_mcp_server(
        [_pass("extra_ocr"), _pass("extra_act"), _pass("extra_mcp")]
    )
    assert result.status == "fail"
    assert "server crashed" in result.detail


def test_mcp_server_fails_when_a_tool_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from openframe import doctor as doctor_mod

    def listed(coro: Any) -> set[str]:
        coro.close()
        return {"capture"}

    monkeypatch.setattr(doctor_mod.asyncio, "run", listed)
    result = doctor_mod._check_mcp_server(
        [_pass("extra_ocr"), _pass("extra_act"), _pass("extra_mcp")]
    )
    assert result.status == "fail"
    assert "find" in result.detail


def test_version_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from openframe import __version__
    from openframe.cli import main

    monkeypatch.setattr("sys.argv", ["open-frame", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def _pass(check_id: str, *, required: bool = True) -> CheckResult:
    return CheckResult(id=check_id, status="pass", detail="ok", required=required)
