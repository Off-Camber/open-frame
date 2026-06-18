from __future__ import annotations

from pathlib import Path

from openframe.flow import Flow, FlowStep
from openframe.runner import FlowRunner
from openframe.types import Frame
from openframe.types import Target


def test_runner_stops_on_first_failure(monkeypatch) -> None:
    flow = Flow(
        name="demo",
        steps=[
            FlowStep(id="one", kind="wait", params={"ms": 0}),
            FlowStep(id="two", kind="not-supported", params={}),
            FlowStep(id="three", kind="wait", params={"ms": 0}),
        ],
    )

    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert len(session.results) == 2
    assert session.results[0].success is True
    assert session.results[1].success is False


def test_runner_completes_simple_wait_flow(monkeypatch) -> None:
    flow = Flow(name="demo", steps=[FlowStep(id="one", kind="wait", params={"ms": 0})])
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert len(session.results) == 1
    assert session.results[0].success is True


def test_runner_supports_phase5_step_kinds_in_dry_run(monkeypatch) -> None:
    flow = Flow(
        name="demo",
        steps=[
            FlowStep(id="app", kind="app", params={"name": "Finder"}),
            FlowStep(id="type", kind="type", params={"text": "hello"}),
            FlowStep(id="key", kind="key", params={"key": "tab"}),
            FlowStep(id="fill", kind="fill", params={"query": "Name", "text": "Alice", "clear": True}),
            FlowStep(id="attach", kind="attach", params={"path": "/tmp/file.txt", "submit_key": "enter"}),
            FlowStep(id="navigate", kind="navigate", params={"url": "https://example.com"}),
            FlowStep(id="click", kind="click", params={"query": "Submit"}),
            FlowStep(id="find", kind="find", params={"query": "Submit"}),
            FlowStep(id="verify", kind="verify", params={"spec": 'text-appeared:"Submit"'}),
            FlowStep(id="wait", kind="wait", params={"ms": 0}),
            FlowStep(id="capture", kind="capture", params={}),
        ],
    )

    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "first") -> list[Target]:
            _ = frame, query, strategy
            return [Target(x=1, y=1, width=10, height=10, confidence=0.9, source="stub", text="Submit")]

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert len(session.results) == len(flow.steps)
    assert all(item.success for item in session.results)


def test_runner_substitutes_variables_and_run_tokens(monkeypatch) -> None:
    flow = Flow(
        name="templated",
        variables={"subject": "Hello"},
        steps=[
            FlowStep(
                id="type-subject",
                kind="type",
                params={"text": "Subject: {{subject}} / run {{run_id}} / {{artifact_dir}}"},
            )
        ],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r123/type-subject"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r123")

    assert session.results[0].success is True
    text_value = session.results[0].details["params"]["text"]
    assert "Hello" in text_value
    assert "r123" in text_value
    assert "runs/r123/type-subject" in text_value
