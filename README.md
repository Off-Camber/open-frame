# Open Frame

Open-source recognition and action for anything on a display.

**Open Frame** is a platform for seeing what's on screen, locating targets, interacting with them, and verifying the result — without brittle selectors or vendor lock-in. Built under the [Off-Camber](https://github.com/Off-Camber) identity.

> Open Frame is an independent project and is not affiliated with or endorsed by any third-party automation vendor.

## Status

Planning and early scaffolding.

**MVP goalpost:** a declarative flow that automates **Outlook → Microsoft 365 → create document → email**, repeatably across desktop apps. See [docs/MVP_GOALPOST.md](docs/MVP_GOALPOST.md).

## Documentation

| Doc | Purpose |
|-----|---------|
| [Vision](docs/VISION.md) | What we're building and for whom |
| [Architecture](docs/ARCHITECTURE.md) | System layers, modules, and interfaces |
| [Action plan](docs/ACTION_PLAN.md) | Phased tasks and checklists |
| [Decisions](docs/DECISIONS.md) | Record of key design choices |
| [Capture manual test](docs/CAPTURE_MANUAL_TEST.md) | Live macOS validation checklist for Phase 1 capture |
| [OCR setup](docs/OCR_SETUP.md) | Install and run the Tesseract recognizer |
| [Accessibility setup](docs/A11Y_SETUP.md) | Configure macOS Accessibility permission for AX recognition |
| [Act setup](docs/ACT_SETUP.md) | Install and safely run click/type actions |
| [Act manual test](docs/ACT_MANUAL_TEST.md) | End-to-end capture → find → click validation steps |
| [Verify setup](docs/VERIFY_SETUP.md) | Configure and use click verification with run artifacts |
| [Flow setup](docs/FLOW_SETUP.md) | Define and run YAML flows |
| [Acceptance runs](docs/ACCEPTANCE_RUNS.md) | Record three consecutive MVP flow runs |
| [API](docs/API.md) | Programmatic `Session` SDK usage and extension points |
| [Contributing](docs/CONTRIBUTING.md) | Development workflow and macOS permission setup |
| [Publish to PyPI](docs/PUBLISH_PYPI.md) | Trusted publishing setup and release checklist |

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
```

## Planned next commands

```bash
# Run the MVP reference flow (prepared desktop: Outlook + browser signed in)
open-frame run examples/flows/outlook-m365-email/flow.yaml

open-frame find "New Email" --click
```

## License

Apache License 2.0 — free to use, modify, and self-host. See [LICENSE](LICENSE).
