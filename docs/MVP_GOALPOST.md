# MVP goalpost (v0.1 milestone context)

This document captures what **done** meant for the first meaningful release
milestone (`v0.1.x`): not a toy demo, but a credible RPA-style cross-app flow.

For the current product direction and active release gates, use:

- [V0_2_0_CHECKPOINT.md](V0_2_0_CHECKPOINT.md) (current checkpoint contract)
- `examples/flows/` (source of truth for executable flow syntax)

---

## Success statement

> A **declarative flow file** can be run repeatedly on a prepared desktop and executes a **multi-application user journey** — Outlook → Microsoft 365 (web) → create documents → compose and send email — with **verification at each step**, producing the **same outcome every run** (within defined environment constraints).

That was the bar for the **v0.1 milestone**.

---

## Reference flow (historical): Outlook → M365 → email

Typical enterprise RPA pattern. Open Frame now ships executable flow specs in:

- `examples/flows/outlook-m365-email/flow.yaml`
- `examples/flows/word-create-only/flow.yaml`
- `examples/flows/outlook-send-only/flow.yaml`
- `examples/flows/doc-attach-email/flow.yaml`

### Narrative (what the bot does)

1. **Outlook (desktop)** — focus the app; start a new email (or open draft folder pattern).
2. **Browser** — open/focus Microsoft 365; create a **Word** document (online) with defined content from flow variables.
3. **Browser** — optionally create or attach a second artifact (e.g. simple **Excel** sheet or PDF export).
4. **Outlook (desktop)** — return to the compose window; set **To**, **Subject**, **Body** from variables; attach the file(s) created in step 2–3.
5. **Send** — send the email (or save to Drafts if `dry_run: true`).
6. **Verify** — confirm send succeeded (sent folder, toast, or absence of compose window).

### Example flow shape (illustrative, not syntax-authoritative)

```yaml
name: outlook-m365-email
variables:
  recipient: "test@example.com"
  subject: "Open Frame MVP run {{run_id}}"
  doc_title: "Weekly summary"
  body: "Automated message from Open Frame."

steps:
  - id: focus-outlook
    app: "Microsoft Outlook"    # Outlook for Mac
    verify: window-focused

  - id: new-email
    click: "New Email"          # a11y name or OCR text
    verify: text-visible: "To"

  - id: open-word-online
    app: "Google Chrome"        # or Safari — pinned in test env (macOS MVP)
    navigate: "https://www.office.com/launch/word"
    verify: text-visible: "Word"

  - id: create-document
    click: "Blank document"
    type: "{{doc_title}}"
    # … save/download to known path …
    verify: file-exists: "{{artifacts.summary.docx}}"

  - id: return-outlook
    app: "Microsoft Outlook"
    fill:
      To: "{{recipient}}"
      Subject: "{{subject}}"
      Body: "{{body}}"
    attach: "{{artifacts.summary.docx}}"

  - id: send
    click: "Send"
    verify: text-visible: "Sent Items"   # or window-closed + sent confirmation

  - id: assert-run
    assert: sent-folder-contains: "{{subject}}"
```

The snippet above is intentionally illustrative and not maintained as the parser
contract. Treat `examples/flows/*.yaml` plus [FLOW_SETUP.md](FLOW_SETUP.md) as
the authoritative syntax reference.

---

## What MVP must prove (engine capabilities)

| Capability | Why the reference flow needs it |
|------------|----------------------------------|
| **Flow file** — ordered steps + variables | Defines the process without recompiling code |
| **App focus** — bring window to front by title/process | Switch Outlook ↔ browser |
| **Find & click** — by a11y label or visible text | Ribbon buttons, links |
| **Type & shortcuts** — fields, Cmd/Ctrl+S, Tab | Compose email, edit doc |
| **Wait** — fixed, or until condition | Pages and dialogs load |
| **Verify** — text visible/gone, window state, file exists | Repeatability |
| **Artifacts** — screenshot + JSON per step on failure | Debug like real RPA |
| **Run ID / variables** — parameterize subject, paths | Same flow, repeatable data |
| **Deterministic recognizers first** — a11y + OCR (+ template where needed) | Same result every time; vision optional later |

