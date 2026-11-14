# Stability release gates

Open Frame keeps permissioned GUI checks off hosted CI. Use this checklist before
changing release-status language or package version.

## Automated CI (every PR)

GitHub Actions runs on Python **3.11** and **3.12** (Ubuntu) and Python **3.11** (`macos-latest`):

- `ruff check` and `ruff format --check`
- `pytest --cov=openframe --cov-fail-under=80` with `.[dev,ocr,flow,mcp,template]` (plus system `tesseract-ocr` on Ubuntu; Tesseract from Homebrew on macOS)
- `python -m build` and `twine check`
- Wheel install smoke test on Ubuntu 3.11: a clean venv installs the built wheel, `open-frame mcp list-tools --json` lists the tools, and the installed version matches `pyproject.toml`

The macOS job runs the unit tests and `open-frame capture`. Hosted runners can take a screenshot. The permissioned live gate stays local.

## Release checklist

Fill this in for the exact commit being tagged. The tag must be `v` plus the `pyproject.toml` version, and it must point at this SHA. The publish workflow rejects any other tag before it builds or uploads.

| Field | Record |
|---|---|
| Commit SHA | |
| Tag | |
| Live gate | pass or fail, date, macOS version |
| Live gate evidence | path or link |
| Strict app matrix | pass count on the same SHA |
| CI | Ubuntu 3.11, Ubuntu 3.12, and macOS green on that SHA |

## Local macOS live gate

Permission-dependent capture, accessibility, safe click, and OCR calibration
must be rerun on a real Mac against a known candidate SHA:

```bash
pip install -e ".[dev,ocr,act,flow,mcp]"
open-frame doctor
./scripts/macos_live_gate.sh
# optional explicit evidence directory:
./scripts/macos_live_gate.sh /tmp/open-frame-live-gate
```

### Preconditions

- macOS with **Screen Recording** and **Accessibility** granted to the
  **exact** terminal or IDE host process running the script (System Settings →
  Privacy & Security). Cursor/IDE helpers and Terminal.app are different hosts.
- TextEdit available (calibration flows use it)
- System `tesseract` on `PATH` (`brew install tesseract`)
- Optional but required for the MCP stdio check: `pip install -e '.[mcp]'`
  (and a green `open-frame doctor`)

If `a11y_bounds` reports an empty accessibility tree, re-run from a host that
already has Accessibility enabled rather than treating OCR-only success as enough.

### What it checks

| Check | Pass criteria |
|---|---|
| Window enumeration | `list-windows --json --displays` returns windows + displays |
| Screen / region / window capture | each capture exits 0 and writes a PNG |
| Accessibility/OCR bounds | frontmost AX elements include non-zero bounds; find/OCR probe succeeds |
| Safe token matching | `AC` does not match `actuation`; dry-run click stays fail-closed |
| Calibration | `examples/flows/calibration-token/flow.yaml` passes **5/5** (override with `OPENFRAME_LIVE_GATE_CALIBRATION_RUNS` only for debugging) |
| Window-scoped click | double-click on the calibration token leaves the insertion point or selection on that token in TextEdit |
| Region click | double-click from a region capture of that window leaves the insertion point or selection on that token |
| `frame_path` click | MCP `click` with the window capture's `frame_path` leaves the insertion point or selection on that token |
| Intentional failure | `examples/flows/calibration-token-miss/flow.yaml` exits nonzero with artifacts |
| GUI client environment | With only `HOME`, `LOGNAME`, `PATH`, `SHELL`, and `USER`, OCR reads a generated image, screen recording passes, and `doctor --mcp` lists its tools. An empty accessibility tree is recorded and does not fail this check. |
| MCP stdio | `open-frame mcp serve` handshake succeeds; dry-run `type` returns `ok: true` envelope |

Outputs:

- `live-gate-summary.md` / `live-gate-summary.json`
- per-check logs and PNGs under the evidence directory

## Full audit package (candidate SHA)

Before a status/version decision, also record:

1. Lint / unit / build / twine on the candidate SHA
2. MCP dry-run repeatability ≥ 95% on
   `examples/flows/mcp-dry-run-wait/flow.yaml` and
   `examples/flows/mcp-dry-run-actions/flow.yaml`
   (`docs/MCP_BENCHMARK.md`)
3. macOS live gate above (including MCP stdio smoke)
4. **App validation matrix** (`./scripts/app_matrix_gate.sh`) for Finder,
   Safari, Mail, System Settings, Notes, and Calendar — see
   [examples/flows/app-matrix/README.md](../examples/flows/app-matrix/README.md).
   App failures seed the robustness burn-down list; they do not by themselves
   block the harness unless `OPENFRAME_APP_MATRIX_STRICT=1`.
5. Bounded read-only agent acceptance (`docs/AGENT_ACCEPTANCE.md`) when API credentials are available
6. Fresh-user walkthrough: install → `open-frame doctor` → MCP client config → first dry-run tool call (under ten minutes)

## Release posture

Remain **beta** for macOS-first releases once the automated matrix and local live
gate are green on the candidate SHA. Do not bump package version or MCP contract
version from green unit tests alone.
