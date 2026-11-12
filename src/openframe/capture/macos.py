"""macOS capture backend for screen snapshots."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from openframe.capture.sidecar import write_frame_sidecar
from openframe.types import Frame


class CaptureError(RuntimeError):
    """Raised when a capture operation fails."""


_SUBPROCESS_TIMEOUT_SEC = 30


def screen(out_path: str | Path | None = None) -> Frame:
    """Capture the primary display to PNG and return frame metadata."""
    _ensure_macos()

    image_path = _resolve_output_path(out_path)
    _run_command(["screencapture", "-x", "-D", "1", str(image_path)])

    width, height = _read_png_dimensions(image_path)
    left, top, logical_width, _logical_height = _main_display_bounds()
    scale_factor = _scale_from_logical_width(physical_width=width, logical_width=logical_width)
    metadata = {
        "backend": "screencapture",
        "display_index": 1,
        "physical_width": width,
        "physical_height": height,
    }

    frame = Frame(
        width=width,
        height=height,
        scale_factor=scale_factor,
        source="screen:1",
        image_path=str(image_path),
        metadata=metadata,
        origin_x=left,
        origin_y=top,
    )
    write_frame_sidecar(frame)
    return frame


def window(
    *,
    title: str | None = None,
    window_id: int | None = None,
    out_path: str | Path | None = None,
) -> Frame:
    """Capture a specific window by title or id, or the active window."""
    _ensure_macos()

    selected = _select_window_info(title=title, window_id=window_id)
    bounds = selected.get("bounds") if isinstance(selected.get("bounds"), dict) else {}
    logical_width = int(bounds.get("width") or 0)
    logical_height = int(bounds.get("height") or 0)
    if logical_width <= 0 or logical_height <= 0:
        raise CaptureError("Window bounds are missing, so the capture scale is unknown.")
    origin_x = int(bounds.get("x") or 0)
    origin_y = int(bounds.get("y") or 0)

    image_path = _resolve_output_path(out_path)
    # -o drops the window shadow so the PNG maps onto the window bounds.
    _run_command(["screencapture", "-x", "-o", "-l", str(selected["id"]), str(image_path)])

    width, height = _read_png_dimensions(image_path)
    scale_factor = _scale_from_logical_width(physical_width=width, logical_width=logical_width)
    metadata = {
        "backend": "screencapture",
        "window_id": selected["id"],
        "window_title": selected["title"],
        "window_owner": selected["owner"],
        "physical_width": width,
        "physical_height": height,
        "logical_width": logical_width,
        "logical_height": logical_height,
    }

    frame = Frame(
        width=width,
        height=height,
        scale_factor=scale_factor,
        source=f"window:{selected['id']}",
        image_path=str(image_path),
        metadata=metadata,
        origin_x=origin_x,
        origin_y=origin_y,
    )
    write_frame_sidecar(frame)
    return frame


def region(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    out_path: str | Path | None = None,
) -> Frame:
    """Capture a rectangular region in screen coordinates."""
    _ensure_macos()
    if width <= 0 or height <= 0:
        raise CaptureError("Region width and height must be greater than zero.")

    image_path = _resolve_output_path(out_path)
    region_spec = f"{x},{y},{width},{height}"
    _run_command(["screencapture", "-x", "-R", region_spec, str(image_path)])

    physical_width, physical_height = _read_png_dimensions(image_path)
    scale_factor = _scale_from_logical_width(physical_width=physical_width, logical_width=width)
    metadata = {
        "backend": "screencapture",
        "region": {"x": x, "y": y, "width": width, "height": height},
        "physical_width": physical_width,
        "physical_height": physical_height,
    }

    frame = Frame(
        width=physical_width,
        height=physical_height,
        scale_factor=scale_factor,
        source=f"region:{x},{y},{width},{height}",
        image_path=str(image_path),
        metadata=metadata,
        origin_x=x,
        origin_y=y,
    )
    write_frame_sidecar(frame)
    return frame


def list_windows() -> list[dict[str, Any]]:
    """Return visible, capturable windows from front to back."""
    _ensure_macos()
    return _list_window_infos()


def list_displays() -> list[dict[str, Any]]:
    """Return basic attached display information."""
    _ensure_macos()
    completed = _run_command(["system_profiler", "SPDisplaysDataType", "-json"])
    try:
        parsed = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise CaptureError("Failed to parse display information from system_profiler.") from exc

    items = parsed.get("SPDisplaysDataType", [])
    if not isinstance(items, list):
        return []

    displays: list[dict[str, Any]] = []
    for controller in items:
        ndrvs = controller.get("spdisplays_ndrvs", [])
        if not isinstance(ndrvs, list):
            continue
        for entry in ndrvs:
            if not isinstance(entry, dict):
                continue
            display = {
                "name": entry.get("_name", ""),
                "resolution": entry.get("_spdisplays_resolution", ""),
                "retina": bool(entry.get("spdisplays_retina")),
                "main": bool(entry.get("spdisplays_main")),
                "online": bool(entry.get("spdisplays_online")),
            }
            displays.append(display)
    return displays


def _ensure_macos() -> None:
    if sys.platform != "darwin":
        raise CaptureError("Screen capture is currently supported on macOS only.")


def _resolve_output_path(out_path: str | Path | None) -> Path:
    if out_path is None:
        fd, temp_path = tempfile.mkstemp(prefix="openframe-", suffix=".png")
        os.close(fd)
        Path(temp_path).unlink(missing_ok=True)
        return Path(temp_path)

    path = Path(out_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise CaptureError(
            f"Capture command timed out after {_SUBPROCESS_TIMEOUT_SEC:g}s: {' '.join(command)}"
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown error"
        raise CaptureError(f"Capture command failed: {' '.join(command)} ({stderr})")
    return completed


def _run_osascript_jxa(script: str) -> subprocess.CompletedProcess[str]:
    return _run_command(["osascript", "-l", "JavaScript", "-e", script])


_LIST_WINDOW_INFOS_SCRIPT = """
ObjC.import('CoreGraphics');
ObjC.import('Foundation');
const options = $.kCGWindowListOptionOnScreenOnly | $.kCGWindowListExcludeDesktopElements;
const infoRef = $.CGWindowListCopyWindowInfo(options, $.kCGNullWindowID);
// macOS 26+ no longer yields a usable JS Array from ObjC.deepUnwrap(CFArray).
// Bridge through NSArray/NSDictionary accessors instead.
const arr = ObjC.castRefToObject(infoRef);
const count = Number(arr.count);

