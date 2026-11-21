#!/usr/bin/env python3
"""Annotate hero demo frames so Open Frame's role is obvious on sight."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

BRAND = "Open Frame"
PHASES = {
    "find": ("FIND", "locate “Post payment”"),
    "click": ("CLICK", "act on matched target"),
    "verify": ("VERIFY", "confirm payment posted"),
}


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


_BUTTON_RGB = (6, 56, 43)


def _is_button_pixel(red: int, green: int, blue: int) -> bool:
    target_r, target_g, target_b = _BUTTON_RGB
    return (
        abs(red - target_r) <= 12
        and abs(green - target_g) <= 12
        and abs(blue - target_b) <= 12
        and green > red + 20
    )


def _find_filled_button(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Return the demo's filled Post payment button, not the page around it."""
    rgb = image.convert("RGB")
    pixels = rgb.load()
    width, height = rgb.size
    seen = bytearray(width * height)
    best: tuple[int, int, int, int] | None = None
    best_area = 0
    for y in range(height):
        row = y * width
        for x in range(width):
            start = row + x
            if seen[start]:
                continue
            red, green, blue = pixels[x, y]
            if not _is_button_pixel(red, green, blue):
                seen[start] = 1
                continue
            stack = [(x, y)]
            seen[start] = 1
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    index = ny * width + nx
                    if seen[index]:
                        continue
                    nr, ng, nb = pixels[nx, ny]
                    if not _is_button_pixel(nr, ng, nb):
                        seen[index] = 1
                        continue
                    seen[index] = 1
                    stack.append((nx, ny))
            box_w = max_x - min_x + 1
            box_h = max_y - min_y + 1
            if not (90 <= box_w <= 280 and 28 <= box_h <= 90):
                continue
            if count < int(box_w * box_h * 0.45):
                continue
            if count > best_area:
                pad = 4
                best_area = count
                best = (
                    max(0, min_x - pad),
                    max(0, min_y - pad),
                    min(width - 1, max_x + pad),
                    min(height - 1, max_y + pad),
                )
    return best


