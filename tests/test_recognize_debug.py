from __future__ import annotations

from pathlib import Path
import sys
import types

from openframe.recognize.debug import draw_debug_overlay
from openframe.types import Target


def test_draw_debug_overlay_saves_png(monkeypatch, tmp_path: Path) -> None:
    saved: dict[str, str] = {}

    class FakeImage:
        def convert(self, _mode: str) -> "FakeImage":
            return self

        def save(self, out_path: Path, format: str) -> None:
            saved["path"] = str(out_path)
            saved["format"] = format

    class FakeDraw:
        def rectangle(self, *_args, **_kwargs) -> None:
            return None

        def text(self, *_args, **_kwargs) -> None:
            return None

    image_module = types.SimpleNamespace(open=lambda _path: FakeImage())
    draw_module = types.SimpleNamespace(Draw=lambda _image: FakeDraw())
    pil_module = types.SimpleNamespace(Image=image_module, ImageDraw=draw_module)
    monkeypatch.setitem(sys.modules, "PIL", pil_module)

    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n0 0 0\n", encoding="utf-8")
    output = tmp_path / "overlay.png"
    targets = [Target(x=1, y=2, width=30, height=20, confidence=0.9, source="ocr", text="Submit")]

    written = draw_debug_overlay(frame_path=source, targets=targets, out_path=output)

    assert str(written) == str(output.resolve())
    assert saved["path"] == str(output.resolve())
    assert saved["format"] == "PNG"
