# Template icon probe

Demonstrates opt-in template matching for an icon-only target (no readable
text on the glyph). OCR alone cannot find `icon`; template matching can.

## Offline (fixture frame)

```bash
pip install -e ".[template,ocr]"

# OCR miss for the icon query (may find unrelated text, but not the glyph):
open-frame find "icon" --frame examples/flows/template-icon-probe/scene.png --json

# Template hit:
open-frame find "icon" \
  --frame examples/flows/template-icon-probe/scene.png \
  --template examples/flows/template-icon-probe/icon-template.png \
  --json
```

Expect `source: "template:ncc"` and non-zero bounds near the glyph.

## Live (optional)

1. Open `scene.png` in Preview and leave it frontmost.
2. Capture + match against a live frame (Screen Recording required):

```bash
open-frame find "icon" \
  --template examples/flows/template-icon-probe/icon-template.png \
  --json
```

Scale must match: the committed crop is 1x logical pixels. On Retina, crop a
2x template from a live capture, or pass `--template-threshold` / scales as needed.
