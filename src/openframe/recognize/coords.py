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


def select_target(
    *,
    targets: list[Target],
    selector: str,
    scale_factor: float = 1.0,
) -> Target:
    """Pick one target using a named selector policy.

    Spatial selectors (``top_most``, ``left_most``, ``right_most``) compare
    logical screen bounds so mixed physical OCR and logical a11y candidates
    stay consistent across FlowRunner, MCP, CLI, and Session.
    """
    if not targets:
        raise ValueError("No targets available for selection.")

    normalized = selector.strip().lower()
    if normalized in {"", "first"}:
        return targets[0]
    if normalized == "top_most":
        return min(
            targets,
            key=lambda item: target_logical_bounds(item, scale_factor=scale_factor)[:2][::-1],
        )
    if normalized == "left_most":
        return min(
            targets,
            key=lambda item: target_logical_bounds(item, scale_factor=scale_factor)[:2],
        )
    if normalized == "highest_confidence":
        return max(targets, key=lambda item: item.confidence)
    if normalized == "right_most":
        return max(
            targets,
            key=lambda item: target_logical_bounds(item, scale_factor=scale_factor)[:2],
        )
    raise ValueError(f"Invalid selector '{selector}'.")
