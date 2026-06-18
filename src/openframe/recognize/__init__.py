"""Recognizer interfaces and implementations."""

from .a11y import MacOSA11yRecognizer
from .base import Recognizer, RecognizerResult
from .debug import draw_debug_overlay
from .locator import Locator, LocatorStrategy
from .ocr import TesseractRecognizer

__all__ = [
    "Locator",
    "LocatorStrategy",
    "MacOSA11yRecognizer",
    "Recognizer",
    "RecognizerResult",
    "TesseractRecognizer",
    "draw_debug_overlay",
]
