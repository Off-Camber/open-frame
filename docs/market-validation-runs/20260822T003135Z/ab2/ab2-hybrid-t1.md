# Scenario `ab2-hybrid-t1` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 94.151
- steps: 14
- model: claude-haiku-4-5-20251001
- prompt_tokens: 93452
- completion_tokens: 3111
- total_tokens: 96563
- cached_tokens: 92287
- cost_usd: 0.0494512
- usage_complete: True

## Agent final

```
PART 1 - Page Heading Confirmed:
The page at http://127.0.0.1:50552/handoff.html displays the heading: "Open Frame handoff"
Full descriptive text: "Hybrid market-validation fixture — browser-use reads this page; Open Frame finds native UI."

PART 2 - Open Frame Desktop Operations:
The following desktop tools were successfully executed:
1. desktop_capture: Result - openframe:capture ok
2. desktop_find with query "Notes": Result - openframe:find ok

Both parts of the task have been completed. Part 1 confirms the page heading "Open Frame handoff" is present. Part 2 confirms the Open Frame tools (desktop_capture and desktop_find) were successfully called to locate the native Notes app on the desktop without clicking.
```

## Open Frame envelopes

Count: 20
