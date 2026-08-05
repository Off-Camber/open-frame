#!/usr/bin/env bash
# Multi-app live validation matrix for Open Frame beta robustness.
# Non-destructive probes (activate + find + verify; no real clicks).
# App failures are recorded; exit nonzero only if the harness itself breaks
# or OPENFRAME_APP_MATRIX_STRICT=1 is set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

OUT_DIR="${1:-}"
if [[ -z "${OUT_DIR}" ]]; then
  STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
  OUT_DIR="${ROOT}/../open-frame-app-matrix-${STAMP}"
fi
mkdir -p "${OUT_DIR}"
OUT_DIR="$(cd "${OUT_DIR}" && pwd)"

if [[ -x "${ROOT}/.venv311/bin/python" ]]; then
  PYTHON_BIN="${ROOT}/.venv311/bin/python"
elif [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT}/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

RUNNER=("${PYTHON_BIN}" -m openframe.cli)
GIT_SHA="$(git -C "${ROOT}" rev-parse HEAD)"
GIT_DESC="$(git -C "${ROOT}" describe --always --dirty 2>/dev/null || true)"
OS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo unknown)"
PY_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])')"
STRICT="${OPENFRAME_APP_MATRIX_STRICT:-0}"

RESULTS_JSON="${OUT_DIR}/checks.json"
SUMMARY_JSON="${OUT_DIR}/app-matrix-summary.json"
SUMMARY_MD="${OUT_DIR}/app-matrix-summary.md"
DEFECTS_MD="${OUT_DIR}/defect-list.md"

echo "Open Frame app validation matrix"
echo "  repo:   ${ROOT}"
echo "  sha:    ${GIT_SHA}"
echo "  out:    ${OUT_DIR}"
echo "  python: ${PYTHON_BIN} (${PY_VERSION})"
echo "  macos:  ${OS_VERSION}"
echo "  strict: ${STRICT}"
echo

export OF_MATRIX_OUT="${OUT_DIR}"
export OF_MATRIX_RESULTS="${RESULTS_JSON}"
export OF_GIT_SHA="${GIT_SHA}"
export OF_GIT_DESC="${GIT_DESC}"
export OF_PY_VERSION="${PY_VERSION}"
export OF_PYTHON_BIN="${PYTHON_BIN}"
export OF_OS_VERSION="${OS_VERSION}"
export OF_MATRIX_STRICT="${STRICT}"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OF_MATRIX_OUT"])
env = {
    "git_sha": os.environ["OF_GIT_SHA"],
    "git_describe": os.environ.get("OF_GIT_DESC", ""),
    "python": os.environ["OF_PY_VERSION"],
    "python_bin": os.environ["OF_PYTHON_BIN"],
    "macos": os.environ["OF_OS_VERSION"],
    "strict": os.environ.get("OF_MATRIX_STRICT", "0"),
    "out_dir": str(out),
}
(out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
Path(os.environ["OF_MATRIX_RESULTS"]).write_text("[]\n")
PY

record_check() {
  local name="$1"
  local status="$2"
  local detail="$3"
  local evidence="${4:-}"
  OF_CHECK_NAME="${name}" OF_CHECK_STATUS="${status}" \
  OF_CHECK_DETAIL="${detail}" OF_CHECK_EVIDENCE="${evidence}" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["OF_MATRIX_RESULTS"])
rows = json.loads(path.read_text()) if path.exists() else []
rows.append(
    {
        "name": os.environ["OF_CHECK_NAME"],
        "status": os.environ["OF_CHECK_STATUS"],
        "detail": os.environ["OF_CHECK_DETAIL"],
        "evidence": os.environ.get("OF_CHECK_EVIDENCE") or None,
    }
)
path.write_text(json.dumps(rows, indent=2) + "\n")
print(
    f"[{os.environ['OF_CHECK_STATUS'].upper()}] "
    f"{os.environ['OF_CHECK_NAME']}: {os.environ['OF_CHECK_DETAIL']}"
)
PY
}

