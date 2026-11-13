# Dogfooding log (beta robustness)

Short evidence that Open Frame MCP tools work from a real client host.

| When (UTC) | Client | What we did | Result |
|---|---|---|---|
| 2026-08-05 | Cursor (this workspace) | `open-frame mcp list-tools --json`; dry-run `type`; template icon probe; scroll probe via `./scripts/run_scroll_probe.sh` | Tools listed including `scroll`; dry-run ok; scroll marker found after 5 scrolls |
| 2026-08-05 | Local CLI | App matrix `./scripts/app_matrix_gate.sh` → `…20260805T040506Z` | **6/6 pass** (Finder + Calendar recovered after focus hardening) |
| 2026-08-05 | Local CLI | MCP dry-run repeatability (5× wait + 5× actions) → `docs/benchmarks/mcp-repeatability-20260805T040800Z.md` | **10/10 (100%)** |
| 2026-08-22 | Local CLI / browser-use | A/B cost harness (`docs/market-validation-runs/20260822Tab-v0`) | AB1 **efficiency** (hybrid cheaper median `$`, 3/3); AB2 **capability** (hybrid 3/3, browser-only 0/3) |
| 2026-11-12 | Local CLI | Live gate and app matrix on macOS 27.0.1, SHA `038aba5`, Python 3.11.15 (`.venv`), Tesseract 5.5.2, one display | Live gate **fail** (calibration 0/5; every other check passed, including MCP stdio with `scroll`). App matrix **3/6** (Mail, System Settings, Notes). Harness exit 0 because strict mode is off. |
| 2026-11-12 | Local CLI | Live gate and strict app matrix on macOS 27.0.1, parent `ff4b84c`, Python 3.11.15 (`.venv`), Tesseract 5.5.2, one display | Live gate **pass** (calibration **5/5**; window, region, and `frame_path` clicks inside `CALMARK89`). App matrix **6/6** with `OPENFRAME_APP_MATRIX_STRICT=1`. |
| 2026-11-12 | Local CLI | Live gate and strict app matrix on macOS 27.0.1, SHA `c924fca`, Python 3.11.15 (`.venv`), Tesseract 5.5.2 | Live gate **pass** (calibration **5/5**; window click (336, 201), region (328, 207), `frame_path` (331, 207), each inside `CALMARK89`). App matrix **6/6** with `OPENFRAME_APP_MATRIX_STRICT=1`. This is the run that backed 0.2.2. |
| 2026-11-13 | Local CLI | Live gate and strict app matrix on macOS 27.0.1, SHA `ecd041c`, Python 3.11.15 (`.venv`), Tesseract 5.5.2, one display. Evidence `/tmp/open-frame-f-live-gate` and `/tmp/open-frame-f-app-matrix`. | Live gate **pass**. Calibration **5/5**. Window click (336, 201), region (328, 207), `frame_path` (331, 207), each with an empty selection and range 5,4 inside `CALMARK89`. App matrix **6/6** with `OPENFRAME_APP_MATRIX_STRICT=1`. |
| 2026-11-13 | Clean venv, wheel from `ecd041c` | README quickstart. `OPENFRAME_RUNS_DIR=/tmp/open-frame-readme-runs`. Tesseract 5.5.2 already installed. | `open-frame doctor` **overall: ok**, including `display_power` awake and unlocked. `doctor --mcp` **overall: ok**, 8 tools. `find "Submit"` exit 0, count 0. Hello dry-run exit 0 and wrote before/after images of about 1.96 MB each. |

## macOS 27 baseline (2026-11-12, `038aba5`)

Evidence from `scripts/macos_live_gate.sh` and `scripts/app_matrix_gate.sh`. No product bugs were fixed in this run.

- **calibration_5x, 0/5.** Each run focused TextEdit, typed `CALMARK89`, and failed `verify-token-visible` with `text "CALMARK89" not appeared`. The marker is on screen in the verify frame, at 12pt rather than the requested 48pt, wrapped onto two lines. Tesseract reads that glyph as `CALMARK839`, so the exact string never matches.
- **finder.** `find-finder-chrome` did not find `Finder`. Finder was frontmost, but the window title is the folder name `01-cv-offer-i94` and the sidebar is folder names. OCR of that frame does not emit the word Finder.
- **safari.** `find-example-domain` passed with 4 matches while Safari showed example.com. `verify-example` then failed in under a second: the window guard read the frontmost app as `Cursor`, not `Safari`.
- **calendar.** Focus brought Calendar forward onto a "What's New in Calendar" sheet, which has no Today label. `find-today` did not find `Today`, and the frame at the end of that step shows Cursor in front again.

