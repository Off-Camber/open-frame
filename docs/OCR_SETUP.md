# OCR setup (Tesseract)

Phase 2 OCR uses Python bindings plus the system `tesseract` binary.

## Install Python extras

```bash
pip install "off-camber-open-frame[ocr]"
# from a clone of this repo:
pip install -e ".[ocr]"
```

## Install `tesseract` on macOS

```bash
tesseract --version
```

When that command is missing and this account can write to Homebrew:

```bash
brew install tesseract
```

`pytesseract` is the Python wrapper; OCR will still fail unless the
system `tesseract` binary is installed and on your PATH. When `brew` cannot
write to `/opt/homebrew/Cellar`, the account that owns Homebrew has to install
Tesseract. See [troubleshooting](TROUBLESHOOTING.md).

## Quick check

```bash
open-frame find "Submit" --frame path/to/frame.png --json
```

Default matching is whole-token / token-phrase. Short queries like `AC` will not
match longer words such as `actuation` unless you explicitly pass
`match_mode: substring`.

For release-style OCR evidence on macOS (including 5× calibration), run:

```bash
./scripts/macos_live_gate.sh
```
