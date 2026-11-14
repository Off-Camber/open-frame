# Changelog

All notable changes to this project are documented in this file.

## Entry format

Use this template for each release:

```md
## vX.Y.Z - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Docs
- ...
```

Guidelines:

- Keep entries user-facing (what changed and why it matters).
- Group by impact area (`Added`, `Changed`, `Fixed`, `Docs`).
- Keep bullets concise and specific.
- Link PRs/issues when available.

## Unreleased

## v0.3.0 - 2026-11-14

Stable version number. The package is still Beta. The MCP contract label stays `v0.3.0`.

### Fixed
- `open-frame doctor` names the interpreter it checked. A `skip` for `mcp` or `template` means that distribution is absent from that interpreter. An installed distribution that cannot be imported is reported separately, and a `VIRTUAL_ENV` that does not match the running process fails the `python` check.

### Docs
- The quickstart checks Python 3.11 before install, creates and activates a virtual environment, upgrades pip, and installs with `python -m pip`. It also explains a shared Homebrew that a standard account cannot write to.
- The standard extras (`ocr`, `act`, `flow`, `mcp`, `template`) are documented separately from the optional `agent` extra. Doctor prints a `note` for an optional extra that was not installed, and a `hint` for a failure. Published installs are told `python -m pip install "off-camber-open-frame[agent]"`; `pip install -e ".[agent]"` stays the checkout command.
- An unpinned install selects this release. `0.3.0rc2` was a pre-release, so the quickstart no longer tells you to pin it.

## v0.3.0rc2 - 2026-11-14

Release candidate. The package is still Beta. The MCP contract label stays `v0.3.0`.

### Fixed
- OCR works when a GUI client starts the server without `TMPDIR`. Tesseract input is written under `~/.openframe/tmp`, because Leptonica rewrites paths that start with `/tmp` and then cannot open the file Python wrote.
- A Tesseract failure is `ocr_error` with a readable message.
- A frame passed as `frame_path` is not deleted after a click. A `capture` with no `out_path` is stored in the runs directory until `open-frame runs prune`.
- `open-frame doctor` reads a generated image, so a broken OCR setup fails before a client calls `find`.
- The live gate's intentional-failure check looks in the configured runs directory. Its no-`TMPDIR` check passes when OCR reads a generated image, screen recording works, and `doctor --mcp` lists its tools. An empty accessibility tree is recorded and does not fail that check.

### Docs
- The MCP server docs say a full-screen find also matches text in the chat that asked for it, and show capturing the target window and passing that `frame_path` to find and click.
- Runtime messages that said `pip install -e` now use the PyPI package name.

## v0.3.0rc1 - 2026-11-12

Release candidate. The package is still Beta. The MCP contract label is `v0.3.0`.

### Added
- `open-frame --version` prints the installed package version, and the MCP handshake reports that same version.
- `open-frame doctor --mcp` fails when the mcp, act, or ocr extras are missing, starts the server and lists its tools, and prints a client config that uses the current interpreter. Screen Recording and Accessibility must be granted to the MCP client (Cursor or Claude Desktop).
- `open-frame doctor` warns when more than one display is online. Capture stays on the primary display.

### Changed
- MCP contract `v0.3.0`. `click`, `type`, `key`, `scroll`, and `run_flow` now default `dry_run` to true. Live input requires `"dry_run": false`.
- A missing Screen Recording or Accessibility grant returns `permission_denied` and names the host process. A locked or sleeping display returns `screen_unavailable` instead of a permission error.
- `key` requires exactly one of `key` or `combo`. `type` rejects empty text. Full `run_flow` step details are capped at 32,000 characters.
- Doctor install hints use `pip install "off-camber-open-frame[extra]"`.
- The README quickstart writes a one-step flow in the current directory so it works from a wheel, without the `examples/` tree.
- Run artifacts go to an absolute directory (`~/.openframe/runs`, or `OPENFRAME_RUNS_DIR`). Tool results return those absolute paths. `open-frame runs prune` deletes runs by age and by count. Temporary capture images are removed once they have been copied into the run directory.

### Docs
- The README quickstart says a dry-run flow still captures the screen, and that `find` exiting 0 with `count` 0 means the text was not on screen.
- API, MCP, verify, and setup docs match the current tools, defaults, and install command. A locked screen is documented separately from a missing permission.

