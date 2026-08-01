from __future__ import annotations

from openframe.recognize.coords import target_logical_bounds, target_uses_physical_pixels
from openframe.types import Target


def test_target_uses_physical_pixels_for_ocr_only() -> None:
    assert target_uses_physical_pixels(
        Target(x=1, y=2, width=3, height=4, confidence=1.0, source="ocr:tesseract")
    )
    assert not target_uses_physical_pixels(
        Target(
            x=1,
            y=2,
            width=3,
            height=4,
            confidence=1.0,
            source="a11y:macos",
            coordinate_space="logical",
        )
    )


def test_target_logical_bounds_scales_ocr_targets() -> None:
    target = Target(x=200, y=100, width=40, height=20, confidence=1.0, source="ocr:tesseract")
    assert target_logical_bounds(target, scale_factor=2.0) == (100, 50, 20, 10)


def test_target_logical_bounds_keeps_a11y_targets() -> None:
    target = Target(
        x=100,
        y=50,
        width=40,
        height=20,
        confidence=1.0,
        source="a11y:macos",
        coordinate_space="logical",
    )
    assert target_logical_bounds(target, scale_factor=2.0) == (100, 50, 40, 20)


def test_target_logical_bounds_preserves_narrow_physical_target() -> None:
    target = Target(x=3, y=5, width=1, height=1, confidence=1.0, source="ocr:tesseract")

    assert target_logical_bounds(target, scale_factor=2.0) == (2, 2, 1, 1)
