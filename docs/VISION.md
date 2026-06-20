# Vision

## One-line pitch

**Open Frame** is the open-source engine for recognizing and interacting with anything visible on a display.

Open Frame is the deterministic desktop execution layer behind AI agents, not the agent itself.

## The problem

Proprietary RPA platforms charge heavily for a capability that boils down to:

1. **Capture** what is on screen
2. **Recognize** a target (text, image, semantic description)
3. **Act** (click, type, scroll, drag)
4. **Verify** the action worked

That layer is often locked behind per-bot licensing, opaque recognizers, and selectors that break when UIs change.

## What we're building

A **composable platform** others can clone, extend, and embed — not a full enterprise RPA suite on day one.

### Product boundary: engine vs assistant UX

- Open Frame is an execution engine with deterministic primitives and run artifacts.
- External assistants/agents provide planning, interpretation, and high-level user conversation.
- Open Frame's job is to keep execution reliable, compact, and auditable regardless of which model is upstream.

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

## Current state

`v0.1.x` proved the deterministic core:

- capture, find, act, verify primitives
- declarative YAML flow execution
- run artifacts for failure debugging
- SDK + packaging for reuse

Detailed `v0.1` milestone criteria are documented in
[MVP_GOALPOST.md](MVP_GOALPOST.md) for historical context.

### v0.2 — agent integration layer (current)

- MCP adapter integration surface for deterministic tool calls
- Compact structured tool responses + artifact-first debugging
- Phase 7 vision remains gated until interface metrics pass

### v1 — usable platform

- Stable CLI and Python SDK
- Documented flow format and recognizer plugins
- **Windows** capture/a11y/act backends — same YAML flows as macOS MVP
- Reference flow validated on Windows for enterprise RPA deployments

### v2 — ecosystem

- Vision/VLM recognizer — **Ollama default + cloud opt-in** (Phase 7, post-MVP); not primary for determinism
- Linux capture; contributor recognizers
- Off-Camber blog / materials for RPA buyers evaluating open source

## Non-goals

- Competing with n8n, Temporal, or MSP stacks on orchestration
- Shipping a hosted SaaS
- Claiming full parity with mature enterprise suites on day one
- **Automating MFA, SSO, or login** — flows assume an authenticated desktop; see [DECISIONS.md](DECISIONS.md)
