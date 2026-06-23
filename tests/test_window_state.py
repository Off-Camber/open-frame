"""Phase 11: window-level state awareness — guards, verifier, and scoping."""

from __future__ import annotations

from pathlib import Path

from openframe.flow import Flow, FlowStep
from openframe.runner import FlowRunner
from openframe.types import Frame, Target
from openframe.verify import WindowStateVerifier
from openframe.window import WindowState, evaluate_window_guard


def _frame(scale: float = 1.0) -> Frame:
    return Frame(width=1, height=1, scale_factor=scale, source="screen", image_path=None)


def test_evaluate_window_guard_matches_all_fields() -> None:
    state = WindowState(app="Outlook", title="Untitled - Message", role="AXWindow", x=0, y=0, width=10, height=10)

    passed, _ = evaluate_window_guard(
        spec={"app": "Outlook", "title_contains": "Message", "role": "AXWindow"},
        state=state,
    )
    assert passed is True


def test_evaluate_window_guard_fails_when_app_mismatch() -> None:
    state = WindowState(app="Outlook", title="Inbox", role="AXWindow", x=0, y=0, width=10, height=10)

    passed, message = evaluate_window_guard(spec={"app": "Chrome"}, state=state)

    assert passed is False
    assert "Outlook" in message and "Chrome" in message


def test_window_state_verifier_uses_injected_provider() -> None:
    state = WindowState(app="Outlook", title="Compose - Message", role="AXWindow", x=0, y=0, width=10, height=10)
    verifier = WindowStateVerifier(
        kind="title_contains", expected="Compose", state_provider=lambda: state
    )

    result = verifier.verify(before=_frame(), after=_frame())

    assert result.success is True
    assert "Compose" in result.message


def test_window_state_verifier_reports_failure_when_state_missing() -> None:
    verifier = WindowStateVerifier(
        kind="title_contains", expected="Compose", state_provider=lambda: None
    )

    result = verifier.verify(before=_frame(), after=_frame())

    assert result.success is False


def test_runner_window_guard_blocks_step_when_app_wrong(monkeypatch) -> None:
    flow = Flow(
        name="guarded",
        steps=[
            FlowStep(
                id="type-token",
                kind="type",
                params={"text": "hi", "window": {"app": "Microsoft Outlook"}},
            )
        ],
    )
    frame = _frame()
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r/step"))
    monkeypatch.setattr(
        "openframe.runner.frontmost_window",
        lambda: WindowState(app="Cursor", title="open-frame", role="AXWindow", x=0, y=0, width=100, height=100),
    )

    session = FlowRunner(dry_run=True).run(flow, run_id="r-guard")

    assert session.results[0].success is False
    assert "window guard failed" in (session.results[0].error or "")


def test_runner_window_scope_filters_targets_outside_window(monkeypatch) -> None:
    flow = Flow(
        name="scoped-click",
        steps=[FlowStep(id="click-in-window", kind="click", params={"query": "Send", "scope": "window"})],
    )
    frame = _frame()

    inside = Target(x=120, y=120, width=20, height=20, confidence=0.9, source="stub", text="Send")
    outside = Target(x=10, y=10, width=20, height=20, confidence=0.9, source="stub", text="Send")
    clicked: dict[str, int] = {}

    class FakeLocator:
        def __init__(self, _recognizers: list[object]) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
            _ = frame, query, strategy
            return [outside, inside]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, *, anchor: str, kind: str, scale_factor: float = 1.0):
            _ = anchor, kind, scale_factor
            clicked["x"] = target.x
            clicked["y"] = target.y
            return (target.x, target.y)

    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.Locator", FakeLocator)
    monkeypatch.setattr("openframe.runner.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.runner.MacOSA11yRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.TesseractRecognizer", lambda: object())
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r/step"))
    monkeypatch.setattr(
        "openframe.runner.frontmost_window",
        lambda: WindowState(app="Outlook", title="Inbox", role="AXWindow", x=100, y=100, width=400, height=400),
    )

    session = FlowRunner(dry_run=True).run(flow, run_id="r-scope")

    assert session.results[0].success is True
    assert clicked == {"x": 120, "y": 120}


def test_runner_window_title_contains_verify_spec(monkeypatch) -> None:
    flow = Flow(
        name="window-verify",
        steps=[
            FlowStep(
                id="verify-compose",
                kind="verify",
                params={"spec": "window-title-contains:Compose", "timeout_ms": 50, "poll_ms": 1},
            )
        ],
    )
    frame = _frame()
    monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
    monkeypatch.setattr("openframe.runner.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r/step"))
    monkeypatch.setattr(
        "openframe.runner.frontmost_window",
        lambda: WindowState(app="Outlook", title="Compose - New Message", role="AXWindow", x=0, y=0, width=10, height=10),
    )

    session = FlowRunner(dry_run=True).run(flow, run_id="r-verify")

    assert session.results[0].success is True
