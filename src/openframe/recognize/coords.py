"""Coordinate-space helpers for recognizer targets."""

from __future__ import annotations

from openframe.types import Target


def target_uses_physical_pixels(target: Target) -> bool:
    """Return True when target bounds are in captured-image pixel space."""
    return target.coordinate_space == "physical"


def target_logical_bounds(
    target: Target, *, scale_factor: float = 1.0
) -> tuple[int, int, int, int]:
    """Return target bounds in logical screen points for window filtering/clicks."""
    if not target_uses_physical_pixels(target):
        return target.x, target.y, target.width, target.height

    scale = scale_factor if scale_factor > 0 else 1.0
    left = round(target.x / scale)
    top = round(target.y / scale)
    right = round((target.x + target.width) / scale)
    bottom = round((target.y + target.height) / scale)
    return (
        left,
        top,
        max(1, right - left),
        max(1, bottom - top),
    )
