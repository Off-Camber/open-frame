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
    monkeypatch.setattr("openframe.doctor._check_platform", lambda: CheckResult("platform", "pass", "Darwin"))
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
    monkeypatch.setattr("openframe.cli.run_doctor", lambda: checks)
    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--json"])

    from openframe.cli import main

    code = main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["checks"][1]["id"] == "tesseract"

    monkeypatch.setattr(
        "openframe.cli.run_doctor",
        lambda: [CheckResult(id="platform", status="pass", detail="Darwin", required=True)],
    )
    monkeypatch.setattr("sys.argv", ["open-frame", "doctor", "--json"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
