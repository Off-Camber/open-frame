# Market validation scorecard — 20260805Tmarket-v0

| Scenario | Mode | Status | Notes |
|---|---|---|---|
| `s1` | `browser-only` | **pass** | browser-use alone on example.com (control) |
| `s2` | `openframe-only` | **pass** | Notes focus + desktop find |
| `s3` | `hybrid` | **pass** | localhost HTML via browser-use + Open Frame find Notes |
| `s4` | `openframe-only` | **pass** | scroll_until_found on scroll-probe fixture |
| `s5` | `openframe-only` | **pass** | template:ncc hit on template-icon-probe |
| `s6` | `openframe-only` | **pass** | dry-run click returned structured `not_found` |

Totals: pass=6 fail=0 blocked=0

## Verdict

**Market-ready for the macOS hybrid thesis under this harness:** browser-use alone covers pure web (S1); Open Frame is required and succeeds for native find, scroll, template, and fail-closed (S2/S4/S5/S6); the hybrid handoff (S3) completes in one agent run with auditable Open Frame envelopes.

Out of scope for this stamp (see `docs/MARKET_VALIDATION.md`): Windows buyers, MFA, unattended enterprise orchestration.

## Environment notes

- Agent: browser-use 0.13.x + Anthropic Haiku (`claude-haiku-4-5-20251001`), `flash_mode`, Chromium via Playwright / `OPENFRAME_BROWSER_EXECUTABLE` discovery
- S3 fixture served over `http://127.0.0.1` (browser-use blocks `file://`)
- Clicks remain dry-run except scroll actuation in S4
