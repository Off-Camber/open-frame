# Capture Manual Test (macOS)

Use this checklist to validate live capture behavior on a real desktop.

## Preconditions

- macOS with Screen Recording permission granted to the terminal or IDE running `open-frame`
- At least one visible application window
- Project virtualenv installed (`pip install -e .[dev]`)

## Commands

```bash
# Full primary display
open-frame capture --out artifacts/screen.png

# Named window capture (adjust title to an open app)
open-frame capture --out artifacts/window.png --window-title "Outlook"

# Region capture
open-frame capture --out artifacts/region.png --x 100 --y 200 --width 700 --height 400

# Discover ids and displays
open-frame list-windows --json --displays
```

## Expected Results

- Each capture command exits with code 0 and prints the output PNG path
- `screen.png` is a full display frame and opens successfully
- `window.png` contains only the selected app window
- `region.png` contains the requested crop area
- `list-windows --json --displays` returns valid JSON with `windows` and `displays` keys
