from __future__ import annotations

import types
from pathlib import Path
import sys

import pytest

from openframe.recognize.ocr.tesseract import TesseractRecognizer, _parse_confidence
from openframe.types import Frame


def test_parse_confidence_normalizes_values() -> None:
    assert _parse_confidence("95") == 0.95
    assert _parse_confidence("-1") == 0.0
    assert _parse_confidence("nope") == 0.0


def test_tesseract_recognizer_returns_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "ocr" / "sample.ppm"
    opened_paths: list[str] = []

    def fake_open(path: str) -> object:
        opened_paths.append(path)
        return object()

    image_module = types.SimpleNamespace(open=fake_open)
    pil_module = types.SimpleNamespace(Image=image_module)
    pytesseract_module = types.SimpleNamespace(
        image_to_data=lambda _image, output_type: {
            "text": ["Submit", "Cancel"],
            "conf": ["90", "85"],
            "left": [100, 200],
            "top": [40, 60],
            "width": [80, 70],
            "height": [20, 18],
        },
        Output=types.SimpleNamespace(DICT="DICT"),
    )
    monkeypatch.setitem(sys.modules, "PIL", pil_module)
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_module)

    recognizer = TesseractRecognizer()
    frame = Frame(
        width=1000,
        height=800,
        scale_factor=2.0,
        source="screen:1",
        image_path=str(fixture_path),
    )

    result = recognizer.find(frame=frame, query="submit")

    assert result.recognizer == "ocr:tesseract"
    assert len(result.targets) == 1
    assert result.targets[0].text == "Submit"
    assert opened_paths == [str(fixture_path)]
