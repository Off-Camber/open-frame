# Open Frame

Open-source recognition and action for anything on a display.

**Open Frame** is a platform for seeing what's on screen, locating targets, interacting with them, and verifying the result — without brittle selectors or vendor lock-in. Built under the [Off-Camber](https://github.com/Off-Camber) identity.

> Open Frame is an independent project and is not affiliated with or endorsed by any third-party automation vendor.

Open Frame is the deterministic desktop execution layer behind AI agents, not the agent itself.

### How this differs from assistant UX tools

- Open Frame executes deterministic capture/recognize/act/verify primitives.
- External LLM agents handle planning and decide which tool call to make next.
- The engine returns compact structured outputs plus artifact paths to reduce context-window pressure.

## Status

Active development. `v0.1.1` is live on PyPI as [`off-camber-open-frame`](https://pypi.org/project/off-camber-open-frame/).

## Documentation

For most users, start with:

- [Flow setup](docs/FLOW_SETUP.md)
- [API](docs/API.md)
- [Act setup](docs/ACT_SETUP.md)
- [Verify setup](docs/VERIFY_SETUP.md)

For contributors/maintainers:

- [Contributing](docs/CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Vision](docs/VISION.md)
- [Full docs index](docs/README.md)

## Quick start (capture)

```bash
# Lower-level primitive available now
open-frame capture --out screen.png
open-frame capture --out crop.png --x 100 --y 200 --width 800 --height 500

# Capture active or named windows
open-frame capture --out active.png --window-title "Outlook"
open-frame capture --out active.png --window-id 123

# Inspect visible windows (and displays)
open-frame list-windows
open-frame list-windows --json --displays

# OCR find on a frame
open-frame find "Submit" --frame screen.png --json
open-frame find "Submit" --frame screen.png --overlay-out overlay.png --json

# Find and click
open-frame click "Submit" --dry-run --json
open-frame click "Save" --verify 'text-gone:"Save"' --json

# Run a flow file
open-frame run flow.yaml --dry-run --json

# Phase 5 smoke flow
open-frame run examples/flows/outlook-new-email/flow.yaml --dry-run --json
open-frame run examples/flows/outlook-browser-outlook/flow.yaml --dry-run --json
open-frame run examples/flows/outlook-m365-email/flow.yaml --dry-run --json

# MCP pilot
open-frame mcp list-tools --json
python examples/mcp-pilot/pilot.py
```

## License

Apache License 2.0 — free to use, modify, and self-host. See [LICENSE](LICENSE).
