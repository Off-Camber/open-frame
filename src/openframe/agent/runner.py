"""Minimal agent loop driving Open Frame's deterministic tools (Phase A).

The runner is deliberately thin: ask the provider for the next action, execute
it against the frozen MCP tool surface, record the structured response, and
repeat until the provider finishes or the step budget is exhausted.

The tool surface and catalog are injectable so the loop can be tested without
touching the real engine or any live screen.
"""

from __future__ import annotations

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
        tool_caller: ToolCaller | None = None,
        tool_catalog: ToolCatalog | None = None,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be > 0.")
        self.provider = provider
        self.max_steps = max_steps
        self._call_tool: ToolCaller = tool_caller or call_mcp_tool
        self._list_tools: ToolCatalog = tool_catalog or list_mcp_tools

    def run(self, task: str) -> AgentResult:
        """Run the agent loop for a natural-language task."""
        if not task or not task.strip():
            raise ValueError("task must be a non-empty string.")

        tools = self._list_tools()
        history: list[AgentStep] = []

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
            history.append(AgentStep(action=action, observation=envelope))

        return AgentResult(
            success=False,
            steps=history,
            final_message=None,
            stop_reason="max_steps_exhausted",
        )
