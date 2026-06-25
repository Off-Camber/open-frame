"""Anthropic-backed agent provider (Phase A.2).

Maps Open Frame's MCP tool catalog onto Anthropic tool-use, asks the model for
the next action each turn, and translates the response back into an
:class:`AgentAction`. The conversation is rebuilt from :class:`AgentStep`
history on every call, so the provider holds no mutable run state itself.

The ``anthropic`` SDK is imported lazily so the rest of the agent layer (and
the test suite) works without it installed. Install with ``pip install
".[agent]"``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openframe.agent.base import AgentAction, AgentStep, Provider

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_MAX_OBSERVATION_CHARS = 4000

SYSTEM_PROMPT = (
    "You are driving Open Frame, a deterministic on-screen UI automation engine, "
    "to accomplish the user's task. You act ONLY by calling the provided tools, "
    "which capture the screen, find on-screen targets, click, type, press keys, "
    "and run flows. Each tool returns a structured JSON result; read it before "
    "deciding the next step. Work in small, verifiable steps: capture or find to "
    "confirm the current state before acting. When the task is complete, stop and "
    "reply with a short summary instead of calling a tool. If a tool returns "
    "ok=false, adapt once based on the error code/data/artifacts; do not repeat "
    "the exact same failing call in a loop. If blocked, explain why and finish. "
    "If you are unsure "
    'whether an action is safe, pass "dry_run": true.'
)

_INT_ARGS = {"x", "y", "width", "height", "window_id"}
_NUMBER_ARGS = {"interval"}
_BOOL_ARGS = {"dry_run", "expect_one"}


def _load_anthropic() -> Any:
    """Import the anthropic SDK or raise a helpful install hint."""
    try:
        import anthropic
    except ImportError as error:  # pragma: no cover - exercised via monkeypatch
        raise RuntimeError(
            'The Anthropic provider requires the "anthropic" package. '
            'Install it with: pip install ".[agent]"'
        ) from error
    return anthropic


def _arg_schema(name: str) -> dict[str, Any]:
    if name == "combo":
        return {"type": "array", "items": {"type": "string"}}
    if name in _BOOL_ARGS:
        return {"type": "boolean"}
    if name in _INT_ARGS:
        return {"type": "integer"}
    if name in _NUMBER_ARGS:
        return {"type": "number"}
    return {"type": "string"}


class AnthropicProvider(Provider):
    """Planner that uses Anthropic tool-use to choose the next action."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system_prompt: str = SYSTEM_PROMPT,
        max_observation_chars: int = DEFAULT_MAX_OBSERVATION_CHARS,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.environ.get("OPENFRAME_AGENT_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.max_observation_chars = max_observation_chars
        self._api_key = api_key
        self._client = client

    def next_action(
        self,
        *,
        task: str,
        tools: list[dict[str, Any]],
        history: list[AgentStep],
    ) -> AgentAction:
        client = self._ensure_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            tools=self._tool_schemas(tools),
            messages=self._build_messages(task=task, history=history),
        )

        tool_use = self._first_tool_use(response)
        if tool_use is not None:
            args = dict(getattr(tool_use, "input", None) or {})
            return AgentAction.call(
                getattr(tool_use, "name"),
                args,
                id=getattr(tool_use, "id", None),
            )
        return AgentAction.finish(self._response_text(response) or None)

    def _ensure_client(self) -> Any:
        if self._client is None:
            anthropic = _load_anthropic()
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _tool_schemas(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for tool in tools:
            name = tool.get("name")
            if not name:
                continue
            required = list(tool.get("required_args", []) or [])
            optional = list(tool.get("optional_args", []) or [])
            properties = {arg: _arg_schema(arg) for arg in [*required, *optional]}
            schemas.append(
                {
                    "name": name,
                    "description": tool.get("description", ""),
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            )
        return schemas

    def _build_messages(self, *, task: str, history: list[AgentStep]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        for index, step in enumerate(history):
            tool_call = step.action.tool_call
            if tool_call is None:
                continue
            use_id = tool_call.id or f"call_{index}"
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": use_id,
                            "name": tool_call.tool,
                            "input": tool_call.args,
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": use_id,
                            "content": self._summarize(step.observation),
                        }
                    ],
                }
            )
        return messages

    def _summarize(self, observation: dict[str, Any] | None) -> str:
        if observation is None:
            return "null"
        try:
            text = json.dumps(observation, default=str)
        except TypeError:
            text = str(observation)
        if len(text) > self.max_observation_chars:
            return text[: self.max_observation_chars] + "...[truncated]"
        return text

    @staticmethod
    def _first_tool_use(response: Any) -> Any | None:
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "tool_use":
                return block
        return None

    @staticmethod
    def _response_text(response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "\n".join(part for part in parts if part).strip()
