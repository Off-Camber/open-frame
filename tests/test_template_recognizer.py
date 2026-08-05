"""Tests for template / image-matching recognition."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("PIL")

from PIL import Image, ImageDraw

from openframe.recognize.coords import select_target, target_logical_bounds
from openframe.recognize.defaults import build_default_locator, recognition_options_from_mapping
from openframe.recognize.match import ensure_actionable_match_count
from openframe.recognize.template import TemplateRecognizer
from openframe.types import Frame


def _draw_glyph(draw: ImageDraw.ImageDraw, origin: tuple[int, int], *, scale: int = 1) -> None:
    """Draw a patterned (non-flat) glyph so NCC has variance to match on."""
    x, y = origin
    s = scale
    draw.rectangle((x, y, x + 30 * s - 1, y + 30 * s - 1), fill=(220, 40, 40))
    draw.rectangle((x + 6 * s, y + 6 * s, x + 14 * s, y + 14 * s), fill=(255, 255, 255))
    draw.line((x + 4 * s, y + 22 * s, x + 26 * s, y + 22 * s), fill=(20, 20, 20), width=max(1, 2 * s))
    draw.ellipse((x + 16 * s, y + 8 * s, x + 26 * s, y + 18 * s), fill=(40, 120, 220))


def _write_scene(path: Path, *, scale: int = 1) -> tuple[Path, Path]:
    """Create a frame with a unique patterned glyph and a matching template crop."""
    width, height = 120 * scale, 80 * scale
    origin = (20 * scale, 15 * scale)
    glyph = (origin[0], origin[1], origin[0] + 30 * scale, origin[1] + 30 * scale)
    frame_img = Image.new("RGB", (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(frame_img)
    _draw_glyph(draw, origin, scale=scale)
    # Add OCR-friendly text elsewhere so OCR has something else to see.
    draw.text((5 * scale, 55 * scale), "LABEL", fill=(0, 0, 0))
    frame_path = path / f"frame-{scale}x.png"
    frame_img.save(frame_path)

    template = frame_img.crop(glyph)
    template_path = path / f"template-{scale}x.png"
    template.save(template_path)
    return frame_path, template_path


def test_template_recognizer_finds_unique_crop(tmp_path: Path) -> None:
    frame_path, template_path = _write_scene(tmp_path, scale=1)
    frame = Frame(
        width=120,
        height=80,
        scale_factor=1.0,
        source="fixture",
        image_path=str(frame_path),
    )
    result = TemplateRecognizer().find(
        frame=frame,
        query="icon",
        options={"template": str(template_path), "template_threshold": 0.8},
    )
    assert len(result.targets) >= 1
    target = result.targets[0]
    assert target.source == "template:ncc"
    assert target.width > 0 and target.height > 0
    assert target.confidence >= 0.8
    assert abs(target.x - 20) <= 2
    assert abs(target.y - 15) <= 2


def test_template_recognizer_noop_without_template(tmp_path: Path) -> None:
    frame_path, _template_path = _write_scene(tmp_path, scale=1)
    frame = Frame(
        width=120,
        height=80,
        scale_factor=1.0,
        source="fixture",
        image_path=str(frame_path),
    )
    result = TemplateRecognizer().find(frame=frame, query="icon", options=None)
    assert result.targets == []
    assert result.metadata["reason"] == "no_template"


def test_template_retina_logical_parity(tmp_path: Path) -> None:
    frame_1x, template_1x = _write_scene(tmp_path, scale=1)
    frame_2x, template_2x = _write_scene(tmp_path, scale=2)

    r1 = TemplateRecognizer().find(
        Frame(120, 80, 1.0, "1x", image_path=str(frame_1x)),
        "icon",
        options={"template": str(template_1x), "template_threshold": 0.8},
    )
    r2 = TemplateRecognizer().find(
        Frame(240, 160, 2.0, "2x", image_path=str(frame_2x)),
        "icon",
        options={"template": str(template_2x), "template_threshold": 0.8},
    )
    assert r1.targets and r2.targets
    logical_1 = target_logical_bounds(r1.targets[0], scale_factor=1.0)
    logical_2 = target_logical_bounds(r2.targets[0], scale_factor=2.0)
    assert logical_1[:2] == pytest.approx(logical_2[:2], abs=2)
    selected_1 = select_target(targets=r1.targets, selector="first", scale_factor=1.0)
    selected_2 = select_target(targets=r2.targets, selector="first", scale_factor=2.0)
    c1 = target_logical_bounds(selected_1, scale_factor=1.0)
    c2 = target_logical_bounds(selected_2, scale_factor=2.0)
    assert c1[0] + c1[2] // 2 == pytest.approx(c2[0] + c2[2] // 2, abs=2)
    assert c1[1] + c1[3] // 2 == pytest.approx(c2[1] + c2[3] // 2, abs=2)


def test_template_ambiguous_fail_closed(tmp_path: Path) -> None:
    # Two identical glyphs → multiple matches above threshold.
    width, height = 160, 80
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    _draw_glyph(draw, (10, 10), scale=1)
    _draw_glyph(draw, (90, 10), scale=1)
    frame_path = tmp_path / "dup-frame.png"
    img.save(frame_path)
    template_path = tmp_path / "dup-template.png"
    img.crop((10, 10, 40, 40)).save(template_path)

    result = TemplateRecognizer().find(
        Frame(width, height, 1.0, "dup", image_path=str(frame_path)),
        "glyph",
        options={"template": str(template_path), "template_threshold": 0.85},
    )
    assert len(result.targets) >= 2
    with pytest.raises(ValueError, match="ambiguous_target"):
        ensure_actionable_match_count(
            query="glyph",
            match_count=len(result.targets),
            selector=None,
            expect_one=False,
        )


def test_default_locator_unchanged_without_template(tmp_path: Path) -> None:
    frame_path, template_path = _write_scene(tmp_path, scale=1)
    frame = Frame(120, 80, 1.0, "fixture", image_path=str(frame_path))
    locator = build_default_locator()
    # Without template option, icon glyph should not be found as text "icon".
    targets = locator.find(frame, "icon", strategy="all")
    assert all(t.source != "template:ncc" for t in targets)

    with_template = locator.find(
        frame,
        "icon",
        strategy="all",
        options={"template": str(template_path), "template_threshold": 0.8},
    )
    assert any(t.source == "template:ncc" for t in with_template)


def test_recognition_options_from_mapping() -> None:
    assert recognition_options_from_mapping(None) is None
    assert recognition_options_from_mapping({}) is None
    opts = recognition_options_from_mapping(
        {"template": "~/icon.png", "template_threshold": "0.9", "match_mode": "token"}
    )
    assert opts == {
        "template": "~/icon.png",
        "template_threshold": 0.9,
        "match_mode": "token",
    }
