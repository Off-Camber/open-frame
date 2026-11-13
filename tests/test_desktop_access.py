"""Display lock and sleep readings."""

from __future__ import annotations

import subprocess
import sys

import pytest

from openframe.desktop_access import (
    DisplayPower,
    _main_display_asleep,
    _notify_state,
    _process_command,
    _session_screen_locked,
    permission_denied_message,
    read_display_power,
    screen_unavailable_message,
)


class _Bound:
    """A callable that accepts the restype and argtypes assignments ctypes uses."""

    def __init__(self, fn) -> None:
        self._fn = fn

    def __call__(self, *args):
        return self._fn(*args)


class _NotifyLib:
    def __init__(self, *, registered: int = 0, read: int = 0, state: int = 0) -> None:
        self.notify_register_check = _Bound(self._register)
        self.notify_get_state = _Bound(self._read)
        self.notify_cancel = _Bound(lambda _token: 0)
        self.registered = registered
        self.read = read
        self.state = state

    def _register(self, _name: bytes, token) -> int:
        token._obj.value = 1
        return self.registered

    def _read(self, _token, state) -> int:
        state._obj.value = self.state
        return self.read


class _SessionLibs:
    def __init__(self, *, session: int = 1, value: int = 0, boolean: bool = True) -> None:
        self.CGSessionCopyCurrentDictionary = _Bound(lambda: session)
        self.CFStringCreateWithCString = _Bound(lambda *_args: 11)
        self.CFDictionaryGetValue = _Bound(lambda *_args: value)
        self.CFGetTypeID = _Bound(lambda _value: 3 if boolean else 4)
        self.CFBooleanGetTypeID = _Bound(lambda: 3)
        self.CFBooleanGetValue = _Bound(lambda _value: True)


def test_lock_notification_marks_the_screen_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("openframe.desktop_access.sys.platform", "darwin")
    monkeypatch.setattr("openframe.desktop_access._notify_state", lambda _name: 1)
    monkeypatch.setattr("openframe.desktop_access._session_screen_locked", lambda: False)
    monkeypatch.setattr("openframe.desktop_access._main_display_asleep", lambda: False)

    state = read_display_power()

    assert state.known is True
    assert state.locked is True
    assert state.asleep is False
    message = screen_unavailable_message(state)
    assert message.startswith("The screen is locked.")
    assert "not a missing Screen Recording or Accessibility grant" in message


def test_display_sleep_is_separate_from_a_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("openframe.desktop_access.sys.platform", "darwin")
    monkeypatch.setattr("openframe.desktop_access._notify_state", lambda _name: 0)
    monkeypatch.setattr("openframe.desktop_access._session_screen_locked", lambda: False)
    monkeypatch.setattr("openframe.desktop_access._main_display_asleep", lambda: True)

    state = read_display_power()

    assert state.unavailable is True
    assert state.asleep is True
    assert screen_unavailable_message(state).startswith("The display is asleep.")


def test_failed_os_queries_do_not_pretend_the_screen_is_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("openframe.desktop_access.sys.platform", "darwin")
    monkeypatch.setattr("openframe.desktop_access._notify_state", lambda _name: None)
    monkeypatch.setattr("openframe.desktop_access._session_screen_locked", lambda: None)
    monkeypatch.setattr("openframe.desktop_access._main_display_asleep", lambda: None)

    state = read_display_power()

    assert state.known is False
    assert state.unavailable is False


def test_locked_and_asleep_share_one_message() -> None:
    message = screen_unavailable_message(DisplayPower(locked=True, asleep=True, known=True))
    assert message.startswith("The screen is locked and the display is asleep.")


def test_notify_state_reads_the_registered_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openframe.desktop_access._libsystem",
        lambda: _NotifyLib(state=0),
    )
    assert _notify_state("com.apple.screenIsLocked") == 0


def test_notify_state_returns_none_when_registration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openframe.desktop_access._libsystem",
        lambda: _NotifyLib(registered=1),
    )
    assert _notify_state("com.apple.screenIsLocked") is None


def test_non_darwin_reports_the_display_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("openframe.desktop_access.sys.platform", "linux")
    assert read_display_power() == DisplayPower(locked=False, asleep=False, known=True)


def test_notify_state_returns_none_when_the_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openframe.desktop_access._libsystem",
        lambda: _NotifyLib(read=1),
    )
    assert _notify_state("com.apple.screenIsLocked") is None


def test_notify_state_returns_none_when_the_library_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing() -> object:
        raise OSError("no library")

    monkeypatch.setattr("openframe.desktop_access._libsystem", missing)
    assert _notify_state("com.apple.screenIsLocked") is None


def test_absent_session_key_means_unlocked(monkeypatch: pytest.MonkeyPatch) -> None:
    libs = _SessionLibs(value=0)

    monkeypatch.setattr("openframe.desktop_access._core_graphics", lambda: libs)
    monkeypatch.setattr("openframe.desktop_access._core_foundation", lambda: libs)
    assert _session_screen_locked() is False


def test_session_boolean_means_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    libs = _SessionLibs(value=5, boolean=True)

    monkeypatch.setattr("openframe.desktop_access._core_graphics", lambda: libs)
    monkeypatch.setattr("openframe.desktop_access._core_foundation", lambda: libs)
    assert _session_screen_locked() is True


def test_non_boolean_session_value_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    libs = _SessionLibs(value=5, boolean=False)

    monkeypatch.setattr("openframe.desktop_access._core_graphics", lambda: libs)
    monkeypatch.setattr("openframe.desktop_access._core_foundation", lambda: libs)
    assert _session_screen_locked() is None


def test_session_query_returns_none_without_a_dictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    libs = _SessionLibs(session=0)

    monkeypatch.setattr("openframe.desktop_access._core_graphics", lambda: libs)
    monkeypatch.setattr("openframe.desktop_access._core_foundation", lambda: libs)
    assert _session_screen_locked() is None


def test_display_sleep_query(monkeypatch: pytest.MonkeyPatch) -> None:
    class Graphics:
        CGMainDisplayID = _Bound(lambda: 1)
        CGDisplayIsAsleep = _Bound(lambda _display: True)

    monkeypatch.setattr("openframe.desktop_access._core_graphics", lambda: Graphics())
    assert _main_display_asleep() is True


def test_display_sleep_query_returns_none_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing() -> object:
        raise OSError("no core graphics")

    monkeypatch.setattr("openframe.desktop_access._core_graphics", missing)
    assert _main_display_asleep() is None


def test_process_command_returns_blank_when_ps_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ps", timeout=2)

    monkeypatch.setattr("openframe.desktop_access.subprocess.run", boom)
    assert _process_command(1) == ""
    assert _process_command(0) == ""


def test_permission_message_names_this_process() -> None:
    from pathlib import Path

    message = permission_denied_message("Screen Recording")
    assert Path(sys.executable).name in message
    assert "Screen Recording is not available to" in message


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS display query")
def test_live_display_power_query_returns_a_reading() -> None:
    """The OS calls succeed. The asserted values are only that the query returns booleans.

    On 2026-11-12, with this Mac awake and unlocked, the same calls returned
    com.apple.screenIsLocked state 0, CGSSessionScreenIsLocked absent, and
    CGDisplayIsAsleep false.
    """
    state = read_display_power()
    assert isinstance(state.locked, bool)
    assert isinstance(state.asleep, bool)
    assert isinstance(state.known, bool)