---

## Acceptance criteria (checklist)

Run on a **documented test environment** (see below). All must pass:

- [ ] Flow runs end-to-end with **zero manual clicks** after prep
- [ ] **3 consecutive runs** complete with the same logical outcome (email sent with expected subject and attachment)
- [ ] Any failed step exits **non-zero**, writes artifacts under `runs/<run_id>/`
- [ ] Flow file is **readable by a non-author** (structure documented in `docs/`)
- [ ] `open-frame run examples/flows/outlook-m365-email/flow.yaml` (or equivalent) is the documented entry point

---

## Test environment (explicit assumptions)

Open Frame automates **after auth** — the same boundary most RPA deployments use in practice.

| Assumption | Notes |
|------------|--------|
| **Sessions already valid** | Outlook desktop signed in; M365 active in browser before `open-frame run` |
| **Human handles login once** | User (or IT) completes SSO/MFA during setup — not during the flow |
| **No auth prompts mid-run** | If a login or MFA dialog appears, the run **fails fast** with artifacts — not something the bot tries to solve |
| **Fixed app versions & layout** | Classic Outlook vs New Outlook documented; one browser; pinned Office language (English UI) |
| **Known screen resolution / scale** | 100% scale recommended for v0; Retina/HiDPI supported but tested config listed |
| **Test mailbox** | Dedicated recipient; avoid spamming real users |
| **Network** | Office.com reachable; no captive portal |

**Prep checklist** (document in `examples/flows/outlook-m365-email/README.md`):

1. Sign in to Outlook desktop  
2. Sign in to Microsoft 365 in the chosen browser  
3. Confirm no MFA prompt is pending  
4. Run the flow  

Document this in `examples/flows/outlook-m365-email/README.md` when the example exists.

---

## Platform (MVP)

**MVP runs on macOS only.** Windows is planned after v0.1 — same flow format, different engine backends.

| MVP environment | Notes |
|-----------------|--------|
| **OS** | macOS (document version, e.g. Sonoma+) |
| **Outlook** | **New Outlook for Mac** (not Legacy) |
| **M365** | **Word Online** in browser (office.com / launch Word) |
| **Browser** | Chrome or Safari — document which |
| **Permissions** | Screen Recording + Accessibility for Terminal/`open-frame` (System Settings) |
| **Scale** | Document display scale (Retina); engine must map coordinates correctly |

Enterprise RPA often deploys on **Windows**; that is a **post-MVP** goal, not a blocker for v0.1.0.

---

## Out of scope (platform — not just MVP)

### Identity & auth (permanent descope)

- **MFA prompt handling** (TOTP, push approve, SMS, etc.)
- **SSO / OAuth / Azure AD login flows**
- **Credential vaults** and secrets management
- **Session refresh** when tokens expire mid-run

RPA buyers typically solve this with **service accounts**, **excluded MFA policies**, **persistent VMs**, or **separate identity products**. Open Frame documents **prep**; it does not replace IdP.

### MVP and later

- Visual workflow designer (drag-and-drop)
- Unattended scheduling / cron / queue
- Exchange admin or server-side send (must be UI-driven for MVP)
- Parallel runs, multi-user orchestration
- Vision/VLM as **primary** locator (optional fallback only if at all)

---

## Relationship to phases (historical framing)

```
Phases 0–4   Engine: capture, recognize, act, verify
Phase 5      Flow runner + reference flow (this goalpost)
Phase 6+     SDK polish, vision, broader platforms
```

At the time, Phase 5 exit criteria in the project action plan were
aligned with this document rather than a toy single-app demo.

---

## Smaller milestones (still useful before full MVP)

Use these to de-risk without losing sight of the goalpost:

1. **Smoke** — single app: click "New Email" in Outlook, verify compose opens
2. **Handoff** — Outlook → browser → back to Outlook (focus + one action each)
3. **File** — create/save a local file, attach in Outlook (simpler than Word Online first)
4. **Full** — Word Online creation + attach + send (MVP)

If Word Online is flaky during build, fix recognition/waits — **do not** silently downgrade MVP to Word desktop without revisiting [DECISIONS.md](DECISIONS.md).
