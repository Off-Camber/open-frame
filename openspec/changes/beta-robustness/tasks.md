# Tasks: Beta Robustness Program (PR Plan)

Track progress per PR. Mark a task complete only when its PR acceptance
criteria are met.

## Step 0 — Local OpenSpec plan (do not commit)

- [x] Create `openspec/changes/beta-robustness/` proposal, design, tasks, and specs
- [x] Mark this package `visibility: local_only` / `commit: never`
- [x] Keep this tree untracked; do not open a docs PR for it

**Acceptance:** planning is usable locally; nothing under this change path is
pushed to the public repository.

## PR 1 — Multi-app live validation matrix

Branch: `chore/app-validation-matrix`  
Spec: `specs/app-validation-matrix/spec.md`  
Status: **merged** — GitHub PR #23 (`bda8eaa` on `main`); feature branch deleted

- [x] Add `examples/flows/app-matrix/` probe flows (Finder, Safari, Mail, System Settings, Notes, Calendar)
- [x] Keep probes non-destructive (find+verify; no compose/send/delete/preference writes)
- [x] Add `scripts/app_matrix_gate.sh` producing JSON + markdown per-app report with artifacts
- [x] Document how to run the matrix and how failures seed the PR 4 defect list
- [x] Run the matrix once on the audited Mac; capture baseline report (failures allowed)
  - Baseline evidence: `/Users/ben/Workspace/open-frame-app-matrix-20260805T032540Z` (4 pass / 2 fail)
  - Defect themes: Calendar cold-start `-600`; Finder menu-bar vs window scope; intermittent `_focus_app` frontmost stickiness/`None`
- [x] Open PR; merge; delete branch

**Acceptance:** operator can run the matrix and get a per-app pass/fail report with
artifacts; matrix tooling merges even if some apps fail.

## PR 2 — Template matching recognizer

Branch: `feat/template-recognizer`  
Spec: `specs/template-recognizer/spec.md`  
Status: **done** (merged to main)

- [x] Add `template` optional extra (Pillow + numpy) and `src/openframe/recognize/template/`
- [x] Implement `Recognizer` with normalized cross-correlation; Retina/`scale_factor` parity
- [x] Opt-in `template` path param through Locator / runner / CLI / MCP (default path unchanged)
- [x] Fail closed on zero/ambiguous matches unless explicit selector
- [x] Fixture tests at 1x and 2x; live icon-only target probe (OCR miss, template hit)
- [x] Open PR; merge; delete branch

**Acceptance:** icon-only target found via template; a11y+OCR-only callers unchanged.

## PR 3 — Scroll and drag flow steps

Branch: `feat/scroll-drag-steps`  
Spec: `specs/scroll-drag-steps/spec.md`  
Status: **in progress**

- [x] Expose `scroll` flow step; add `Actuator.drag` + `drag` flow step
- [x] Add bounded `scroll_until_found` params on `find` / `click`
- [x] Add MCP `scroll` tool to adapter + stdio server (schemas + tests)
- [x] Unit tests with monkeypatched actuator; live Safari below-fold probe
- [ ] Open PR; merge; delete branch

**Acceptance:** a below-fold Safari target is reachable via scroll_until_found;
drag unit-covered; MCP lists `scroll`.

## PR 4 — Defect burn-down + MCP hardening

Branch: `chore/robustness-gates`  
Spec: `specs/robustness-gates/spec.md`  
Status: **planned** — depends on PRs 1–3

- [ ] Triage PR 1 matrix defect list; fix timeboxed local defects
- [ ] MCP server: per-tool timeout, bounded payloads, docs for sequential single-client use
- [ ] Dogfooding evidence log (Claude Desktop and/or Cursor)
- [ ] Rerun CI + live gate + app matrix + MCP repeatability + agent acceptance
- [ ] Decide version (`0.2.x` vs `0.3.0`) from evidence; bump only if gates pass
- [ ] Open PR; merge; delete branch; tag/publish if version bumped

**Acceptance:** gates green on candidate SHA; promotion decision is evidence-based.

## Suggested merge order

1. Keep Step 0 local
2. PR 1
3. PRs 2 and 3 in any order
4. PR 4 last
