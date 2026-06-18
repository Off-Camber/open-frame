# Outlook → M365 → Email (MVP Reference Flow)

This is the full Phase 5.7 reference flow aligned to the MVP goalpost.

## Flow intent

1. Focus Outlook and open compose
2. Switch to browser and open Word Online (M365)
3. Type document content/title
4. Return to Outlook, fill recipient/subject/body, attach file path, and send
5. Verify sent-state text

## Prep checklist (required before run)

1. Sign in to **New Outlook for Mac**
2. Sign in to Microsoft 365 in your chosen browser
3. Confirm no MFA prompt is pending
4. Ensure `open-frame` host app has:
   - Accessibility permission
   - Screen Recording permission
5. Keep Outlook and browser windows visible

## Environment assumptions

- OS: macOS
- Outlook variant: New Outlook for Mac
- Browser: Chrome by default in this flow (`variables.browser_app`)
- UI language: English

## Run commands

Dry-run:

```bash
open-frame run examples/flows/outlook-m365-email/flow.yaml --dry-run --json
```

Live run:

```bash
open-frame run examples/flows/outlook-m365-email/flow.yaml --json
```

## Notes

- `attachment_path` uses variable substitution (`{{run_dir}}`, `{{run_id}}`) and assumes the file is prepared by your surrounding process.
- Adjust queries (`To`, `Subject`, `Message`, `Send`) if your Outlook UI labels differ.
