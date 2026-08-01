"""Tesseract-based OCR recognizer."""

from __future__ import annotations

from typing import Any

from openframe.recognize.base import Recognizer, RecognizerResult
from openframe.types import Frame, Target


class TesseractRecognizer(Recognizer):
    """Find text targets using Tesseract OCR output boxes."""

    name = "ocr:tesseract"

    def __init__(self, *, priority: int = 200) -> None:
        super().__init__(priority=priority)

    def find(
        self, frame: Frame, query: str, options: dict[str, Any] | None = None
    ) -> RecognizerResult:
        if not frame.image_path:
            raise ValueError("TesseractRecognizer requires frame.image_path to be set.")

        try:
            import pytesseract
            from PIL import Image
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "OCR dependencies are missing. Install with: pip install -e .[ocr]"
            ) from exc

        image = Image.open(frame.image_path)
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        query_normalized = _normalize_text(query)
        if not query_normalized:
            return RecognizerResult(
                recognizer=self.name,
                targets=[],
                metadata={"query": query, "match_count": 0},
            )
        multi_word = len(query_normalized.split()) > 1

        word_targets = _targets_from_words(
            data, query_normalized=query_normalized, source=self.name
        )
        line_targets = (
            _targets_from_lines(
                data, query_normalized=query_normalized, source=self.name
            )
            if multi_word
            else []
        )

        if multi_word:
            targets = line_targets or word_targets
        else:
            targets = word_targets or line_targets

        targets.sort(key=lambda item: item.confidence, reverse=True)
        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={"query": query, "match_count": len(targets)},
        )


def _targets_from_words(
    data: dict[str, Any], *, query_normalized: str, source: str
) -> list[Target]:
    targets: list[Target] = []
    total = len(data.get("text", []))
    for idx in range(total):
        raw_text = str(data["text"][idx]).strip()
        if not raw_text:
            continue

        if query_normalized not in _normalize_text(raw_text):
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
    data: dict[str, Any], *, query_normalized: str, source: str
) -> list[Target]:
    groups: dict[tuple[int, int, int, int], list[int]] = {}
    total = len(data.get("text", []))
    for idx in range(total):
        if not str(data["text"][idx]).strip():
            continue
        key = _line_key(data, idx)
        groups.setdefault(key, []).append(idx)

    targets: list[Target] = []
    for indices in groups.values():
        words = [str(data["text"][idx]).strip() for idx in indices]
        normalized_words = [_normalize_text(word) for word in words]
        for start, end in _matching_word_spans(normalized_words, query_normalized):
            matched_indices = indices[start:end]
            left = min(int(data["left"][idx]) for idx in matched_indices)
            top = min(int(data["top"][idx]) for idx in matched_indices)
            right = max(
                int(data["left"][idx]) + int(data["width"][idx])
                for idx in matched_indices
            )
            bottom = max(
                int(data["top"][idx]) + int(data["height"][idx])
                for idx in matched_indices
            )
            confidences = [
                _parse_confidence(
                    data.get("conf", [])[idx] if idx < len(data.get("conf", [])) else ""
                )
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


def _matching_word_spans(
    normalized_words: list[str], query_normalized: str
) -> list[tuple[int, int]]:
    """Return word-index spans whose joined text contains the normalized query."""
    spans: list[tuple[int, int]] = []
    query_word_count = len(query_normalized.split())
    if query_word_count == 0:
        return spans
    for start in range(len(normalized_words) - query_word_count + 1):
        end = start + query_word_count
        if query_normalized in " ".join(normalized_words[start:end]):
            spans.append((start, end))
    return spans


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


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
