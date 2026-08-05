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
