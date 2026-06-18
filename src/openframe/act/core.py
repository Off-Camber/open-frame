"""Action execution primitives for UI automation."""

from __future__ import annotations

import time
from typing import Callable
from typing import Literal

from openframe.types import Frame
from openframe.types import Target

ClickAnchor = Literal["center", "top-left", "top-right", "bottom-left", "bottom-right"]
ClickKind = Literal["click", "double", "right"]


class ActError(RuntimeError):
    """Raised when an action cannot be executed."""


class Actuator:
    """Execute input actions with optional dry-run safety."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def point_for_target(self, target: Target, *, anchor: ClickAnchor = "center") -> tuple[int, int]:
        """Map target bounds to a click point."""
        if anchor == "center":
            return (target.x + target.width // 2, target.y + target.height // 2)
        if anchor == "top-left":
            return (target.x, target.y)
        if anchor == "top-right":
            return (target.x + target.width, target.y)
        if anchor == "bottom-left":
            return (target.x, target.y + target.height)
        if anchor == "bottom-right":
            return (target.x + target.width, target.y + target.height)
        raise ValueError(f"Unsupported click anchor: {anchor}")

    def click_target(self, target: Target, *, anchor: ClickAnchor = "center", kind: ClickKind = "click") -> tuple[int, int]:
        """Click a target at a mapped point."""
        x, y = self.point_for_target(target, anchor=anchor)
        self.click_point(x, y, kind=kind)
        return (x, y)

    def click_point(self, x: int, y: int, *, kind: ClickKind = "click") -> None:
        """Click at absolute screen coordinates."""
        if self.dry_run:
            return

        pyautogui = _load_pyautogui()
        if kind == "click":
            pyautogui.click(x=x, y=y, button="left")
            return
        if kind == "double":
            pyautogui.doubleClick(x=x, y=y, button="left")
            return
        if kind == "right":
            pyautogui.click(x=x, y=y, button="right")
            return
        raise ValueError(f"Unsupported click kind: {kind}")

    def type_text(self, text: str, *, interval: float = 0.0) -> None:
        """Type plain text at current focus."""
        if self.dry_run:
            return
        pyautogui = _load_pyautogui()
        pyautogui.write(text, interval=interval)

    def key_combo(self, *keys: str) -> None:
        """Press a key combination, e.g. ('command', 'v')."""
        if self.dry_run:
            return
        if not keys:
            raise ValueError("At least one key is required.")
        pyautogui = _load_pyautogui()
        pyautogui.hotkey(*keys)

    def press_key(self, key: str) -> None:
        """Press a single key."""
        if self.dry_run:
            return
        if not key:
            raise ValueError("key is required")
        pyautogui = _load_pyautogui()
        pyautogui.press(key)

    def scroll(self, clicks: int, *, x: int | None = None, y: int | None = None) -> None:
        """Scroll at a point (or current cursor position)."""
        if self.dry_run:
            return
        pyautogui = _load_pyautogui()
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
            return
        pyautogui.scroll(clicks)

    def wait_ms(self, milliseconds: int) -> None:
        """Wait for a fixed duration."""
        if milliseconds < 0:
            raise ValueError("milliseconds must be >= 0")
        time.sleep(milliseconds / 1000.0)

    def wait_for_frame_change(
        self,
        *,
        capture_frame: Callable[[], Frame],
        timeout_ms: int = 3000,
        poll_ms: int = 150,
    ) -> bool:
        """Poll capture until frame image/source changes or timeout."""
        if timeout_ms < 0 or poll_ms <= 0:
            raise ValueError("timeout_ms must be >= 0 and poll_ms must be > 0")

        baseline = capture_frame()
        baseline_key = _frame_change_key(baseline)
        deadline = time.monotonic() + (timeout_ms / 1000.0)

        while time.monotonic() <= deadline:
            current = capture_frame()
            if _frame_change_key(current) != baseline_key:
                return True
            time.sleep(poll_ms / 1000.0)
        return False


def _load_pyautogui():  # type: ignore[no-untyped-def]
    try:
        import pyautogui
    except ImportError as exc:
        raise ActError("Action dependencies missing. Install with: pip install -e .[act]") from exc
    return pyautogui


def _frame_change_key(frame: Frame) -> tuple[str | None, str]:
    return (frame.image_path, frame.source)
