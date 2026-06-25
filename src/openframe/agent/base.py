"""Agent integration layer contracts (Phase A).

Open Frame stays the deterministic execution engine. This module defines the
thin contract an external planner (an LLM-backed provider) implements to drive
the engine's MCP tool surface. The loop itself lives in ``runner.py``.

The agent layer is intentionally minimal: plan -> call a tool -> observe the
structured result -> decide again. Depth stays in the engine; this is a
reference loop, not a general agent framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class ToolCall:
    """A single deterministic tool invocation the agent wants to make.

    ``id`` is an opaque, provider-assigned handle (for example, an Anthropic
    ``tool_use`` id). It lets a provider faithfully reconstruct its own
    conversation from :class:`AgentStep` history. It is optional so non-LLM
    providers (and tests) can omit it.
    """

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass(slots=True)
class AgentAction:
    """A provider's decision for one turn: call a tool, or finish."""

    kind: Literal["tool_call", "finish"]
    tool_call: ToolCall | None = None
    final_message: str | None = None

    @classmethod
    def call(
        cls,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        id: str | None = None,
    ) -> "AgentAction":
        """Build a tool-call action."""
        return cls(kind="tool_call", tool_call=ToolCall(tool=tool, args=args or {}, id=id))

    @classmethod
    def finish(cls, message: str | None = None) -> "AgentAction":
        """Build a finish action that ends the run."""
        return cls(kind="finish", final_message=message)


@dataclass(slots=True)
class AgentStep:
    """One executed turn: the action taken and the tool response observed."""

    action: AgentAction
    observation: dict[str, Any] | None = None


@dataclass(slots=True)
class AgentResult:
    """Outcome of an agent run."""

    success: bool
    steps: list[AgentStep]
    final_message: str | None = None
    stop_reason: str = "finished"


class Provider(ABC):
    """Planner contract.

    Given the task, the available tool catalog, and the history so far, decide
    the next action. Concrete implementations wrap a specific LLM backend
    (added in later Phase A tasks).
    """

    @abstractmethod
    def next_action(
        self,
        *,
        task: str,
        tools: list[dict[str, Any]],
        history: list[AgentStep],
    ) -> AgentAction:
        """Return the next action to take for this task."""
        raise NotImplementedError
