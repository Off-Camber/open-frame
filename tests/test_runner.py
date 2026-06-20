from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from openframe.flow import Flow, FlowStep
from openframe.runner import FlowRunner
from openframe.runner import _focus_app
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


def test_runner_write_file_creates_artifact(monkeypatch, tmp_path) -> None:
    target = tmp_path / "nested" / "doc.txt"
    flow = Flow(
        name="write",
        steps=[
            FlowStep(
                id="write-doc",
                kind="write_file",
                params={"path": str(target), "text": "hello world"},
            )
        ],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=False).run(flow, run_id="r1")

    assert session.results[0].success is True
    assert target.read_text(encoding="utf-8") == "hello world"
    assert session.results[0].details["bytes_written"] == len("hello world")


def test_runner_write_file_skips_in_dry_run(monkeypatch, tmp_path) -> None:
    target = tmp_path / "doc.txt"
    flow = Flow(
        name="write-dry",
        steps=[FlowStep(id="write-doc", kind="write_file", params={"path": str(target), "text": "x"})],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True
    assert not target.exists()


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


def test_runner_resolves_nested_templates(monkeypatch) -> None:
    flow = Flow(
        name="templated-nested",
        variables={"token": "OF-CAL-{{run_id}}"},
        steps=[
            FlowStep(
                id="type-token",
                kind="type",
                params={"text": "{{token}}"},
            )
        ],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r999/type-token"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r999")

    assert session.results[0].success is True
    assert session.results[0].details["params"]["text"] == "OF-CAL-r999"


def test_runner_retries_click_until_target_found(monkeypatch) -> None:
    flow = Flow(
        name="retry-click",
        steps=[FlowStep(id="click-retry", kind="click", params={"query": "Submit", "timeout_ms": 50, "poll_ms": 1})],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            self.calls = 0

        def find(self, frame: Frame, query: str, strategy: str = "first") -> list[Target]:
            _ = frame, query, strategy
            self.calls += 1
            if self.calls < 2:
                return []
            return [Target(x=1, y=1, width=10, height=10, confidence=0.9, source="stub", text="Submit")]

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True


def test_runner_click_expect_one_fails_on_multiple_matches(monkeypatch) -> None:
    flow = Flow(
        name="ambiguous-click",
        steps=[FlowStep(id="click-one", kind="click", params={"query": "Create", "expect_one": True})],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
            _ = frame, query, strategy
            return [
                Target(x=1, y=1, width=10, height=10, confidence=0.9, source="stub", text="Create"),
                Target(x=20, y=20, width=10, height=10, confidence=0.9, source="stub", text="Create"),
            ]

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is False
    assert "ambiguous_target" in (session.results[0].error or "")


def test_runner_click_selector_top_most_picks_upper_target(monkeypatch) -> None:
    flow = Flow(
        name="selector-click",
        steps=[FlowStep(id="click-selector", kind="click", params={"query": "Create", "selector": "top_most"})],
    )
    frame = Frame(width=1, height=1, scale_factor=2.0, source="screen", image_path=None)
    clicked: dict[str, int] = {}

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
            _ = frame, query, strategy
            return [
                Target(x=40, y=200, width=10, height=10, confidence=0.9, source="stub", text="Create"),
                Target(x=30, y=100, width=10, height=10, confidence=0.8, source="stub", text="Create"),
            ]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, *, anchor: str, kind: str, scale_factor: float = 1.0):
            _ = anchor, kind
            clicked["x"] = target.x
            clicked["y"] = target.y
            clicked["scale_factor"] = scale_factor
            return (target.x, target.y)

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True
    assert clicked == {"x": 30, "y": 100, "scale_factor": 2.0}


def test_runner_verify_polls_until_spec_passes(monkeypatch) -> None:
    flow = Flow(
        name="retry-verify",
        steps=[
            FlowStep(
                id="verify-compose",
                kind="verify",
                params={"spec": 'text-appeared:"To"', "timeout_ms": 50, "poll_ms": 1},
            )
        ],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            self.calls = 0

        def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
            _ = frame, query, strategy
            self.calls += 1
            if self.calls < 3:
                return []
            return [Target(x=1, y=1, width=10, height=10, confidence=0.9, source="stub", text="To")]

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True


def test_focus_app_raises_when_frontmost_differs(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_run(command, check, capture_output, text):
        _ = command, check, capture_output, text
        calls["count"] += 1
        if calls["count"] == 1:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="Terminal\n", stderr="")

    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("openframe.runner.sleep", lambda *_args, **_kwargs: None)

    try:
        _focus_app("TextEdit")
        assert False, "Expected _focus_app to raise when frontmost app mismatches."
    except RuntimeError as error:
        assert "frontmost app is 'Terminal'" in str(error)


def test_runner_click_point_uses_logical_coordinates(monkeypatch) -> None:
    flow = Flow(
        name="click-point",
        steps=[FlowStep(id="focus-body", kind="click_point", params={"x_ratio": 0.5, "y_ratio": 0.5})],
    )
    frame = Frame(width=2000, height=1000, scale_factor=2.0, source="screen", image_path=None)
    clicked: dict[str, int] = {}

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_point(self, x: int, y: int, *, kind: str = "click") -> None:
            _ = kind
            clicked["x"] = x
            clicked["y"] = y

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.runner.Locator", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True
    assert clicked == {"x": 500, "y": 250}


def test_runner_fill_selector_right_most_clicks_right_target(monkeypatch) -> None:
    flow = Flow(
        name="fill-right",
        steps=[
            FlowStep(
                id="fill-subject",
                kind="fill",
                params={"query": "Subject", "selector": "right_most", "text": "hello"},
            )
        ],
    )
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=None)
    clicked: dict[str, int] = {}

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
            _ = frame, query, strategy
            return [
                Target(x=100, y=50, width=10, height=10, confidence=0.9, source="stub", text="Subject"),
                Target(x=900, y=120, width=10, height=10, confidence=0.8, source="stub", text="Subject"),
            ]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, *, anchor: str, kind: str, scale_factor: float = 1.0):
            _ = anchor, kind, scale_factor
            clicked["x"] = target.x
            return (target.x, target.y)

        def key_combo(self, *keys: str) -> None:
            _ = keys

        def type_text(self, text: str, *, interval: float = 0.0) -> None:
            _ = text, interval

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step"))

    session = FlowRunner(dry_run=True).run(flow, run_id="r1")

    assert session.results[0].success is True
    assert clicked["x"] == 900
