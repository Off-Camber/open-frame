"""Tesseract-based OCR recognizer."""

from __future__ import annotations

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
                "OCR dependencies are missing. Install with: pip install -e .[ocr]"
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


def _parse_confidence(value: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0:
        return 0.0
    return min(1.0, numeric / 100.0)
