#!/usr/bin/env bash
# Local macOS live stability gate for permissioned capture/a11y/act/OCR checks.
# Hosted CI cannot replace this; run it against a known candidate SHA on a Mac
# with Screen Recording + Accessibility granted to the terminal/IDE host.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

OUT_DIR="${1:-}"
if [[ -z "${OUT_DIR}" ]]; then
  STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
  OUT_DIR="${ROOT}/../open-frame-live-gate-${STAMP}"
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
TESSERACT_VERSION="$(tesseract --version 2>&1 | head -n 1 || echo missing)"

SUMMARY_JSON="${OUT_DIR}/live-gate-summary.json"
SUMMARY_MD="${OUT_DIR}/live-gate-summary.md"
RESULTS_JSON="${OUT_DIR}/checks.json"

echo "Open Frame macOS live gate"
echo "  repo:      ${ROOT}"
echo "  sha:       ${GIT_SHA}"
echo "  out:       ${OUT_DIR}"
echo "  python:    ${PYTHON_BIN} (${PY_VERSION})"
echo "  macos:     ${OS_VERSION}"
echo "  tesseract: ${TESSERACT_VERSION}"
echo

export OF_LIVE_GATE_OUT="${OUT_DIR}"
export OF_LIVE_GATE_RESULTS="${RESULTS_JSON}"
export OF_GIT_SHA="${GIT_SHA}"
export OF_GIT_DESC="${GIT_DESC}"
export OF_PY_VERSION="${PY_VERSION}"
export OF_PYTHON_BIN="${PYTHON_BIN}"
export OF_OS_VERSION="${OS_VERSION}"
export OF_TESSERACT="${TESSERACT_VERSION}"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OF_LIVE_GATE_OUT"])
env = {
    "git_sha": os.environ["OF_GIT_SHA"],
    "git_describe": os.environ.get("OF_GIT_DESC", ""),
    "python": os.environ["OF_PY_VERSION"],
    "python_bin": os.environ["OF_PYTHON_BIN"],
    "macos": os.environ["OF_OS_VERSION"],
    "tesseract": os.environ["OF_TESSERACT"],
    "out_dir": str(out),
}
(out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
# Always start from a clean checklist for this invocation.
Path(os.environ["OF_LIVE_GATE_RESULTS"]).write_text("[]\n")
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

path = Path(os.environ["OF_LIVE_GATE_RESULTS"])
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

run_logged() {
  local out_base="$1"
  local code
  shift
  "$@" >"${out_base}.out" 2>"${out_base}.err"
  code=$?
  echo "${code}" >"${out_base}.exit"
  return "${code}"
}

check_platform() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    record_check "platform" "fail" "macOS required; got $(uname -s)"
    return 1
  fi
  record_check "platform" "pass" "Darwin ${OS_VERSION}"
}

check_list_windows() {
  local base="${OUT_DIR}/list-windows"
  if ! run_logged "${base}" "${RUNNER[@]}" list-windows --json --displays; then
    record_check "window_enumeration" "fail" "list-windows exited $(cat "${base}.exit")" "${base}.err"
    return 1
  fi
  if ! python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OF_LIVE_GATE_OUT"])
payload = json.loads((out / "list-windows.out").read_text())
windows = payload.get("windows") or []
displays = payload.get("displays") or []
if not windows:
    raise SystemExit("no windows returned")
if not displays:
    raise SystemExit("no displays returned")
(out / "window-id.txt").write_text(str(windows[0]["id"]))
(out / "window-count.txt").write_text(str(len(windows)))
print(f"windows={len(windows)} displays={len(displays)} first_id={windows[0]['id']}")
PY
  then
    record_check "window_enumeration" "fail" "invalid list-windows payload" "${base}.out"
    return 1
  fi
  record_check "window_enumeration" "pass" "$(cat "${OUT_DIR}/window-count.txt") windows" "${base}.out"
}

