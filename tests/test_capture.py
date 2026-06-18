from __future__ import annotations

import struct
from pathlib import Path

import pytest

from openframe.capture import macos


def _png_bytes(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    iend_chunk = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    return signature + ihdr_chunk + iend_chunk


def test_read_png_dimensions(tmp_path: Path) -> None:
    png_path = tmp_path / "frame.png"
    png_path.write_bytes(_png_bytes(640, 480))

    width, height = macos._read_png_dimensions(png_path)

    assert (width, height) == (640, 480)


def test_detect_scale_factor_defaults_on_parse_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        stdout = "invalid"

    monkeypatch.setattr(macos, "_run_command", lambda _command: Result())
    assert macos._detect_scale_factor(3000) == 1.0


def test_screen_returns_frame_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_path = tmp_path / "capture.png"

    def fake_run(command: list[str]) -> object:
        class Result:
            stdout = "0, 0, 1512, 982"

        if command[0] == "screencapture":
            Path(command[-1]).write_bytes(_png_bytes(3024, 1964))
            return Result()
        if command[0] == "osascript":
            return Result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_resolve_output_path", lambda _out_path: out_path)
    monkeypatch.setattr(macos, "_run_command", fake_run)

    frame = macos.screen(out_path=out_path)

    assert frame.width == 3024
    assert frame.height == 1964
    assert frame.scale_factor == 2.0
    assert frame.image_path == str(out_path)
    assert frame.source == "screen:1"


def test_window_capture_by_title(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_path = tmp_path / "window.png"

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_resolve_output_path", lambda _out_path: out_path)
    monkeypatch.setattr(
        macos,
        "_list_window_infos",
        lambda: [
            {"id": 200, "owner": "Slack", "title": "Engineering", "bounds": {}},
            {"id": 201, "owner": "Google Chrome", "title": "Open Frame Docs", "bounds": {}},
        ],
    )
    monkeypatch.setattr(macos, "_detect_scale_factor", lambda _width: 2.0)

    def fake_run(command: list[str]) -> object:
        class Result:
            stdout = ""

        if command[0] == "screencapture":
            Path(command[-1]).write_bytes(_png_bytes(1500, 900))
            return Result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(macos, "_run_command", fake_run)

    frame = macos.window(title="chrome", out_path=out_path)

    assert frame.source == "window:201"
    assert frame.metadata["window_owner"] == "Google Chrome"
    assert frame.metadata["window_title"] == "Open Frame Docs"


def test_list_windows_returns_backend_output(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [{"id": 99, "owner": "Finder", "title": "", "bounds": {"x": 0, "y": 0}}]
    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_list_window_infos", lambda: expected)

    assert macos.list_windows() == expected


def test_list_displays_parses_system_profiler(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        stdout = """
{"SPDisplaysDataType":[{"spdisplays_ndrvs":[{"_name":"Built-in Retina Display","_spdisplays_resolution":"3024 x 1964 Retina","spdisplays_retina":"spdisplays_yes","spdisplays_main":"spdisplays_yes","spdisplays_online":"spdisplays_yes"}]}]}
""".strip()

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_run_command", lambda _command: Result())

    displays = macos.list_displays()

    assert len(displays) == 1
    assert displays[0]["name"] == "Built-in Retina Display"
    assert displays[0]["main"] is True


def test_region_capture_uses_region_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_path = tmp_path / "region.png"

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_resolve_output_path", lambda _out_path: out_path)
    monkeypatch.setattr(macos, "_detect_scale_factor", lambda _width: 2.0)

    def fake_run(command: list[str]) -> object:
        class Result:
            stdout = ""

        if command[0] == "screencapture":
            assert command[3] == "10,20,300,150"
            Path(command[-1]).write_bytes(_png_bytes(600, 300))
            return Result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(macos, "_run_command", fake_run)

    frame = macos.region(x=10, y=20, width=300, height=150, out_path=out_path)

    assert frame.source == "region:10,20,300,150"
    assert frame.metadata["region"] == {"x": 10, "y": 20, "width": 300, "height": 150}
