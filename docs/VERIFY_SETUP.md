# Verify setup

Phase 4 verification is available through `open-frame click --verify ...`.

## Verification specs

- `text-gone:"Save"`: succeeds when text is no longer found after click
- `text-appeared:"Done"`: succeeds when text is found after click
- `target-gone:"Dialog"`: succeeds when query is no longer found
- `diff:0.15`: succeeds when screenshot diff ratio is at or below threshold

## Example

```bash
open-frame click "Save" --verify 'text-gone:"Save"' --json
```

On every verified click, artifacts are written to:

```text
runs/<run_id>/click/
  before.png
  after.png
  step.json
```
