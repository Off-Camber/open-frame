# Agent setup

Open Frame is a deterministic execution engine. The **agent layer** is a thin,
optional loop that lets an external LLM-backed planner drive that engine through
its MCP tools. The engine stays the source of truth for execution and evidence;
the agent only decides what to do next.

> Status: Phase A in progress. Ships the loop contract, a minimal runner, and
> the first real provider (`AnthropicProvider`). A reference task and
> failure-recovery patterns land in following Phase A tasks.

## Install

```bash
pip install -e ".[agent]"
```

The Anthropic provider reads your API key from the `ANTHROPIC_API_KEY`
environment variable (or pass `api_key=` explicitly). The model defaults to
`claude-haiku-4-5-20251001` and can be overridden with `OPENFRAME_AGENT_MODEL`
or the `model=` argument.

## The loop

```text
provider.next_action(task, tools, history)
        │
        ▼
   AgentAction ── finish ──▶ AgentResult(success=True)
        │
     tool_call
        │
        ▼
call_mcp_tool(tool, args)  ──▶  structured envelope recorded in history
        │
        └──────────── repeat until finish or max_steps ───────────┘
```

- **Engine boundary:** the agent never touches the screen directly. It only
  issues deterministic MCP tool calls (`capture`, `find`, `click`, `type`,
  `key`, `run_flow`, `get_run_artifacts`) and reads their structured responses.
- **Evidence:** tool responses carry artifact paths, so an agent run is
  auditable the same way a flow run is.

## Run it locally (Anthropic)

This drives the **real** engine, so it will capture your screen and may move the
mouse / type. Start with a read-only task (capture + find), and use `dry_run`
for any action steps while you build confidence.

```python
from openframe import AgentRunner, AnthropicProvider

provider = AnthropicProvider()  # uses ANTHROPIC_API_KEY
runner = AgentRunner(provider=provider, max_steps=12)

result = runner.run(
    "Capture the screen and tell me whether a 'Send' button is visible. "
    "Do not click anything."
)

print("success:", result.success, "| stop:", result.stop_reason)
print("final:", result.final_message)
for step in result.steps:
    call = step.action.tool_call
    ok = step.observation.get("ok") if step.observation else None
    print(f"  -> {call.tool}({call.args}) ok={ok}")
```

macOS will prompt for **Screen Recording** (and **Accessibility**, if the agent
acts) the first time — see `docs/ACT_SETUP.md` for permission details.

## Custom contract

Any provider implements one method:

```python
from openframe import AgentAction, AgentRunner, Provider


class MyProvider(Provider):
    def next_action(self, *, task, tools, history) -> AgentAction:
        # Decide the next move from the task, tool catalog, and history.
        # Return AgentAction.call("find", {"query": "Send"}) or
        # AgentAction.finish("done").
        ...


result = AgentRunner(provider=MyProvider(), max_steps=20).run("send the report email")
print(result.success, result.stop_reason)
```

## What ships next (Phase A)

- A.3 — a reference task in `examples/agents/`.
- A.4 — failure-recovery patterns using structured errors + artifacts.
- A.7 — acceptance: an agent completes real tasks end-to-end, repeatably.
