# Vision

## One-line pitch

**Open Frame** is the open-source engine for recognizing and interacting with anything visible on a display.

## The problem

Proprietary RPA platforms charge heavily for a capability that boils down to:

1. **Capture** what is on screen
2. **Recognize** a target (text, image, semantic description)
3. **Act** (click, type, scroll, drag)
4. **Verify** the action worked

That layer is often locked behind per-bot licensing, opaque recognizers, and selectors that break when UIs change.

## What we're building

A **composable platform** others can clone, extend, and embed — not a full enterprise RPA suite on day one.

| In scope (core) | Out of scope |
|-----------------|--------------|
| Display capture (window, monitor, region) | Orchestration / scheduling |
| Pluggable recognizers (a11y, OCR, template, vision) | MFA / SSO / login automation |
| Actions with evidence (screenshots, logs) | Credential vaults, identity providers |
| Flow runner + verification | Full visual workflow designer |
| CLI + library SDK | Full parity with enterprise suites on day one |

## Audience

1. **RPA buyers** looking for a self-hosted, open recognition/action layer
2. **Developers** building agents, test automation, or accessibility tools
3. **Contributors** who want a clear recognizer plugin model

## Design principles

1. **Display-first** — work on what's rendered, not how the app was built (web, native, game, PDF, RDP, terminal).
2. **Hybrid recognition** — try fast/deterministic strategies first (accessibility, OCR), fall back to vision when needed.
3. **Prove every action** — capture before/after state; fail loudly with artifacts for debugging.
4. **Pluggable by default** — recognizers and actuators are swappable; core stays thin.
5. **Clone-friendly** — clear docs, minimal magic, sensible defaults for a fork.

## Success criteria

Full MVP definition: **[MVP goalpost](MVP_GOALPOST.md)**.

### MVP (v0.1.0) — the bar

A **declarative flow** runs repeatedly on a prepared desktop and automates a **multi-app RPA journey**:

**Outlook (desktop) → Microsoft 365 (web) → create document(s) → compose email with attachment → send**, with step verification and the **same outcome on every run** (within documented environment assumptions).

See the reference flow, acceptance checklist, and scope boundaries in [MVP_GOALPOST.md](MVP_GOALPOST.md).

### Before MVP — engine milestones

Incremental proof on the way to the goalpost:

- Capture, find (a11y + OCR), act, verify on a **single app**
- App focus and handoff between **two apps**
- Flow runner executing an ordered step list with variables

### v1 — usable platform

- Stable CLI and Python SDK
- Documented flow format and recognizer plugins
- **Windows** capture/a11y/act backends — same YAML flows as macOS MVP
- Reference flow validated on Windows for enterprise RPA deployments

### v2 — ecosystem

- Vision/VLM recognizer — **Ollama default + cloud opt-in** (Phase 7, post-MVP); not primary for determinism
- MCP server — **deferred** past MVP/v1
- Linux capture; contributor recognizers
- Off-Camber blog / materials for RPA buyers evaluating open source

## Non-goals

- Competing with n8n, Temporal, or MSP stacks on orchestration
- Shipping a hosted SaaS
- Claiming full parity with mature enterprise suites on day one
- **Automating MFA, SSO, or login** — flows assume an authenticated desktop; see [DECISIONS.md](DECISIONS.md)
