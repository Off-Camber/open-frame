"""Tesseract-based OCR recognizer."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from openframe.recognize.base import Recognizer, RecognizerResult
from openframe.recognize.match import (
    MatchMode,
    matching_token_spans,
    normalize_text,
    text_matches_query,
    tokenize,
)
from openframe.recognize.ocr.workspace import ocr_scratch_dir
from openframe.types import Frame, Target

# Measured on the macOS 27 TextEdit frames: 80 keeps CALMARK89, Example
# Domain, and the Finder "Date Added" header. 60 drops "Example". 100 splits
# the caret fixture into CALMARK8.
_INK_THRESHOLD = 80


class OcrError(RuntimeError):
    """Tesseract failed to read an image."""


class TesseractRecognizer(Recognizer):
    """Find text targets using Tesseract OCR output boxes."""

    name = "ocr:tesseract"

    def __init__(self, *, priority: int = 200) -> None:
        super().__init__(priority=priority)

    def find(
        self, frame: Frame, query: str, options: dict[str, Any] | None = None
    ) -> RecognizerResult:
        if not frame.image_path:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"reason": "missing_image_path", "query": query},
            )

        try:
            import pytesseract
            from PIL import Image
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                'OCR dependencies are missing. Install with: pip install "off-camber-open-frame[ocr]"'
            ) from exc

        # Grayscale keeps a caret from becoming an extra digit. A hard
        # threshold drops TextEdit's gray spell-check dots, which otherwise
        # turn a large C into G. The same threshold breaks a clean region
        # capture of that token, so both readings are kept.
        image = Image.open(frame.image_path).convert("L")
        rendered = (
            image,
            image.point(lambda pixel: 255 if pixel > _INK_THRESHOLD else 0),
        )
        query_normalized = normalize_text(query)
        if not query_normalized:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"query": query, "match_count": 0},
            )
        multi_word = len(tokenize(query)) > 1
        match_mode = _match_mode(options)
        targets: list[Target] = []
        for variant in rendered:
            try:
                with ocr_scratch_dir():
                    data = pytesseract.image_to_data(variant, output_type=Output.DICT)
            except (UnicodeDecodeError, pytesseract.TesseractError) as exc:
                raise OcrError(_ocr_failure_message(exc)) from exc
            word_targets = _targets_from_words(
                data, query=query, source=self.name, match_mode=match_mode
            )
            line_targets = (
                _targets_from_lines(data, query=query, source=self.name, match_mode=match_mode)
                if multi_word or match_mode == "substring"
                else []
            )
            if multi_word:
                targets.extend(line_targets or word_targets)
            else:
                targets.extend(word_targets or line_targets)

        targets = _dedupe_targets(targets)
        targets.sort(key=lambda item: item.confidence, reverse=True)
        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={"query": query, "match_count": len(targets), "match_mode": match_mode},
        )


def _ocr_failure_message(exc: BaseException) -> str:
    """Turn a Tesseract or decode failure into one readable sentence."""
    if isinstance(exc, UnicodeDecodeError):
        return (
            "Tesseract failed to read the image. Its error output was not text, "
            "which means Leptonica could not open the OCR input."
        )
    raw = getattr(exc, "message", None)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw.strip():
        raw = str(exc)
    cleaned = " ".join("".join(char if char.isprintable() else " " for char in raw).split())
    if not cleaned:
        return "Tesseract failed to read the image."
    return f"Tesseract failed to read the image: {cleaned}"


def _dedupe_targets(targets: list[Target]) -> list[Target]:
    seen: set[tuple[str | None, int, int, int, int]] = set()
    unique: list[Target] = []
    for target in targets:
        key = (target.text, target.x, target.y, target.width, target.height)
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def _match_mode(options: dict[str, Any] | None) -> MatchMode:
    raw = str((options or {}).get("match_mode", "token")).strip().lower()
    if raw == "substring":
        return "substring"
    return "token"


def _targets_from_words(
    data: dict[str, Any],
    *,
    query: str,
    source: str,
    match_mode: MatchMode = "token",
) -> list[Target]:
    targets: list[Target] = []
    total = len(data.get("text", []))
    for idx in range(total):
        raw_text = str(data["text"][idx]).strip()
        if not raw_text:
            continue

        if not text_matches_query(raw_text, query, mode=match_mode):
            continue

        confidence = _parse_confidence(
            data.get("conf", [])[idx] if idx < len(data.get("conf", [])) else ""
        )
        targets.append(
            Target(
                x=int(data["left"][idx]),
                y=int(data["top"][idx]),
                width=int(data["width"][idx]),
                height=int(data["height"][idx]),
                confidence=confidence,
                source=source,
                text=raw_text,
            )
        )
    return targets


def _targets_from_lines(
    data: dict[str, Any],
    *,
    query: str,
    source: str,
    match_mode: MatchMode = "token",
) -> list[Target]:
    groups: dict[tuple[int, int, int, int], list[int]] = {}
    total = len(data.get("text", []))
    for idx in range(total):
        if not str(data["text"][idx]).strip():
            continue
        key = _line_key(data, idx)
        groups.setdefault(key, []).append(idx)

    query_tokens = tokenize(query)
    targets: list[Target] = []
    for indices in groups.values():
        words = [str(data["text"][idx]).strip() for idx in indices]
        if match_mode == "substring":
            joined = " ".join(words)
            if not text_matches_query(joined, query, mode="substring"):
                continue
            start = 0
            end = len(words)
            matched_indices = indices
        else:
            word_tokens = [tokenize(word)[0] if tokenize(word) else "" for word in words]
            spans = matching_token_spans(word_tokens, query_tokens)
            if not spans:
                continue
            start, end = spans[0]
            matched_indices = indices[start:end]

        left = min(int(data["left"][idx]) for idx in matched_indices)
        top = min(int(data["top"][idx]) for idx in matched_indices)
        right = max(int(data["left"][idx]) + int(data["width"][idx]) for idx in matched_indices)
        bottom = max(int(data["top"][idx]) + int(data["height"][idx]) for idx in matched_indices)
        confidences = [
            _parse_confidence(data.get("conf", [])[idx] if idx < len(data.get("conf", [])) else "")
            for idx in matched_indices
        ]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        targets.append(
            Target(
                x=left,
                y=top,
                width=max(1, right - left),
                height=max(1, bottom - top),
                confidence=confidence,
                source=source,
                text=" ".join(words[start:end]),
            )
        )
    return targets


def _line_key(data: dict[str, Any], idx: int) -> tuple[int, int, int, int]:
    def at(key: str) -> int:
        values = data.get(key, [])
        if idx < len(values):
            return int(values[idx])
        return 0

    return (at("page_num"), at("block_num"), at("par_num"), at("line_num"))


def image_words(image_path: str) -> list[dict[str, Any]]:
    """Read every OCR word in an image, with pixel boxes and a line key."""
    try:
        import pytesseract
        from PIL import Image
        from pytesseract import Output
    except ImportError as exc:
        raise RuntimeError(
            'OCR dependencies are missing. Install with: pip install "off-camber-open-frame[ocr]"'
        ) from exc

    image = Image.open(image_path).convert("L")
    try:
        with ocr_scratch_dir():
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
    except (UnicodeDecodeError, pytesseract.TesseractError, OSError) as exc:
        raise OcrError(_ocr_failure_message(exc)) from exc

    words: list[dict[str, Any]] = []
    total = len(data.get("text", []))
    for idx in range(total):
        text = str(data["text"][idx]).strip()
        if not text:
            continue
        raw_conf = data.get("conf", [])[idx] if idx < len(data.get("conf", [])) else ""
        try:
            if float(raw_conf) < 0:
                continue
        except (TypeError, ValueError):
            pass
        try:
            left = int(data["left"][idx])
            top = int(data["top"][idx])
            width = int(data["width"][idx])
            height = int(data["height"][idx])
        except (TypeError, ValueError, KeyError):
            continue
        if width <= 0 or height <= 0:
            continue
        words.append(
            {
                "text": text,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "line": _line_key(data, idx),
            }
        )
    return words


# A toolbar is one OCR line. Words inside one button sit about half a text
# height apart ("Mark" to "Unread" was 10px at 21px height). The next button,
# including its icon, starts farther away (19px on that same toolbar).
_CONTROL_GAP_HEIGHT_RATIO = 0.6
_LABEL_CROP_HALF_WIDTH = 400
_LABEL_CROP_HALF_HEIGHT = 80


def label_from_words(words: list[dict[str, Any]], x: int, y: int) -> str | None:
    """Return the words of the control whose box contains an image pixel.

    Words on the same OCR line are separate controls when a gap separates
    them. A point with no control returns None.
    """
    lines: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for word in words:
        if not isinstance(word, dict):
            continue
        text = str(word.get("text") or "").strip()
        if not text:
            continue
        try:
            left = int(word["left"])
            top = int(word["top"])
            width = int(word["width"])
            height = int(word["height"])
        except (TypeError, ValueError, KeyError):
            continue
        if width <= 0 or height <= 0:
            continue
        line = word.get("line")
        key = line if isinstance(line, tuple) else (0,)
        lines.setdefault(key, []).append(
            {"text": text, "left": left, "top": top, "width": width, "height": height}
        )

    hits: list[list[dict[str, Any]]] = []
    for group in lines.values():
        for cluster in _control_clusters(group):
            if _cluster_contains(cluster, x, y):
                hits.append(cluster)
    if not hits:
        return None
    chosen = min(hits, key=_line_area)
    chosen.sort(key=lambda item: (item["left"], item["top"]))
    return " ".join(str(item["text"]) for item in chosen)


def label_in_frame(frame: Frame, x: int, y: int) -> str | None:
    """Read the control at a logical screen point from a captured image.

    The point is converted into that image's pixels. A missing image, an OCR
    failure, or a point with no words returns None.
    """
    if not frame.image_path:
        return None
    scale = frame.scale_factor if frame.scale_factor > 0 else 1.0
    pixel_x = round((x - frame.origin_x) * scale)
    pixel_y = round((y - frame.origin_y) * scale)
    try:
        words = _image_words_near(frame.image_path, pixel_x, pixel_y)
    except (OcrError, OSError, RuntimeError):
        return None
    return label_from_words(words, pixel_x, pixel_y)


def _image_words_near(image_path: str, pixel_x: int, pixel_y: int) -> list[dict[str, Any]]:
    """OCR a window around the point and shift the boxes back to image pixels."""
    crop = _crop_around(image_path, pixel_x, pixel_y)
    if crop is None:
        return image_words(image_path)
    temp_path, origin_x, origin_y = crop
    try:
        words = image_words(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)
    shifted: list[dict[str, Any]] = []
    for word in words:
        item = dict(word)
        try:
            item["left"] = int(item["left"]) + origin_x
            item["top"] = int(item["top"]) + origin_y
        except (TypeError, ValueError, KeyError):
            continue
        shifted.append(item)
    return shifted


def _crop_around(image_path: str, pixel_x: int, pixel_y: int) -> tuple[str, int, int] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image = Image.open(image_path)
    except (OSError, FileNotFoundError):
        return None
    width, height = image.size
    left = max(0, pixel_x - _LABEL_CROP_HALF_WIDTH)
    top = max(0, pixel_y - _LABEL_CROP_HALF_HEIGHT)
    right = min(width, pixel_x + _LABEL_CROP_HALF_WIDTH)
    bottom = min(height, pixel_y + _LABEL_CROP_HALF_HEIGHT)
    if right <= left or bottom <= top:
        return None
    if left == 0 and top == 0 and right == width and bottom == height:
        return None
    crop = image.crop((left, top, right, bottom))
    with ocr_scratch_dir():
        handle, temp_path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    crop.save(temp_path)
    return temp_path, left, top


def _control_clusters(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    ordered = sorted(words, key=lambda item: (int(item["left"]), int(item["top"])))
    if not ordered:
        return []
    clusters: list[list[dict[str, Any]]] = [[ordered[0]]]
    for word in ordered[1:]:
        if _same_control(clusters[-1][-1], word):
            clusters[-1].append(word)
        else:
            clusters.append([word])
    return clusters


def _same_control(left: dict[str, Any], right: dict[str, Any]) -> bool:
    gap = int(right["left"]) - (int(left["left"]) + int(left["width"]))
    if gap < 0:
        return True
    limit = _CONTROL_GAP_HEIGHT_RATIO * min(int(left["height"]), int(right["height"]))
    return gap <= limit


def _cluster_contains(words: list[dict[str, Any]], x: int, y: int) -> bool:
    left = min(int(item["left"]) for item in words)
    top = min(int(item["top"]) for item in words)
    right = max(int(item["left"]) + int(item["width"]) for item in words)
    bottom = max(int(item["top"]) + int(item["height"]) for item in words)
    return left <= x <= right and top <= y <= bottom


def _line_area(words: list[dict[str, Any]]) -> int:
    left = min(int(item["left"]) for item in words)
    top = min(int(item["top"]) for item in words)
    right = max(int(item["left"]) + int(item["width"]) for item in words)
    bottom = max(int(item["top"]) + int(item["height"]) for item in words)
    return max(1, right - left) * max(1, bottom - top)


def _parse_confidence(value: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0:
        return 0.0
    return min(1.0, numeric / 100.0)
