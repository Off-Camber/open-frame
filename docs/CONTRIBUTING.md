# Contributing

Thanks for contributing to Open Frame.

## Development setup

1. Use Python 3.11+.
2. Create and activate a local virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

3. Install in editable mode:

```bash
python -m pip install -e ".[dev,ocr,act,flow,mcp,template]"
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

7. Optional: install git hooks so ruff runs on commit:

```bash
pip install pre-commit
pre-commit install
```

Hooks are defined in `.pre-commit-config.yaml` (`ruff check --fix` and `ruff format` on staged files). CI runs `ruff check .`, `ruff format --check .`, and `pytest` on every push/PR.

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
- MCP server: install `.[mcp]`.
- Template matching: install `.[template]`.

## Test guidance

- Prefer unit tests with fixture images where possible.
- Keep OS-specific behavior behind abstractions and guard checks.
- For manual tests, document app versions, display scaling, and expected outcomes.

## Release / stability gates

Hosted CI covers lint, format, unit tests (including the template extra), a wheel install smoke test, and packaging on Python 3.11 and 3.12, plus unit tests on a macOS runner. Permissioned GUI checks are local-only:

```bash
./scripts/macos_live_gate.sh
```

See `docs/RELEASE_GATES.md` for the full candidate-SHA checklist before changing
release-status language or package version.
