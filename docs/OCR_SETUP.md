# OCR setup (Tesseract)

Phase 2 OCR uses Python bindings plus the system `tesseract` binary.

## Install Python extras

```bash
pip install -e .[ocr]
```

## Install `tesseract` on macOS

```bash
brew install tesseract
```

## Quick check

```bash
open-frame find "Submit" --frame path/to/frame.png --json
```
