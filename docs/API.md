# API

Open Frame has two integration surfaces:

- `Session` for Python SDK usage.
- `mcp` commands for agent/orchestrator tool calls.

If you are new, start with the SDK quick start below, then move to MCP.

## Install

```bash
pip install off-camber-open-frame
```

For local development with extras:

```bash
pip install -e .[ocr,act,flow]
```

## SDK quick start (`Session`)

```python
from openframe import Session

session = Session(dry_run=True)

targets = session.find("New")
print(f"matches: {len(targets)}")

if targets:
    point = session.click("New", kind="click", anchor="center")
    print("would click:", point)
```

Run a short in-memory flow:

```python
results = session.run(
    [
        {"id": "focus", "kind": "app", "name": "Microsoft Outlook"},
        {"id": "compose", "kind": "click", "query": "New"},
        {"id": "wait", "kind": "wait", "ms": 300},
    ]
)
print([r.ok for r in results])
```

`Session` also supports `register_recognizer(...)` for custom matching logic.

## MCP quick start (CLI surface)

List available MCP tools:

```bash
.venv311/bin/python -m openframe.cli mcp list-tools --json
```

Call a tool:

```bash
.venv311/bin/python -m openframe.cli mcp call find --args-json '{"query":"New"}'
```

Run a flow via MCP:

```bash
.venv311/bin/python -m openframe.cli mcp call run_flow --args-json '{
  "flow_path": "examples/flows/outlook-new-email/flow.yaml",
  "dry_run": true,
  "run_id": "compose-dry-1"
}'
```

If `run_flow` returns `ok: false`, inspect artifacts:

```bash
.venv311/bin/python -m openframe.cli mcp call get_run_artifacts --args-json '{"run_id":"compose-dry-1"}'
```

## MCP tool set (v0.2 checkpoint)

- `capture`
- `find`
- `click`
- `type`
- `key`
- `run_flow`
- `get_run_artifacts`

The current frozen contract identifier is `v0.2.0-checkpoint-1`.

## Response contract

All MCP calls return the same envelope:

```json
{
  "ok": true,
  "tool": "find",
  "run_id": "20260618T220000Z",
  "data": {},
  "error": null,
  "artifacts": {}
}
```

When `ok` is `false`, read `error.code` and `error.message`, then use `artifacts` paths for debugging.

Stable error codes used by MCP tools include:

- `unknown_tool`
- `ambiguous_target`
- `validation_error`
- `capture_error`
- `action_error`
- `not_found`
- `flow_failed`
- `runtime_error`
- `internal_error`

`click` also accepts:

- `expect_one: true` for deterministic targeting (multiple matches return `ambiguous_target`)
- `selector` for deterministic candidate choice when multiple matches are allowed (`first`, `top_most`, `left_most`, `right_most`, `highest_confidence`)

## Choosing SDK vs MCP

- Use `Session` when your automation lives in Python code in the same process.
- Use MCP when an external agent needs deterministic desktop actions with compact JSON responses.

## Advanced: custom recognizers

You can register recognizers without changing Open Frame core. See `examples/custom_recognizer/` for a complete working example.
