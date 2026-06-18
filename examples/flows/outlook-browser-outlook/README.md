# Outlook → Browser → Outlook Handoff

This flow validates cross-app focus and action handoff for Phase 5.6.

## What it does

1. Focuses Outlook and opens a compose surface
2. Switches to browser and navigates to Microsoft 365
3. Verifies browser surface text
4. Returns to Outlook and verifies compose text

## Dry-run first

```bash
open-frame run examples/flows/outlook-browser-outlook/flow.yaml --dry-run --json
```

## Live run

```bash
open-frame run examples/flows/outlook-browser-outlook/flow.yaml --json
```

## Notes

- Default browser app in this flow is `Google Chrome`; adjust `variables.browser_app` if needed.
- Keep all apps signed in and visible before running.
