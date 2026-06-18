"""macOS accessibility recognizer using System Events."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from openframe.recognize.base import Recognizer, RecognizerResult
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
            return RecognizerResult(recognizer=self.name, targets=[], metadata={"reason": "non-macos"})

        query_lower = query.strip().lower()
        if not query_lower:
            return RecognizerResult(recognizer=self.name, targets=[])

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
            if query_lower not in text.lower():
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
                    text=text,
                    label=str(item.get("role", "")) or None,
                )
            )

        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={"query": query, "match_count": len(targets), "elements_seen": len(elements)},
        )


def _is_macos() -> bool:
    return subprocess.run(["uname", "-s"], check=False, capture_output=True, text=True).stdout.strip() == "Darwin"


def _list_frontmost_elements() -> list[dict[str, Any]]:
    script = """
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
  if (pos && pos.x !== undefined && pos.y !== undefined) { x = Number(pos.x); y = Number(pos.y); }
  if (size && size.width !== undefined && size.height !== undefined) { w = Number(size.width); h = Number(size.height); }

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

    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown accessibility error"
        raise RuntimeError(f"macOS accessibility query failed: {message}")

    try:
        parsed = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("macOS accessibility recognizer returned invalid JSON.") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("macOS accessibility recognizer returned non-list output.")
    return parsed
