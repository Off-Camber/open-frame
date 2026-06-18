from __future__ import annotations

import sys

import pytest

from openframe.act import ActError, Actuator
from openframe.types import Frame
from openframe.types import Target


def _target() -> Target:
    return Target(x=10, y=20, width=100, height=40, confidence=0.9, source="test")


def test_point_for_target_center_and_corners() -> None:
    actuator = Actuator(dry_run=True)
    target = _target()

    assert actuator.point_for_target(target, anchor="center") == (60, 40)
    assert actuator.point_for_target(target, anchor="top-left") == (10, 20)
    assert actuator.point_for_target(target, anchor="bottom-right") == (110, 60)


def test_click_target_dry_run_returns_point_without_backend() -> None:
    actuator = Actuator(dry_run=True)
    point = actuator.click_target(_target(), anchor="center", kind="double")
    assert point == (60, 40)


def test_click_point_uses_pyautogui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple, dict]] = []

    class StubPyAuto:
        def click(self, *args, **kwargs):
            calls.append(("click", args, kwargs))

        def doubleClick(self, *args, **kwargs):
            calls.append(("doubleClick", args, kwargs))

    monkeypatch.setitem(sys.modules, "pyautogui", StubPyAuto())
    actuator = Actuator(dry_run=False)
    actuator.click_point(10, 20, kind="double")

    assert calls[0][0] == "doubleClick"
    assert calls[0][2]["x"] == 10
    assert calls[0][2]["y"] == 20


def test_missing_pyautogui_raises_act_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openframe.act.core._load_pyautogui",
        lambda: (_ for _ in ()).throw(ActError("Action dependencies missing.")),
    )
    actuator = Actuator(dry_run=False)

    with pytest.raises(ActError):
        actuator.click_point(1, 2)


def test_wait_for_frame_change_detects_change() -> None:
    actuator = Actuator(dry_run=True)
    frames = [
        Frame(width=1, height=1, scale_factor=1.0, source="screen:1", image_path="a.png"),
        Frame(width=1, height=1, scale_factor=1.0, source="screen:1", image_path="a.png"),
        Frame(width=1, height=1, scale_factor=1.0, source="screen:1", image_path="b.png"),
    ]

    def capture() -> Frame:
        return frames.pop(0) if frames else Frame(width=1, height=1, scale_factor=1.0, source="screen:1")

    changed = actuator.wait_for_frame_change(capture_frame=capture, timeout_ms=50, poll_ms=1)

    assert changed is True
