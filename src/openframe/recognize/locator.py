"""Locator API for querying recognizers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from openframe.recognize.base import Recognizer
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
                _merge_target(merged_targets, candidate, dedupe_iou_threshold)

            if strategy == "first":
                break

        return merged_targets


def _merge_target(collected: list[Target], candidate: Target, iou_threshold: float) -> None:
    for idx, existing in enumerate(collected):
        if _iou(existing, candidate) < iou_threshold:
            continue

        # Keep the best-confidence target when boxes likely refer to same UI element.
        if candidate.confidence > existing.confidence:
            collected[idx] = candidate
        return

    collected.append(candidate)


def _iou(left: Target, right: Target) -> float:
    left_x2 = left.x + left.width
    left_y2 = left.y + left.height
    right_x2 = right.x + right.width
    right_y2 = right.y + right.height

    inter_left = max(left.x, right.x)
    inter_top = max(left.y, right.y)
    inter_right = min(left_x2, right_x2)
    inter_bottom = min(left_y2, right_y2)

    inter_width = max(0, inter_right - inter_left)
    inter_height = max(0, inter_bottom - inter_top)
    inter_area = inter_width * inter_height
    if inter_area == 0:
        return 0.0

    left_area = left.width * left.height
    right_area = right.width * right.height
    union = left_area + right_area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union
