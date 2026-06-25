# Agent setup

Open Frame is a deterministic execution engine. The **agent layer** is a thin,
optional loop that lets an external LLM-backed planner drive that engine through
its MCP tools. The engine stays the source of truth for execution and evidence;
the agent only decides what to do next.

> Status: Phase A in progress. This release ships the loop contract and a
> minimal runner. A real LLM provider and reference task land in following
> Phase A tasks.

## Install

```bash
pip install -e ".[agent]"
```

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

## Contract

A provider implements one method:

```python
from openframe import AgentAction, AgentRunner, Provider, AgentStep


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

- A.2 — first concrete provider (Anthropic).
- A.3 — a reference task in `examples/agents/`.
- A.4 — failure-recovery patterns using structured errors + artifacts.
- A.7 — acceptance: an agent completes real tasks end-to-end, repeatably.