check_capture() {
  local screen="${OUT_DIR}/screen.png"
  local region="${OUT_DIR}/region.png"
  local window="${OUT_DIR}/window.png"
  local window_id
  window_id="$(cat "${OUT_DIR}/window-id.txt")"

  if ! run_logged "${OUT_DIR}/capture-screen" "${RUNNER[@]}" capture --out "${screen}"; then
    record_check "screen_capture" "fail" "screen capture failed" "${OUT_DIR}/capture-screen.err"
    return 1
  fi
  record_check "screen_capture" "pass" "wrote screen.png" "${screen}"

  if ! run_logged "${OUT_DIR}/capture-region" \
    "${RUNNER[@]}" capture --out "${region}" --x 100 --y 100 --width 400 --height 300; then
    record_check "region_capture" "fail" "region capture failed" "${OUT_DIR}/capture-region.err"
    return 1
  fi
  record_check "region_capture" "pass" "wrote region.png" "${region}"

  if ! run_logged "${OUT_DIR}/capture-window" \
    "${RUNNER[@]}" capture --out "${window}" --window-id "${window_id}"; then
    record_check "window_capture" "fail" "window capture failed for id ${window_id}" \
      "${OUT_DIR}/capture-window.err"
    return 1
  fi
  record_check "window_capture" "pass" "wrote window.png for id ${window_id}" "${window}"
}

