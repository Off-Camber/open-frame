"""Cooperative cancellation for a timed-out MCP tool call.

The MCP adapter binds one :class:`threading.Event` for the worker thread. On
timeout it sets the event. Actuation and the flow runner check it and refuse
to start another click, keystroke, scroll, drag, or flow step.
"""

from __future__ import annotations

import threading
from contextvars import ContextVar, Token


class ToolCancelled(RuntimeError):
    """The current tool call was cancelled after its wall-clock timeout."""


_cancellation: ContextVar[threading.Event | None] = ContextVar(
    "openframe_tool_cancellation", default=None
)


def bind_tool_cancellation(event: threading.Event) -> Token[threading.Event | None]:
    """Bind ``event`` for the current thread. Reset with the returned token."""
    return _cancellation.set(event)


def reset_tool_cancellation(token: Token[threading.Event | None]) -> None:
    """Restore the cancellation state captured by :func:`bind_tool_cancellation`."""
    _cancellation.reset(token)


def tool_cancelled() -> bool:
    """Return True when the current tool call has been cancelled."""
    event = _cancellation.get()
    return event is not None and event.is_set()


def raise_if_tool_cancelled() -> None:
    """Raise when the current tool call has been cancelled."""
    if tool_cancelled():
        raise ToolCancelled("Tool call was cancelled after timeout; refusing to actuate.")
