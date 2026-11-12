#!/usr/bin/env bash
# Records the calibration flow CLI output for the README cast.
# Output is intentionally deterministic (dry-run) so the cast looks the same every time.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=python_bin.sh
source "${ROOT}/scripts/python_bin.sh"
PYTHON_BIN="$(openframe_python_bin "${ROOT}")"

cat <<'BANNER'
$ open-frame run examples/flows/calibration-token/flow.yaml --dry-run --json
BANNER

sleep 0.6
"${PYTHON_BIN}" -m openframe.cli run examples/flows/calibration-token/flow.yaml --dry-run --json
