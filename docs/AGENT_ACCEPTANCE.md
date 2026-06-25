# Agent acceptance (A.7)

This checklist validates the current agent integration end-to-end with bounded
failure behavior.

## Preconditions

- `pip install -e ".[agent]"`
- `ANTHROPIC_API_KEY` exported
- `OPENFRAME_AGENT_MODEL` set (optional; defaults to `claude-haiku-4-5-20251001`)
- macOS Screen Recording granted for your terminal/python process

## Run

```bash
./scripts/agent_acceptance.sh
```

The script writes a timestamped summary under `docs/acceptance-runs/`:

- `agent-acceptance-<timestamp>.md`
- one log file per check

## Checks and pass criteria

1. `probe-send`
   - exits 0
   - prints `success=True stop=finished`
   - includes a `capture(...)` tool call in step trace
2. `probe-calendar`
   - exits 0
   - prints `success=True stop=finished`
   - includes a `capture(...)` tool call in step trace
3. `guard-failfast`
   - deterministic injected failure check
   - exits 0
   - prints `stop=repeated_tool_error`
   - confirms the runner stops after 2 repeated failures

## Notes

- The first two checks are live model runs and can vary in final wording.
- They are intentionally read-only tasks; no click/type/key/run_flow actions.
- If a live check fails due to permissions or API auth, fix that root cause and re-run.
