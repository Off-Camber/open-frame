from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

import pytest

from openframe.recognize.ocr.tesseract import TesseractRecognizer, _parse_confidence
from openframe.types import Frame


class _FakeImage:
    def __init__(self, mode: str = "RGB") -> None:
        self.mode = mode

    def convert(self, mode: str) -> _FakeImage:
        return _FakeImage(mode)

    def point(self, _fn: object) -> _FakeImage:
        return self


def test_parse_confidence_normalizes_values() -> None:
    assert _parse_confidence("95") == 0.95
    assert _parse_confidence("-1") == 0.0
    assert _parse_confidence("nope") == 0.0


def test_tesseract_recognizer_returns_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "ocr" / "sample.ppm"
    opened_paths: list[str] = []
    seen_modes: list[str] = []

    def fake_open(path: str) -> _FakeImage:
        opened_paths.append(path)
        return _FakeImage()

    def image_to_data(image: _FakeImage, output_type: str) -> dict[str, list[object]]:
        _ = output_type
        seen_modes.append(image.mode)
        return {
            "text": ["Submit", "Cancel"],
            "conf": ["90", "85"],
            "left": [100, 200],
            "top": [40, 60],
            "width": [80, 70],
            "height": [20, 18],
            "page_num": [1, 1],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 2],
        }

    pytesseract_module = types.SimpleNamespace(
        image_to_data=image_to_data,
        Output=types.SimpleNamespace(DICT="DICT"),
    )
    monkeypatch.setitem(
        sys.modules, "PIL", types.SimpleNamespace(Image=types.SimpleNamespace(open=fake_open))
    )
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
    assert seen_modes == ["L", "L"]

    empty_result = recognizer.find(frame=frame, query=" \t ")

    assert empty_result.targets == []


def test_tesseract_recognizer_matches_multi_word_queries_on_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "ocr" / "sample.ppm"
    pil_module = types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda _path: _FakeImage()))
    pytesseract_module = types.SimpleNamespace(
        image_to_data=lambda _image, output_type: {
            "text": ["Invoice", "No:", "Vendor", "Reference"],
            "conf": ["90", "88", "92", "86"],
            "left": [10, 90, 140, 220],
            "top": [20, 20, 20, 20],
            "width": [70, 30, 70, 90],
            "height": [18, 18, 18, 18],
            "page_num": [1, 1, 1, 1],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 1, 1],
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

    result = recognizer.find(frame=frame, query="  Invoice   No  ")

    assert len(result.targets) == 1
    assert result.targets[0].text == "Invoice No:"
    assert (result.targets[0].x, result.targets[0].width) == (10, 110)


def test_tesseract_recognizer_rejects_substring_inside_longer_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "ocr" / "sample.ppm"
    pil_module = types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda _path: _FakeImage()))

    def _data_for(texts: list[str]) -> dict[str, list[object]]:
        count = len(texts)
        return {
            "text": texts,
            "conf": ["90"] * count,
            "left": [10 + idx * 120 for idx in range(count)],
            "top": [20] * count,
            "width": [100] * count,
            "height": [18] * count,
            "page_num": [1] * count,
            "block_num": [1] * count,
            "par_num": [1] * count,
            "line_num": [1] * count,
        }

    current = {"payload": _data_for(["actuation"])}
    pytesseract_module = types.SimpleNamespace(
        image_to_data=lambda _image, output_type: current["payload"],
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

    assert recognizer.find(frame=frame, query="AC").targets == []

    current["payload"] = _data_for(["actuation", "AC"])
    result = recognizer.find(frame=frame, query="AC")
    assert len(result.targets) == 1
    assert result.targets[0].text == "AC"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_tesseract_reads_calmark89_beside_a_colored_caret() -> None:
    """The blue TextEdit caret used to be read as an extra digit."""
    pytest.importorskip("pytesseract")
    pytest.importorskip("PIL")
    fixture = Path(__file__).parent / "fixtures" / "ocr" / "textedit-caret-calmark89.png"
    frame = Frame(
        width=1172,
        height=976,
        scale_factor=2.0,
        source="fixture:textedit-caret",
        image_path=str(fixture),
    )

    result = TesseractRecognizer().find(frame=frame, query="CALMARK89")

    assert result.targets
    assert any(target.text == "CALMARK89" for target in result.targets)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_tesseract_reads_calmark89_through_spellcheck_dots() -> None:
    """Gray spell-check dots under the large token were read as part of the glyph."""
    pytest.importorskip("pytesseract")
    pytest.importorskip("PIL")
    fixture = Path(__file__).parent / "fixtures" / "ocr" / "textedit-dotted-calmark89.png"
    frame = Frame(
        width=1110,
        height=180,
        scale_factor=2.0,
        source="fixture:textedit-dots",
        image_path=str(fixture),
    )

    result = TesseractRecognizer().find(frame=frame, query="CALMARK89")

    assert any(target.text == "CALMARK89" for target in result.targets)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_tesseract_reads_calmark89_on_a_clean_region_capture() -> None:
    """Thresholding this region capture splits the token; grayscale does not."""
    pytest.importorskip("pytesseract")
    pytest.importorskip("PIL")
    fixture = Path(__file__).parent / "fixtures" / "ocr" / "textedit-region-calmark89.png"
    frame = Frame(
        width=1172,
        height=976,
        scale_factor=2.0,
        source="fixture:textedit-region",
        image_path=str(fixture),
    )

    result = TesseractRecognizer().find(frame=frame, query="CALMARK89")

    assert any(target.text == "CALMARK89" for target in result.targets)
