"""Locator API for querying recognizers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from openframe.recognize.base import Recognizer
from openframe.recognize.coords import target_logical_bounds
from openframe.types import Frame, Target

LocatorStrategy = Literal["first", "all"]


class Locator:
    """Runs recognizers in priority order and returns matching targets."""

    def __init__(self, recognizers: Iterable[Recognizer] | None = None) -> None:
        self._recognizers: list[Recognizer] = []
        if recognizers:
            for recognizer in recognizers:
                self.register(recognizer)

    def register(self, recognizer: Recognizer) -> None:
        """Register one recognizer instance."""
        self._recognizers.append(recognizer)

    def find(
        self,
        frame: Frame,
        query: str,
        strategy: LocatorStrategy = "first",
        options: dict[str, Any] | None = None,
    ) -> list[Target]:
        """Locate targets for a query by running recognizers by priority."""
        if strategy not in ("first", "all"):
            raise ValueError(f"Unsupported locator strategy: {strategy}")

        merged_targets: list[Target] = []
        dedupe_iou_threshold = float((options or {}).get("dedupe_iou_threshold", 0.5))

        ordered = sorted(self._recognizers, key=lambda item: item.priority)

        for recognizer in ordered:
            result = recognizer.find(frame=frame, query=query, options=options)
            if not result.targets:
                continue

            for candidate in result.targets:
                _merge_target(
                    merged_targets,
                    candidate,
                    dedupe_iou_threshold,
                    scale_factor=frame.scale_factor,
                )

            if strategy == "first":
                break

        return merged_targets


def _merge_target(
    collected: list[Target],
    candidate: Target,
    iou_threshold: float,
    *,
    scale_factor: float,
) -> None:
    for idx, existing in enumerate(collected):
        if _iou(existing, candidate, scale_factor=scale_factor) < iou_threshold:
            continue

        # Keep the best-confidence target when boxes likely refer to same UI element.
        if candidate.confidence > existing.confidence:
            collected[idx] = candidate
        return

    collected.append(candidate)


def _iou(left: Target, right: Target, *, scale_factor: float = 1.0) -> float:
    left_x, left_y, left_width, left_height = target_logical_bounds(
        left, scale_factor=scale_factor
    )
    right_x, right_y, right_width, right_height = target_logical_bounds(
        right, scale_factor=scale_factor
    )
    left_x2 = left_x + left_width
    left_y2 = left_y + left_height
    right_x2 = right_x + right_width
    right_y2 = right_y + right_height

    inter_left = max(left_x, right_x)
    inter_top = max(left_y, right_y)
    inter_right = min(left_x2, right_x2)
    inter_bottom = min(left_y2, right_y2)

    inter_width = max(0, inter_right - inter_left)
    inter_height = max(0, inter_bottom - inter_top)
    inter_area = inter_width * inter_height
    if inter_area == 0:
        return 0.0

    left_area = left_width * left_height
    right_area = right_width * right_height
    union = left_area + right_area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union
