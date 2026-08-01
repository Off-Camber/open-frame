"""Verification layer."""

from .base import Verifier, VerifyResult
from .core import (
    MatchBounds,
    ScreenshotDiffVerifier,
    TargetGoneVerifier,
    TextPresenceVerifier,
    WindowStateVerifier,
    filter_targets,
    parse_match_bounds,
    write_step_artifacts,
)

__all__ = [
    "MatchBounds",
    "ScreenshotDiffVerifier",
    "TargetGoneVerifier",
    "TextPresenceVerifier",
    "Verifier",
    "VerifyResult",
    "WindowStateVerifier",
    "filter_targets",
    "parse_match_bounds",
    "write_step_artifacts",
]
