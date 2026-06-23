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

### Added
- Window-level state awareness (Phase 11): `frontmost_window()` API, optional `window` guard on flow steps, `scope: window` recognition scoping, and verify specs `window-title-contains`, `window-role`, `window-app`.

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
