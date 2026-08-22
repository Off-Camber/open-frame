# Scenario `ab2-hybrid-t2` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 23.225
- steps: 7
- model: claude-haiku-4-5-20251001
- prompt_tokens: 42815
- completion_tokens: 1308
- total_tokens: 44123
- cached_tokens: 42594
- cost_usd: 0.0189504
- usage_complete: True

## Agent final

```
TASK COMPLETED:

**Part 1 - Page Heading Confirmation:**
The page heading on http://127.0.0.1:49836/handoff.html is: "Open Frame handoff"

**Part 2 - Desktop Find Result:**
Desktop capture and desktop_find have been executed. The Open Frame find operation returned 'openframe:find ok', indicating the Notes app search completed successfully on the native macOS system.

**Summary:**
- Part 1: ✓ Confirmed heading "Open Frame handoff" on the hybrid market-validation fixture page
- Part 2: ✓ Successfully executed desktop_capture and desktop_find to locate the native Notes app without clicking

Both parts of the task have been completed as requested.
```

## Open Frame envelopes

Count: 6
