#!/usr/bin/env bash
set -euo pipefail

FLOW_PATH="${1:-examples/flows/outlook-m365-email/flow.yaml}"
MODE="${2:-dry-run}"
OUT_DIR="${3:-docs/acceptance-runs}"

if [[ "${MODE}" != "dry-run" && "${MODE}" != "live" ]]; then
  echo "mode must be dry-run or live" >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
SUMMARY_PATH="${OUT_DIR}/summary-${STAMP}.md"

{
  echo "# Acceptance run set ${STAMP}"
  echo
  echo "- Flow: \`${FLOW_PATH}\`"
  echo "- Mode: \`${MODE}\`"
  echo
  echo "| Run | Exit code | JSON log |"
  echo "|-----|-----------|----------|"
} > "${SUMMARY_PATH}"

FLAGS=(--json)
if [[ "${MODE}" == "dry-run" ]]; then
  FLAGS+=(--dry-run)
fi

RUNNER=()
if command -v open-frame >/dev/null 2>&1; then
  RUNNER=(open-frame)
elif [[ -x ".venv311/bin/python" ]]; then
  RUNNER=(".venv311/bin/python" -m openframe.cli)
else
  RUNNER=(python -m openframe.cli)
fi

for idx in 1 2 3; do
  RUN_ID="accept-${STAMP}-${idx}"
  LOG_PATH="${OUT_DIR}/run-${RUN_ID}.json"
  set +e
  "${RUNNER[@]}" run "${FLOW_PATH}" --run-id "${RUN_ID}" "${FLAGS[@]}" > "${LOG_PATH}" 2>&1
  CODE=$?
  set -e
  echo "| ${idx} | ${CODE} | \`${LOG_PATH}\` |" >> "${SUMMARY_PATH}"
done

if rg "\| [123] \| [^0]" "${SUMMARY_PATH}" >/dev/null 2>&1; then
  echo "One or more runs failed. See: ${SUMMARY_PATH}" >&2
  exit 1
fi

echo "Wrote acceptance summary: ${SUMMARY_PATH}"
