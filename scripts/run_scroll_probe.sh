#!/usr/bin/env bash
# Run the Safari below-fold scroll_until_found probe with a machine-local file URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAGE_URI="$(
  python3 - <<PY
from pathlib import Path
print((Path("${ROOT}") / "examples/demo/scroll-probe/index.html").resolve().as_uri())
PY
)"
FLOW_SRC="${ROOT}/examples/flows/scroll-until-found/flow.yaml"
TMP="$(mktemp -t open-frame-scroll-XXXXXX.yaml)"
trap 'rm -f "${TMP}"' EXIT

python3 - <<PY
from pathlib import Path
src = Path("${FLOW_SRC}").read_text(encoding="utf-8")
src = src.replace(
    "file:///ABSOLUTE/PATH/TO/open-frame/examples/demo/scroll-probe/index.html",
    "${PAGE_URI}",
)
Path("${TMP}").write_text(src, encoding="utf-8")
PY

exec open-frame run "${TMP}" "$@"
