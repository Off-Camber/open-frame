"""Live clicks that check window, region, and frame_path geometry.

Run by scripts/macos_live_gate.sh. Each check double-clicks the calibration
token in TextEdit and passes only when that click selects the token. Prints
one JSON object and exits nonzero if any check fails. All three checks run
even when an earlier one fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MARKER = "CALMARK89"
ROOT = Path(__file__).resolve().parents[1]

PREPARE_FLOW = """name: geometry-prepare
steps:
  - id: focus-textedit
    kind: app
    name: TextEdit
  - id: type-token
    kind: type
    text: CALMARK89
    via: applescript
    size: 48
    window:
      app: TextEdit
  - id: wait-settle
    kind: wait
    ms: 900
  - id: refocus
    kind: app
    name: TextEdit
"""

WINDOW_CLICK_FLOW = """name: geometry-window-click
steps:
  - id: focus-textedit
    kind: app
    name: TextEdit
  - id: click-token
    kind: click
    query: CALMARK89
    scope: window
    anchor: center
    click_kind: double
    timeout_ms: 8000
    window:
      app: TextEdit
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: calibration_geometry_checks.py OUT_DIR", file=sys.stderr)
        return 2
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, str]] = {}
    try:
        _close_textedit()
        results["geometry_window_click"] = _check_window(out_dir)
        results["geometry_region_click"] = _check_region(out_dir)
        results["geometry_frame_path_click"] = _check_frame_path(out_dir)
    finally:
        _close_textedit()
    print(json.dumps(results, indent=2))
    return 0 if all(item["status"] == "pass" for item in results.values()) else 1


def _check_window(out_dir: Path) -> dict[str, str]:
    prepare = _prepare(out_dir)
    if prepare.returncode != 0:
        return _fail(
            "could not prepare TextEdit: "
            + (flow_step_error(prepare.stdout) or _flat(prepare.stderr or prepare.stdout))
        )
    window = _textedit_window()
    if window is None:
        return _fail("TextEdit window bounds were not listed")
    completed = _run_flow(
        out_dir / "geometry-window-click.yaml", WINDOW_CLICK_FLOW, "geometry-window"
    )
    point = _point_from_run(completed.stdout)
    return _judge("window-scoped click", point, completed)


def _check_region(out_dir: Path) -> dict[str, str]:
    prepare = _prepare(out_dir)
    if prepare.returncode != 0:
        return _fail(
            "could not prepare TextEdit: "
            + (flow_step_error(prepare.stdout) or _flat(prepare.stderr or prepare.stdout))
        )
    window = _textedit_window()
    if window is None:
        return _fail("TextEdit window bounds were not listed")
    bounds = window["bounds"]
    image = out_dir / "geometry-region.png"
    capture = _cli(
        "capture",
        "--out",
        str(image),
        "--x",
        str(int(bounds["x"])),
        "--y",
        str(int(bounds["y"])),
        "--width",
        str(int(bounds["width"])),
        "--height",
        str(int(bounds["height"])),
    )
    if capture.returncode != 0:
        return _fail(f"region capture failed: {_flat(capture.stderr)}")
    click = _cli(
        "click", MARKER, "--frame", str(image), "--json", "--expect-one", "--kind", "double"
    )
    return _judge("region click", _point_from_click(click.stdout), click)


