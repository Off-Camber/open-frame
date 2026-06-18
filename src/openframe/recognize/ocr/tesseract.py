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
            from PIL import Image
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "OCR dependencies are missing. Install with: pip install -e .[ocr]"
            ) from exc

        image = Image.open(frame.image_path)
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        query_lower = query.strip().lower()
        targets: list[Target] = []

        total = len(data.get("text", []))
        for idx in range(total):
            raw_text = str(data["text"][idx]).strip()
            if not raw_text:
                continue

            text_lower = raw_text.lower()
            if query_lower not in text_lower:
                continue

            confidence = _parse_confidence(data.get("conf", [])[idx] if idx < len(data.get("conf", [])) else "")
            target = Target(
                x=int(data["left"][idx]),
                y=int(data["top"][idx]),
                width=int(data["width"][idx]),
                height=int(data["height"][idx]),
                confidence=confidence,
                source=self.name,
                text=raw_text,
            )
            targets.append(target)

        targets.sort(key=lambda item: item.confidence, reverse=True)
        return RecognizerResult(
            recognizer=self.name,
            targets=targets,
            metadata={"query": query, "match_count": len(targets)},
        )


def _parse_confidence(value: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0:
        return 0.0
    return min(1.0, numeric / 100.0)
