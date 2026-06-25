"""Tests for the Anthropic agent provider (Phase A.2).

A stub client stands in for the anthropic SDK so the provider's tool-use
mapping, message reconstruction, and finish handling are exercised offline.
"""

from __future__ import annotations

from typing import Any

import pytest

from openframe.agent import AgentAction, AgentRunner, AgentStep
from openframe.agent.providers import anthropic_provider
from openframe.agent.providers.anthropic_provider import AnthropicProvider


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, *, id: str, name: str, input: dict[str, Any]) -> None:
        self.id = id
        self.name = name
        self.input = input


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self, content: list[Any], stop_reason: str = "tool_use") -> None:
        self.content = content
        self.stop_reason = stop_reason


class _StubMessages:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _StubClient:
    def __init__(self, responses: list[_Response]) -> None:
        self.messages = _StubMessages(responses)


_TOOLS = [
    {
        "name": "find",
        "description": "Find targets by query on a frame",
        "required_args": ["query"],
        "optional_args": ["strategy", "frame_path"],
    },
    {
        "name": "click",
        "description": "Find and click a target by query",
        "required_args": ["query"],
        "optional_args": ["dry_run", "x", "y"],
    },
]


def test_provider_returns_tool_call_from_tool_use() -> None:
    client = _StubClient([_Response([_ToolUseBlock(id="tu_1", name="find", input={"query": "Send"})])])
    provider = AnthropicProvider(client=client)

    action = provider.next_action(task="send email", tools=_TOOLS, history=[])

    assert action.kind == "tool_call"
    assert action.tool_call is not None
    assert action.tool_call.tool == "find"
    assert action.tool_call.args == {"query": "Send"}
    assert action.tool_call.id == "tu_1"


def test_provider_finishes_on_text_only() -> None:
    client = _StubClient([_Response([_TextBlock("All done.")], stop_reason="end_turn")])
    provider = AnthropicProvider(client=client)

    action = provider.next_action(task="task", tools=_TOOLS, history=[])

    assert action.kind == "finish"
    assert action.final_message == "All done."


def test_provider_builds_tool_schemas_with_typed_args() -> None:
    client = _StubClient([_Response([_TextBlock("done")], stop_reason="end_turn")])
    provider = AnthropicProvider(client=client)

    provider.next_action(task="task", tools=_TOOLS, history=[])

    sent_tools = client.messages.calls[0]["tools"]
    click_schema = next(item for item in sent_tools if item["name"] == "click")
    props = click_schema["input_schema"]["properties"]
    assert props["dry_run"] == {"type": "boolean"}
    assert props["x"] == {"type": "integer"}
    assert props["query"] == {"type": "string"}
    assert click_schema["input_schema"]["required"] == ["query"]


def test_provider_rebuilds_conversation_from_history() -> None:
    client = _StubClient([_Response([_TextBlock("done")], stop_reason="end_turn")])
    provider = AnthropicProvider(client=client)
    history = [
        AgentStep(
            action=AgentAction.call("find", {"query": "Send"}, id="tu_1"),
            observation={"ok": True, "tool": "find", "data": {"count": 1}},
        )
    ]

    provider.next_action(task="send email", tools=_TOOLS, history=history)

    messages = client.messages.calls[0]["messages"]
    assert messages[0] == {"role": "user", "content": "send email"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[1]["content"][0]["id"] == "tu_1"
    assert messages[2]["role"] == "user"
    result_block = messages[2]["content"][0]
    assert result_block["type"] == "tool_result"
    assert result_block["tool_use_id"] == "tu_1"
    assert '"count": 1' in result_block["content"]


def test_provider_truncates_large_observations() -> None:
    client = _StubClient([_Response([_TextBlock("done")], stop_reason="end_turn")])
    provider = AnthropicProvider(client=client, max_observation_chars=20)
    history = [
        AgentStep(
            action=AgentAction.call("find", {"query": "x"}, id="tu_1"),
            observation={"blob": "y" * 500},
        )
    ]

    provider.next_action(task="task", tools=_TOOLS, history=history)

    result_block = client.messages.calls[0]["messages"][2]["content"][0]
    assert result_block["content"].endswith("...[truncated]")
    assert len(result_block["content"]) <= 20 + len("...[truncated]")


def test_provider_drives_runner_end_to_end() -> None:
    client = _StubClient(
        [
            _Response([_ToolUseBlock(id="tu_1", name="find", input={"query": "Send"})]),
            _Response([_TextBlock("Found it; done.")], stop_reason="end_turn"),
        ]
    )
    provider = AnthropicProvider(client=client)
    seen: list[tuple[str, dict[str, Any]]] = []

    def fake_caller(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        seen.append((tool, args))
        return {"ok": True, "tool": tool, "data": {"count": 1}}

    runner = AgentRunner(
        provider=provider,
        tool_caller=fake_caller,
        tool_catalog=lambda: _TOOLS,
    )
    result = runner.run("send the email")

    assert result.success is True
    assert result.final_message == "Found it; done."
    assert seen == [("find", {"query": "Send"})]
    assert len(result.steps) == 1


def test_missing_anthropic_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise RuntimeError(
            'The Anthropic provider requires the "anthropic" package. '
            'Install it with: pip install ".[agent]"'
        )

    monkeypatch.setattr(anthropic_provider, "_load_anthropic", boom)
    provider = AnthropicProvider()  # no injected client -> must construct one

    with pytest.raises(RuntimeError, match="requires the .anthropic. package"):
        provider.next_action(task="task", tools=_TOOLS, history=[])