def _check_frame_path(out_dir: Path) -> dict[str, str]:
    prepare = _prepare(out_dir)
    if prepare.returncode != 0:
        return _fail(
            "could not prepare TextEdit: "
            + (flow_step_error(prepare.stdout) or _flat(prepare.stderr or prepare.stdout))
        )
    window = _textedit_window()
    if window is None:
        return _fail("TextEdit window bounds were not listed")
    image = out_dir / "geometry-window.png"
    capture = _cli("capture", "--out", str(image), "--window-id", str(int(window["id"])))
    if capture.returncode != 0:
        return _fail(f"window capture failed: {_flat(capture.stderr)}")
    args = json.dumps(
        {
            "query": MARKER,
            "frame_path": str(image),
            "dry_run": False,
            "expect_one": True,
            "kind": "double",
        }
    )
    click = _cli("mcp", "call", "click", "--args-json", args)
    point = None
    if click.returncode == 0:
        try:
            payload = json.loads(click.stdout)
            raw = payload.get("data", {}).get("point")
            if isinstance(raw, dict):
                point = (int(raw["x"]), int(raw["y"]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            point = None
    return _judge("frame_path click", point, click)


def _judge(
    label: str,
    point: tuple[int, int] | None,
    completed: subprocess.CompletedProcess[str],
) -> dict[str, str]:
    if completed.returncode != 0 or point is None:
        detail = (
            flow_step_error(completed.stdout)
            or _flat(completed.stderr or completed.stdout)
            or f"{label} produced no click point"
        )
        return _fail(detail)
    hit = _textedit_hit()
    detail = f"{label} at {point[0]},{point[1]}; {hit['detail']}"
    if not click_hits_marker(hit, MARKER):
        return _fail(detail)
    return {"status": "pass", "detail": detail}


def _prepare(out_dir: Path) -> subprocess.CompletedProcess[str]:
    """Retype the token so a previous double-click selection cannot change the next capture."""
    return _run_flow(out_dir / "geometry-prepare.yaml", PREPARE_FLOW, "geometry-prepare")


def _run_flow(path: Path, text: str, run_id: str) -> subprocess.CompletedProcess[str]:
    path.write_text(text, encoding="utf-8")
    return _cli("run", str(path), "--json", "--run-id", run_id)


def _point_from_run(stdout: str) -> tuple[int, int] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    for step in payload.get("steps", []):
        raw = (step.get("details") or {}).get("point")
        if isinstance(raw, dict) and "x" in raw and "y" in raw:
            return (int(raw["x"]), int(raw["y"]))
    return None


def _point_from_click(stdout: str) -> tuple[int, int] | None:
    try:
        payload = json.loads(stdout)
        raw = payload.get("point")
        if isinstance(raw, dict):
            return (int(raw["x"]), int(raw["y"]))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def _textedit_window() -> dict | None:
    completed = _cli("list-windows", "--json")
    if completed.returncode != 0:
        return None
    try:
        windows = json.loads(completed.stdout).get("windows", [])
    except json.JSONDecodeError:
        return None
    matches = [
        item
        for item in windows
        if str(item.get("owner", "")) == "TextEdit" and isinstance(item.get("bounds"), dict)
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: int(item["bounds"].get("width", 0)) * int(item["bounds"].get("height", 0)),
    )


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openframe.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _close_textedit() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "TextEdit" to close every document saving no'],
        check=False,
        capture_output=True,
        text=True,
    )


def flow_step_error(stdout: str) -> str:
    """Return every failed step error from an ``open-frame run --json`` payload."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    errors: list[str] = []
    for step in payload.get("steps") or []:
        if step.get("success", True):
            continue
        errors.append(str(step.get("error") or f"{step.get('step_id')} failed"))
    return " ".join(errors)


def selection_is_marker(selected: str, marker: str = MARKER) -> bool:
    """Return True when TextEdit's selection is the calibration token."""
    return " ".join(selected.split()) == marker


def click_hits_marker(hit: dict[str, object], marker: str = MARKER) -> bool:
    """Return True when the selection or insertion point lies on the token.

    A double-click on the word selects it. pyautogui's double-click on this
    Mac leaves the caret in the word instead, and TextEdit then reports the
    selection as a newline. The insertion-point index still falls inside the
    token, which is the click landing on it.
    """
    selected = str(hit.get("selected") or "")
    if selection_is_marker(selected):
        return True
    document = str(hit.get("value") or "")
    location = hit.get("location")
    length = hit.get("length")
    if not isinstance(location, int) or location < 0:
        return False
    span = max(int(length) if isinstance(length, int) else 0, 1)
    end = location + span
    start = 0
    while True:
        index = document.find(marker, start)
        if index < 0:
            return False
        if location < index + len(marker) and end > index:
            return True
        start = index + 1


def _textedit_hit() -> dict[str, object]:
    script = r"""
function safe(fn, fallback) {
  try { return fn(); } catch (e) { return fallback; }
}
var se = Application("System Events");
var procs = se.applicationProcesses.whose({ name: "TextEdit" });
if (procs.length === 0) {
  JSON.stringify({ error: "TextEdit is not running" });
} else {
  function findArea(elem, depth) {
    if (!elem || depth > 10) return null;
    var role = safe(function () { return String(elem.role()); }, "");
    if (role === "AXTextArea") return elem;
    var kids = safe(function () { return elem.uiElements(); }, []);
    for (var i = 0; i < kids.length; i++) {
      var found = findArea(kids[i], depth + 1);
      if (found) return found;
    }
    return null;
  }
  var windows = safe(function () { return procs[0].windows(); }, []);
  var area = null;
  for (var w = 0; w < windows.length; w++) {
    area = findArea(windows[w], 0);
    if (area) break;
  }
  function attr(name) {
    if (!area) return null;
    return safe(function () { return area.attributes.byName(name).value(); }, null);
  }
  JSON.stringify({
    selected: attr("AXSelectedText"),
    value: attr("AXValue"),
    range: attr("AXSelectedTextRange"),
    found_area: Boolean(area)
  });
}
""".strip()
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {
            "detail": _flat(completed.stderr or completed.stdout) or "accessibility query failed"
        }
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {"detail": _flat(completed.stdout) or "accessibility returned invalid JSON"}
    if not isinstance(payload, dict):
        return {"detail": "accessibility returned an unexpected payload"}
    location, length = _range_parts(payload.get("range"))
    selected = str(payload.get("selected") or "")
    value = str(payload.get("value") or "")
    detail = f"selected {selected!r} range {location},{length}"
    if payload.get("error"):
        detail = str(payload["error"])
    if payload.get("found_area") is False:
        detail = "TextEdit text area was not found"
    return {
        "selected": selected,
        "value": value,
        "location": location,
        "length": length,
        "detail": detail,
    }


def _range_parts(raw: object) -> tuple[int, int]:
    if isinstance(raw, dict):
        location = raw.get("location", raw.get("loc"))
        length = raw.get("length", raw.get("len"))
        if isinstance(location, int) and isinstance(length, int):
            return location, length
    if isinstance(raw, list) and len(raw) >= 2 and all(isinstance(item, int) for item in raw[:2]):
        return int(raw[0]), int(raw[1])
    if isinstance(raw, str) and "," in raw:
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) >= 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
            return int(parts[0]), int(parts[1])
    return -1, 0


def _fail(detail: str) -> dict[str, str]:
    return {"status": "fail", "detail": _flat(detail)}


def _flat(text: str) -> str:
    return " ".join(text.split())


if __name__ == "__main__":
    raise SystemExit(main())
