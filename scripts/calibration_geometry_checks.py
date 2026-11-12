"""Live clicks that check window, region, and frame_path geometry.

Run by scripts/macos_live_gate.sh. Each check clicks the calibration token in
TextEdit and requires the reported point to fall inside the TextEdit window
bounds reported by the OS. Prints one JSON object and exits nonzero if any
check fails. All three checks run even when an earlier one fails.
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
    click_kind: click
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
        prepare = _run_flow(out_dir / "geometry-prepare.yaml", PREPARE_FLOW, "geometry-prepare")
        window = _textedit_window()
        results["geometry_window_click"] = _check_window(out_dir, prepare, window)
        results["geometry_region_click"] = _check_region(out_dir)
        results["geometry_frame_path_click"] = _check_frame_path(out_dir)
    finally:
        _close_textedit()
    print(json.dumps(results, indent=2))
    return 0 if all(item["status"] == "pass" for item in results.values()) else 1


def _check_window(
    out_dir: Path, prepare: subprocess.CompletedProcess[str], window: dict | None
) -> dict[str, str]:
    if prepare.returncode != 0:
        return _fail(f"could not prepare TextEdit: {_tail(prepare.stderr or prepare.stdout)}")
    if window is None:
        return _fail("TextEdit window bounds were not listed")
    completed = _run_flow(out_dir / "geometry-window-click.yaml", WINDOW_CLICK_FLOW, "geometry-window")
    point = _point_from_run(completed.stdout)
    return _judge("window-scoped click", point, window, completed)


def _check_region(out_dir: Path) -> dict[str, str]:
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
        return _fail(f"region capture failed: {_tail(capture.stderr)}")
    click = _cli("click", MARKER, "--frame", str(image), "--json", "--expect-one")
    return _judge("region click", _point_from_click(click.stdout), _textedit_window() or window, click)


def _check_frame_path(out_dir: Path) -> dict[str, str]:
    window = _textedit_window()
    if window is None:
        return _fail("TextEdit window bounds were not listed")
    image = out_dir / "geometry-window.png"
    capture = _cli("capture", "--out", str(image), "--window-id", str(int(window["id"])))
    if capture.returncode != 0:
        return _fail(f"window capture failed: {_tail(capture.stderr)}")
    args = json.dumps(
        {"query": MARKER, "frame_path": str(image), "dry_run": False, "expect_one": True}
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
    return _judge("frame_path click", point, _textedit_window() or window, click)


def _judge(
    label: str,
    point: tuple[int, int] | None,
    window: dict,
    completed: subprocess.CompletedProcess[str],
) -> dict[str, str]:
    if completed.returncode != 0 or point is None:
        detail = _tail(completed.stderr or completed.stdout) or f"{label} produced no click point"
        return _fail(detail)
    bounds = window["bounds"]
    left = int(bounds["x"])
    top = int(bounds["y"])
    right = left + int(bounds["width"])
    bottom = top + int(bounds["height"])
    inside = left <= point[0] <= right and top <= point[1] <= bottom
    detail = (
        f"{label} at {point[0]},{point[1]}; "
        f"TextEdit bounds {left},{top} {int(bounds['width'])}x{int(bounds['height'])}"
    )
    if not inside:
        return _fail(detail)
    return {"status": "pass", "detail": detail}


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


def _fail(detail: str) -> dict[str, str]:
    return {"status": "fail", "detail": detail.replace("\n", " ").strip()[:300]}


def _tail(text: str) -> str:
    return " ".join(text.split())[-300:]


if __name__ == "__main__":
    raise SystemExit(main())
