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
| 2026-11-13 | Local CLI | Live gate and strict app matrix on macOS 27.0.1, SHA `98342fb`, Python 3.11.15 (`.venv`), Tesseract 5.5.2, one display. Evidence `/tmp/open-frame-030rc1-live-gate` and `/tmp/open-frame-030rc1-app-matrix`. This is the `0.3.0rc1` commit. | Live gate **pass**. Calibration **5/5**. Window click (336, 201), region (328, 207), `frame_path` (331, 207), each with an empty selection and range 5,4 inside `CALMARK89`. App matrix **6/6** with `OPENFRAME_APP_MATRIX_STRICT=1`. |
| 2026-11-13 | Clean venv, PyPI `0.3.0rc1` | `pip install "off-camber-open-frame[mcp,ocr,act,flow,template]==0.3.0rc1"` into `/tmp/open-frame-030rc1-pypi-venv`. `OPENFRAME_RUNS_DIR=/tmp/open-frame-030rc1-pypi-runs`. | `open-frame --version` printed `open-frame 0.3.0rc1`. `doctor --mcp` exit 0, **overall: ok**, 8 tools. One MCP `run_flow` call with `dry_run` true returned `isError` false and `success` true. Before/after images were about 1.78 MB each and were deleted after the size check. |
| 2026-11-14 | Cursor and Claude Desktop, PyPI `0.3.0rc1` in `~/of-rc` | Short check. Cursor: full-screen `find` and `click` on `CALMARK89`. Claude Desktop: `find`, then a window capture, `find`, and `click` on that path. The fresh-account README check was not done. | Cursor connected with 8 tools. Full-screen `find` returned 3 matches; `expect_one` returned `ambiguous_target` (4 matches) and sent no click. `left_most` dry-run and live click returned ok at (100, 228) for a target at physical (138, 448), 126×18 (run `20261114T023512Z`). Not confirmed by eye. Claude `find` failed with `validation_error` until `TMPDIR` was set; a click then deleted the capture path. With an `out_path` outside the temp directory, the live click returned ok at (197, 240) (run `20261114T041857Z`). Not confirmed by eye. `doctor` and `doctor --mcp` passed from a terminal that had `TMPDIR` and did not run OCR. |

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

## macOS 27 gates (2026-11-13, `98342fb`, version `0.3.0rc1`)

Evidence from `scripts/macos_live_gate.sh` (`/tmp/open-frame-030rc1-live-gate`) and `scripts/app_matrix_gate.sh` with `OPENFRAME_APP_MATRIX_STRICT=1` (`/tmp/open-frame-030rc1-app-matrix`). This is the commit later tagged `v0.3.0rc1`. The PyPI install check is recorded below.

- **calibration_5x, 5/5.**
- **geometry clicks.** Each double-click left the TextEdit insertion point inside `CALMARK89` (selected text empty, range 5,4). Window-scoped click at (336, 201). Region click at (328, 207). `frame_path` click at (331, 207).
- **intentional failure.** The flow exited 1 and wrote `/tmp/open-frame-030rc1-live-gate/runs/live-gate-miss`. The gate's own check still looks for `runs/live-gate-miss` relative to the repo. That directory is from 2026-08-03, so the check passed against the leftover directory.
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

## PyPI install (2026-11-13, `0.3.0rc1`)

Clean venv `/tmp/open-frame-030rc1-pypi-venv`, Python 3.11.15. Installed from PyPI with `pip install "off-camber-open-frame[mcp,ocr,act,flow,template]==0.3.0rc1"`. `importlib.metadata` reported `0.3.0rc1`. `OPENFRAME_RUNS_DIR=/tmp/open-frame-030rc1-pypi-runs`, so the dry-run images did not go to `~/.openframe`. The png files were deleted after the size check. Tesseract 5.5.2 was already on `PATH`.

- `open-frame --version` printed `open-frame 0.3.0rc1`.
- `open-frame doctor --mcp` exit 0, `overall: ok`. `display_power` passed, awake and unlocked. Screen recording and accessibility passed. One display. `extra_agent` skipped. `mcp_server` listed 8 tools. The config command was `/private/tmp/open-frame-030rc1-pypi-venv/bin/python3.11`. stderr printed `Processing request of type ListToolsRequest`.
- One MCP tool call, `run_flow` on `/tmp/open-frame-030rc1-pypi/hello.yaml` with `dry_run` true. The flow is a one-step wait and does not click or type. `isError` was false. The envelope had `ok` true, `dry_run` true, and `success` true. The pause step succeeded in 580 ms. `before.png` was 1,779,236 bytes and `after.png` was 1,781,152 bytes. stderr printed `Processing request of type CallToolRequest` and `Processing request of type ListToolsRequest`.

## rc1 short check (2026-11-14, PyPI `0.3.0rc1`)

Ben ran this against `0.3.0rc1` installed from PyPI in `~/of-rc`. The README check from a macOS account that has never had Open Frame installed was not done.

### Cursor

The server connected and listed 8 tools. A full-screen `find` for `CALMARK89` returned 3 matches. A `click` with `expect_one` returned `ambiguous_target` (4 matches) because the chat itself contained the token, and no click was sent. With `selector: left_most`, the dry run reported (100, 228) for a target at physical (138, 448), 126×18. The live click returned ok at the same point (run `20261114T023512Z`). Ben has not confirmed by eye where it landed.

### Claude Desktop

`find` failed every time with `validation_error: 'utf-8' codec can't decode byte 0x89 in position 270`. `capture` worked. The underlying error is Leptonica failing to open `/tmp/tess_*_input.PNG`. Claude starts the server with only `HOME`, `LOGNAME`, `PATH`, `SHELL`, and `USER`, so there is no `TMPDIR` and Python uses `/tmp`.

The same `find` from a terminal returns count 1 with `TMPDIR` set and the same decode error with `env -u TMPDIR`. Bare `tesseract` on a copy of the image under `/tmp` failed to open it; the same file under `~/.openframe/tmp` was read.

Claude Desktop's config was given `"env": {"TMPDIR": "/Users/ben/.openframe/tmp"}` for `open-frame` so the rest of the check could run. With that set, `find` works. That entry has to be removed before the rc2 check.

After a window capture and a successful `find` on its `image_path`, a click on the same path returned `Frame path does not exist`. The first click deletes a temporary capture after copying it into the run directory. A capture written with `out_path` outside the temp directory survived, and the live click on it returned ok at (197, 240) for a target at (16, 179), 507×112, confidence 0.92 (run `20261114T041857Z`). Not confirmed by eye.

`doctor` and `doctor --mcp` passed on this install. Neither ran OCR, and both ran from a terminal with `TMPDIR` set.

A live click with `left_most` returned ok at (894, 427) on a match whose text was `"CALMARK89"` with quotes, which is Claude's own chat text rather than TextEdit. The token at 12pt and selected was not read in a window capture (count 0); at 48pt and unselected it was read with confidence 0.92.

## Notes

- Prefer sequential tool calls on one stdio server (see [MCP_SERVER.md](MCP_SERVER.md)).
- After timeouts, restart the MCP server process before continuing.
