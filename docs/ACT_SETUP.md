# Act setup

Action execution uses `pyautogui` for mouse and keyboard control.

## Install dependencies

```bash
pip install -e .[act]
```

## Safety

- Start with dry-run mode:

```bash
open-frame click "Submit" --dry-run --json
```

- Remove `--dry-run` only after verifying the point is correct.
