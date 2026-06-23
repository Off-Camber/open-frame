# Verify setup

Phase 4 verification is available through `open-frame click --verify ...`.

## Verification specs

- `text-gone:"Save"`: succeeds when text is no longer found after click
- `text-appeared:"Done"`: succeeds when text is found after click
- `target-gone:"Dialog"`: succeeds when query is no longer found
- `diff:0.15`: succeeds when screenshot diff ratio is at or below threshold
- `window-title-contains:"Compose"`: succeeds when the frontmost window title contains the value
- `window-role:"AXWindow"`: succeeds when the frontmost window role matches
- `window-app:"Microsoft Outlook"`: succeeds when the frontmost window belongs to the named app

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
