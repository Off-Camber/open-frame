# OCR setup (Tesseract)

Phase 2 OCR uses Python bindings plus the system `tesseract` binary.

## Install Python extras

```bash
pip install -e ".[ocr]"
```

## Install `tesseract` on macOS

```bash
brew install tesseract
```

`pytesseract` is the Python wrapper; OCR will still fail unless the
system `tesseract` binary is installed and on your PATH.

## Quick check

```bash
open-frame find "Submit" --frame path/to/frame.png --json
```
