# Action plan

Phased checklist for building Open Frame. Estimate effort as **S** (days), **M** (1–2 weeks), **L** (multi-week). Adjust as you learn.

**Current phase:** v0.2 checkpoint — MCP interface before vision

**MVP goalpost:** [MVP_GOALPOST.md](MVP_GOALPOST.md) — Outlook → M365 → create doc → email, repeatable via a flow file.

---

## Phase 0 — Foundation

**Goal:** Repo is real; decisions documented; empty architecture compiles.

| # | Task | Size | Status |
|---|------|------|--------|
| 0.1 | Initialize git repo; add `.gitignore` (Python, OS, artifacts) | S | ☑ |
| 0.2 | Choose license (Apache 2.0 recommended for enterprise OSS) | S | ☑ |
| 0.3 | Pin stack decision in [DECISIONS.md](DECISIONS.md) (Python 3.11+, packaging) | S | ☑ |
| 0.4 | Create package skeleton `src/openframe/` + `pyproject.toml` | S | ☑ |
| 0.5 | Add CI: lint + test on push (GitHub Actions) | S | ☑ |
| 0.6 | Define core types in `types.py` (`Frame`, `Target`, `Action`, `StepResult`) | S | ☑ |
| 0.7 | Create GitHub repo `off-camber/open-frame`; push | S | ☑ |

**Exit criteria:** `pip install -e .` works; CI green; types importable.

---

## Phase 1 — Capture

**Goal:** Reliable screenshots of display content on macOS.

| # | Task | Size | Status |
|---|------|------|--------|
| 1.1 | Research macOS capture APIs (ScreenCaptureKit vs Quartz `CGWindowListCreateImage`) | S | ☑ |
| 1.2 | Implement `capture.screen()` — primary monitor | M | ☑ |
| 1.3 | Implement `capture.window(title \| id)` — active or named window | M | ☑ |
| 1.4 | Implement `capture.region(x, y, w, h)` | S | ☑ |
| 1.5 | Handle Retina scale factor in `Frame` metadata | M | ☑ |
| 1.6 | List windows / displays CLI: `open-frame list-windows` | S | ☑ |
| 1.7 | CLI: `open-frame capture --out frame.png` | S | ☑ |
| 1.8 | Tests with fixture images (unit); manual test doc for live capture | S | ☑ |

**Exit criteria:** Capture active window to PNG with correct dimensions documented.

---

## Phase 2 — Recognize (first recognizers)

**Goal:** Find a target on a frame and return bounds.

| # | Task | Size | Status |
|---|------|------|--------|
| 2.1 | Define `Recognizer` protocol / ABC in `recognize/base.py` | S | ☑ |
| 2.2 | Implement **Tesseract OCR recognizer** (`pytesseract`) — find text, return boxes; document OS binary install | M | ☑ |
| 2.3 | Implement **macOS accessibility recognizer** — search AX tree by role/name | L | ☑ |
| 2.4 | Implement recognizer chain: run by priority, merge/d dedupe overlapping targets | M | ☑ |
| 2.5 | `Locator.find(frame, query, strategy=...)` public API | S | ☑ |
| 2.6 | CLI: `open-frame find "Submit" --json` | S | ☑ |
| 2.7 | Draw debug overlay (boxes on screenshot) for development | S | ☑ |
| 2.8 | Tests: OCR against saved fixture screenshots | M | ☑ |

**Exit criteria:** Given a screenshot with known text, `find` returns a bounding box within tolerance.

---

## Phase 3 — Act

**Goal:** Perform input from a `Target` or coordinates.