check_a11y_bounds() {
  # Prefer a known app tree so the gate is not tied to whichever UI is frontmost.
  osascript -e 'tell application "TextEdit" to activate' >/dev/null 2>&1 || true
  osascript -e 'tell application "TextEdit" to if (count of documents) is 0 then make new document' >/dev/null 2>&1 || true
  sleep 1.0

  # Enumerate frontmost AX elements and require non-zero bounds. Also OCR the
  # already-captured screen so perception still has a second signal.
  if ! "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

from openframe.recognize.a11y.macos import MacOSA11yRecognizer, _list_frontmost_elements
from openframe.recognize.ocr.tesseract import TesseractRecognizer
from openframe.types import Frame

out = Path(os.environ["OF_LIVE_GATE_OUT"])
elements = _list_frontmost_elements()
valid = [
    item
    for item in elements
    if float(item.get("width") or 0) > 0 and float(item.get("height") or 0) > 0
]
screen = out / "screen.png"
ocr_targets = []
if screen.exists():
    frame = Frame(
        width=1,
        height=1,
        scale_factor=1.0,
        source="live-gate:screen",
        image_path=str(screen),
    )
    recognizer = TesseractRecognizer()
    for query in ("File", "Edit", "View", "Open", "Frame"):
        result = recognizer.find(frame=frame, query=query)
        for target in result.targets:
            if target.width > 0 and target.height > 0:
                ocr_targets.append(
                    {
                        "query": query,
                        "text": target.text,
                        "width": target.width,
                        "height": target.height,
                        "source": target.source,
                    }
                )
        if ocr_targets:
            break

a11y_matches = []
recognizer = MacOSA11yRecognizer()
titles = [
    str(item.get("title") or "").strip()
    for item in valid
    if str(item.get("title") or "").strip()
]
probe = next((title for title in titles if 1 <= len(title.split()) <= 3), None)
if probe:
    frame = Frame(
        width=1,
        height=1,
        scale_factor=1.0,
        source="live-gate:a11y",
        image_path=str(screen) if screen.exists() else None,
    )
    found = recognizer.find(frame=frame, query=probe)
    a11y_matches = [
        {
            "text": t.text,
            "width": t.width,
            "height": t.height,
            "source": t.source,
        }
        for t in found.targets
        if t.width > 0 and t.height > 0
    ]

metrics = {
    "elements_seen": len(elements),
    "valid_bounds": len(valid),
    "a11y_probe": probe,
    "a11y_matches": len(a11y_matches),
    "ocr_matches": len(ocr_targets),
    "sample_a11y": valid[:5],
    "sample_ocr": ocr_targets[:5],
}
(out / "a11y-bounds-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics))
if len(valid) < 1:
    raise SystemExit(
        "accessibility tree returned no elements with bounds; grant Accessibility "
        "to the terminal/IDE hosting this script and ensure TextEdit can activate"
    )
if len(a11y_matches) < 1 and len(ocr_targets) < 1:
    raise SystemExit("accessibility bounds present but find probes returned no targets")
PY
  then
    record_check "a11y_bounds" "fail" "a11y/OCR bounds probe failed" \
      "${OUT_DIR}/a11y-bounds-metrics.json"
    osascript -e 'tell application "TextEdit" to close every document saving no' >/dev/null 2>&1 || true
    return 1
  fi
  local detail
  detail="$("${PYTHON_BIN}" -c 'import json,os; from pathlib import Path; m=json.loads(Path(os.environ["OF_LIVE_GATE_OUT"],"a11y-bounds-metrics.json").read_text()); print("%s ax / %s ocr" % (m["valid_bounds"], m["ocr_matches"]))')"
  record_check "a11y_bounds" "pass" "${detail}" "${OUT_DIR}/a11y-bounds-metrics.json"
  # Drop the probe document so calibration does not hit a save sheet.
  osascript -e 'tell application "TextEdit" to close every document saving no' >/dev/null 2>&1 || true
}

check_safe_matching() {
  if ! "${PYTHON_BIN}" - <<'PY'
from openframe.recognize.match import text_matches_query

assert text_matches_query("actuation", "AC", mode="token") is False
assert text_matches_query("AC", "AC", mode="token") is True
assert text_matches_query("actuation", "AC", mode="substring") is True
print("token_match_ok")
PY
  then
    record_check "safe_token_matching" "fail" "token matcher regression"
    return 1
  fi
  record_check "safe_token_matching" "pass" "AC does not match actuation in token mode"

  local base="${OUT_DIR}/safe-click"
  local code
  "${RUNNER[@]}" click "AC" --dry-run --json >"${base}.out" 2>"${base}.err"
  code=$?
  echo "${code}" >"${base}.exit"

  if ! python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OF_LIVE_GATE_OUT"])
out = (out_dir / "safe-click.out").read_text()
err = (out_dir / "safe-click.err").read_text()
text = out + "\n" + err
code = int((out_dir / "safe-click.exit").read_text().strip() or "1")
if "ambiguous_target" in text:
    raise SystemExit(0)
try:
    payload = json.loads(out)
except Exception:
    payload = {}
selected = ""
if isinstance(payload, dict):
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    selected = str(
        payload.get("selected_text")
        or payload.get("text")
        or data.get("text")
        or ""
    )
if code == 0 and selected and "actu" in selected.casefold():
    raise SystemExit("unsafe substring click selected actuation-like text")
if code != 0:
    raise SystemExit(0)
print("dry_run_ok_unique_or_none")
PY
  then
    record_check "safe_click_fail_closed" "fail" "unsafe AC handling" "${base}.err"
    return 1
  fi
  record_check "safe_click_fail_closed" "pass" "AC dry-run did not click actuation" "${base}.out"
}

check_calibration() {
  local passes=0
  local runs="${OPENFRAME_LIVE_GATE_CALIBRATION_RUNS:-5}"
  local idx
  local base
  local code
  if ! [[ "${runs}" =~ ^[1-9][0-9]*$ ]]; then
    record_check "calibration_5x" "fail" "invalid OPENFRAME_LIVE_GATE_CALIBRATION_RUNS=${runs}"
    return 1
  fi

  # Drop leftover Untitled docs so window guards and OCR stay deterministic.
  osascript -e 'tell application "TextEdit" to close every document saving no' >/dev/null 2>&1 || true
  osascript -e 'tell application "TextEdit" to activate' >/dev/null 2>&1 || true
  sleep 0.5

  : >"${OUT_DIR}/calibration-codes.txt"
  for idx in $(seq 1 "${runs}"); do
    base="${OUT_DIR}/calibration-${idx}"
    osascript -e 'tell application "TextEdit" to activate' >/dev/null 2>&1 || true
    sleep 0.2
    "${RUNNER[@]}" run examples/flows/calibration-token/flow.yaml \
      --run-id "live-gate-cal-${idx}" --json >"${base}.out" 2>"${base}.err"
    code=$?
    echo "${code}" >>"${OUT_DIR}/calibration-codes.txt"
    echo "${code}" >"${base}.exit"
    if [[ "${code}" -eq 0 ]]; then
      passes=$((passes + 1))
    fi
  done

  osascript -e 'tell application "TextEdit" to close every document saving no' >/dev/null 2>&1 || true

  if ! OF_CAL_PASSES="${passes}" OF_CAL_RUNS="${runs}" "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

passes = int(os.environ["OF_CAL_PASSES"])
runs = int(os.environ["OF_CAL_RUNS"])
summary = {
    "runs": runs,
    "passes": passes,
    "pass_rate_percent": round((passes / runs) * 100.0, 1),
}
Path(os.environ["OF_LIVE_GATE_OUT"], "calibration-summary.json").write_text(
    json.dumps(summary, indent=2) + "\n"
)
print(json.dumps(summary))
if passes != runs:
    raise SystemExit(f"calibration gate failed: {passes}/{runs}")
PY
  then
    record_check "calibration_${runs}x" "fail" "${passes}/${runs}" "${OUT_DIR}/calibration-summary.json"
    return 1
  fi
  record_check "calibration_${runs}x" "pass" "${passes}/${runs}" "${OUT_DIR}/calibration-summary.json"
}

check_intentional_failure() {
  local base="${OUT_DIR}/intentional-failure"
  local code
  "${RUNNER[@]}" run examples/flows/calibration-token-miss/flow.yaml \
    --run-id "live-gate-miss" --json >"${base}.out" 2>"${base}.err"
  code=$?
  echo "${code}" >"${base}.exit"

  if ! python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OF_LIVE_GATE_OUT"])
code = int((out_dir / "intentional-failure.exit").read_text().strip())
out = (out_dir / "intentional-failure.out").read_text()
payload = {}
try:
    payload = json.loads(out)
except Exception:
    pass
success = payload.get("success")
artifact = Path("runs/live-gate-miss")
has_artifact = artifact.exists()
summary = {
    "exit_code": code,
    "nonzero": code != 0,
    "reported_success": success,
    "artifact_exists": has_artifact,
    "artifact": str(artifact.resolve()) if has_artifact else None,
}
(out_dir / "intentional-failure-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
if code == 0 or success is True:
    raise SystemExit("intentional failure unexpectedly succeeded")
if not has_artifact:
    raise SystemExit("intentional failure missing run artifacts under runs/live-gate-miss")
print(json.dumps(summary))
PY
  then
    record_check "intentional_failure" "fail" "missing failure artifacts or unexpected success" \
      "${base}.out"
    return 1
  fi
  record_check "intentional_failure" "pass" "nonzero exit with artifacts" \
    "${OUT_DIR}/intentional-failure-summary.json"
}

finalize() {
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(os.environ["OF_LIVE_GATE_OUT"])
checks_path = Path(os.environ["OF_LIVE_GATE_RESULTS"])
checks = json.loads(checks_path.read_text()) if checks_path.exists() else []
failed = [c for c in checks if c.get("status") != "pass"]
overall = "pass" if not failed else "fail"
env = json.loads((out_dir / "environment.json").read_text())
summary = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "overall_gate": overall,
    "git_sha": env.get("git_sha"),
    "checks": checks,
    "failed": [c["name"] for c in failed],
}
(out_dir / "live-gate-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
lines = [
    "# macOS live gate summary",
    "",
    f"- Overall: `{overall}`",
    f"- Git SHA: `{env.get('git_sha')}`",
    f"- macOS: `{env.get('macos')}`",
    f"- Python: `{env.get('python')}`",
    f"- Tesseract: `{env.get('tesseract')}`",
    "",
    "| Check | Status | Detail |",
    "|---|---|---|",
]
for check in checks:
    lines.append(f"| {check['name']} | {check['status']} | {check['detail']} |")
if failed:
    lines.extend(["", "## Failed checks", ""])
    for check in failed:
        lines.append(f"- **{check['name']}**: {check['detail']}")
(out_dir / "live-gate-summary.md").write_text("\n".join(lines) + "\n")
print(f"Wrote {out_dir / 'live-gate-summary.md'}")
print(f"overall_gate={overall}")
raise SystemExit(0 if overall == "pass" else 1)
PY
}

GATE_FAILED=0
run_check() {
  set +e
  "$@"
  code=$?
  set +e
  if [[ "${code}" -ne 0 ]]; then
    GATE_FAILED=1
  fi
}

set +e
run_check check_platform
run_check check_list_windows
run_check check_capture
run_check check_a11y_bounds
run_check check_safe_matching
run_check check_calibration
run_check check_intentional_failure
finalize
FINAL_CODE=$?
set -e

if [[ "${GATE_FAILED}" -ne 0 || "${FINAL_CODE}" -ne 0 ]]; then
  echo "Live gate failed. See ${SUMMARY_MD}" >&2
  exit 1
fi

echo "Live gate passed. See ${SUMMARY_MD}"
exit 0