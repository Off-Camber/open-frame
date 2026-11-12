# Scenario `ab2-browser-only-t1` — Capability — native Notes find

- Status: **fail**
- Mode: `browser-only`
- Profiles: P1, P2
- Notes: envelope_ok failed for desktop_find; count_gte 1 failed for desktop_find (count=0)

## Metrics

- wall_seconds: 12.003
- steps: 3
- model: claude-haiku-4-5-20251001
- prompt_tokens: 9552
- completion_tokens: 453
- total_tokens: 10005
- cached_tokens: 9529
- cost_usd: 0.00426465
- usage_complete: True

## Agent final

```
**PART 1 - COMPLETED:** Successfully opened http://127.0.0.1:50463/handoff.html and confirmed the page heading: 'Open Frame handoff'

The page displays the text: 'Open Frame handoff' followed by 'Hybrid market-validation fixture — browser-use reads this page; Open Frame finds native UI.'

**PART 2 - CANNOT COMPLETE:** You requested to use 'desktop_capture' and 'desktop_find' tools to locate the native Notes app. However, my available tools are browser DOM tools only (navigate, click, input, extract, scroll, etc.). These desktop inspection tools are not available in my current toolkit. 

To complete Part 2, I would need access to:
- desktop_capture: To capture the desktop
- desktop_find: To search for 'Notes' in the captured desktop

I cannot inspect native desktop UI with the browser tools available to me. Please provide these desktop inspection tools or clarify if there's an alternative approach.
```

## Open Frame envelopes

Count: 0
