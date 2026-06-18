"""Verifier interfaces and result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openframe.types import Frame


@dataclass(slots=True)
class VerifyResult:
    """Result produced by a verifier."""

    verifier: str
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class Verifier(ABC):
    """Base verifier contract."""

    name = "verifier"

    @abstractmethod
    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        """Verify whether expected state change happened."""
