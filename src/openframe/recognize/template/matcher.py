"""Normalized cross-correlation template matching recognizer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openframe.recognize.base import Recognizer, RecognizerResult
from openframe.types import Frame, Target

DEFAULT_THRESHOLD = 0.88
DEFAULT_MAX_MATCHES = 20
DEFAULT_NMS_RADIUS = 8


class TemplateRecognizer(Recognizer):
    """Find targets by matching a template image crop against the frame.

    Opt-in via ``options["template"]`` (filesystem path to a PNG/JPEG crop).
    Without that key the recognizer returns no targets so default a11y+OCR
    behavior is unchanged when this plugin is registered.
    """

    name = "template:ncc"

    def __init__(self, *, priority: int = 50) -> None:
        super().__init__(priority=priority)

    def find(
        self, frame: Frame, query: str, options: dict[str, Any] | None = None
    ) -> RecognizerResult:
        opts = options or {}
        template_path = str(opts.get("template", "") or "").strip()
        if not template_path:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"reason": "no_template", "query": query},
            )
        if not frame.image_path:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"reason": "missing_image_path", "query": query},
            )

        try:
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Template matching dependencies are missing. "
                "Install with: pip install -e '.[template]'"
            ) from exc

        path = Path(template_path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Template image not found: {path}")

        threshold = float(opts.get("template_threshold", DEFAULT_THRESHOLD))
        max_matches = int(opts.get("template_max_matches", DEFAULT_MAX_MATCHES))
        nms_radius = int(opts.get("template_nms_radius", DEFAULT_NMS_RADIUS))
        scales = _parse_scales(opts.get("template_scales"))

        haystack = np.asarray(Image.open(frame.image_path).convert("L"), dtype=np.float64)
        needle_base = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
        if haystack.size == 0 or needle_base.size == 0:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"reason": "empty_image", "query": query, "template": str(path)},
            )

        targets: list[Target] = []
        for scale in scales:
            needle = _resize_gray(needle_base, scale)
            if needle.shape[0] < 2 or needle.shape[1] < 2:
                continue
            if needle.shape[0] > haystack.shape[0] or needle.shape[1] > haystack.shape[1]:
                continue
            corr = _normalized_cross_correlation(haystack, needle)
            peaks = _peaks_above_threshold(
                corr, threshold=threshold, max_matches=max_matches, nms_radius=nms_radius
            )
            height, width = needle.shape
            for row, col, score in peaks:
                targets.append(
                    Target(
                        x=int(col),
                        y=int(row),
                        width=int(width),
                        height=int(height),
                        confidence=float(score),
                        source=self.name,
                        coordinate_space="physical",
                        label=path.name,
                        text=query or path.stem,
                    )
                )

        targets.sort(key=lambda item: item.confidence, reverse=True)
        if max_matches > 0:
            targets = targets[:max_matches]

        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={
                "query": query,
                "template": str(path),
                "threshold": threshold,
                "scales": scales,
                "match_count": len(targets),
            },
        )


def _parse_scales(raw: Any) -> list[float]:
    if raw is None:
        return [1.0]
    if isinstance(raw, (int, float)):
        return [float(raw)]
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        values = [float(part) for part in parts]
        return values or [1.0]
    if isinstance(raw, (list, tuple)):
        values = [float(item) for item in raw]
        return values or [1.0]
    return [1.0]


def _resize_gray(image, scale: float):  # type: ignore[no-untyped-def]
    import numpy as np
    from PIL import Image

    if abs(scale - 1.0) < 1e-9:
        return image
    height, width = image.shape
    new_w = max(1, round(width * scale))
    new_h = max(1, round(height * scale))
    pil = Image.fromarray(image.astype(np.uint8), mode="L")
    resized = pil.resize((new_w, new_h), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float64)


def _normalized_cross_correlation(image, template):  # type: ignore[no-untyped-def]
    """Return a 2D NCC score map for grayscale float arrays.

    Flat (zero-variance) templates cannot use NCC; fall back to a mean absolute
    difference score in ``[0, 1]`` so solid icon crops still match.
    """
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view

    th, tw = template.shape
    out_h = image.shape[0] - th + 1
    out_w = image.shape[1] - tw + 1
    if out_h <= 0 or out_w <= 0:
        return np.zeros((0, 0), dtype=np.float64)

    # Materialize windows so mean/subtraction is safe on non-writeable views.
    windows = np.asarray(sliding_window_view(image, (th, tw)), dtype=np.float64)
    t = template - template.mean()
    t_energy = float(np.sqrt((t * t).sum()))
    if t_energy < 1e-9:
        mad = np.abs(windows - float(template.mean())).mean(axis=(2, 3))
        return 1.0 - np.clip(mad / 255.0, 0.0, 1.0)

    w_mean = windows.mean(axis=(2, 3), keepdims=True)
    w_norm = windows - w_mean
    w_energy = np.sqrt((w_norm * w_norm).sum(axis=(2, 3)))
    return (w_norm * t).sum(axis=(2, 3)) / (w_energy * t_energy + 1e-9)


def _peaks_above_threshold(
    corr,  # type: ignore[no-untyped-def]
    *,
    threshold: float,
    max_matches: int,
    nms_radius: int,
) -> list[tuple[int, int, float]]:
    import numpy as np

    if corr.size == 0:
        return []
    mask = corr >= threshold
    if not mask.any():
        return []

    candidates = [
        (int(r), int(c), float(corr[r, c]))
        for r, c in zip(*np.nonzero(mask), strict=False)
    ]
    candidates.sort(key=lambda item: item[2], reverse=True)

    selected: list[tuple[int, int, float]] = []
    for row, col, score in candidates:
        if any(abs(row - sr) <= nms_radius and abs(col - sc) <= nms_radius for sr, sc, _ in selected):
            continue
        selected.append((row, col, score))
        if len(selected) >= max_matches:
            break
    return selected
