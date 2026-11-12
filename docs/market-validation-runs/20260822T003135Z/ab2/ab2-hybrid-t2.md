# Scenario `ab2-hybrid-t2` — Capability — native Notes find

- Status: **pass**
- Mode: `hybrid`
- Profiles: P1, P2
- Notes: all checks passed

## Metrics

- wall_seconds: 15.638
- steps: 4
- model: claude-haiku-4-5-20251001
- prompt_tokens: 21366
- completion_tokens: 644
- total_tokens: 22010
- cached_tokens: 21297
- cost_usd: 0.0088812
- usage_complete: True

## Agent final

```
PART 1 COMPLETE: Successfully opened http://127.0.0.1:50613/handoff.html and confirmed the page heading reads 'Open Frame handoff' - exactly as required.

PART 2 COMPLETE: Called desktop_capture and desktop_find with query 'Notes':
- desktop_capture result: openframe:capture ok
- desktop_find result: openframe:find ok

Both custom tools executed successfully and located the native Notes app on the desktop without clicking it.
```

## Open Frame envelopes

Count: 2
