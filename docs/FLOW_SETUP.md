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
- `click` (`query`, optional `anchor`, `click_kind`, `timeout_ms`, `poll_ms`)
- `type` (`text`, optional `interval`)
- `key` (`key` or `combo`)
- `fill` (`query`, `text`, optional `clear`, `timeout_ms`, `poll_ms`)
- `attach` (`path`, optional `submit_key`)
- `navigate` (`url`)
- `wait` (`ms`)
- `verify` (`spec` or `specs`, optional `timeout_ms`, `poll_ms`)
- `find` (`query`, optional `timeout_ms`, `poll_ms`)
- `capture` (optional `out`)

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

### 4) Add fallbacks for brittle points

When a step is known to be sensitive, maintain two flow variants:

- primary path (preferred primitive)
- fallback path (alternative primitive or query wording)

At the orchestration layer (script/agent), run primary first, then fallback only on failure.

### 5) Keep queries specific and app-aware

For text-driven matching, avoid broad labels like `"New"` when multiple matches are possible. Use narrower terms that reflect the target app surface.

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
