# Outlook New Email Smoke Flow

This flow is the first Phase 5 smoke target.

## What it does

1. Focuses Microsoft Outlook
2. Clicks `New Email`
3. Verifies compose UI text appears (`To`)
4. Waits briefly for stabilization

## Dry-run first

```bash
open-frame run examples/flows/outlook-new-email/flow.yaml --dry-run --json
```

## Live run

```bash
open-frame run examples/flows/outlook-new-email/flow.yaml --json
```

## Notes

- Ensure Outlook is already signed in and visible.
- Keep Accessibility and Screen Recording permissions enabled for the app running `open-frame`.
