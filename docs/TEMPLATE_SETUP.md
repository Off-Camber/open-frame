# Template matching (icon / image recognition)

Open Frame can locate non-text UI by matching a cropped template image against
the current frame (normalized cross-correlation, with a flat-template fallback).

## Install

```bash
pip install -e ".[template]"
# or with other extras:
pip install "off-camber-open-frame[template,ocr,act,flow]"
```

## Usage

CLI:

```bash
open-frame find "icon" --template ./my-icon.png --frame screen.png --json
open-frame click "icon" --template ./my-icon.png --dry-run
```

Flow YAML (`find` / `click` / `fill` steps):

```yaml
- id: click-icon
  kind: click
  query: "icon"
  template: examples/flows/template-icon-probe/icon-template.png
  selector: first
```

Run with `open-frame run … --dry-run` when you want actuation safety.

MCP `find` / `click` accept optional `template` and `template_threshold`.

Without `template`, recognition stays a11y + OCR only.

## Tips

- Crop the template from a capture at the same display scale (Retina 2x crop
  for a 2x frame). Prefer crops with visual structure (edges/contrast); solid
  color rectangles still match via the MAD fallback, but icons work better.
- Default match threshold is `0.88` (`--template-threshold` / `template_threshold`).
- Multiple matches fail closed for click/fill unless you pass `selector` or
  `expect_one`.

See also: [examples/flows/template-icon-probe](../examples/flows/template-icon-probe/).
