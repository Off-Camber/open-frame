from __future__ import annotations

import pytest

from openframe.recognize.a11y import macos as a11y_macos
from openframe.recognize.a11y.macos import MacOSA11yRecognizer
from openframe.types import Frame


def test_a11y_recognizer_filters_matching_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")

    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: True)
    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "Submit", "role": "AXButton", "x": 10, "y": 20, "width": 80, "height": 30},
            {"title": "Cancel", "role": "AXButton", "x": 100, "y": 20, "width": 80, "height": 30},
        ],
    )

    result = recognizer.find(frame=frame, query="submit")

    assert len(result.targets) == 1
    assert result.targets[0].text == "Submit"
    assert result.targets[0].source == "a11y:macos"


def test_a11y_list_script_parses_array_and_object_bounds() -> None:
    script = a11y_macos._LIST_FRONTMOST_ELEMENTS_SCRIPT
    assert "Array.isArray(pos)" in script
    assert "Array.isArray(size)" in script
    assert "pos.x !== undefined" in script
    assert "size.width !== undefined" in script


def test_a11y_recognizer_accepts_array_shaped_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates JXA output after array-shaped position/size parsing."""
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")

    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: True)
    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "Submit", "role": "AXButton", "x": 12, "y": 34, "width": 90, "height": 28},
        ],
    )

    result = recognizer.find(frame=frame, query="Submit")

    assert len(result.targets) == 1
    assert result.targets[0].x == 12
    assert result.targets[0].y == 34
    assert result.targets[0].width == 90
    assert result.targets[0].height == 28
    assert result.targets[0].coordinate_space == "logical"
    assert result.metadata["match_count"] == 1
    assert result.metadata["elements_seen"] == 1


def test_a11y_recognizer_skips_zero_bounds_elements(monkeypatch: pytest.MonkeyPatch) -> None:
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")

    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: True)
    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "Submit", "role": "AXButton", "x": 0, "y": 0, "width": 0, "height": 0},
            {"title": "Submit", "role": "AXButton", "x": 10, "y": 20, "width": 80, "height": 30},
        ],
    )

    result = recognizer.find(frame=frame, query="Submit")

    assert len(result.targets) == 1
    assert result.metadata["match_count"] == 1
    assert result.metadata["elements_seen"] == 2


def test_a11y_recognizer_gracefully_reports_query_error(monkeypatch: pytest.MonkeyPatch) -> None:
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")

    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: True)
    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: (_ for _ in ()).throw(RuntimeError("permission denied")),
    )

    result = recognizer.find(frame=frame, query="submit")

    assert result.targets == []
    assert "error" in result.metadata


def test_a11y_recognizer_returns_empty_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")
    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: False)

    result = recognizer.find(frame=frame, query="submit")

    assert result.targets == []
    assert result.metadata["reason"] == "non-macos"


def test_a11y_recognizer_uses_token_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    recognizer = MacOSA11yRecognizer()
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")

    monkeypatch.setattr("openframe.recognize.a11y.macos._is_macos", lambda: True)
    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "actuation", "role": "AXStaticText", "x": 10, "y": 20, "width": 80, "height": 30},
            {"title": "AC", "role": "AXButton", "x": 100, "y": 20, "width": 40, "height": 30},
            {"title": "Invoice No 123", "role": "AXStaticText", "x": 10, "y": 60, "width": 120, "height": 20},
        ],
    )

    ac_matches = recognizer.find(frame=frame, query="AC")
    assert len(ac_matches.targets) == 1
    assert ac_matches.targets[0].text == "AC"

    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "actuation", "role": "AXStaticText", "x": 10, "y": 20, "width": 80, "height": 30},
        ],
    )
    assert recognizer.find(frame=frame, query="AC").targets == []

    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements",
        lambda: [
            {"title": "Invoice No 123", "role": "AXStaticText", "x": 10, "y": 60, "width": 120, "height": 20},
        ],
    )
    phrase = recognizer.find(frame=frame, query="Invoice No")
    assert len(phrase.targets) == 1
    assert phrase.targets[0].text == "Invoice No 123"
