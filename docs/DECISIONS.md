# Decisions

Log of significant project decisions. Add a row when something is locked in.

Format: **Date · Decision · Rationale**

---

## Locked in

### Project identity

| Decision | Rationale |
|----------|-----------|
| **Product name:** Open Frame | Display/frame metaphor; "open" signals OSS. Repo under Off-Camber, not a standalone company (yet). |
| **GitHub:** `off-camber/open-frame` | Org = identity; repo = project. Matches local folder `open-frame`. |
| **Not using:** UI, Path, Vector, Traverse as product name | Trademark / namespace / collision risk (see naming discussions). |

### Scope

| Decision | Rationale |
|----------|-----------|
| **Display-first**, not UI-tree-first | Apps, games, legacy, PDFs, RDP — anything on screen. |
| **Core loop:** capture → recognize → act → verify | Same primitive enterprise RPA tools depend on; keep core thin. |
| **MVP goalpost** | Declarative flow: Outlook → M365 web → create doc → email; repeatable. See [MVP_GOALPOST.md](MVP_GOALPOST.md). |
| **MVP auth scope** | **Sessions must exist before run starts.** Human completes login/MFA/SSO once; bot runs on an authenticated desktop. Same practical model used across unattended RPA deployments. |
| **MFA / SSO automation** | **Permanent descope** — not Open Frame’s job; document prep steps instead. |
| **Platform strategy** | **MVP on macOS only**; Windows port after MVP (v1). Same YAML flows; OS-specific capture/a11y/act backends later. |
| **Not building** full RPA suite / orchestration in v0 | Flow runner + recognition layer; scheduling/credentials later. |

### Technical

| Decision | Rationale |
|----------|-----------|
| **Language:** Python **3.11+** (minimum 3.11) | Project targets 3.11; `requires-python = ">=3.11"` in packaging. |
| **Package name:** `openframe` (import) / PyPI `off-camber-open-frame` | Avoid npm-style `openframe` collision on PyPI if needed. |
| **License:** Apache 2.0 | Free to use, modify, and self-host; enterprise-friendly patent grant. See [LICENSE](../LICENSE). |
| **Recognizer order default:** a11y → OCR → template → vision | Fast/deterministic first; expensive AI last. |
| **OCR backend:** Tesseract (via `pytesseract`) | Lightweight, fast on CPU, Apache 2.0; pair with a11y for Outlook/MVP. System binary required — document install per OS. |
| **Flow format:** YAML | Declarative, readable for RPA authors; matches MVP goalpost examples; no code execution in flow files. |
| **MVP apps:** **New Outlook for Mac** + **Word Online** (browser) | Single documented UI target; matches goalpost (M365 web), not Legacy Outlook or Word desktop shortcut. |
| **Vision provider (post-MVP):** **Both** — local (Ollama) default + cloud API opt-in | Self-hosted story first; cloud behind explicit flag for hard targets. Not required for MVP. |
| **MCP integration strategy:** MCP-first for `v0.2.0` | Open Frame is positioned as deterministic engine infrastructure for external agents; MCP is the primary integration surface after MVP stabilization. |

---

## Pending

_None — all planned decisions locked for MVP scope. Revisit if scope changes._

---

## Rejected

| Idea | Why |
|------|-----|
| Product name "A Better Path" | Too close to an existing vendor's naming |
| Product name "Open Frame" as standalone company | OK as repo; risky as global product trademark |
| npm package `openframe` unscoped | Taken (digital art frame project) |
| Start with vision/VLM recognizer | Too slow/flaky for v0; prove loop with OCR/a11y first |
| MFA / SSO / identity login automation | Industry RPA usually assumes pre-authenticated sessions or separate identity tooling; out of scope for Open Frame |
| Credential vault / Azure AD login flows | Same — orchestration/identity layer, not screen recognition |
| MIT License | Chose Apache 2.0 for clearer patent language and enterprise adoption |
| EasyOCR as default OCR | Heavy PyTorch deps and slower; Tesseract sufficient with a11y-first chain; optional fallback later if needed |
| Python DSL as primary flow format | YAML better for non-developer RPA authors and matches declarative MVP; Python SDK for programmatic use instead |
| Windows-first MVP | macOS-only MVP chosen; Windows port after v0.1 for enterprise RPA deployments |
| Rust core + Python bindings | Python 3.11+ sufficient for MVP velocity; revisit if perf becomes bottleneck |
| Legacy Outlook for Mac (MVP) | New Outlook chosen; one UI target for repeatable flows |
| Word desktop / local .docx shortcut (MVP) | Word Online chosen; matches M365 web goalpost |
| Vision: local-only or cloud-only | Both: Ollama default + cloud API opt-in (Phase 7, post-MVP) |
| MCP server in MVP | Deferred for MVP only; integration resumed in `v0.2.0` checkpoint |

---

### 2026-06-14 — Vision: local + cloud (Phase 7)

**Decision:** Vision recognizer supports **both** backends: **Ollama (local) by default**, **cloud API opt-in** (explicit flag only).

