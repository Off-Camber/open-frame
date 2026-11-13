"""Whether the Mac display can be captured right now.

A locked session or a sleeping display is its own condition. It must not be
reported as a missing Screen Recording or Accessibility grant.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from ctypes import c_bool, c_char_p, c_int, c_uint32, c_uint64, c_void_p
from dataclasses import dataclass
from pathlib import Path

_LOCK_NOTIFICATION = "com.apple.screenIsLocked"
_SESSION_LOCK_KEY = "CGSSessionScreenIsLocked"
_UTF8 = 0x08000100


@dataclass(frozen=True, slots=True)
class DisplayPower:
    """Lock and sleep readings. ``known`` is false when the OS query failed."""

    locked: bool
    asleep: bool
    known: bool

    @property
    def unavailable(self) -> bool:
        return self.known and (self.locked or self.asleep)


def read_display_power() -> DisplayPower:
    """Read the current session lock and main-display sleep state."""
    if sys.platform != "darwin":
        return DisplayPower(locked=False, asleep=False, known=True)
    locked_notify = _notify_state(_LOCK_NOTIFICATION)
    session_locked = _session_screen_locked()
    asleep = _main_display_asleep()
    known = any(item is not None for item in (locked_notify, session_locked, asleep))
    return DisplayPower(
        locked=bool(locked_notify) or bool(session_locked),
        asleep=bool(asleep),
        known=known,
    )


def screen_unavailable_message(state: DisplayPower) -> str:
    """Doctor and MCP text for a locked or sleeping display."""
    if state.locked and state.asleep:
        why = "The screen is locked and the display is asleep."
    elif state.locked:
        why = "The screen is locked."
    else:
        why = "The display is asleep."
    return (
        f"{why} Wake the display and unlock it, then try again. "
        "This is not a missing Screen Recording or Accessibility grant."
    )


def permission_denied_message(setting: str) -> str:
    """Name the process that needs the privacy grant."""
    host = host_process_label()
    return (
        f"{setting} is not available to {host}. "
        f"System Settings → Privacy & Security → {setting} — enable {host}, then restart it."
    )


def host_process_label() -> str:
    """The process a privacy prompt should name."""
    executable = str(Path(sys.executable).resolve())
    name = Path(executable).name
    label = f"{name} ({executable})"
    parent = _process_command(os.getppid())
    if parent and parent not in {name, executable}:
        return f"{label}, started by {parent}"
    return label


def _notify_state(name: str) -> int | None:
    """Return a Darwin notify state, or None when the call fails."""
    try:
        lib = _libsystem()
        token = c_int()
        registered = lib.notify_register_check(name.encode(), ctypes.byref(token))
        if registered != 0:
            return None
        state = c_uint64()
        try:
            read = lib.notify_get_state(token, ctypes.byref(state))
        finally:
            lib.notify_cancel(token)
        if read != 0:
            return None
        return int(state.value)
    except (OSError, AttributeError):
        return None


def _session_screen_locked() -> bool | None:
    """True when the window-server session says the screen is locked.

    The key is absent while the session is unlocked, which is not an error.
    """
    try:
        core_graphics = _core_graphics()
        core_foundation = _core_foundation()
        core_graphics.CGSessionCopyCurrentDictionary.restype = c_void_p
        session = core_graphics.CGSessionCopyCurrentDictionary()
        if not session:
            return None
        core_foundation.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
        core_foundation.CFStringCreateWithCString.restype = c_void_p
        core_foundation.CFDictionaryGetValue.argtypes = [c_void_p, c_void_p]
        core_foundation.CFDictionaryGetValue.restype = c_void_p
        core_foundation.CFGetTypeID.argtypes = [c_void_p]
        core_foundation.CFGetTypeID.restype = ctypes.c_ulong
        core_foundation.CFBooleanGetTypeID.restype = ctypes.c_ulong
        core_foundation.CFBooleanGetValue.argtypes = [c_void_p]
        core_foundation.CFBooleanGetValue.restype = c_bool
        key = core_foundation.CFStringCreateWithCString(None, _SESSION_LOCK_KEY.encode(), _UTF8)
        value = core_foundation.CFDictionaryGetValue(session, key)
        if not value:
            return False
        if core_foundation.CFGetTypeID(value) != core_foundation.CFBooleanGetTypeID():
            return None
        return bool(core_foundation.CFBooleanGetValue(value))
    except (OSError, AttributeError):
        return None


def _main_display_asleep() -> bool | None:
    try:
        core_graphics = _core_graphics()
        core_graphics.CGMainDisplayID.restype = c_uint32
        core_graphics.CGDisplayIsAsleep.argtypes = [c_uint32]
        core_graphics.CGDisplayIsAsleep.restype = c_bool
        return bool(core_graphics.CGDisplayIsAsleep(core_graphics.CGMainDisplayID()))
    except (OSError, AttributeError):
        return None


def _libsystem() -> ctypes.CDLL:
    return ctypes.CDLL("/usr/lib/libSystem.B.dylib")


def _core_graphics() -> ctypes.CDLL:
    return ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")


def _core_foundation() -> ctypes.CDLL:
    return ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")


def _process_command(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        completed = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (completed.stdout or "").strip()