| # | Task | Size | Status |
|---|------|------|--------|
| 3.1 | Map `Target` bounds → click point (center, configurable) | S | ☑ |
| 3.2 | Implement click, double-click, right-click (macOS) | M | ☑ |
| 3.3 | Implement type text + key combos | M | ☑ |
| 3.4 | Implement scroll at point | S | ☑ |
| 3.5 | `wait(ms)` and `wait_for_frame_change` helpers | M | ☑ |
| 3.6 | CLI: `open-frame click "Submit"` (find + click) | S | ☑ |
| 3.7 | Safety: optional `--dry-run` (log action, don't execute) | S | ☑ |

**Exit criteria:** End-to-end: capture → find "OK" → click → manual confirmation on a test app. See [ACT_MANUAL_TEST.md](ACT_MANUAL_TEST.md).

---

## Phase 4 — Verify

**Goal:** Know if a step succeeded; produce artifacts for debugging.

| # | Task | Size | Status |
|---|------|------|--------|
| 4.1 | Define `Verifier` interface | S | ☑ |
| 4.2 | **Screenshot diff** verifier — pixel or perceptual hash threshold | M | ☑ |
| 4.3 | **Text appeared / disappeared** verifier (OCR on after-frame) | M | ☑ |
| 4.4 | **Target gone** verifier (element no longer found) | S | ☑ |
| 4.5 | Session runner writes `runs/<id>/` with before/after PNG + `step.json` | M | ☑ |
| 4.6 | CLI: `open-frame click "Save" --verify text-gone:"Save"` | M | ☑ |

**Exit criteria:** Failed verify returns non-zero exit code and saves artifacts.

---

## Phase 5 — Flow runner + MVP (goalpost)

**Goal:** [MVP goalpost](MVP_GOALPOST.md) — declarative multi-app flow, repeatable Outlook → M365 → email.

| # | Task | Size | Status |
|---|------|------|--------|
| 5.1 | `Flow` model: name, variables, ordered steps | M | ☑ |
| 5.2 | Flow runner: load **YAML** flow, execute steps, stop on failure, emit `runs/<id>/` artifacts | M | ☑ |
| 5.3 | Step types: `app` (focus), `click`, `type`, `fill`, `attach`, `navigate`, `wait`, `verify` | L | ☑ |
| 5.4 | Variable substitution (`{{subject}}`, `{{run_id}}`, artifact paths) | M | ☑ |
| 5.5 | **Smoke:** `examples/flows/outlook-new-email/` — focus Outlook, new email, verify compose | M | ☑ |
| 5.6 | **Handoff:** subflow Outlook → browser → Outlook (focus + one action each) | M | ☑ |
| 5.7 | **Full MVP:** `examples/flows/outlook-m365-email/` per goalpost doc | L | ☑ |
| 5.8 | Environment README: login prep, app versions, resolution, test mailbox | S | ☑ |
| 5.9 | Acceptance test: 3 consecutive successful runs documented (see [ACCEPTANCE_RUNS.md](ACCEPTANCE_RUNS.md)) | M | ☑ |
| 5.10 | Tag **v0.1.0** when [MVP goalpost](MVP_GOALPOST.md) checklist passes | S | ☑ |

**Exit criteria:** Goalpost acceptance checklist complete on **macOS** (Outlook for Mac + documented browser). Windows port is post-MVP.

### Phase 5 — de-risk order

```
5.5 smoke (Outlook only) → 5.6 handoff → 5.7 full flow → 5.9 three runs → 5.10 release
```

---

## Phase 6 — SDK & developer experience

**Goal:** Embeddable library, not only CLI.

| # | Task | Size | Status |
|---|------|------|--------|
| 6.1 | Python API: `Session`, `session.find()`, `session.click()`, `session.run(steps)` | M | ☑ |
| 6.2 | Publish to PyPI as `off-camber-open-frame` | S | ☑ |
| 6.3 | `docs/API.md` — core types and examples | M | ☑ |
| 6.4 | `docs/CONTRIBUTING.md` — dev setup, test capture permissions on macOS | S | ☑ |
| 6.5 | Recognizer plugin example in `examples/custom_recognizer/` | M | ☑ |

**Exit criteria:** Third party can register a custom recognizer without forking core.

---

## v0.2 checkpoint — Interface-first integration

**Goal:** Keep Open Frame as a deterministic execution engine and expose it to LLMs through a compact MCP-facing interface.

| # | Task | Size | Status |
|---|------|------|--------|
| C.1 | Publish checkpoint brief in [V0_2_0_CHECKPOINT.md](V0_2_0_CHECKPOINT.md) | S | ☑ |
| C.2 | Document LLM ↔ MCP ↔ engine boundary in [ARCHITECTURE.md](ARCHITECTURE.md) | S | ☑ |
| C.3 | Define MCP MVP tools + JSON response contract in docs | M | ☑ |
| C.4 | Define `v0.2.0` release gates focused on context reduction + reliability | S | ☑ |
| C.5 | Defer full Phase 7 implementation until checkpoint gates pass | S | ☑ |
| C.6 | Freeze MCP contract identifier + per-tool arg/error metadata | S | ☑ |
| C.7 | Add MCP contract tests for envelope shape and validation failures | S | ☑ |
| C.8 | Run a repeatability benchmark for representative MCP flows | M | ☑ |

**Exit criteria:** A clear `v0.2.0` interface plan exists and Phase 7 remains gated behind interface stabilization.

---

## Phase 7 — Vision recognizer

**Status:** deferred until `v0.2.0` interface checkpoint gates are met.

**Goal:** Natural-language / semantic find ("the settings gear icon").

| # | Task | Size | Status |
|---|------|------|--------|
| 7.1 | Vision recognizer interface; optional deps extra `[vision]` | S | ☐ |
| 7.2 | **Local:** Ollama integration · **Cloud:** API backend (OpenAI / Anthropic / etc.) — pluggable; cloud requires explicit opt-in flag | L | ☐ |
| 7.3 | Return bounding box from model output (structured JSON) | M | ☐ |
| 7.4 | Cost/latency guards: cache frame hash, max calls per run | M | ☐ |
| 7.5 | Document privacy: screenshots sent to API only with explicit flag | S | ☐ |

**Exit criteria:** `find --vision "blue Submit button"` works on a non-a11y surface.

---

## Phase 8 — Template recognizer & hybrid tuning

| # | Task | Size | Status |
|---|------|------|--------|
| 8.1 | Template match recognizer (OpenCV) | M | ☐ |
| 8.2 | Save/load template from user snippet | S | ☐ |
| 8.3 | Tune default recognizer order per platform | M | ☐ |
| 8.4 | Benchmark doc: accuracy/latency per recognizer on sample apps | L | ☐ |

---

## Phase 9 — Windows port

| # | Task | Size | Status |
|---|------|------|--------|
| 9.1 | Abstract `PlatformCapture`, `PlatformAct`, `PlatformA11y` | M | ☐ |
| 9.2 | Windows capture (Win32 / DXGI) | L | ☐ |
| 9.3 | Windows UI Automation recognizer | L | ☐ |
| 9.4 | Windows input (SendInput) | M | ☐ |
| 9.5 | CI matrix: macOS + Windows | M | ☐ |

---

## Phase 10 — Ecosystem & RPA buyer story

| # | Task | Size | Status |
|---|------|------|--------|
| 10.1 | One-pager PDF/markdown: vs proprietary RPA recognition layer | S | ☐ |
| 10.2 | Integration example: call from Python agent / n8n / Temporal activity | M | ☐ |
| 10.3 | Full multi-tenant MCP server productization (beyond local adapter) | M | ☐ |
| 10.4 | Blog post on Off-Camber site; link from `projects.json` | S | ☐ |
| 10.5 | Linux capture spike (document blockers if any) | L | ☐ |

---

## Phase 11 — Window-level state awareness

Motivation: some screen states cannot be distinguished by OCR text alone. For
example, an open Outlook compose window vs. the main screen with a message
selected both show "To:", so a `text-gone:"To"` guard is unreliable (validated
live, 2026-06). Reliable state guards and recovery need to know *which window
and role is frontmost*, not just what text is visible. See
[FLOW_SETUP.md](FLOW_SETUP.md) "State guards vs. recovery".

**Whole-screen OCR scope hazard (validated live, 2026-06):** OCR clicks match
text *anywhere on the display*, including the IDE/chat window that is driving
the run. A `click "Subject"` step matched the word "Subject" in the controlling
chat transcript, stole focus to that window, and routed subsequent keystrokes
there instead of the target app. Generic-label OCR clicks ("Subject", "Send",
"To", "Attach") are unsafe whenever another window shows the same word. The
durable fix is window-scoped recognition so OCR only considers the target app's
window; until then, prefer keyboard navigation for field focus (keystrokes go
to the frontmost app and cannot leak to other windows).

| # | Task | Size | Status |
|---|------|------|--------|
| 11.1 | Expose frontmost window title/role via macOS accessibility (extend `_frontmost_app_name`) | M | ☐ |
| 11.2 | Add `window-title-contains` / `window-role` verify specs | M | ☐ |
| 11.3 | Optional `window` field on guard steps to assert frontmost window before acting | S | ☐ |
| 11.4 | Document guard-signal selection: prefer window-aware checks over fragile OCR tokens | S | ☐ |
| 11.5 | Windows parity for window-state queries (after Phase 9) | M | ☐ |
| 11.6 | Constrain OCR/find/click to the target app window bounds (avoid matching the controlling IDE/chat or other windows) | M | ☐ |

**Note:** This is engine-side state *reporting*, not branching/recovery.
Choosing a different action based on the reported state remains an agent-mode
responsibility (keeps flows linear; preserves the engine/agent boundary).

---

## Suggested order of work

```
Weeks 1–2   Phase 0–1 (foundation + capture)
Weeks 3–4   Phase 2–3 (recognize + act)
Week 5      Phase 4 (verify + run artifacts)
Weeks 6–8   Phase 5 smoke → handoff → full MVP flow
Week 9+     Phase 6 + v0.2 checkpoint (MCP/interface), then Phase 7+
```

MVP is **macOS-only**; Windows backends follow after v0.1.0 ([DECISIONS.md](DECISIONS.md)).

---

## Open questions (resolve before or during Phase 2)

| Question | Options | Decide by |
|----------|---------|-----------|
| ~~Vision provider (Phase 7)~~ | **Locked:** Ollama + cloud opt-in | — |
| ~~MCP integration direction~~ | **Locked:** MCP-first interface in v0.2; broader server productization later | — |

Track decisions in [DECISIONS.md](DECISIONS.md).

---

## How to use this doc

- Check boxes as tasks complete (`☐` → `☑` or `[x]` in git)
- Split large tasks into GitHub issues linked from here
- Update **Current phase** at the top when exiting criteria met
- Don't start full Phase 7 implementation until v0.2 interface checkpoint gates pass
