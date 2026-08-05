# Proposal: Beta Robustness Program

## Why

`v0.2.0` Beta shipped the adoption surface (MCP stdio server, doctor,
onboarding). The product claim — recognition and action for anything on a
display — is only proven for text targets, in TextEdit, on one Mac.

Four claim gaps remain before the tool is safe to promote publicly:

1. Recognition is text-only (a11y + OCR). Icon buttons and custom widgets
   are invisible.
2. Interaction primitives are incomplete (`scroll` exists on the actuator
   but not as a flow/MCP step; no `drag`).
3. Evidence is one app on one machine. No systematic Finder / Safari /
   Mail / Settings / Notes / Calendar coverage.
4. The MCP stdio server is unhardened under real agent load (timeouts,
   payload bounds, long `run_flow`).

## Success criterion

On the audited Mac, a multi-app live matrix reports pass for the agreed
built-in apps and Safari probes; template matching can locate an icon-only
target OCR cannot; scroll/drag flows reach below-the-fold targets; and the
full gate package (CI + live gate + matrix + MCP repeatability + agent
acceptance) is green on a candidate SHA.

## Scope

In scope:

- Multi-app live validation matrix (Finder, Safari, Mail, System Settings,
  Notes, Calendar) with non-destructive dry-run probes
- Template/image matching recognizer (opt-in `template` param)
- `scroll` and `drag` flow steps; `scroll_until_found` on find/click;
  MCP `scroll` tool
- Defect burn-down from matrix results; MCP server timeout/payload hardening
- Dogfooding evidence and full gate rerun before any version decision

Out of scope:

- Vision/VLM recognizer (Phase 7 stays gated)
- Windows/Linux backends
- Orchestration, MFA/SSO, credential vaults
- Multi-provider agent work

## Delivery model

Local OpenSpec planning package (this tree, not committed) plus four
public PRs.

| Step | Branch suggestion | Capability | Merge gate |
|---|---|---|---|
| 0 (local only) | n/a — do not commit | This OpenSpec change | Local planning artifact only |
| 1 | `chore/app-validation-matrix` | `app-validation-matrix` | Matrix runs + report artifact; matrix failures OK to merge |
| 2 | `feat/template-recognizer` | `template-recognizer` | Fixture 1x/2x + live icon probe |
| 3 | `feat/scroll-drag-steps` | `scroll-drag-steps` | Unit + live Safari scroll probe |
| 4 | `chore/robustness-gates` | `robustness-gates` | CI + matrix + live gate + MCP + agent green |

PR 1 first. PRs 2 and 3 can proceed in parallel after PR 1 lands. PR 4
last and owns the version decision.

## Release posture

Remain on published `0.2.0` Beta until PR 4's gate checklist passes.
Version bump (`0.2.x` or `0.3.0`) only after evidence, and only if PR 3's
MCP contract addition warrants it.
