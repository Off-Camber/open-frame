# v0.2.0 checkpoint

This checkpoint defines Open Frame's next product shape after `v0.1.x`.

## Product definition

Open Frame is a deterministic desktop automation engine that AI systems call.

- **Engine, not copilot:** Open Frame executes capture/recognize/act/verify steps.
- **LLM role:** planning, decomposition, and choosing the next tool call.
- **Contract:** Open Frame returns compact structured outputs and artifact paths, not long natural-language transcripts.

## First integrator user

Developer automators building agent workflows who need:

1. reliable desktop actions,
2. auditable evidence on failure, and
3. minimal context-window pressure while orchestrating complex flows.

## Scope for v0.2.0

### In scope

- MCP as the primary integration interface.
- Deterministic tool surface mapped to existing engine behavior.
- Stable JSON response contracts with explicit error objects.
- Artifact-first debugging (`runs/<run_id>/<step_id>/...`).

### Out of scope

- Full vision recognizer implementation (Phase 7 deferred).
- Multi-provider agent runtime strategy.
- Orchestration/scheduling/queueing platform work.

## MCP tool surface (MVP)

Initial tools should be thin wrappers over engine primitives:

- `capture`
- `find`
- `click`
- `type`
- `key`
- `run_flow`
- `get_run_artifacts`

## Response contract requirements

All MCP tools should return compact, deterministic JSON:

- `ok` (`true`/`false`)
- `tool`
- `run_id` (when applicable)
- `data` (tool-specific payload)
- `error` (stable code + message when `ok=false`)
- `artifacts` (paths only, no large binary payloads inline)

## Release gates for v0.2.0

`v0.2.0` is ready when:

1. one representative agent flow runs end-to-end through MCP calls only;
2. failure handling always returns artifact pointers and stable error codes;
3. tool responses remain compact enough that agent prompts avoid large transcript bloat;
4. integration docs let a third party wire an agent to Open Frame without reading internals.

## Decision gate before Phase 7

Do not start full Phase 7 implementation until the MCP integration release gates above are met.
