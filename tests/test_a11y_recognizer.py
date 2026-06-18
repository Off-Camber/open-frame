from __future__ import annotations

import pytest

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
