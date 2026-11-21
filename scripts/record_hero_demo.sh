#!/usr/bin/env bash
# Serve the invoice demo, run the flow, and capture an 8–12s hero GIF.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=python_bin.sh
source "${ROOT}/scripts/python_bin.sh"
PYTHON="$(openframe_python_bin "${ROOT}")"

PORT="${OPENFRAME_HERO_PORT:-8765}"
DEMO_DIR="${ROOT}/examples/demo/invoice-approve"
FLOW="${ROOT}/examples/flows/invoice-approve-demo/flow.record.yaml"
OUT_GIF="${ROOT}/docs/assets/invoice-approve.gif"
WORK="$(mktemp -d -t openframe-hero.XXXXXX)"
FRAMES="${WORK}/frames"
SERVER_PID=""
GRAB_PID=""

cleanup() {
  if [[ -n "${GRAB_PID}" ]]; then
    kill "${GRAB_PID}" >/dev/null 2>&1 || true
    wait "${GRAB_PID}" 2>/dev/null || true
  fi
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${WORK}"
}
trap cleanup EXIT

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required to render the hero GIF (brew install ffmpeg)" >&2
  exit 1
fi

if lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -tiTCP:"${PORT}" -sTCP:LISTEN | xargs kill >/dev/null 2>&1 || true
  sleep 0.3
fi

"${PYTHON}" -m http.server "${PORT}" --bind 127.0.0.1 --directory "${DEMO_DIR}" \
  >/tmp/openframe-hero-http.log 2>&1 &
SERVER_PID=$!
sleep 0.5
curl -sf "http://127.0.0.1:${PORT}/" >/dev/null

osascript <<APPLESCRIPT >/dev/null
tell application "Safari"
  activate
  make new document
  set URL of front document to "about:blank"
  set bounds of front window to {80, 60, 980, 780}
end tell
APPLESCRIPT
sleep 0.4
osascript <<APPLESCRIPT >/dev/null
tell application "Safari"
  activate
  set URL of front document to "http://127.0.0.1:${PORT}/?hero=$(date +%s)"
  set bounds of front window to {80, 60, 980, 780}
end tell
APPLESCRIPT
sleep 2.0

mkdir -p "${FRAMES}"

# Keep grabbing until the flow has finished and the success state has been on screen.
# A fixed deadline was ending while the click was still running, so the saved
# frames stayed on Pending even though the flow reported success.
STOP="${WORK}/stop-grab"
(
  i=0
  while [[ ! -f "${STOP}" ]]; do
    printf -v name "%04d.png" "${i}"
    screencapture -x -R80,60,900,720 "${FRAMES}/${name}" || true
    i=$((i + 1))
  done
  echo "${i}" >"${WORK}/frame_count.txt"
) &
GRAB_PID=$!

# Pending lead-in, then actuate, then hold success.
sleep 2.5

set +e
"${PYTHON}" -m openframe.cli run "${FLOW}" --json --run-id hero-invoice-approve \
  >"${WORK}/run.json" 2>"${WORK}/run.err"
RUN_STATUS=$?
set -e

sleep 3.5
touch "${STOP}"
wait "${GRAB_PID}" || true
GRAB_PID=""

if [[ "${RUN_STATUS}" -ne 0 ]]; then
  echo "hero flow failed (exit ${RUN_STATUS})" >&2
  cat "${WORK}/run.err" >&2 || true
  cat "${WORK}/run.json" >&2 || true
  exit "${RUN_STATUS}"
fi

"${PYTHON}" - <<PY
import json
from pathlib import Path
from PIL import Image
import pytesseract

payload = json.loads(Path(r"${WORK}/run.json").read_text())
assert payload.get("success") is True, payload
frames = sorted(Path(r"${FRAMES}").glob("*.png"))
assert frames, "no frames captured"
early = pytesseract.image_to_string(Image.open(frames[0]))
late = pytesseract.image_to_string(Image.open(frames[-1]))
print("capture_frames:", len(frames))
print("steps:", [s["step_id"] for s in payload.get("steps", [])])
print("early_has_payment_posted", "payment posted" in early.lower())
print("late_has_payment_posted", "payment posted" in late.lower())
if "payment posted" in early.lower():
    raise SystemExit("recording started after success state; pending lead-in missing")
if "payment posted" not in late.lower():
    raise SystemExit("recording never reached success state")
print("arc_ok: pending -> posted")
PY

"${PYTHON}" "${ROOT}/scripts/annotate_hero_gif.py" --frames "${FRAMES}" --seconds 10 "${OUT_GIF}"
echo "hero gif: ${OUT_GIF}"
echo "bytes: $(stat -f %z "${OUT_GIF}")"
