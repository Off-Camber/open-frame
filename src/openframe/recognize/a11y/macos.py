"""macOS accessibility recognizer using System Events."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from openframe.recognize.base import Recognizer, RecognizerResult
from openframe.recognize.match import MatchMode, text_matches_query
from openframe.types import Frame, Target


class MacOSA11yRecognizer(Recognizer):
    """Find targets by querying the frontmost app accessibility tree."""

    name = "a11y:macos"

    def __init__(self, *, priority: int = 100) -> None:
        super().__init__(priority=priority)

    def find(
        self, frame: Frame, query: str, options: dict[str, Any] | None = None
    ) -> RecognizerResult:
        if not _is_macos():
            return RecognizerResult(
                recognizer=self.name, targets=[], metadata={"reason": "non-macos"}
            )

        if not query.strip():
            return RecognizerResult(recognizer=self.name, targets=[])

        match_mode = _match_mode(options)

        try:
            elements = _list_frontmost_elements()
        except RuntimeError as exc:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"error": str(exc)},
            )

        targets: list[Target] = []
        for item in elements:
            text = str(item.get("title", "")).strip()
            if not text:
                continue
            if not text_matches_query(text, query, mode=match_mode):
                continue

            width = int(item.get("width", 0))
            height = int(item.get("height", 0))
            if width <= 0 or height <= 0:
                continue

            targets.append(
                Target(
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=width,
                    height=height,
                    confidence=0.95,
                    source=self.name,
                    coordinate_space="logical",
                    text=text,
                    label=str(item.get("role", "")) or None,
                )
            )

        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={
                "query": query,
                "match_count": len(targets),
                "elements_seen": len(elements),
                "match_mode": match_mode,
            },
        )


def _match_mode(options: dict[str, Any] | None) -> MatchMode:
    raw = str((options or {}).get("match_mode", "token")).strip().lower()
    if raw == "substring":
        return "substring"
    return "token"


def _is_macos() -> bool:
    return (
        subprocess.run(["uname", "-s"], check=False, capture_output=True, text=True).stdout.strip()
        == "Darwin"
    )


_LIST_FRONTMOST_ELEMENTS_SCRIPT = """
function safeCall(fn, fallback) {
  try { return fn(); } catch (e) { return fallback; }
}

function collect(elem, depth, out) {
  if (!elem || depth > 5 || out.length >= 400) return;
  var title = safeCall(function () { return elem.name(); }, "") || "";
  if (!title) {
    title = safeCall(function () { return elem.description(); }, "") || "";
  }
  var role = safeCall(function () { return elem.role(); }, "") || "";
  var pos = safeCall(function () { return elem.position(); }, null);
  var size = safeCall(function () { return elem.size(); }, null);
  var x = 0, y = 0, w = 0, h = 0;
  // System Events may return [x, y] / [width, height] arrays or {x,y}/{width,height} objects.
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

  out.push({ title: String(title), role: String(role), x: x, y: y, width: w, height: h });

  var children = safeCall(function () { return elem.uiElements(); }, []);
  for (var i = 0; i < children.length; i++) {
    collect(children[i], depth + 1, out);
  }
}

var se = Application("System Events");
var procs = se.applicationProcesses.whose({ frontmost: true });
if (procs.length === 0) {
  JSON.stringify([]);
} else {
  var root = procs[0];
  var out = [];
  var windows = safeCall(function () { return root.windows(); }, []);
  for (var w = 0; w < windows.length; w++) {
    collect(windows[w], 0, out);
  }
  JSON.stringify(out);
}
""".strip()


def _list_frontmost_elements() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", _LIST_FRONTMOST_ELEMENTS_SCRIPT],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = (
            completed.stderr.strip() or completed.stdout.strip() or "unknown accessibility error"
        )
        raise RuntimeError(f"macOS accessibility query failed: {message}")

    try:
        parsed = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("macOS accessibility recognizer returned invalid JSON.") from exc

    if not isinstance(parsed, list):
        raise TypeError("macOS accessibility recognizer returned non-list output.")
    return parsed
