"""Tests for the minimal agent loop (Phase A).

The loop is exercised with a scripted provider and a fake tool caller so no
real engine or screen is touched.
"""

from __future__ import annotations

from typing import Any

import pytest

from openframe.agent import AgentAction, AgentRunner, AgentStep, Provider


class ScriptedProvider(Provider):
    """Provider that replays a fixed list of actions, finishing when empty."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self._actions = list(actions)
        self.calls: list[int] = []

    def next_action(
        self,
        *,
        task: str,
        tools: list[dict[str, Any]],
        history: list[AgentStep],
    ) -> AgentAction:
        self.calls.append(len(history))
        if self._actions:
            return self._actions.pop(0)
        return AgentAction.finish("ran out of script")


def _fake_catalog() -> list[dict[str, Any]]:
    return [{"name": "find"}, {"name": "click"}]


def _fake_caller_factory() -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    seen: list[tuple[str, dict[str, Any]]] = []

    def caller(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        seen.append((tool, args))
        return {"ok": True, "tool": tool, "data": {"echo": args}}

    return caller, seen


def test_runner_executes_tool_calls_then_finishes() -> None:
    caller, seen = _fake_caller_factory()
    provider = ScriptedProvider(
        [
            AgentAction.call("find", {"query": "Send"}),
            AgentAction.call("click", {"query": "Send"}),
            AgentAction.finish("done"),
        ]
    )
    runner = AgentRunner(provider=provider, tool_caller=caller, tool_catalog=_fake_catalog)

    result = runner.run("send the email")

    assert result.success is True
    assert result.stop_reason == "finished"
    assert result.final_message == "done"
    assert len(result.steps) == 2
    assert seen == [("find", {"query": "Send"}), ("click", {"query": "Send"})]
    assert result.steps[0].observation == {"ok": True, "tool": "find", "data": {"echo": {"query": "Send"}}}


def test_runner_passes_tool_catalog_to_provider() -> None:
    caller, _ = _fake_caller_factory()
    provider = ScriptedProvider([AgentAction.finish()])
    runner = AgentRunner(provider=provider, tool_caller=caller, tool_catalog=_fake_catalog)

    result = runner.run("inspect")

    assert result.success is True
    assert result.steps == []


def test_runner_stops_at_max_steps() -> None:
    caller, seen = _fake_caller_factory()
    provider = ScriptedProvider(
        [AgentAction.call("find", {"query": str(i)}) for i in range(10)]
    )
    runner = AgentRunner(
        provider=provider, max_steps=3, tool_caller=caller, tool_catalog=_fake_catalog
    )

    result = runner.run("loop forever")

    assert result.success is False
    assert result.stop_reason == "max_steps_exhausted"
    assert len(result.steps) == 3
    assert len(seen) == 3


def test_runner_rejects_tool_call_without_payload() -> None:
    caller, _ = _fake_caller_factory()
    bad_action = AgentAction(kind="tool_call", tool_call=None)
    provider = ScriptedProvider([bad_action])
    runner = AgentRunner(provider=provider, tool_caller=caller, tool_catalog=_fake_catalog)

    with pytest.raises(ValueError, match="tool_call action must include a ToolCall"):
        runner.run("broken")


def test_runner_rejects_empty_task() -> None:
    provider = ScriptedProvider([AgentAction.finish()])
    runner = AgentRunner(provider=provider, tool_catalog=_fake_catalog)

    with pytest.raises(ValueError, match="task must be a non-empty string"):
        runner.run("   ")


def test_runner_rejects_non_positive_max_steps() -> None:
    provider = ScriptedProvider([AgentAction.finish()])
    with pytest.raises(ValueError, match="max_steps must be > 0"):
        AgentRunner(provider=provider, max_steps=0)
