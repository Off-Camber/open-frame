# Custom recognizer example

This example shows how to register a third-party recognizer with `Session` without forking Open Frame core.

## Run

```bash
python examples/custom_recognizer/demo.py
```

The demo uses `dry_run=True` and a synthetic recognizer that returns a fixed target when a query starts with `demo`.
