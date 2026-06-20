from __future__ import annotations

import json
from pathlib import Path

import pytest

from openframe.cli import main
from openframe.types import Frame
from openframe.types import StepResult
from openframe.types import Target


def test_capture_command_prints_output_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    out_path = tmp_path / "frame.png"

    def fake_screen(out_path: Path) -> Frame:
        return Frame(
            width=100,
            height=100,
            scale_factor=1.0,
            source="screen:1",
            image_path=str(out_path),
        )

    monkeypatch.setattr("openframe.cli.screen", fake_screen)
    monkeypatch.setattr("sys.argv", ["open-frame", "capture", "--out", str(out_path)])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_path)


def test_capture_window_id_uses_window_backend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    out_path = tmp_path / "window.png"

    def fake_window(*, title: str | None, window_id: int | None, out_path: Path) -> Frame:
        assert title is None
        assert window_id == 123
        return Frame(
            width=200,
            height=120,
            scale_factor=2.0,
            source="window:123",
            image_path=str(out_path),
        )

    monkeypatch.setattr("openframe.cli.window", fake_window)
    monkeypatch.setattr("sys.argv", ["open-frame", "capture", "--out", str(out_path), "--window-id", "123"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_path)


def test_list_windows_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    windows = [{"id": 1, "owner": "Finder", "title": "Desktop", "bounds": {"x": 0, "y": 0}}]
    monkeypatch.setattr("openframe.cli.list_windows", lambda: windows)
    monkeypatch.setattr("sys.argv", ["open-frame", "list-windows", "--json"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {"windows": windows}


def test_list_windows_with_displays_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    windows = [{"id": 1, "owner": "Finder", "title": "Desktop", "bounds": {"x": 0, "y": 0}}]
    displays = [{"name": "Built-in Retina Display", "resolution": "3024 x 1964 Retina", "retina": True}]
    monkeypatch.setattr("openframe.cli.list_windows", lambda: windows)
    monkeypatch.setattr("openframe.cli.list_displays", lambda: displays)
    monkeypatch.setattr("sys.argv", ["open-frame", "list-windows", "--json", "--displays"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {"windows": windows, "displays": displays}


def test_capture_rejects_both_window_title_and_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["open-frame", "capture", "--out", "frame.png", "--window-title", "Mail", "--window-id", "1"],
    )
    with pytest.raises(SystemExit):
        main()


def test_capture_region_uses_region_backend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    out_path = tmp_path / "region.png"

    def fake_region(*, x: int, y: int, width: int, height: int, out_path: Path) -> Frame:
        assert (x, y, width, height) == (10, 20, 300, 150)
        return Frame(
            width=600,
            height=300,
            scale_factor=2.0,
            source="region:10,20,300,150",
            image_path=str(out_path),
        )

    monkeypatch.setattr("openframe.cli.region", fake_region)
    monkeypatch.setattr(
        "sys.argv",
        [
            "open-frame",
            "capture",
            "--out",
            str(out_path),
            "--x",
            "10",
            "--y",
            "20",
            "--width",
            "300",
            "--height",
            "150",
        ],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_path)


def test_capture_rejects_partial_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["open-frame", "capture", "--out", "frame.png", "--x", "10", "--y", "20"])
    with pytest.raises(SystemExit):
        main()


def test_find_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    frame = Frame(width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png")

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str) -> list[Target]:
            assert frame.source == "screen:1"
            assert query == "Submit"
            assert strategy == "first"
            return [Target(x=1, y=2, width=3, height=4, confidence=0.9, source="ocr", text="Submit")]

    monkeypatch.setattr("openframe.cli._resolve_find_frame", lambda _frame_path: frame)
    monkeypatch.setattr("openframe.cli.Locator", FakeLocator)
    monkeypatch.setattr("openframe.cli.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("sys.argv", ["open-frame", "find", "Submit", "--json"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["count"] == 1
    assert payload["targets"][0]["text"] == "Submit"


def test_find_with_overlay_writes_overlay_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    frame = Frame(width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png")
    overlay_path = tmp_path / "overlay.png"

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str) -> list[Target]:
            return [Target(x=1, y=2, width=3, height=4, confidence=0.9, source="ocr", text="Submit")]

    monkeypatch.setattr("openframe.cli._resolve_find_frame", lambda _frame_path: frame)
    monkeypatch.setattr("openframe.cli.Locator", FakeLocator)
    monkeypatch.setattr("openframe.cli.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.cli.draw_debug_overlay", lambda **_kwargs: overlay_path)
    monkeypatch.setattr(
        "sys.argv",
        ["open-frame", "find", "Submit", "--json", "--overlay-out", str(overlay_path)],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["overlay_path"] == str(overlay_path)


def test_click_command_dry_run_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    frame = Frame(width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png")
    target = Target(x=10, y=20, width=30, height=40, confidence=0.9, source="ocr", text="Submit")

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str) -> list[Target]:
            assert query == "Submit"
            assert strategy == "first"
            return [target]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            assert dry_run is True

        def click_target(self, target: Target, *, anchor: str, kind: str, scale_factor: float = 1.0) -> tuple[int, int]:
            assert target.text == "Submit"
            assert anchor == "center"
            assert kind == "click"
            return (25, 40)

    monkeypatch.setattr("openframe.cli._resolve_find_frame", lambda _frame_path: frame)
    monkeypatch.setattr("openframe.cli.Locator", FakeLocator)
    monkeypatch.setattr("openframe.cli.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.cli.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.cli.Actuator", FakeActuator)
    monkeypatch.setattr("sys.argv", ["open-frame", "click", "Submit", "--dry-run", "--json"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["point"] == {"x": 25, "y": 40}
    assert payload["dry_run"] is True


def test_click_with_failed_verification_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = Frame(width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png")
    target = Target(x=10, y=20, width=30, height=40, confidence=0.9, source="ocr", text="Submit")

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str) -> list[Target]:
            return [target]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, *, anchor: str, kind: str, scale_factor: float = 1.0) -> tuple[int, int]:
            _ = target, anchor, kind, scale_factor
            return (25, 40)

    class FakeVerifierResult:
        success = False
        message = "verification failed"
        verifier = "verify:text"
        details = {}

    monkeypatch.setattr("openframe.cli._resolve_find_frame", lambda _frame_path: frame)
    monkeypatch.setattr("openframe.cli.screen", lambda: frame)
    monkeypatch.setattr("openframe.cli.Locator", FakeLocator)
    monkeypatch.setattr("openframe.cli.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.cli.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.cli.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.cli._run_verification_specs", lambda **_kwargs: FakeVerifierResult())
    monkeypatch.setattr("openframe.cli.write_step_artifacts", lambda **_kwargs: Path("runs/r1/click"))
    monkeypatch.setattr("sys.argv", ["open-frame", "click", "Submit", "--verify", "text-gone:Submit"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "verification failed" in captured.out


def test_run_command_json_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeFlow:
        name = "demo"

    class FakeRunner:
        def __init__(self, *, dry_run: bool) -> None:
            assert dry_run is True

        def run(self, flow, *, run_id: str):
            class SessionObj:
                results = [
                    StepResult(
                        step_id="one",
                        success=True,
                        duration_ms=10,
                        details={"kind": "wait"},
                    )
                ]

            _ = flow, run_id
            return SessionObj()

    monkeypatch.setattr("openframe.cli.load_flow", lambda _path: FakeFlow())
    monkeypatch.setattr("openframe.cli.FlowRunner", FakeRunner)
    monkeypatch.setattr("sys.argv", ["open-frame", "run", "flow.yaml", "--dry-run", "--json"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["flow"] == "demo"
    assert payload["success"] is True


def test_mcp_list_tools_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "openframe.cli.list_mcp_tools",
        lambda: [{"name": "capture", "description": "Capture screen/window/region into a frame"}],
    )
    monkeypatch.setattr("sys.argv", ["open-frame", "mcp", "list-tools", "--json"])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["tools"][0]["name"] == "capture"


def test_mcp_call_returns_nonzero_for_tool_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "openframe.cli.call_mcp_tool",
        lambda tool, args: {
            "ok": False,
            "tool": tool,
            "run_id": None,
            "data": {"args": args},
            "error": {"code": "validation_error", "message": "bad args"},
            "artifacts": {},
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        ["open-frame", "mcp", "call", "find", "--args-json", '{"query":"Submit"}'],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "validation_error"
