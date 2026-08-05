# App matrix defect triage (PR 4)

Baseline: `/Users/ben/Workspace/open-frame-app-matrix-20260805T032540Z` (4 pass / 2 fail)  
Post-fix matrix: `/Users/ben/Workspace/open-frame-app-matrix-20260805T040506Z` (**6/6 pass**)  
SHA at post-fix: `06ecb643…` (+ this PR's focus hardening).

| Defect | Theme | Disposition | Notes |
|---|---|---|---|
| Finder `File` not found under `scope: window` | Menu-bar vs window scope | **Deferred** (probe fixed) | Window scope correctly excludes menu bar. Probe now queries in-window chrome (`Finder`). Menu-bar AX as a first-class scope is future work. |
| Calendar `activate` → AppleEvent `-600` | Cold-start race | **Fixed in this PR** | `_focus_app` now `open -a` launches first, retries on `-600`, and nudges via System Events frontmost. |
| Intermittent `_focus_app` stickiness / `frontmost=None` | Focus verification | **Fixed in this PR** | Clearer None vs mismatch errors; System Events frontmost nudge; case-insensitive name match + Settings aliases. |

## Follow-ups (not blocking this PR)

- Menu-bar / global accessibility scope mode
- Windows/Linux app focus equivalents
- Stricter app-matrix gate (`OPENFRAME_APP_MATRIX_STRICT=1`) once Calendar+Finder stay green across cold starts
