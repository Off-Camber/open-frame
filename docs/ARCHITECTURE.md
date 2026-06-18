# Architecture

## Session & flow runner (MVP)

Above single steps, a **Flow** is an ordered list of steps with variables — the unit RPA authors care about. See [MVP_GOALPOST.md](MVP_GOALPOST.md).

```
Flow file (YAML)
    → FlowRunner
        → for each step: focus app → capture → locate → act → verify
        → on failure: write runs/<run_id>/<step_id>/ artifacts, exit non-zero
```

| Step kind (MVP) | Purpose |
|-----------------|--------|
| `app` | Focus window by process name / title |
| `click` | Find target, click |
| `type` / `fill` | Keyboard input into fields |
| `navigate` | Browser URL (optional dedicated browser module) |
| `attach` | File path into Outlook compose |
| `wait` | Time or until verify predicate |
| `verify` | Assert; fail run if not met |

**Repeatability** comes from deterministic recognizers + explicit waits + verify — not from AI guessing each run.

---

## Core loop

Every automation step follows the same loop:

```
┌──────────┐    ┌────────────┐    ┌─────────┐    ┌──────────┐
│ Capture  │───▶│ Recognize  │───▶│   Act   │───▶│  Verify  │
│ (frame)  │    │ (locate)   │    │ (input) │    │ (proof)  │
└──────────┘    └────────────┘    └─────────┘    └──────────┘
      ▲                                                    │
      └──────────────── retry / next step ─────────────────┘
```

**Frame** = one snapshot of display content at a point in time (image + optional metadata).

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│  CLI / SDK / (future: REST; MCP deferred post-v1)           │
├─────────────────────────────────────────────────────────────┤
│  Session & workflow  —  sequences of steps, artifacts       │
├─────────────────────────────────────────────────────────────┤
│  Verify              —  diff, predicate, timeout            │
├─────────────────────────────────────────────────────────────┤
│  Act                 —  click, type, scroll, drag, wait     │
├─────────────────────────────────────────────────────────────┤
│  Locate              —  merge recognizer results → Target   │
├─────────────────────────────────────────────────────────────┤
│  Recognizers         —  a11y | OCR | template | vision      │
├─────────────────────────────────────────────────────────────┤
│  Capture             —  screen, window, region, cursor      │
└─────────────────────────────────────────────────────────────┘
```

## Key types (conceptual)

| Type | Description |
|------|-------------|
| `Frame` | Image (PNG/raw) + dimensions, scale factor, timestamp, source (monitor/window id) |
| `Target` | Bounds (x, y, w, h), confidence, source recognizer, optional label/text |
| `Action` | Kind (click, type, key, scroll), parameters, target or coordinates |
| `StepResult` | success, before/after frames, error, duration |
| `Recognizer` | Plugin: `find(frame, query) -> list[Target]` |
| `Verifier` | Plugin: `check(before, after, expectation) -> bool` |

## Recognizer strategy order (default)

Run recognizers in priority order; stop when confidence exceeds threshold:

1. **Accessibility** — OS a11y tree (fast, precise when available)
2. **OCR** — text search in frame (broad, works on anything readable)
3. **Template** — image patch match (deterministic, brittle to theme/scale)
4. **Vision** — VLM / description ("the blue Submit button") — slow, flexible

Callers can override order and thresholds per step.

## Coordinate spaces

Must handle consistently:

- **Logical vs physical pixels** (Retina / HiDPI)
- **Window origin** vs **screen origin**
- **Multi-monitor** layouts

All public APIs should use **screen coordinates** with documented conversion from window-local captures.

## Module layout (proposed)

```
open-frame/
├── docs/
├── src/openframe/           # Python package (proposed)
│   ├── capture/
│   ├── recognize/
│   │   ├── base.py
│   │   ├── a11y/
│   │   ├── ocr/
│   │   ├── template/
│   │   └── vision/
│   ├── act/
│   ├── verify/
│   ├── session.py
│   └── types.py
├── cli/                     # open-frame entrypoint
├── examples/
└── tests/
```

Package publish name: `@off-camber/open-frame` or PyPI `off-camber-open-frame` (avoid bare `openframe` on npm — taken).

## Extension points

| Extension | Interface sketch |
|-----------|------------------|
| Recognizer | `name`, `priority`, `find(frame, query, options) -> RecognizerResult` |
| Actuator | `execute(action, target) -> None` (platform-specific) |
| Verifier | `verify(before, after, spec) -> VerifyResult` |
| Capture backend | `grab(source: CaptureSource) -> Frame` |

## Platform plan

| Phase | Platform |
|-------|----------|
| **MVP (v0.1)** | **macOS** — full engine + reference flow |
| **v1** | **Windows** — port capture/a11y/act; reuse YAML flows |
| **v2** | Linux (X11/Wayland — capture complexity) |

Design capture/a11y/act as **backends behind interfaces** from day one so Windows is a second implementation, not a rewrite.

Remote desktop (Citrix, RDP) is a **recognizer/capture problem** later — same loop, different capture source.

## Observability

Every step should emit structured artifacts:

- `before.png`, `after.png`
- `step.json` (query, targets found, action, timing, success)
- Optional trace directory per run for CI and debugging

## Security note

This engine can control the user's machine. Document clearly:

- Runs with user privileges
- **Does not** automate login, MFA, or SSO — operator must establish sessions before a run
- No silent network exfil of screenshots by default
- Explicit opt-in for cloud vision APIs