**Rationale:** Matches self-hosted RPA positioning; cloud for harder targets when user accepts cost/privacy tradeoff. Still last in recognizer chain; not part of MVP.

**Alternatives considered:** Local-only — limits quality; cloud-only — bad for privacy/air-gap.

---

### 2026-06-14 — Phase 1 capture backend on macOS

**Decision:** For Phase 1 capture, use macOS native `screencapture` (Quartz-backed) as the initial backend; defer direct ScreenCaptureKit integration.

**Rationale:** Zero additional Python dependencies, stable behavior on macOS, and fast path to `open-frame capture --out ...` while the capture surface is still evolving.

**Alternatives considered:** Direct ScreenCaptureKit bridge now — modern but adds bridge complexity early; direct `CGWindowListCreateImage` pyobjc path now — workable but still introduces pyobjc dependency surface before we need window/region depth.

---

### 2026-06-14 — MCP deferred past MVP

**Decision:** **No MCP server for MVP.** Revisit after YAML runner + SDK are stable.

**Rationale:** MVP proves declarative flows first; defer agent-facing interface until core is proven.

**Alternatives considered:** MCP in MVP — rejected; minimal stub during MVP — rejected.

**Status:** Superseded by 2026-06-18 `v0.2.0` checkpoint (MCP-first interface strategy after MVP).

---

### 2026-06-14 — New Outlook + Word Online (MVP apps)

**Decision:** Reference flow uses **New Outlook for Mac** and **Word Online** in the browser (not Legacy Outlook, not Word desktop as a substitute).

**Rationale:** Matches MVP goalpost (Outlook → M365 web → email); one ribbon/layout to test against; Word Online exercises browser + web UI recognition.

**Alternatives considered:** Legacy Outlook — different UI; Word desktop/local file — easier but skips the hard part of the demo.

---

### 2026-06-14 — Python 3.11

**Decision:** Minimum Python version is **3.11** (`>=3.11`).

**Rationale:** Stable ecosystem for Tesseract, macOS automation, and YAML/CLI work; no benefit to requiring 3.12+ for MVP.

**Alternatives considered:** Rust core — deferred; 3.12/3.13 as minimum — unnecessary friction for contributors.

---

### 2026-06-14 — macOS-only MVP; Windows later

**Decision:** **MVP (v0.1.0)** is implemented and accepted on **macOS only**. **Windows** support follows after MVP (target v1 / Phase 9).

**Rationale:** Develop on the available platform first; prove the engine and reference flow end-to-end. YAML flows stay portable; Windows adds a second capture/a11y/act backend set.

**Alternatives considered:** Windows MVP acceptance for enterprise buyer parity — deferred until post-MVP port.

**MVP test stack:** Outlook for Mac + Chrome (or Safari) + Microsoft 365 in browser. Document one Outlook variant and macOS permissions (Screen Recording, Accessibility).

---

### 2026-06-14 — YAML flow format

**Decision:** Automation flows are defined in **YAML** files (e.g. `flow.yaml`).

**Rationale:** Readable, diff-friendly, familiar to RPA authors; separates process definition from engine code. Aligns with [MVP_GOALPOST.md](MVP_GOALPOST.md) reference flow.

**Alternatives considered:** Python DSL — more flexible but harder for buyers to review/approve; keep Python for SDK/scripts that *invoke* flows, not as the default flow language.

---

### 2026-06-14 — Tesseract OCR

**Decision:** Default OCR recognizer uses **Tesseract** (Python: `pytesseract` + system `tesseract` binary).

**Rationale:** Small install footprint, fast on CPU, fits repeatable RPA loops; works after accessibility when UI text must be read from pixels. Apache 2.0 aligns with project license.

**Alternatives considered:** EasyOCR — better on messy UI out of the box, but large PyTorch/model deps and slower; defer as optional plugin if Tesseract + a11y miss too often on M365 web.

---

### 2026-06-14 — Apache 2.0 license

**Decision:** Open Frame is licensed under **Apache License 2.0**.

**Rationale:** Free for everyone to use, modify, and self-host; familiar to enterprise RPA buyers; explicit patent grant for contributors and adopters.

**Alternatives considered:** MIT (simpler text, weaker patent section) — rejected in favor of Apache.

---

### 2026-06-14 — MFA / SSO descoped

**Decision:** Open Frame does not automate MFA prompts, SSO login, or identity provider flows — ever, not just for MVP.

**Rationale:** Proprietary RPA platforms generally expect an already-logged-in user session or enterprise-side identity setup (dedicated service accounts, conditional access exceptions, etc.). Competing on auth would distract from the core: see screen → act → verify.

**Alternatives considered:** Building MFA handlers for Outlook/M365 — rejected as high fragility, high security risk, and poor fit for an open recognition engine.

---

```markdown
### YYYY-MM-DD — Short title

**Decision:** …  
**Rationale:** …  
**Alternatives considered:** …
```
