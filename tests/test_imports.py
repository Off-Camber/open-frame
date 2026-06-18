from openframe import Action, Actuator, Frame, Locator, Recognizer, Session, StepResult, Target
from openframe.recognize import RecognizerResult


def test_core_imports() -> None:
    frame = Frame(width=100, height=60, scale_factor=2.0, source="screen:0")
    target = Target(
        x=10,
        y=10,
        width=20,
        height=12,
        confidence=0.9,
        source="ocr",
        text="Send",
    )
    action = Action(kind="click", target=target)
    result = StepResult(step_id="send", success=True, duration_ms=42)
    session = Session(run_id="r1")
    locator = Locator()
    actuator = Actuator(dry_run=True)
    session.record(result)

    assert frame.width == 100
    assert action.target is not None
    assert isinstance(locator, Locator)
    assert isinstance(actuator, Actuator)
    assert issubclass(Recognizer, object)
    assert RecognizerResult(recognizer="stub").recognizer == "stub"
    assert session.results[0].step_id == "send"
