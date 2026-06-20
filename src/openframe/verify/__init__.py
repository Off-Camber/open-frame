"""Verification layer."""

from .base import VerifyResult, Verifier
from .core import (
    MatchBounds,
    ScreenshotDiffVerifier,
    TargetGoneVerifier,
    TextPresenceVerifier,
    filter_targets,
    parse_match_bounds,
    write_step_artifacts,
)

__all__ = [
    "MatchBounds",
    "ScreenshotDiffVerifier",
    "TargetGoneVerifier",
    "TextPresenceVerifier",
    "VerifyResult",
    "Verifier",
    "filter_targets",
    "parse_match_bounds",
    "write_step_artifacts",
]
