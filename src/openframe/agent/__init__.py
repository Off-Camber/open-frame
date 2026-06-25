"""Agent integration layer (Phase A).

Thin, embeddable loop that lets an external LLM-backed planner drive Open
Frame's deterministic MCP tools. The engine stays the source of truth for
execution and evidence; the agent only decides what to do next.
"""

from .base import AgentAction, AgentResult, AgentStep, Provider, ToolCall
from .runner import AgentRunner

__all__ = [
    "AgentAction",
    "AgentResult",
    "AgentRunner",
    "AgentStep",
    "Provider",
    "ToolCall",
]
