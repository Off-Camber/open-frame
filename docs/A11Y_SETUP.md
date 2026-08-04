# Accessibility recognizer setup (macOS)

The macOS accessibility recognizer reads UI elements from the frontmost app through `System Events`.

## Grant Accessibility permission

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Enable access for the app running `open-frame` (Terminal, iTerm, or Cursor)

## Quick check

```bash
open-frame find "Submit" --json
```

Targets should include non-zero `width`/`height`. If every element has zero
bounds, Accessibility permission or AX parsing is broken.

If permission is missing, the recognizer returns no AX matches and OCR remains as fallback.

The local live gate includes an accessibility bounds check:

```bash
./scripts/macos_live_gate.sh
```
