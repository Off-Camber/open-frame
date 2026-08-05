# Stability release gates

Open Frame keeps permissioned GUI checks off hosted CI. Use this checklist before
changing release-status language or package version.

## Automated CI (every PR)

GitHub Actions runs on Python **3.11** and **3.12**:

- `ruff check`
- `pytest` with `.[dev,ocr,flow]` (plus system `tesseract-ocr` on Ubuntu)
- `python -m build` and `twine check`

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
| Intentional failure | `examples/flows/calibration-token-miss/flow.yaml` exits nonzero with artifacts |
| MCP stdio | `open-frame mcp serve` handshake succeeds; dry-run `type` returns `ok: true` envelope |

Outputs:

- `live-gate-summary.md` / `live-gate-summary.json`
- per-check logs and PNGs under the evidence directory

## Full audit package (candidate SHA)

Before a status/version decision, also record:

1. Lint / unit / coverage / build / twine on the candidate SHA
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
