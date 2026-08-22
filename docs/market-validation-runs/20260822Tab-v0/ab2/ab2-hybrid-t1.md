# Scenario `ab2-hybrid-t1` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 17.45
- steps: 4
- model: claude-haiku-4-5-20251001
- prompt_tokens: 21366
- completion_tokens: 823
- total_tokens: 22189
- cached_tokens: 21297
- cost_usd: 0.009801200000000001
- usage_complete: True

## Agent final

```
TASK COMPLETED - Both parts successfully executed:

**PART 1 - Web Navigation:**
URL: http://127.0.0.1:49813/handoff.html
Page Heading: "Open Frame handoff"
Subheading: "Hybrid market-validation fixture — browser-use reads this page; Open Frame finds native UI."
✓ Confirmed the heading mentions "Open Frame handoff" exactly as requested.

**PART 2 - Desktop Operations:**
✓ Called desktop_capture: openframe:capture ok
✓ Called desktop_find with query "Notes": openframe:find ok

Both parts of the request have been completed as specified. Part 1 confirms the web page heading. Part 2 successfully executed the Open Frame desktop_capture and desktop_find operations to locate the native Notes app (the operations completed without errors).
```

## Open Frame envelopes

Count: 2
