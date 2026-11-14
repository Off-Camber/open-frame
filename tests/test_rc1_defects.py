"""Regressions from the 0.3.0rc1 client check."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from openframe.capture.sidecar import write_frame_sidecar
from openframe.integrations.mcp.adapter import call_mcp_tool
from openframe.recognize.ocr.tesseract import OcrError, TesseractRecognizer, _ocr_failure_message
from openframe.runs import runs_root
from openframe.types import Frame, Target

FIXTURE = Path(__file__).parent / "fixtures" / "ocr" / "calibration_marker.png"
MARKER = "OFMARKZXQ"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_ocr_reads_a_fixture_when_tmpdir_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pytesseract")
    pytest.importorskip("PIL")
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", None)

    recognizer = TesseractRecognizer()
    frame = Frame(
        width=1200,
        height=400,
        scale_factor=1.0,
        source="fixture:calibration",
        image_path=str(FIXTURE),
    )
    result = recognizer.find(frame=frame, query=MARKER)

    assert result.targets
    assert any(MARKER.casefold() in (target.text or "").casefold() for target in result.targets)


def test_capture_path_survives_dry_run_and_live_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_screen(out_path: str | Path | None = None) -> Frame:
        if out_path is None:
            descriptor, name = tempfile.mkstemp(prefix="openframe-", suffix=".png")
            os_close = __import__("os").close
            os_close(descriptor)
            path = Path(name)
        else:
            path = Path(out_path)
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        frame = Frame(
            width=10,
            height=10,
            scale_factor=1.0,
            source="screen:1",
            image_path=str(path),
        )
        write_frame_sidecar(frame)
        return frame

    class FakeLocator:
        def find(
            self, frame: Frame, query: str, strategy: str = "all", options=None
        ) -> list[Target]:
            _ = frame, query, strategy, options
            return [Target(x=1, y=1, width=4, height=4, confidence=0.9, source="ocr", text="Save")]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            _ = target, kwargs
            return (2, 2)

    monkeypatch.setattr("openframe.integrations.mcp.adapter.screen", fake_screen)
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)

    captured = call_mcp_tool("capture", {"mode": "screen"})
    assert captured["ok"] is True
    frame_path = Path(captured["data"]["frame"]["image_path"])
    assert frame_path.is_file()
    assert frame_path.resolve().is_relative_to(runs_root())

    dry = call_mcp_tool(
        "click",
        {"query": "Save", "frame_path": str(frame_path), "dry_run": True, "selector": "first"},
    )
    assert dry["ok"] is True
    assert frame_path.is_file()

    live = call_mcp_tool(
        "click",
        {"query": "Save", "frame_path": str(frame_path), "dry_run": False, "selector": "first"},
    )
    assert live["ok"] is True
    assert frame_path.is_file()
    assert Path(str(frame_path) + ".openframe.json").is_file()


def test_caller_supplied_temp_frame_survives_both_clicks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor, name = tempfile.mkstemp(prefix="openframe-", suffix=".png")
    os_close = __import__("os").close
    os_close(descriptor)
    frame_path = Path(name)
    frame_path.write_bytes(b"png")
    frame = Frame(
        width=10,
        height=10,
        scale_factor=1.0,
        source="screen:1",
        image_path=str(frame_path),
    )
    write_frame_sidecar(frame)

    class FakeLocator:
        def find(
            self, frame: Frame, query: str, strategy: str = "all", options: object = None
        ) -> list[Target]:
            _ = frame, query, strategy, options
            return [Target(x=1, y=1, width=4, height=4, confidence=0.9, source="ocr", text="Save")]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            _ = target, kwargs
            return (2, 2)

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.screen",
        lambda out_path=None: Frame(
            width=10, height=10, scale_factor=1.0, source="screen:1", image_path=None
        ),
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)

    for dry_run in (True, False):
        result = call_mcp_tool(
            "click",
            {
                "query": "Save",
                "frame_path": str(frame_path),
                "dry_run": dry_run,
                "selector": "first",
            },
        )
        assert result["ok"] is True
        assert frame_path.is_file()
        assert Path(str(frame_path) + ".openframe.json").is_file()


def test_tesseract_decode_failure_is_ocr_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytesseract = pytest.importorskip("pytesseract")
    image_module = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "probe.png"
    image_module.new("L", (20, 20), 255).save(image_path)

    def fail_decode(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise UnicodeDecodeError("utf-8", b"\x89PNG", 0, 1, "invalid start byte")

    monkeypatch.setattr(pytesseract, "image_to_data", fail_decode)
    with pytest.raises(OcrError, match="not text"):
        TesseractRecognizer().find(
            frame=Frame(
                width=20,
                height=20,
                scale_factor=1.0,
                source="probe",
                image_path=str(image_path),
            ),
            query="HELLO",
        )

    result = call_mcp_tool(
        "find",
        {"query": "OCRERRTOKEN9", "frame_path": str(image_path), "strategy": "all"},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "ocr_error"
    assert "utf-8" not in result["error"]["message"]


def test_tesseract_error_message_is_not_a_tuple() -> None:
    pytesseract = pytest.importorskip("pytesseract")
    exc = pytesseract.TesseractError(1, "Error in fopenReadStream: failed to open locally")
    message = _ocr_failure_message(exc)
    assert message.startswith("Tesseract failed to read the image:")
    assert "fopenReadStream" in message
    assert not message.startswith("Tesseract failed to read the image: (")


def test_live_gate_uses_the_configured_runs_directory_and_gui_env() -> None:
    script = (
        Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("scripts/macos_live_gate.sh")
        .read_text(encoding="utf-8")
    )
    assert 'Path("runs/live-gate-miss")' not in script
    assert 'lookup_run_directory("live-gate-miss")' in script
    assert "env -i" in script
    assert "check_gui_client_env" in script
