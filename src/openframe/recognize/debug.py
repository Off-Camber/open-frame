"""Debug helpers for visualizing recognizer targets."""

from __future__ import annotations

from pathlib import Path

from openframe.types import Target


def draw_debug_overlay(*, frame_path: str | Path, targets: list[Target], out_path: str | Path) -> Path:
    """Draw target boxes on top of a frame and write a PNG overlay image."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Overlay drawing requires Pillow. Install with: pip install -e .[ocr]") from exc

    source = Path(frame_path).expanduser().resolve()
    output = Path(out_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)

    for target in targets:
        left = target.x
        top = target.y
        right = target.x + target.width
        bottom = target.y + target.height
        draw.rectangle([(left, top), (right, bottom)], outline=(255, 0, 0), width=2)
        label = (target.text or target.label or target.source or "target")[:40]
        draw.text((left + 2, max(0, top - 12)), label, fill=(255, 0, 0))

    image.save(output, format="PNG")
    return output
