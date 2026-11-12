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

## Notes

- Prefer sequential tool calls on one stdio server (see [MCP_SERVER.md](MCP_SERVER.md)).
- After timeouts, restart the MCP server process before continuing.
