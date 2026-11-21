"""The hero overlay box follows the filled button, not a guessed rectangle."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw


def _annotator():
    path = Path(__file__).resolve().parent.parent / "scripts" / "annotate_hero_gif.py"
    spec = importlib.util.spec_from_file_location("annotate_hero_gif", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filled_button_box_wraps_the_control() -> None:
    image = Image.new("RGB", (240, 140), (250, 248, 242))
    ImageDraw.Draw(image).rectangle((48, 62, 168, 102), fill=(6, 56, 43))

    box = _annotator()._find_filled_button(image)

    assert box is not None
    left, top, right, bottom = box
    assert left <= 48
    assert top <= 62
    assert right >= 168
    assert bottom >= 102
    assert left > 30
    assert top > 40
