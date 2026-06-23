# Flow setup

Phase 5 introduces YAML flow execution with `open-frame run`.

## Install flow dependency

```bash
pip install -e .[flow]
```

## Minimal flow example

```yaml
name: smoke
steps:
  - id: wait-briefly
    kind: wait
    ms: 250
```

Run it:

```bash
open-frame run flow.yaml --dry-run --json
```

## Supported step kinds (current)

- `app` (`name`)
- `click` (`query`, optional `anchor`, `click_kind`, `expect_one`, `selector`, `timeout_ms`, `poll_ms`)
- `click_point` (`x_ratio`+`y_ratio` or `x`+`y`, optional `click_kind`)
- `type` (`text`, optional `interval`)
- `key` (`key` or `combo`)
- `fill` (`query`, `text`, optional `clear`, `expect_one`, `selector`, `timeout_ms`, `poll_ms`)
- `attach` (`path`, optional `submit_key`)
- `write_file` (`path`, `content`)  
- `navigate` (`url`)
- `wait` (`ms`)
- `verify` (`spec` or `specs`, optional `timeout_ms`, `poll_ms`, `match_bounds`)
- `find` (`query`, optional `timeout_ms`, `poll_ms`)
- `capture` (optional `out`)

`click_point` clicks a position when there is no text target to match (for
example, focusing an empty document canvas). Prefer `x_ratio`/`y_ratio` (0.0–1.0
of the screen) over absolute `x`/`y` so flows survive different display sizes.
Coordinates are interpreted in logical screen points; the engine handles
Retina/physical-pixel scaling internally.

`verify` accepts an optional `match_bounds` map to scope where a text match
counts, which prevents false positives from the same text appearing elsewhere
on screen:

```yaml
match_bounds:
  left_of_query: "From"   # only count matches left of the "From" label
  margin: 40
  # also supported: min_x / max_x / min_y / max_y (logical pixels),
  # min_x_ratio / max_x_ratio (0.0–1.0 of frame width)
```

`timeout_ms` and `poll_ms` let query/verify steps retry briefly for dynamic UI updates before failing.

## Flow authoring strategy (for unknown app flows)

Open Frame does not need hardcoded logic for each app. It stays general by combining primitives with verification and fallback steps.

### 1) Choose the most stable primitive first

For each intent, prefer the most deterministic control path available:

1. `key` / `combo` (app shortcuts, menu accelerators)
2. `fill` on known fields
3. `click` by visible text/target
4. `type` only after focus is explicitly established

If more than one primitive can achieve the same intent, start with the one least sensitive to UI layout changes.

### 2) Verify after state-changing actions

After actions that change screen state (`click`, `key`, `navigate`, `attach`), add a `verify` step with a clear predicate:

- `text-appeared:"..."`
- `text-gone:"..."`

This keeps failures explicit and diagnosable in artifacts.

### 3) Use retries for dynamic UI

For `click`, `find`, `fill`, and `verify`, set `timeout_ms` and `poll_ms` when UI may take time to render.

This is preferred over hardcoding long `wait` steps.

### 3b) Fail fast on ambiguous targets

Set `expect_one: true` on `click` and `fill` when the step should only ever match one element.

If multiple matches exist, the runner fails with `ambiguous_target` so the agent/orchestrator can disambiguate instead of guessing.

When you intentionally allow multiple matches, you can set a deterministic `selector` (on `click` and `fill`):

- `first` (default)
- `top_most`
- `left_most`
- `right_most`
- `highest_confidence`

### 4) Add fallbacks for brittle points

When a step is known to be sensitive, maintain two flow variants:

- primary path (preferred primitive)
- fallback path (alternative primitive or query wording)

At the orchestration layer (script/agent), run primary first, then fallback only on failure.

### 5) Keep queries specific and app-aware

For text-driven matching, avoid broad labels like `"New"` when multiple matches are possible. Use narrower terms that reflect the target app surface.

### 5b) Avoid generic OCR label clicks across windows

OCR matching currently scans the visible screen. If another window also contains
the same word (for example `"Subject"`, `"Send"`, `"Attach"`, `"To"`), a `click`
step can target the wrong app.

For compose-style forms, prefer keyboard field navigation (`tab`, shortcuts) once
the target app is frontmost. This keeps text entry deterministic and avoids
cross-window focus theft from generic labels.

### 5c) Use window-aware guards and scoping (Phase 11)

When a state cannot be expressed as a reliable visible signal, lean on
window-level checks instead of inventing a fragile OCR token. Two primitives
are available:

- **Window guard** on a step asserts the frontmost window before acting:

  ```yaml
  - id: type-recipient
    kind: type
    text: "{{recipient}}"
    window:
      app: "Microsoft Outlook"
      title_contains: "Message"
  ```

  If the frontmost window does not match the spec, the step fails fast with
  `window guard failed: ...` rather than typing into the wrong app.

- **Window-scoped recognition** confines OCR/find to the frontmost window's
  bounds, so `"Subject"` in another window cannot satisfy the query:

  ```yaml
  - id: click-send
    kind: click
    query: "Send"
    scope: window
  ```

  Both `click`, `find`, `fill`, and `verify` accept `scope: window`.

