#!/usr/bin/env bash
# Records the calibration flow CLI output for the README cast.
# Output is intentionally deterministic (dry-run) so the cast looks the same every time.
set -euo pipefail

cat <<'BANNER'
$ open-frame run examples/flows/calibration-token/flow.yaml --dry-run --json
BANNER

sleep 0.6
.venv311/bin/python -m openframe.cli run examples/flows/calibration-token/flow.yaml --dry-run --json
