"""Frontmost window state reporting via macOS accessibility.

Phase 11 (window-level state awareness). Exposes the frontmost application
window's title, role, and bounds so guards can be based on the actual window
state rather than fragile OCR tokens that may match text in any window.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import sys
from typing import Callable


@dataclass(frozen=True, slots=True)
class WindowState:
    """Snapshot of the currently frontmost window."""

    app: str
    title: str
    role: str
    x: int
    y: int
    width: int
    height: int

    def contains(self, *, x: int, y: int, width: int, height: int) -> bool:
        """Return True if the given target bounds lie inside this window."""
        if width <= 0 or height <= 0:
            return False
        return (
            x >= self.x
            and y >= self.y
            and (x + width) <= (self.x + self.width)
            and (y + height) <= (self.y + self.height)
        )


WindowStateProvider = Callable[[], "WindowState | None"]


def frontmost_window() -> WindowState | None:
    """Return the frontmost window state, or None if it cannot be queried."""
    if sys.platform != "darwin":
        return None

    script = """
function safeCall(fn, fallback) {
  try { return fn(); } catch (e) { return fallback; }
}

var se = Application("System Events");
var procs = se.applicationProcesses.whose({ frontmost: true });
if (procs.length === 0) {
  JSON.stringify(null);
} else {
  var proc = procs[0];
  var name = safeCall(function () { return proc.name(); }, "") || "";
  var windows = safeCall(function () { return proc.windows(); }, []);
  if (windows.length === 0) {
    JSON.stringify({ app: String(name), title: "", role: "", x: 0, y: 0, width: 0, height: 0 });
  } else {
    var win = windows[0];
    var title = safeCall(function () { return win.name(); }, "") || "";
    var role = safeCall(function () { return win.role(); }, "") || "";
    var pos = safeCall(function () { return win.position(); }, null);
    var size = safeCall(function () { return win.size(); }, null);
    var x = 0, y = 0, w = 0, h = 0;
    if (pos) {
      if (Array.isArray(pos) && pos.length >= 2) { x = Number(pos[0]); y = Number(pos[1]); }
      else if (pos.x !== undefined && pos.y !== undefined) { x = Number(pos.x); y = Number(pos.y); }
    }
    if (size) {
      if (Array.isArray(size) && size.length >= 2) { w = Number(size[0]); h = Number(size[1]); }
      else if (size.width !== undefined && size.height !== undefined) {
        w = Number(size.width); h = Number(size.height);
      }
    }
    JSON.stringify({
      app: String(name), title: String(title), role: String(role),
      x: x, y: y, width: w, height: h
    });
  }
}
""".strip()

    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None

    raw = completed.stdout.strip()
    if not raw or raw == "null":
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    return WindowState(
        app=str(payload.get("app", "")),
        title=str(payload.get("title", "")),
        role=str(payload.get("role", "")),
        x=int(payload.get("x", 0) or 0),
        y=int(payload.get("y", 0) or 0),
        width=int(payload.get("width", 0) or 0),
        height=int(payload.get("height", 0) or 0),
    )


def evaluate_window_guard(
    *,
    spec: dict[str, str],
    state: WindowState | None,
) -> tuple[bool, str]:
    """Compare a guard spec against a window state snapshot.

    Returns (passed, message). `spec` may include keys ``app``,
    ``title_contains``, and ``role``. All provided keys must match.
    """
    if not spec:
        return True, "no window guard"
    if state is None:
        return False, "frontmost window unavailable"

    expected_app = str(spec.get("app", "")).strip()
    if expected_app and expected_app != state.app:
        return False, f"window app '{state.app}' != expected '{expected_app}'"

    expected_role = str(spec.get("role", "")).strip()
    if expected_role and expected_role != state.role:
        return False, f"window role '{state.role}' != expected '{expected_role}'"

    fragment = str(spec.get("title_contains", "")).strip()
    if fragment and fragment.lower() not in state.title.lower():
        return False, f"window title '{state.title}' does not contain '{fragment}'"

    return True, "window guard passed"
