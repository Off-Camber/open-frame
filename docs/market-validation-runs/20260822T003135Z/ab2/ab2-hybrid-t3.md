# Scenario `ab2-hybrid-t3` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 16.942
- steps: 4
- model: claude-haiku-4-5-20251001
- prompt_tokens: 21366
- completion_tokens: 726
- total_tokens: 22092
- cached_tokens: 21297
- cost_usd: 0.00925245
- usage_complete: True

## Agent final

```
TASK COMPLETED SUCCESSFULLY

**Part 1 - Page Verification:**
✓ Successfully navigated to http://127.0.0.1:50639/handoff.html
✓ Confirmed page heading: "Open Frame handoff"
✓ Full heading text: "Open Frame handoff" with subtitle "Hybrid market-validation fixture — browser-use reads this page; Open Frame finds native UI."

**Part 2 - Desktop Tool Execution:**
✓ desktop_capture: Successfully captured the desktop screen
✓ desktop_find: Successfully located native Notes app with query "Notes"
✓ No click action was performed as instructed

**Results Summary:**
- Page Heading: "Open Frame handoff"
- Open Frame desktop_find Result: Successfully found the Notes app on the macOS desktop (not clicked per instructions)
```

## Open Frame envelopes

Count: 2