Passed live-gate checks: platform, window enumeration, screen/region/window capture, accessibility bounds, safe token matching, safe click fail-closed, intentional failure, MCP stdio (`capture`, `click`, `find`, `get_run_artifacts`, `key`, `run_flow`, `scroll`, `type`).

## macOS 27 gates (2026-11-12, parent `ff4b84c`)

Evidence from `scripts/macos_live_gate.sh` (`/tmp/open-frame-a2-live-gate-4`) and `scripts/app_matrix_gate.sh` with `OPENFRAME_APP_MATRIX_STRICT=1` (`/tmp/open-frame-a2-app-matrix-5`).

- **calibration_5x, 5/5.**
- **geometry clicks.** Each double-click left the TextEdit insertion point inside `CALMARK89` (selected text empty, range 5,4). Window-scoped and region clicks at (336, 201). `frame_path` click at (331, 207).
- **app matrix, 6/6.** Finder, Safari, Mail, System Settings, Notes, Calendar. One earlier strict run failed Mail because the window guard saw Cursor. The recorded run is the one after a guarded step takes the expected app back and checks again.

## macOS 27 gates (2026-11-12, `c924fca`)

Evidence from `scripts/macos_live_gate.sh` (`/tmp/open-frame-c-live-gate`) and `scripts/app_matrix_gate.sh` with `OPENFRAME_APP_MATRIX_STRICT=1` (`/tmp/open-frame-c-app-matrix`). This is the run that backed release 0.2.2. The published tag is one commit later and only changes the version, changelog, and contract label.

- **calibration_5x, 5/5.**
- **geometry clicks.** Each double-click left the TextEdit insertion point inside `CALMARK89` (selected text empty, range 5,4). Window-scoped click at (336, 201). Region click at (328, 207). `frame_path` click at (331, 207).
- **app matrix, 6/6.** Finder, Safari, Mail, System Settings, Notes, Calendar.

## macOS 27 gates (2026-11-13, `ecd041c`)

Evidence from `scripts/macos_live_gate.sh` (`/tmp/open-frame-f-live-gate`) and `scripts/app_matrix_gate.sh` with `OPENFRAME_APP_MATRIX_STRICT=1` (`/tmp/open-frame-f-app-matrix`). The README walk is not part of this run.

- **calibration_5x, 5/5.**
- **geometry clicks.** Each double-click left the TextEdit insertion point inside `CALMARK89` (selected text empty, range 5,4). Window-scoped click at (336, 201). Region click at (328, 207). `frame_path` click at (331, 207).
- **intentional failure.** The flow exited 1 and wrote `/tmp/open-frame-f-live-gate/runs/live-gate-miss`. The gate's own check still looks for `runs/live-gate-miss` relative to the repo. That directory is from 2026-08-03, so the check passed against the leftover directory. This run's artifacts are the ones under `OPENFRAME_RUNS_DIR`.
- **app matrix, 6/6.** Finder, Safari, Mail, System Settings, Notes, Calendar. Strict mode on.

## README walk (2026-11-13, wheel from `ecd041c`)

Clean venv `/tmp/open-frame-readme-walk-venv`. Installed `/tmp/open-frame-readme-dist/off_camber_open_frame-0.2.2-py3-none-any.whl` with extras `mcp,ocr,act,flow,template`. `OPENFRAME_RUNS_DIR=/tmp/open-frame-readme-runs`, so the dry-run images did not go to `~/.openframe`. Those images were deleted after the size check. Tesseract 5.5.2 was already on `PATH`; `brew install tesseract` was not run again.

- `open-frame --version` printed `open-frame 0.2.2`.
- `open-frame doctor` exit 0, `overall: ok`. `display_power` passed, awake and unlocked. Screen recording and accessibility passed. `extra_agent` skipped, which the README says does not fail the report.
- `open-frame doctor --mcp` exit 0, `overall: ok`, `mcp_server` listed 8 tools. The config command was the walk venv's Python. stderr printed `Processing request of type ListToolsRequest`.
- `python -m openframe.cli doctor` exit 0, `overall: ok`.
- `open-frame mcp serve` stays running while stdin is open. A background launch in this shell exited because stdin closed.
- `open-frame find "Submit" --json` exit 0, `count` 0, source `screen:1`.
- `open-frame run hello.yaml --dry-run --json` exit 0, `success` true, `dry_run` true. `before.png` was 1,958,270 bytes and `after.png` was 1,958,100 bytes. Paths were absolute under `OPENFRAME_RUNS_DIR`.

## Notes

- Prefer sequential tool calls on one stdio server (see [MCP_SERVER.md](MCP_SERVER.md)).
- After timeouts, restart the MCP server process before continuing.
