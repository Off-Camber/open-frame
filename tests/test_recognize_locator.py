from __future__ import annotations

from openframe.recognize import Locator, Recognizer, RecognizerResult
from openframe.types import Frame, Target


class StubRecognizer(Recognizer):
    name = "stub"

    def __init__(self, *, priority: int, target_text: str | None) -> None:
        super().__init__(priority=priority)
        self._target_text = target_text
        self._target_bounds = (1, 2, 50, 20)
        self._confidence = 0.9

    def find(self, frame: Frame, query: str, options: dict | None = None) -> RecognizerResult:
        if self._target_text is None:
            return RecognizerResult(recognizer=self.name, targets=[])
        x, y, width, height = self._target_bounds
        return RecognizerResult(
            recognizer=self.name,
            targets=[
                Target(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    confidence=self._confidence,
                    source=self.name,
                    text=self._target_text,
                )
            ],
            metadata={"query": query, "source": frame.source},
        )


def test_locator_returns_first_strategy_match() -> None:
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")
    low_priority = StubRecognizer(priority=20, target_text="Second")
    high_priority = StubRecognizer(priority=10, target_text="First")
    locator = Locator([low_priority, high_priority])

    targets = locator.find(frame, "Submit", strategy="first")

    assert len(targets) == 1
    assert targets[0].text == "First"


def test_locator_returns_all_matches() -> None:
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")
    recognizer_a = StubRecognizer(priority=10, target_text="One")
    recognizer_a._target_bounds = (1, 2, 30, 20)
    recognizer_b = StubRecognizer(priority=20, target_text="Two")
    recognizer_b._target_bounds = (60, 2, 30, 20)
    locator = Locator([recognizer_b, recognizer_a])

    targets = locator.find(frame, "Submit", strategy="all")

    assert [target.text for target in targets] == ["One", "Two"]


def test_locator_dedupes_overlapping_targets_prefers_higher_confidence() -> None:
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")
    first = StubRecognizer(priority=10, target_text="Submit")
    first._target_bounds = (10, 10, 80, 30)
    first._confidence = 0.6

    second = StubRecognizer(priority=20, target_text="Submit")
    second._target_bounds = (12, 11, 78, 29)
    second._confidence = 0.95

    locator = Locator([first, second])
    targets = locator.find(frame, "Submit", strategy="all")

    assert len(targets) == 1
    assert targets[0].confidence == 0.95


def test_locator_keeps_distinct_targets_when_not_overlapping() -> None:
    frame = Frame(width=100, height=100, scale_factor=2.0, source="screen:1")
    left = StubRecognizer(priority=10, target_text="Left")
    left._target_bounds = (10, 10, 20, 20)

    right = StubRecognizer(priority=20, target_text="Right")
    right._target_bounds = (60, 10, 20, 20)

    locator = Locator([left, right])
    targets = locator.find(frame, "button", strategy="all")

    assert len(targets) == 2
    assert {target.text for target in targets} == {"Left", "Right"}
