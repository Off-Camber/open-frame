"""Core datatypes for Open Frame."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Frame:
    """A captured display frame and its metadata."""

    width: int
    height: int
    scale_factor: float
    source: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Target:
    """A located target within a frame."""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    source: str
    label: str | None = None
    text: str | None = None


@dataclass(slots=True)
class Action:
    """An action to execute against a target or coordinates."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    target: Target | None = None


@dataclass(slots=True)
class StepResult:
    """Result data for one automation step."""

    step_id: str
    success: bool
    duration_ms: int
    error: str | None = None
    before_frame_path: str | None = None
    after_frame_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
