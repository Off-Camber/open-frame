"""Base recognizer protocol used by locator strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openframe.types import Frame, Target


@dataclass(slots=True)
class RecognizerResult:
    """Result envelope returned by recognizers."""

    recognizer: str
    targets: list[Target] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Recognizer(ABC):
    """Base class for recognizer plugins."""

    name = "recognizer"

    def __init__(self, *, priority: int = 100) -> None:
        self.priority = priority

    @abstractmethod
    def find(
        self, frame: Frame, query: str, options: dict[str, Any] | None = None
    ) -> RecognizerResult:
        """Find potential targets for a query on a frame."""