function scalar(dict, key) {
  const value = dict.objectForKey(key);
  if (value === undefined || value === null) return null;
  return ObjC.unwrap(value);
}

function boundNumber(boundsDict, upper, lower) {
  if (!boundsDict) return 0;
  const value = scalar(boundsDict, upper) ?? scalar(boundsDict, lower) ?? 0;
  return Number(value);
}

const windows = [];
for (let i = 0; i < count; i++) {
  const dict = arr.objectAtIndex(i);
  const layer = Number(scalar(dict, 'kCGWindowLayer') ?? 0);
  const alpha = Number(scalar(dict, 'kCGWindowAlpha') ?? 1);
  const boundsDict = dict.objectForKey('kCGWindowBounds');
  const width = boundNumber(boundsDict, 'Width', 'width');
  const height = boundNumber(boundsDict, 'Height', 'height');
  if (layer !== 0 || alpha <= 0 || width <= 1 || height <= 1) continue;
  windows.push({
    id: Number(scalar(dict, 'kCGWindowNumber')),
    owner: String(scalar(dict, 'kCGWindowOwnerName') ?? ''),
    title: String(scalar(dict, 'kCGWindowName') ?? ''),
    bounds: {
      x: boundNumber(boundsDict, 'X', 'x'),
      y: boundNumber(boundsDict, 'Y', 'y'),
      width,
      height,
    }
  });
}
JSON.stringify(windows);
""".strip()


def _list_window_infos() -> list[dict[str, Any]]:
    completed = _run_osascript_jxa(_LIST_WINDOW_INFOS_SCRIPT)
    try:
        parsed = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise CaptureError("Failed to parse window list from macOS capture API.") from exc
    if not isinstance(parsed, list):
        raise CaptureError("Window list output was not a JSON array.")
    return parsed


def _select_window_info(
    *, title: str | None = None, window_id: int | None = None
) -> dict[str, Any]:
    windows = _list_window_infos()
    if not windows:
        raise CaptureError("No capturable windows are currently visible.")

    if window_id is not None:
        for item in windows:
            if int(item.get("id", -1)) == window_id:
                return item
        raise CaptureError(f"Could not find a visible window with id {window_id}.")

    if title:
        target = title.lower()
        for item in windows:
            owner = str(item.get("owner", "")).lower()
            window_title = str(item.get("title", "")).lower()
            if target in window_title or target in owner:
                return item
        raise CaptureError(f'Could not find a visible window matching "{title}".')

    return windows[0]


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise CaptureError(f"Expected PNG data at {path}")
    width, height = struct.unpack(">II", raw[16:24])
    return width, height


def _main_display_bounds() -> tuple[int, int, int, int]:
    """Return the main display as left, top, width, height in logical points."""
    try:
        completed = _run_command(
            [
                "osascript",
                "-e",
                'tell application "Finder" to get bounds of window of desktop',
            ]
        )
    except CaptureError as exc:
        raise CaptureError(
            "Cannot read the main display size, so the capture scale is unknown."
        ) from exc

    values = [segment.strip() for segment in completed.stdout.strip().split(",")]
    if len(values) != 4:
        raise CaptureError("Cannot read the main display size, so the capture scale is unknown.")

    try:
        left, top, right, bottom = (int(value) for value in values)
    except ValueError as exc:
        raise CaptureError(
            "Cannot read the main display size, so the capture scale is unknown."
        ) from exc

    logical_width = right - left
    logical_height = bottom - top
    if logical_width <= 0 or logical_height <= 0:
        raise CaptureError("Cannot read the main display size, so the capture scale is unknown.")
    return left, top, logical_width, logical_height


def _scale_from_logical_width(*, physical_width: int, logical_width: int) -> float:
    """Return physical pixels per logical point for sizes that are already known."""
    if physical_width <= 0 or logical_width <= 0:
        raise CaptureError("Cannot compute scale: width must be positive.")
    ratio = physical_width / logical_width
    for expected in (1.0, 2.0, 3.0):
        if abs(ratio - expected) <= 0.02:
            return expected
    return round(ratio, 2)
