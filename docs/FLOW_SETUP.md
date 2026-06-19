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
