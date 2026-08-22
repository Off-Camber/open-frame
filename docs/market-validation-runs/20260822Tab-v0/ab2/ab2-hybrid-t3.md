# Scenario `ab2-hybrid-t3` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 39.375
- steps: 13
- model: claude-haiku-4-5-20251001
- prompt_tokens: 86213
- completion_tokens: 2728
- total_tokens: 88941
- cached_tokens: 85188
- cost_usd: 0.04444505
- usage_complete: True

## Agent final

```
Both parts completed successfully:

**Part 1: Page Heading Confirmation**
Navigated to http://127.0.0.1:49864/handoff.html
Page heading confirmed: "Open Frame handoff"
Page content: "Hybrid market-validation fixture — browser-use reads this page; Open Frame finds native UI."

**Part 2: Open Frame Desktop Tools**
1. Called desktop_capture to capture the native system screen
2. Called desktop_find with query "Notes" to locate the native Notes app
3. Result: openframe:find ok - Successfully located the Notes app on the system

Both parts of the user request have been completed as required.
```

## Open Frame envelopes

Count: 12
