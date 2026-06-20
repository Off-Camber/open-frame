# Contributing

Thanks for contributing to Open Frame.

## Development setup

1. Use Python 3.11+.
2. Create and activate a local virtual environment:

```bash
python3 -m venv .venv311
source .venv311/bin/activate
```

3. Install in editable mode:

```bash
pip install -e .[dev,ocr,act,flow]
```

4. Use CLI via Python module if `open-frame` is not on PATH:

```bash
python -m openframe.cli mcp list-tools --json
```

5. Run tests:

```bash
pytest
```

6. Run lint:

```bash
ruff check .
```

## macOS permissions for live runs

Open Frame needs explicit permissions for real capture and input automation:

- **Screen Recording** for your terminal or Python runtime.
- **Accessibility** for your terminal or Python runtime.

Configure in System Settings:

1. Open **System Settings** -> **Privacy & Security**.
2. Under **Screen Recording**, enable your terminal app (Terminal, iTerm, Cursor terminal host).
3. Under **Accessibility**, enable the same app.
4. Restart the terminal after toggling permissions.

Without these permissions, capture/recognize/act steps may fail or return empty results.

## Optional dependencies

- OCR support: install `.[ocr]` and Tesseract binary on macOS.
- Input actions: install `.[act]`.
- YAML flow loading: install `.[flow]`.

## Test guidance

- Prefer unit tests with fixture images where possible.
- Keep OS-specific behavior behind abstractions and guard checks.
- For manual tests, document app versions, display scaling, and expected outcomes.