run_app_probe() {
  local app_id="$1"
  local flow_path="$2"
  local launch_name="${3:-}"
  local run_id="matrix-${app_id}"
  local base="${OUT_DIR}/${app_id}"
  mkdir -p "${base}"

  if [[ -n "${launch_name}" ]]; then
    # Prefer LaunchServices open so apps that are not running get started;
    # also helps when a prior app (e.g. Notes) sticky-holds activation.
    open -a "${launch_name}" >/dev/null 2>&1 || true
    sleep 1.2
  fi

  if [[ ! -f "${flow_path}" ]]; then
    record_check "${app_id}" "skip" "missing flow ${flow_path}"
    return 0
  fi

  set +e
  "${RUNNER[@]}" run "${flow_path}" --run-id "${run_id}" --json \
    >"${base}/flow.out" 2>"${base}/flow.err"
  local code=$?
  set -e
  echo "${code}" >"${base}/flow.exit"

  OF_APP_ID="${app_id}" OF_APP_BASE="${base}" OF_APP_CODE="${code}" \
  OF_APP_RUN_ID="${run_id}" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

app_id = os.environ["OF_APP_ID"]
base = Path(os.environ["OF_APP_BASE"])
code = int(os.environ["OF_APP_CODE"])
run_id = os.environ["OF_APP_RUN_ID"]
out_text = (base / "flow.out").read_text(encoding="utf-8", errors="replace")
err_text = (base / "flow.err").read_text(encoding="utf-8", errors="replace")
payload = {}
try:
    payload = json.loads(out_text) if out_text.strip() else {}
except json.JSONDecodeError:
    payload = {}

success = bool(payload.get("success")) and code == 0
artifact = Path("runs") / run_id
summary = {
    "app": app_id,
    "exit_code": code,
    "success": success,
    "flow": payload.get("flow"),
    "steps": payload.get("steps"),
    "artifact_dir": str(artifact.resolve()) if artifact.exists() else None,
    "stderr_tail": err_text[-800:] if err_text else "",
}
(base / "probe-summary.json").write_text(json.dumps(summary, indent=2) + "\n")

results_path = Path(os.environ["OF_MATRIX_RESULTS"])
rows = json.loads(results_path.read_text()) if results_path.exists() else []
if success:
    rows.append(
        {
            "name": app_id,
            "status": "pass",
            "detail": f"flow ok ({len(payload.get('steps') or [])} steps)",
            "evidence": str(base / "probe-summary.json"),
        }
    )
    print(f"[PASS] {app_id}: flow ok")
else:
    detail = "flow failed"
    for step in payload.get("steps") or []:
        if not step.get("success", True):
            detail = f"step {step.get('step_id')}: {step.get('error') or 'failed'}"
            break
    if not payload and err_text.strip():
        detail = err_text.strip().splitlines()[-1][:200]
    rows.append(
        {
            "name": app_id,
            "status": "fail",
            "detail": detail,
            "evidence": str(base / "probe-summary.json"),
        }
    )
    print(f"[FAIL] {app_id}: {detail}")
results_path.write_text(json.dumps(rows, indent=2) + "\n")
PY
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  record_check "platform" "fail" "macOS required; got $(uname -s)"
else
  record_check "platform" "pass" "Darwin ${OS_VERSION}"
fi

run_app_probe "finder" "examples/flows/app-matrix/finder/flow.yaml" "Finder"
run_app_probe "safari" "examples/flows/app-matrix/safari/flow.yaml" "Safari"
run_app_probe "mail" "examples/flows/app-matrix/mail/flow.yaml" "Mail"
run_app_probe "system-settings" "examples/flows/app-matrix/system-settings/flow.yaml" "System Settings"
run_app_probe "notes" "examples/flows/app-matrix/notes/flow.yaml" "Notes"
run_app_probe "calendar" "examples/flows/app-matrix/calendar/flow.yaml" "Calendar"

python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(os.environ["OF_MATRIX_OUT"])
checks = json.loads(Path(os.environ["OF_MATRIX_RESULTS"]).read_text())
apps = [c for c in checks if c["name"] != "platform"]
failed = [c for c in apps if c.get("status") == "fail"]
passed = [c for c in apps if c.get("status") == "pass"]
skipped = [c for c in apps if c.get("status") == "skip"]
platform = next((c for c in checks if c["name"] == "platform"), None)
env = json.loads((out_dir / "environment.json").read_text())
strict = os.environ.get("OF_MATRIX_STRICT", "0") == "1"
harness_ok = platform is not None and platform.get("status") == "pass"
overall = "pass" if harness_ok and (not strict or not failed) else (
    "fail" if not harness_ok else ("fail" if strict and failed else "complete")
)

summary = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "overall": overall,
    "strict": strict,
    "git_sha": env.get("git_sha"),
    "apps_passed": len(passed),
    "apps_failed": len(failed),
    "apps_skipped": len(skipped),
    "checks": checks,
    "failed_apps": [c["name"] for c in failed],
}
(out_dir / "app-matrix-summary.json").write_text(json.dumps(summary, indent=2) + "\n")

md = [
    "# App validation matrix summary",
    "",
    f"- Overall: `{overall}`",
    f"- Git SHA: `{env.get('git_sha')}`",
    f"- macOS: `{env.get('macos')}`",
    f"- Python: `{env.get('python')}`",
    f"- Strict mode: `{strict}`",
    f"- Passed: `{len(passed)}`  Failed: `{len(failed)}`  Skipped: `{len(skipped)}`",
    "",
    "| App | Status | Detail |",
    "|---|---|---|",
]
for check in checks:
    md.append(f"| {check['name']} | {check['status']} | {check['detail']} |")

if failed:
    md.extend(["", "## Failed apps (seed PR 4 defect list)", ""])
    for check in failed:
        md.append(f"- **{check['name']}**: {check['detail']}")
        if check.get("evidence"):
            md.append(f"  - evidence: `{check['evidence']}`")

(out_dir / "app-matrix-summary.md").write_text("\n".join(md) + "\n")

defects = [
    "# App matrix defect list",
    "",
    "Failures from this matrix run seed burn-down work in the",
    "`beta-robustness` OpenSpec PR 4 (`chore/robustness-gates`).",
    "",
    f"- Generated: `{summary['generated_at']}`",
    f"- Git SHA: `{env.get('git_sha')}`",
    "",
]
if not failed:
    defects.append("_No app failures in this run._")
else:
    defects.extend(["| App | Detail | Evidence |", "|---|---|---|"])
    for check in failed:
        defects.append(
            f"| {check['name']} | {check['detail']} | `{check.get('evidence') or ''}` |"
        )
(out_dir / "defect-list.md").write_text("\n".join(defects) + "\n")

print(f"Wrote {out_dir / 'app-matrix-summary.md'}")
print(f"Wrote {out_dir / 'defect-list.md'}")
print(f"overall={overall} passed={len(passed)} failed={len(failed)}")
if not harness_ok:
    raise SystemExit(1)
if strict and failed:
    raise SystemExit(1)
raise SystemExit(0)
PY
