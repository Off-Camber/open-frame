# Act Manual Test (macOS)

Use this runbook to validate the Phase 3 exit criteria safely on a real app.

## Preconditions

- macOS with:
  - Screen Recording permission for the app running `open-frame`
  - Accessibility permission for the app running `open-frame`
- Action dependencies installed:

```bash
pip install -e .[act]
```

- A visible app/window with a clickable text target (for example, a button labeled "OK")

## 1) Capture

```bash
open-frame capture --out artifacts/phase3-screen.png
```

Expected:
- Command exits with code 0
- PNG exists at `artifacts/phase3-screen.png`

## 2) Find

```bash
open-frame find "OK" --frame artifacts/phase3-screen.png --overlay-out artifacts/phase3-overlay.png --json
```

Expected:
- JSON contains `count >= 1`
- JSON includes at least one target with bounds
- Overlay file exists and shows a box around the target

## 3) Dry-run click

```bash
open-frame click "OK" --frame artifacts/phase3-screen.png --dry-run --json
```

Expected:
- JSON includes a click `point`
- No actual click is sent to the system

## 4) Live click (manual confirmation)

1. Focus the target window.
2. Run:

```bash
open-frame click "OK"
```

Expected:
- The target receives a real click.
- You manually confirm intended behavior in the app (for example, dialog closes).

## Exit Criteria Record

When done, record:
- App name/version
- macOS version
- Target text used
- Whether dry-run and live click both behaved as expected
