# API

This document covers the programmatic Python API for Open Frame.

## Install

```bash
pip install off-camber-open-frame
```

For editable local development:

```bash
pip install -e .
```

Install extras as needed:

```bash
pip install -e .[ocr,act,flow]
```

## Core types

- `Frame`: captured display image metadata and optional image path.
- `Target`: located bounds and confidence for a UI element candidate.
- `StepResult`: outcome for one executed step in a run.

## Session

`Session` is the primary SDK entrypoint for embedded usage.

### Create a session

```python
from openframe import Session

session = Session(dry_run=True)
```

### Find a target

```python
targets = session.find("New Email")
if targets:
    print(targets[0].x, targets[0].y, targets[0].confidence)
```

### Click by query

```python
point = session.click("Send", kind="click", anchor="center")
print(point)
```

### Run in-memory steps

```python
results = session.run(
    [
        {"id": "focus", "kind": "app", "name": "Microsoft Outlook"},
        {"id": "compose", "kind": "click", "query": "New Email"},
        {"id": "type", "kind": "type", "text": "Automated message"},
        {"id": "wait", "kind": "wait", "ms": 300},
    ]
)
```

Each run appends `StepResult` records to `session.results`.

## Custom recognizers

You can register recognizers without changing Open Frame core:

```python
from openframe import Session
from openframe.recognize import Recognizer, RecognizerResult
from openframe.types import Target


class StartsWithRecognizer(Recognizer):
    name = "starts-with"

    def find(self, frame, query, options=None):
        if query.lower().startswith("demo"):
            return RecognizerResult(
                recognizer=self.name,
                targets=[Target(x=20, y=20, width=120, height=36, confidence=0.9, source=self.name, text=query)],
            )
        return RecognizerResult(recognizer=self.name, targets=[])


session = Session(dry_run=True)
session.register_recognizer(StartsWithRecognizer(priority=10))
print(session.find("demo button"))
```

See `examples/custom_recognizer/` for a complete example.

## Agent integration guidance (v0.2 direction)

Open Frame is designed to be called by an agent via MCP with compact structured responses.

### MCP MVP tools

- `capture`
- `find`
- `click`
- `type`
- `key`
- `run_flow`
- `get_run_artifacts`

### Response shape

Use a stable JSON envelope for all tool responses:

```json
{
  "ok": true,
  "tool": "find",
  "run_id": "20260618T220000Z",
  "data": {},
  "error": null,
  "artifacts": {
    "step_dir": "runs/20260618T220000Z/find-button"
  }
}
```

When `ok` is `false`, keep `error.code` and `error.message` deterministic and include artifact paths.

### Context minimization rules

- Return IDs, bounds, and file paths instead of long natural-language explanations.
- Keep screenshots and large payloads in artifacts, not inline tool output.
- Let the agent keep reasoning state while Open Frame stays focused on deterministic execution.
