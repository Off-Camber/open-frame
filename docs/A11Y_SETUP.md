# Accessibility recognizer setup (macOS)

The macOS accessibility recognizer reads UI elements from the frontmost app through `System Events`.

## Grant Accessibility permission

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Enable access for the app running `open-frame` (Terminal, iTerm, or Cursor)

## Quick check

```bash
open-frame find "Submit" --json
```

If permission is missing, the recognizer returns no AX matches and OCR remains as fallback.
