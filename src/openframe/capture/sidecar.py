"""Metadata written beside a capture so a later click can map image pixels."""

from __future__ import annotations

import json
from pathlib import Path

from openframe.types import Frame

SIDECAR_SUFFIX = ".openframe.json"


def sidecar_path(image_path: Path) -> Path:
    """Return the metadata path for a capture PNG."""
    return Path(str(image_path) + SIDECAR_SUFFIX)


def write_frame_sidecar(frame: Frame) -> None:
    """Write scale and origin next to ``frame.image_path``."""
    if not frame.image_path:
        return
    payload = {
        "width": frame.width,
        "height": frame.height,
        "scale_factor": frame.scale_factor,
        "origin_x": frame.origin_x,
        "origin_y": frame.origin_y,
        "source": frame.source,
    }
    path = sidecar_path(Path(frame.image_path))
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_frame_sidecar(image_path: Path) -> Frame | None:
    """Load a frame from its sidecar, or None when the sidecar is absent."""
    path = sidecar_path(image_path)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Frame(
        width=int(payload["width"]),
        height=int(payload["height"]),
        scale_factor=float(payload["scale_factor"]),
        source=str(payload.get("source") or f"file:{image_path.name}"),
        image_path=str(image_path),
        origin_x=int(payload.get("origin_x", 0)),
        origin_y=int(payload.get("origin_y", 0)),
        metadata={"input": "file", "sidecar": str(path)},
    )