- **Window verify specs** let you assert the active window directly:

  - `window-title-contains:"Compose"`
  - `window-role:"AXWindow"`
  - `window-app:"Microsoft Outlook"`

Prefer these over OCR-token guards whenever the distinction you care about is
"which window is frontmost" rather than "is this text visible somewhere."

### Example pattern

```yaml
name: compose-stable
steps:
  - id: focus-outlook
    kind: app
    name: "Microsoft Outlook"

  - id: open-compose
    kind: key
    combo: [command, n]

  - id: wait-compose
    kind: verify
    timeout_ms: 2500
    poll_ms: 250
    specs:
      - 'text-appeared:"To"'
```

This approach keeps the engine deterministic while still allowing user-defined and novel flows.

## Outcome confidence model

A flow step can succeed without proving the business outcome you care about. Treat verification in two layers:

- **Step success:** primitive executed and local verify passed.
- **Business outcome success:** external state actually changed (mail sent, record created, file visible, etc.).

For outcome-critical flows, verify a unique run token in the destination surface (for example a subject containing `{{run_id}}` in `Sent Items`) instead of relying only on transient toast text.

## State guards vs. recovery

Open Frame separates two responsibilities, and flows should only take on the first:

- **Guarding (flow's job):** before a state-changing step, confirm the screen
  matches what the step assumes. If it does not, fail explicitly. This is
  linear — it never branches or chooses an alternative action.
- **Recovery / branching (agent's job):** observe the actual state, decide how
  to get back on track, and pick a different action. This is deliberately
  **not** a flow feature.

The engine's contract is to interact reliably and report state truthfully.
Recovering from an unexpected state is the responsibility of an orchestrating
agent (or, until agent mode exists, a human reading the failure). Keeping
branching out of flows is what preserves the engine/agent split and keeps the
LLM context window small.

### A good guard: app focus

The `app` step is a reliable precondition guard. After activating an app it
verifies the app is actually frontmost and fails otherwise, so later steps
never run against the wrong window:

```yaml
- id: focus-outlook
  kind: app
  name: "Microsoft Outlook"
```

### Choosing a guard signal (and when you can't)

A guard is only as good as the signal you pick, and some states cannot be
distinguished by a single visible token. The `command+n` case is a concrete
example.

A step like `key combo: [command, n]` silently assumes "no compose window is
open." If one already is, `command+n` does not open a new message — it types
`n` into whatever field has focus. The engine executed the keypress correctly;
the flow was wrong about the world.

The tempting guard is `text-gone:"To"` before `command+n` (if compose is open,
"To" should be visible). **This does not work for Outlook.** Outlook's reading
pane always shows "To:" for the currently selected message, so "To" is on the
main screen too — the guard would block the normal happy path on every run.
There is no cheap single OCR token that separates "compose open" from "main
screen with a message selected."

The lesson: when a state cannot be expressed as a reliable visible signal, do
**not** invent a fragile one. That detection needs window-level awareness (which
window/role is frontmost) — a capability that belongs to agent mode or a future
engine primitive, not an OCR-text guard. Until then, rely on the focus guard
above and on truthful outcome verification (see "Outcome confidence model"), and
let a human or agent handle the rarer "already mid-task" states.

> Anti-pattern: do not grow flows into `if open then skip / else create`
> decision trees, and do not ship a guess-y guard signal just to have one.
> Nested conditionals and unreliable guards reinvent agent logic inside YAML,
> make flows brittle, and erode the engine/agent boundary. Keep flows
> linear, guard only on signals you can trust, and defer real recovery to the
> agent layer.

## Calibration flow (run this first on new environments)

Before running complex cross-app flows, run a calibration flow that checks an undeniable visible effect:

```bash
open-frame run examples/flows/calibration-token/flow.yaml --json
```

The calibration flow writes a unique token (`OF-CAL-{{run_id}}`) into TextEdit and verifies that token appears on screen.

If calibration fails, pause and fix environment/setup (permissions, focus behavior, recognizer setup) before trusting higher-level flow results.

## Split complex flows during debugging

When a full multi-app flow fails repeatedly, split it into outcome-specific flows first:

- `examples/flows/word-create-only/flow.yaml` (prove Word document creation marker appears)
- `examples/flows/outlook-send-only/flow.yaml` (prove sent-mail marker appears in `Sent`)
- `examples/flows/doc-attach-email/flow.yaml` (prove local artifact handoff into Outlook attachment + send)

Run each independently, then recombine into the larger end-to-end flow.

## Variable substitution

Template placeholders are resolved in step params:

- `{{run_id}}`
- `{{run_dir}}`
- `{{step_id}}`
- `{{step_kind}}`
- `{{step_artifact_dir}}` (alias: `{{artifact_dir}}`)
- any key from flow `variables`

Example:

```yaml
name: templated
variables:
  subject: Hello
steps:
  - id: type-subject
    kind: type
    text: "Subject: {{subject}} (run {{run_id}})"
```
