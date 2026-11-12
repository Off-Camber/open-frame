"""Scale and origin from the measured Retina capture table.

True scale is 2.0. The desktop is 1710 logical points wide.

| Capture | Logical size | PNG size | Old reported scale |
|---|---|---|---|
| Full screen | 1710 wide | 3420 wide | 2.0 |
| Region | 400×300 | 800×600 | 0.47 |
| Finder window | 1283×578 | 2658×1248 | 1.55 |
| Cursor window | 1710×980 | 3644×2184 | 2.0 by coincidence |
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from openframe.capture import macos
from openframe.types import Frame

DESKTOP_BOUNDS = "0, 0, 1710, 1112"


def _png_bytes(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    iend_chunk = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    return signature + ihdr_chunk + iend_chunk


def _install_capture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, png_size: tuple[int, int]):
    commands: list[list[str]] = []
    out_path = tmp_path / "frame.png"

    def fake_run(command: list[str]) -> object:
        class Result:
            stdout = DESKTOP_BOUNDS

        commands.append(list(command))
        if command[0] == "screencapture":
            Path(command[-1]).write_bytes(_png_bytes(*png_size))
            return Result()
        if command[0] == "osascript":
            return Result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_resolve_output_path", lambda _out_path: out_path)
    monkeypatch.setattr(macos, "_run_command", fake_run)
    return commands, out_path


def _assert_sidecar(frame: Frame) -> None:
    assert frame.image_path is not None
    payload = json.loads(Path(frame.image_path + ".openframe.json").read_text(encoding="utf-8"))
    assert payload["scale_factor"] == frame.scale_factor
    assert payload["origin_x"] == frame.origin_x
    assert payload["origin_y"] == frame.origin_y
    assert payload["width"] == frame.width
    assert payload["height"] == frame.height


def test_screen_scale_uses_main_display_width(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_capture(monkeypatch, tmp_path, (3420, 2224))

    frame = macos.screen()

    assert frame.scale_factor == 2.0
    assert (frame.origin_x, frame.origin_y) == (0, 0)
    _assert_sidecar(frame)


def test_region_scale_uses_requested_width_not_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_capture(monkeypatch, tmp_path, (800, 600))

    frame = macos.region(x=120, y=80, width=400, height=300)

    assert frame.scale_factor == 2.0
    assert (frame.origin_x, frame.origin_y) == (120, 80)
    _assert_sidecar(frame)


def test_finder_window_scale_uses_window_bounds_and_omits_shadow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, _out = _install_capture(monkeypatch, tmp_path, (2566, 1156))
    monkeypatch.setattr(
        macos,
        "_list_window_infos",
        lambda: [
            {
                "id": 42,
                "owner": "Finder",
                "title": "Documents",
                "bounds": {"x": 40, "y": 55, "width": 1283, "height": 578},
            }
        ],
    )

    frame = macos.window(window_id=42)

    assert any(command[0] == "screencapture" and "-o" in command for command in commands)
    assert frame.scale_factor == 2.0
    assert (frame.origin_x, frame.origin_y) == (40, 55)
    _assert_sidecar(frame)


def test_cursor_window_scale_is_not_a_desktop_coincidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, _out = _install_capture(monkeypatch, tmp_path, (3420, 1960))
    monkeypatch.setattr(
        macos,
        "_list_window_infos",
        lambda: [
            {
                "id": 7,
                "owner": "Cursor",
                "title": "open-frame",
                "bounds": {"x": 15, "y": 30, "width": 1710, "height": 980},
            }
        ],
    )

    frame = macos.window(window_id=7)

    assert any(command[0] == "screencapture" and "-o" in command for command in commands)
    assert frame.scale_factor == 2.0
    assert (frame.origin_x, frame.origin_y) == (15, 30)
    _assert_sidecar(frame)


def test_screen_scale_probe_failure_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_path = tmp_path / "frame.png"

    def fake_run(command: list[str]) -> object:
        class Result:
            stdout = "not-a-bounds-list"

        if command[0] == "screencapture":
            Path(command[-1]).write_bytes(_png_bytes(3420, 2224))
            return Result()
        if command[0] == "osascript":
            return Result()
        raise AssertionError(command)

    monkeypatch.setattr(macos, "_ensure_macos", lambda: None)
    monkeypatch.setattr(macos, "_resolve_output_path", lambda _out_path: out_path)
    monkeypatch.setattr(macos, "_run_command", fake_run)

    with pytest.raises(macos.CaptureError, match="main display"):
        macos.screen()
