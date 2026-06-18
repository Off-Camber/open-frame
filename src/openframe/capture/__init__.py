"""Capture backends and interfaces."""

from .macos import CaptureError, list_displays, list_windows, region, screen, window

__all__ = ["CaptureError", "list_displays", "list_windows", "region", "screen", "window"]
