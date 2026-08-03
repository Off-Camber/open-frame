from __future__ import annotations

from pathlib import Path

import pytest

from openframe import Session
from openframe.recognize import Recognizer, RecognizerResult
from openframe.types import Frame, Target


class DemoRecognizer(Recognizer):
    name = "demo"

    def find(self, frame: Frame, query: str, options=None) -> RecognizerResult:  # type: ignore[override]
        _ = frame, options
        if query != "demo":
            return RecognizerResult(recognizer=self.name, targets=[])
        return RecognizerResult(
            recognizer=self.name,
            targets=[Target(x=10, y=20, width=30, height=40, confidence=0.9, source=self.name, text=query)],
        )


def test_session_find_supports_custom_recognizer() -> None:
    session = Session(dry_run=True)
    session.register_recognizer(DemoRecognizer(priority=5))
    frame = Frame(width=1, height=1, scale_factor=1.0, source="test", image_path=None)

    targets = session.find("demo", frame=frame)

    assert len(targets) == 1
    assert targets[0].text == "demo"


def test_session_click_returns_point() -> None:
    session = Session(dry_run=True)
    session.register_recognizer(DemoRecognizer(priority=5))
    frame = Frame(width=1, height=1, scale_factor=1.0, source="test", image_path=None)

    point = session.click("demo", frame=frame)

    assert point == (25, 40)


def test_session_click_fails_closed_on_ambiguous_targets() -> None:
    class MultiRecognizer(Recognizer):
        name = "multi"

        def find(self, frame: Frame, query: str, options=None) -> RecognizerResult:  # type: ignore[override]
            _ = frame, options
            return RecognizerResult(
                recognizer=self.name,
                targets=[
                    Target(x=10, y=20, width=30, height=40, confidence=0.9, source=self.name, text=query),
                    Target(x=50, y=60, width=30, height=40, confidence=0.8, source=self.name, text=query),
                ],
            )

    session = Session(dry_run=True)
    session.register_recognizer(MultiRecognizer(priority=5))
    frame = Frame(width=1, height=1, scale_factor=1.0, source="test", image_path=None)

    with pytest.raises(ValueError, match="ambiguous_target"):
        session.click("demo", frame=frame)

    point = session.click("demo", frame=frame, selector="top_most")
    assert point == (25, 40)


def test_session_run_executes_in_memory_steps(monkeypatch) -> None:
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))
    session = Session(run_id="r1", dry_run=True)

    results = session.run([{"id": "wait-1", "kind": "wait", "ms": 0}])

    assert len(results) == 1
    assert results[0].success is True
    assert session.results[0].step_id == "wait-1"
