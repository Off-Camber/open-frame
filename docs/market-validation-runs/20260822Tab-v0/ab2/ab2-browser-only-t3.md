# Scenario `ab2-browser-only-t3` — Capability — native Notes find

- Status: **fail**
- Mode: `browser-only`
- Profiles: P1, P2
- Notes: envelope_ok failed for desktop_find; count_gte 1 failed for desktop_find (count=0)

## Metrics

- wall_seconds: 6.355
- steps: 2
- model: claude-haiku-4-5-20251001
- prompt_tokens: 9552
- completion_tokens: 395
- total_tokens: 9947
- cached_tokens: 9529
- cost_usd: 0.00395965
- usage_complete: True

## Agent final

```
Part 1 COMPLETED: Confirmed the page heading at http://127.0.0.1:49793/handoff.html is 'Open Frame handoff'.

Part 2 LIMITATION: I have only browser DOM tools available. The user requested calling 'desktop_capture' and 'desktop_find' with query "Notes", which are native desktop inspection tools outside the browser DOM. These tools are not available in my current toolkit. I can only interact with the browser and its webpage content.

To complete part 2, you would need to:
- Use Open Frame's desktop_capture function to capture the native desktop
- Use Open Frame's desktop_find function with the query "Notes" to locate the native Notes app

I cannot access these native desktop UI inspection capabilities from the browser tools I have available.
```

## Open Frame envelopes

Count: 0