### Fixed
- A flow window guard that names an app focuses that app once and checks again before the step fails ([#34](https://github.com/Off-Camber/open-frame/pull/34)).

## v0.2.2 - 2026-11-12

### Changed
- MCP contract label `v0.2.2`. Envelope keys are unchanged. `busy` is an added error code for a tool call that arrives while another call is still running, including one that already returned `timeout` ([#35](https://github.com/Off-Camber/open-frame/pull/35)).

### Fixed
- Window, region, and `frame_path` clicks map image pixels with the capture scale and origin. A live `frame_path` click without capture metadata is refused ([#33](https://github.com/Off-Camber/open-frame/pull/33)).
- The calibration token is read from both a grayscale pass and a threshold pass, so spell-check dots and a clean region capture can both match ([#34](https://github.com/Off-Camber/open-frame/pull/34)).
- A timed-out MCP tool does not start another click, keystroke, scroll, drag, or flow step. `click` and `run_flow` timeouts include `run_id` ([#35](https://github.com/Off-Camber/open-frame/pull/35)).
- `screencapture` and `osascript` stop after 30 seconds instead of blocking. A flow `diff` check compares a fresh capture with the previous step's starting frame. An accessibility failure is reported, and a find with no matches after a recognizer error is no longer `not_found` ([#36](https://github.com/Off-Camber/open-frame/pull/36)).

### Docs
- macOS 27 live-gate and strict app-matrix results are in the dogfooding log.

## v0.2.1 - 2026-08-05

### Added
- Flow `scroll` / `drag` steps and bounded `scroll_until_found` on find/click.
- Opt-in template/image matching recognizer (`.[template]`).
- MCP wall-clock tool timeouts (`timeout` error code) and summarized `run_flow` step payloads by default.

### Changed
- MCP contract label `v0.2.1` (envelope keys unchanged).
- `_focus_app` launches via `open -a`, retries AppleEvent `-600`, and nudges System Events frontmost.

### Fixed
- Calendar cold-start focus failures and intermittent frontmost stickiness/`None` reads on the app matrix.

### Docs
- Robustness triage, dogfooding log, MCP sequential-use / payload-bound guidance.

## v0.2.0 - 2026-08-05

### Added
- MCP stdio server via `open-frame mcp serve` (optional `.[mcp]` extra) so Claude Desktop / Cursor can call the seven Open Frame tools over the MCP protocol ([#20](https://github.com/Off-Camber/open-frame/pull/20)).
- `open-frame doctor` diagnostics for platform, extras, tesseract, Screen Recording, and Accessibility ([#21](https://github.com/Off-Camber/open-frame/pull/21)).
- Live gate MCP stdio smoke check (handshake + dry-run tool call).

### Changed
- Package status promoted to **Beta**; MCP contract label is now `v0.2.0` (envelope unchanged).

### Docs
- README quickstart reworked as install → doctor → connect MCP client → first flow.
- New [MCP server setup](docs/MCP_SERVER.md) with Claude Desktop and Cursor config.

## v0.1.2 - 2026-06-22

### Added
- Window-level state awareness (Phase 11): `frontmost_window()` API, optional `window` guard on flow steps, `scope: window` recognition scoping, and verify specs `window-title-contains`, `window-role`, `window-app`.

### Fixed
- Frontmost window bounds correctly read array-shaped `position`/`size` returned by System Events JXA; previously bounds collapsed to zero.

### Docs
- Flow setup guide gains a "window-aware guards and scoping" section; verify setup lists the new window specs.

## v0.1.1 - 2026-06-18

### Changed
- Upgraded GitHub Actions workflow versions for CI and publishing.
- Improved flow reliability with retryable find behavior and verify polling.

### Fixed
- Made PyPI publish workflow reruns idempotent via `skip-existing`.

### Docs
- Polished release-facing documentation and clarified current roadmap/checkpoint framing.

## v0.1.0 - 2026-06-15

### Added
- Initial Open Frame MVP engine: capture, recognize, act, verify, and YAML flow runner.
- Example Outlook/M365 flows and acceptance-run artifact reporting.

### Docs
- Added setup, verification, flow, and planning docs for MVP usage.
