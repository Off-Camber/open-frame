"""OCR fixture coverage for calibration-like markers."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openframe.recognize.ocr.tesseract import TesseractRecognizer
from openframe.types import Frame

FIXTURE = Path(__file__).parent / "fixtures" / "ocr" / "calibration_marker.png"
MARKER = "OFMARKZXQ"


def test_calibration_marker_fixture_exists() -> None:
    assert FIXTURE.is_file()
    assert FIXTURE.stat().st_size > 0


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_tesseract_recognizer_finds_calibration_marker_on_fixture() -> None:
    pytest.importorskip("pytesseract")
    pytest.importorskip("PIL")

    recognizer = TesseractRecognizer()
    frame = Frame(
        width=1200,
        height=400,
        scale_factor=1.0,
        source="fixture:calibration",
        image_path=str(FIXTURE),
    )

    result = recognizer.find(frame=frame, query=MARKER)

    assert result.targets
    assert any(MARKER.casefold() in (target.text or "").casefold() for target in result.targets)
    assert result.metadata["match_count"] >= 1
