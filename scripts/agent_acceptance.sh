#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-docs/acceptance-runs}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
SUMMARY_PATH="${OUT_DIR}/agent-acceptance-${STAMP}.md"

mkdir -p "${OUT_DIR}"

if [[ -x ".venv311/bin/python" ]]; then
  PYTHON_BIN=".venv311/bin/python"
else
  PYTHON_BIN="python3"
fi

MODEL="${OPENFRAME_AGENT_MODEL:-claude-haiku-4-5-20251001}"
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set. Export it before running this script." >&2
  exit 2
fi

{
  echo "# Agent acceptance run ${STAMP}"
  echo
  echo "- Model: \`${MODEL}\`"
  echo "- Python: \`${PYTHON_BIN}\`"
  echo
  echo "| Check | Exit | Result | Log |"
  echo "|---|---:|---|---|"
} > "${SUMMARY_PATH}"

record_row() {
  local check_name="$1"
  local code="$2"
  local result="$3"
  local log_path="$4"
  echo "| ${check_name} | ${code} | ${result} | \`${log_path}\` |" >> "${SUMMARY_PATH}"
}

run_probe_check() {
  local check_name="$1"
  local task="$2"
  local max_steps="$3"
  local log_path="${OUT_DIR}/agent-${STAMP}-${check_name}.log"
  local result="FAIL"

  set +e
  "${PYTHON_BIN}" examples/agents/read_only_probe.py --task "${task}" --max-steps "${max_steps}" > "${log_path}" 2>&1
  local code=$?
  set -e

  if [[ ${code} -eq 0 ]] && rg '^success=True stop=finished$' "${log_path}" >/dev/null 2>&1; then
    if rg 'capture\(' "${log_path}" >/dev/null 2>&1; then
      result="PASS"
    fi
  fi

  record_row "${check_name}" "${code}" "${result}" "${log_path}"
}

run_guard_check() {
  local check_name="guard-failfast"
  local log_path="${OUT_DIR}/agent-${STAMP}-${check_name}.log"
  local result="FAIL"

  set +e
  "${PYTHON_BIN}" - <<'PY' > "${log_path}" 2>&1
from openframe import AgentAction, AgentRunner, Provider


class RepeatFailureProvider(Provider):
    def next_action(self, *, task, tools, history):
        _ = task, tools, history
        return AgentAction.call("find", {"query": "missing"})


def failing_caller(tool, args):
    _ = tool, args
    return {
        "ok": False,
        "tool": "find",
        "error": {"code": "not_found", "message": "simulated"},
        "data": {},
        "artifacts": {},
    }


runner = AgentRunner(
    provider=RepeatFailureProvider(),
    tool_caller=failing_caller,
    tool_catalog=lambda: [{"name": "find"}],
    max_repeated_tool_errors=2,
    max_consecutive_tool_errors=5,
)
result = runner.run("trigger guard")
print(f"success={result.success} stop={result.stop_reason} steps={len(result.steps)}")
if not (result.success is False and result.stop_reason == "repeated_tool_error" and len(result.steps) == 2):
    raise SystemExit(1)
PY
  local code=$?
  set -e

  if [[ ${code} -eq 0 ]] && rg 'stop=repeated_tool_error' "${log_path}" >/dev/null 2>&1; then
    result="PASS"
  fi
  record_row "${check_name}" "${code}" "${result}" "${log_path}"
}

run_probe_check "probe-send" \
  "Capture the screen and tell me whether the phrase 'Send' appears. Do not click, type, press keys, or run flows." \
  8

run_probe_check "probe-calendar" \
  "Capture the screen and tell me whether the phrase 'Calendar' appears. Do not click, type, press keys, or run flows." \
  8

run_guard_check

if rg '\| .* \| [^|]* \| FAIL \|' "${SUMMARY_PATH}" >/dev/null 2>&1; then
  echo "Acceptance failed. See ${SUMMARY_PATH}" >&2
  exit 1
fi

echo "Wrote acceptance summary: ${SUMMARY_PATH}"