def _find_button_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Return approximate Post payment button bounds via OCR word boxes."""
    try:
        import pytesseract
    except ImportError:
        return None

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words: list[tuple[str, int, int, int, int]] = []
    for i, raw in enumerate(data.get("text", [])):
        text = str(raw or "").strip()
        if not text:
            continue
        words.append(
            (
                text,
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            )
        )

    for idx in range(len(words) - 1):
        a, b = words[idx], words[idx + 1]
        if a[0].lower() == "post" and b[0].lower().startswith("payment"):
            x1, y1 = a[1], a[2]
            x2, y2 = b[1] + b[3], b[2] + b[4]
            pad = 10
            return (x1 - pad, y1 - pad, x2 + pad, y2 + pad)

    for text, x, y, w, h in words:
        if re.fullmatch(r"post", text, flags=re.IGNORECASE):
            pad = 14
            return (x - pad, y - pad, x + max(w, 160) + 40, y + h + pad)
    return None


def _phase_for_index(*, index: int, verify_at: int, click_at: int) -> str:
    if index >= verify_at:
        return "verify"
    if index >= click_at:
        return "click"
    return "find"


def _draw_overlay(
    image: Image.Image,
    *,
    phase: str,
    button_box: tuple[int, int, int, int] | None,
) -> Image.Image:
    frame = image.convert("RGBA")
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = frame.size

    title_font = _font(22)
    body_font = _font(16)
    brand_font = _font(15)

    brand = BRAND
    bw, bh = _measure(draw, brand, brand_font)
    bx0, by0 = 18, 16
    bx1, by1 = bx0 + bw + 22, by0 + bh + 14
    draw.rounded_rectangle((bx0, by0, bx1, by1), radius=6, fill=(16, 21, 28, 220))
    draw.text((bx0 + 11, by0 + 6), brand, font=brand_font, fill=(244, 239, 230, 255))

    label, detail = PHASES[phase]
    accent = {
        "find": (232, 168, 56, 255),
        "click": (64, 156, 255, 255),
        "verify": (46, 184, 122, 255),
    }[phase]
    panel_h = 58
    draw.rectangle((0, height - panel_h, width, height), fill=(12, 16, 22, 230))
    draw.rectangle((0, height - panel_h, 6, height), fill=accent)
    draw.text((18, height - 46), label, font=title_font, fill=accent)
    label_w, _ = _measure(draw, label, title_font)
    draw.text((18 + label_w + 14, height - 42), detail, font=body_font, fill=(220, 226, 232, 255))

    crumbs = ["FIND", "CLICK", "VERIFY"]
    x = width - 18
    for name in reversed(crumbs):
        active = (
            (phase == "verify" and name in {"FIND", "CLICK", "VERIFY"})
            or (phase == "click" and name in {"FIND", "CLICK"})
            or (phase == "find" and name == "FIND")
        )
        tw, th = _measure(draw, name, brand_font)
        x1 = x
        x0 = x - tw - 16
        y0 = height - 42
        y1 = y0 + th + 10
        fill = (
            accent
            if name.lower() == phase
            else ((40, 48, 58, 230) if active else (28, 34, 42, 200))
        )
        text_fill = (16, 21, 28, 255) if name.lower() == phase else (200, 208, 216, 255)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=5, fill=fill)
        draw.text((x0 + 8, y0 + 4), name, font=brand_font, fill=text_fill)
        x = x0 - 8

    if button_box is not None and phase in {"find", "click"}:
        x0, y0, x1, y1 = button_box
        y1 = min(y1, height - panel_h - 8)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=8, outline=accent, width=3)
        tag = "target"
        tw, th = _measure(draw, tag, brand_font)
        tx0, ty0 = x0, max(8, y0 - th - 14)
        draw.rounded_rectangle(
            (tx0, ty0, tx0 + tw + 14, ty0 + th + 10),
            radius=5,
            fill=accent,
        )
        draw.text((tx0 + 7, ty0 + 4), tag, font=brand_font, fill=(16, 21, 28, 255))

    if phase == "verify":
        msg = "outcome confirmed"
        tw, th = _measure(draw, msg, body_font)
        mx0 = width - tw - 34
        my0 = 16
        draw.rounded_rectangle(
            (mx0, my0, mx0 + tw + 18, my0 + th + 14),
            radius=6,
            fill=(46, 184, 122, 230),
        )
        draw.text((mx0 + 9, my0 + 6), msg, font=body_font, fill=(12, 24, 18, 255))

    return Image.alpha_composite(frame, overlay).convert("RGB")


def annotate_frames(frames: list[Image.Image]) -> list[Image.Image]:
    if not frames:
        return []

    verify_at = len(frames)
    for idx, frame in enumerate(frames):
        try:
            import pytesseract
        except ImportError:
            text = ""
        else:
            try:
                text = pytesseract.image_to_string(frame.convert("RGB")).lower()
            except pytesseract.TesseractError:
                text = ""
        if "payment posted" in text:
            verify_at = idx
            break

    if verify_at >= len(frames):
        verify_at = int(len(frames) * 0.62)
    click_at = max(int(len(frames) * 0.28), verify_at - max(3, len(frames) // 12))

    button_box = None
    for frame in frames[:8]:
        button_box = _find_filled_button(frame.convert("RGB"))
        if button_box is not None:
            break
    if button_box is None:
        button_box = _find_button_box(frames[min(2, len(frames) - 1)].convert("RGB"))

    annotated: list[Image.Image] = []
    for idx, frame in enumerate(frames):
        phase = _phase_for_index(index=idx, verify_at=verify_at, click_at=click_at)
        annotated.append(_draw_overlay(frame, phase=phase, button_box=button_box))
    return annotated


def load_gif(path: Path) -> tuple[list[Image.Image], int]:
    image = Image.open(path)
    frames: list[Image.Image] = []
    duration = 100
    for frame in ImageSequence.Iterator(image):
        frames.append(frame.convert("RGB"))
        duration = int(frame.info.get("duration", duration) or duration)
    if len(frames) < 8:
        # Pillow sometimes collapses optimized GIFs; explode via ffmpeg.
        frames = _explode_with_ffmpeg(path)
    return frames, duration


def _explode_with_ffmpeg(path: Path) -> list[Image.Image]:
    if shutil.which("ffmpeg") is None:
        return []
    with tempfile.TemporaryDirectory(prefix="openframe-hero-frames-") as tmp:
        pattern = str(Path(tmp) / "frame_%04d.png")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), pattern],
            check=True,
            capture_output=True,
        )
        files = sorted(Path(tmp).glob("frame_*.png"))
        return [Image.open(file).convert("RGB") for file in files]


def save_gif(frames: list[Image.Image], duration_ms: int, out: Path) -> None:
    if not frames:
        raise SystemExit("no frames to save")
    if shutil.which("ffmpeg") is None:
        frames[0].save(
            out,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            disposal=2,
        )
        return

    with tempfile.TemporaryDirectory(prefix="openframe-hero-out-") as tmp:
        for idx, frame in enumerate(frames):
            frame.save(Path(tmp) / f"frame_{idx:04d}.png")
        fps = max(4, min(12, round(1000 / max(duration_ms, 1))))
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(Path(tmp) / "frame_%04d.png"),
                "-vf",
                "split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=2",
                str(out),
            ],
            check=True,
            capture_output=True,
        )


def _load_scaled_frames(frames_dir: Path, width: int = 720) -> list[Image.Image]:
    files = sorted(frames_dir.glob("*.png"))
    frames: list[Image.Image] = []
    for file in files:
        image = Image.open(file).convert("RGB")
        if image.width != width:
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        frames.append(image)
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_gif", nargs="?", type=Path)
    parser.add_argument("output_gif", type=Path)
    parser.add_argument("--frames", type=Path, help="PNG frames to scale, annotate, and encode")
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()

    if args.frames is not None:
        frames = _load_scaled_frames(args.frames)
        duration = int(1000 * args.seconds / max(len(frames), 1))
    else:
        if args.input_gif is None:
            raise SystemExit("pass an input GIF or --frames")
        frames, duration = load_gif(args.input_gif)
        if len(frames) < 8:
            raise SystemExit(
                f"input GIF only has {len(frames)} frames; re-run scripts/record_hero_demo.sh"
            )
    annotated = annotate_frames(frames)
    save_gif(annotated, duration, args.output_gif)
    print(f"annotated {len(annotated)} frames -> {args.output_gif}")


if __name__ == "__main__":
    main()
