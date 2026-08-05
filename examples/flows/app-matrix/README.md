# App validation matrix

Non-destructive live probes for built-in macOS apps and Safari. Used by the
beta robustness program to measure recognition beyond TextEdit calibration.

## Apps

| App | Flow | Probe target |
|---|---|---|
| Finder | `finder/flow.yaml` | `Finder` chrome label |
| Safari | `safari/flow.yaml` | `Example Domain` on example.com |
| Mail | `mail/flow.yaml` | `Inbox` |
| System Settings | `system-settings/flow.yaml` | `General` |
| Notes | `notes/flow.yaml` | `Notes` |
| Calendar | `calendar/flow.yaml` | `Today` |

Each probe activates the app, finds a known label, and verifies window/app
state. There are **no real clicks** (flow-level `--dry-run` would skip app
activation, so probes use find+verify instead). The gate pre-launches each
app with `open -a` before the flow.

## Run

```bash
pip install -e ".[dev,ocr,act,flow]"
./scripts/app_matrix_gate.sh
# optional evidence directory:
./scripts/app_matrix_gate.sh /tmp/open-frame-app-matrix
```

Preconditions: macOS with Screen Recording + Accessibility for the exact
terminal/IDE host; English UI labels recommended.

By default, individual app failures do **not** fail the harness exit code —
they are written to `defect-list.md` for PR 4 burn-down. Set
`OPENFRAME_APP_MATRIX_STRICT=1` to require every app probe to pass.

## Outputs

- `app-matrix-summary.md` / `.json` — per-app pass/fail
- `defect-list.md` — failures to triage in robustness PR 4
- `runs/matrix-<app>/` — step artifacts from `open-frame run`

## Baseline notes (audited Mac)

First useful run after landing the harness (`20260805T032540Z`):

| App | Result |
|---|---|
| Safari / Mail / System Settings / Notes | pass |
| Finder | fail — `File` not found under window scope (menu bar outside window); probe later switched to `Finder` chrome |
| Calendar | fail — `activate` while not running returned AppleEvent `-600` |

Follow-up runs also surfaced sticky / missing frontmost process detection
(`Could not focus app … frontmost app is 'Notes'|'None'`), which is a
product defect for `_focus_app` to address in robustness PR 4 — not a
reason to withhold the measurement harness.
