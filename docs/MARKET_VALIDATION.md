# Market validation — profiles and browser-use harness

Open Frame is a **desktop execution engine** for agents, not an agent itself.
This document defines who would buy/use it, what jobs we expect them to run,
and how we score those jobs with an established agent (**browser-use**) plus
Open Frame as custom tools.

Harness code lives in [`examples/market-validation/`](../examples/market-validation/).

## Thesis

| Mode | Wins when |
|---|---|
| browser-use alone | Pure web/DOM tasks |
| Open Frame alone | Native apps, unlabeled icon chrome, Retina/desktop coords, auditable dry-run |
| Hybrid | Desktop ↔ browser handoffs in one agent loop |

**Market fit signal:** a hybrid browser-use agent finishes jobs that browser-use
alone cannot, with Open Frame envelopes and `runs/` artifacts for failures.

## Out of scope (v0)

- Windows / Linux buyers
- Unattended MFA / SSO automation (sessions must already be authenticated)
- Enterprise orchestration / scheduling
- Cursor / Claude Desktop as the primary agent (secondary later)

---

## User profiles

### P1 — Agent platform builder

| | |
|---|---|
| **Who** | Engineer embedding an agent framework (browser-use or similar) into a product |
| **Job** | Wire Open Frame as custom tools so the agent can act on native desktop UI |
| **Why not browser-only** | Their users’ workflows leave the DOM (Electron chrome, Finder, Mail, Settings) |
| **Success metric** | Custom tools call `capture` / `find` / `click` (dry-run) and return compact envelopes |
| **Open Frame tools** | `capture`, `find`, `click`, `get_run_artifacts` |

### P2 — Internal ops automator

| | |
|---|---|
| **Who** | Ops / IT automating recurring Mac desk work |
| **Job** | Native app + browser handoff (e.g. Notes/Finder → web form) without a full RPA suite |
| **Why not browser-only** | Source of truth is a desktop app; browser is only the submit surface |
| **Success metric** | Hybrid scenario completes with artifacts; no wild clicks on miss |
| **Open Frame tools** | `find`, `click` (dry-run), `type`, `key`, `run_flow`, `scroll` |

### P3 — QA / release engineer

| | |
|---|---|
| **Who** | Engineer owning release gates for a desktop or hybrid product |
| **Job** | Non-destructive smoke: find + dry-run click + verify across Safari + a native app |
| **Why not browser-only** | Must assert native chrome and window focus, not only page DOM |
| **Success metric** | Repeatable pass/fail with artifact paths; fail-closed on ambiguity |
| **Open Frame tools** | `capture`, `find`, `click` (dry-run), `run_flow` |

### P4 — RPA evaluator (self-hosted)

| | |
|---|---|
| **Who** | Team comparing self-hosted open engines vs proprietary RPA |
| **Job** | Replace a brittle selector script with capture → find → act → verify |
| **Why not browser-only** | Target apps are not all web; need auditable before/after frames |
| **Success metric** | Flow or agent run leaves `runs/<id>/` evidence; structured error codes |
| **Open Frame tools** | Full surface including `run_flow`, `get_run_artifacts` |

### P5 — Accessibility / support tooling

| | |
|---|---|
| **Who** | Support or a11y engineer automating unlabeled icon chrome |
| **Job** | Locate icon-only targets OCR cannot read; refuse ambiguous matches |
| **Why not browser-only** | Icons live in native toolbars / non-DOM surfaces |
| **Success metric** | Template hit with bounds; miss/ambiguity returns `not_found` / `ambiguous_target` |
| **Open Frame tools** | `find` + `template`, `click` (dry-run) |

---

## Scenario matrix

Auth precondition for all scenarios: **human-completed login/MFA**. Open Frame
does not automate identity.

| ID | Name | Profiles | Mode | Prompt summary | Pass criteria |
|---|---|---|---|---|---|
| S1 | Web-only baseline | P1 | `browser-only` | Open example.com; report the H1 text | Agent reports “Example Domain”; Open Frame tools unused |
| S2 | Desktop find | P2, P3, P4 | `openframe-only` | Focus Notes (or TextEdit); find a known label; do not click | `desktop_find` (or capture+find) returns `ok` with `count >= 1` |
| S3 | Hybrid handoff | P1, P2 | `hybrid` | Open local HTML in browser; also find native Notes chrome via desktop tools | Browser step succeeds **and** desktop find returns a match |
| S4 | Below-fold desktop | P3, P4 | `openframe-only` | Run scroll probe / find `OFSCROLLMARKER` with scroll_until_found | Find succeeds; details include `scroll_until_found` |
| S5 | Template icon | P5 | `openframe-only` | Find icon via template on fixture frame (OCR would miss) | Target `source` is `template:ncc`; count ≥ 1 |
| S6 | Fail-closed | P3, P5 | `openframe-only` | Click/find a string that does not exist; dry-run only | Envelope `ok: false` with `not_found` (or flow failure); no actuating click |

### Score values

- `pass` — objective criteria met
- `fail` — criteria not met with a healthy environment
- `blocked` — permissions, missing apps, or API keys prevented a fair run

Aggregate verdict lives in each run directory under
[`docs/market-validation-runs/`](market-validation-runs/) (see harness README).

### Known failure modes

| Symptom | Likely cause |
|---|---|
| Capture / doctor fail | Screen Recording not granted to the host process |
| Focus / find miss on native app | Accessibility permission; app not frontmost |
| OCR miss on icon | Expected for S5 — use `template` |
| browser-use cannot start | Missing Chromium / LLM API key; set `OPENFRAME_BROWSER_EXECUTABLE` if needed |
| `file://` navigation blocked | Expected — harness serves fixtures over `http://127.0.0.1` |
| Overlapping tool calls hang | Use sequential calls; see [MCP_SERVER.md](MCP_SERVER.md) |

---

## How to run

```bash
pip install -e ".[dev,ocr,act,flow,mcp,template]"
pip install "browser-use>=0.13"
# LLM key required for agent scenarios (S1–S3), e.g.:
# export OPENAI_API_KEY=...   # or provider key browser-use is configured for

python examples/market-validation/run_scenario.py --scenario s1
python examples/market-validation/run_scenario.py --scenario s2
python examples/market-validation/run_scenario.py --all
```

See [`examples/market-validation/README.md`](../examples/market-validation/README.md)
for permissions, dry-run policy, and scorecard layout.
