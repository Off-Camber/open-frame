# Scenario `ab2-browser-only-t1` — Capability — native Notes find

- Status: **fail**
- Mode: `browser-only`
- Profiles: P1, P2
- Notes: envelope_ok failed for desktop_find; count_gte 1 failed for desktop_find (count=0)

## Metrics

- wall_seconds: 6.322
- steps: 2
- model: claude-haiku-4-5-20251001
- prompt_tokens: 9552
- completion_tokens: 382
- total_tokens: 9934
- cached_tokens: 9529
- cost_usd: 0.0038946500000000004
- usage_complete: True

## Agent final

```
Part 1 COMPLETE: Page heading confirmed as 'Open Frame handoff' on http://127.0.0.1:49753/handoff.html

Part 2 INCOMPLETE: I do not have access to desktop_capture or desktop_find tools. These are not available in my browser DOM toolset. Available tools are: navigate, click, input, scroll, wait, extract, search_page, find_elements, find_text, send_keys, save_as_pdf, screenshot, switch, close, go_back, evaluate, dropdown_options, select_dropdown, upload_file, write_file, read_file, replace_file.

As you requested: I cannot inspect native desktop UI and cannot locate the Notes app with the available tools. The browser DOM tools cannot access native applications or desktop capture functionality.
```

## Open Frame envelopes

Count: 0
