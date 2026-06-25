"""Minimal agent loop driving Open Frame's deterministic tools (Phase A).

The runner is deliberately thin: ask the provider for the next action, execute
it against the frozen MCP tool surface, record the structured response, and
repeat until the provider finishes or the step budget is exhausted.

The tool surface and catalog are injectable so the loop can be tested without
touching the real engine or any live screen.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from openframe.agent.base import AgentResult, AgentStep, Provider
from openframe.integrations.mcp.adapter import call_mcp_tool, list_mcp_tools

ToolCaller = Callable[[str, dict[str, Any]], dict[str, Any]]
ToolCatalog = Callable[[], list[dict[str, Any]]]


class AgentRunner:
    """Drive a :class:`Provider` through Open Frame's MCP tool surface."""

    def __init__(
        self,
        *,
        provider: Provider,
        max_steps: int = 20,
        max_consecutive_tool_errors: int = 3,
        max_repeated_tool_errors: int = 2,
        tool_caller: ToolCaller | None = None,
        tool_catalog: ToolCatalog | None = None,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be > 0.")
        if max_consecutive_tool_errors <= 0:
            raise ValueError("max_consecutive_tool_errors must be > 0.")
        if max_repeated_tool_errors <= 0:
            raise ValueError("max_repeated_tool_errors must be > 0.")
        self.provider = provider
        self.max_steps = max_steps
        self.max_consecutive_tool_errors = max_consecutive_tool_errors
        self.max_repeated_tool_errors = max_repeated_tool_errors
        self._call_tool: ToolCaller = tool_caller or call_mcp_tool
        self._list_tools: ToolCatalog = tool_catalog or list_mcp_tools

    def run(self, task: str) -> AgentResult:
        """Run the agent loop for a natural-language task."""
        if not task or not task.strip():
            raise ValueError("task must be a non-empty string.")

        tools = self._list_tools()
        history: list[AgentStep] = []
        consecutive_errors = 0
        last_error_signature: str | None = None
        repeated_error_count = 0

        for _ in range(self.max_steps):
            action = self.provider.next_action(task=task, tools=tools, history=history)

            if action.kind == "finish":
                return AgentResult(
                    success=True,
                    steps=history,
                    final_message=action.final_message,
                    stop_reason="finished",
                )

            if action.tool_call is None:
                raise ValueError("A tool_call action must include a ToolCall.")

            envelope = self._call_tool(action.tool_call.tool, action.tool_call.args)
            step = AgentStep(action=action, observation=envelope)
            history.append(step)

            if envelope.get("ok") is True:
                consecutive_errors = 0
                last_error_signature = None
                repeated_error_count = 0
                continue

            consecutive_errors += 1
            error_signature = _error_signature(step=step)
            if error_signature == last_error_signature:
                repeated_error_count += 1
            else:
                repeated_error_count = 1
                last_error_signature = error_signature

            if repeated_error_count >= self.max_repeated_tool_errors:
                return AgentResult(
                    success=False,
                    steps=history,
                    final_message=(
                        "Agent stopped after repeating the same failed tool call. "
                        "Inspect the last tool error and artifacts."
                    ),
                    stop_reason="repeated_tool_error",
                )

            if consecutive_errors >= self.max_consecutive_tool_errors:
                return AgentResult(
                    success=False,
                    steps=history,
                    final_message=(
                        "Agent stopped after consecutive tool errors. "
                        "Inspect the last tool error and artifacts."
                    ),
                    stop_reason="consecutive_tool_errors",
                )

        return AgentResult(
            success=False,
            steps=history,
            final_message=None,
            stop_reason="max_steps_exhausted",
        )


def _error_signature(*, step: AgentStep) -> str:
    """Stable signature for identifying repeated failed calls."""
    tool_call = step.action.tool_call
    if tool_call is None:
        return "missing_tool_call"
    try:
        args = json.dumps(tool_call.args, sort_keys=True, default=str)
    except TypeError:
        args = str(tool_call.args)
    envelope = step.observation or {}
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if isinstance(error, dict):
        error_code = str(error.get("code", "unknown"))
    else:
        error_code = "unknown"
    return f"{tool_call.tool}|{args}|{error_code}"
