# Acceptance runs (Phase 5.9)

Use this procedure to document the required three consecutive runs.

## Option A: helper script

Dry-run logging:

```bash
./scripts/acceptance_three_runs.sh examples/flows/outlook-m365-email/flow.yaml dry-run
```

Live logging:

```bash
./scripts/acceptance_three_runs.sh examples/flows/outlook-m365-email/flow.yaml live
```

Outputs:

- Summary markdown: `docs/acceptance-runs/summary-<timestamp>.md`
- Per-run logs: `docs/acceptance-runs/run-accept-<timestamp>-<n>.json`

## Option B: manual log table

| Run | Run ID | Command | Exit code | Outcome notes |
|-----|--------|---------|-----------|---------------|
| 1 | | `open-frame run examples/flows/outlook-m365-email/flow.yaml --json` | | |
| 2 | | `open-frame run examples/flows/outlook-m365-email/flow.yaml --json` | | |
| 3 | | `open-frame run examples/flows/outlook-m365-email/flow.yaml --json` | | |

## Completion rule

Phase 5.9 is complete when three sequential runs of the full MVP flow finish with success and the evidence is captured in `docs/acceptance-runs/`.

## Reliability guardrail for real outcomes

Do not treat run success as proof of business outcome by itself. For outcome-critical flows:

- first run `examples/flows/calibration-token/flow.yaml` successfully on the same machine/session,
- then verify an outcome-specific signal in the target system (for example: unique subject token appears in `Sent Items`).
