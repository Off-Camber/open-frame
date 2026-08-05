# Spec: App Validation Matrix

**PR:** 1 — `chore/app-validation-matrix`

## Requirements

### Requirement: Probe flows cover agreed built-in apps and Safari

The repository SHALL include non-destructive probe flows under
`examples/flows/app-matrix/` for Finder, Safari, Mail, System Settings,
Notes, and Calendar.

#### Scenario: probe shape
- **WHEN** an operator inspects an app-matrix flow
- **THEN** it activates the app, finds a known visible target, performs a
  dry-run click (or equivalent non-destructive action), and optionally
  verifies a stable on-screen condition
- **AND** it does not compose, send, delete, or write preferences

### Requirement: Matrix gate produces a per-app report

A runnable script (`scripts/app_matrix_gate.sh`) SHALL execute the probe
flows and write JSON + markdown summarizing each app as pass, fail, or
skip with artifact paths.

#### Scenario: operator run
- **WHEN** an operator runs the matrix gate on a permissioned Mac
- **THEN** a report lists every app with status and evidence location

### Requirement: Matrix failures do not block shipping the instrument

Merging the matrix tooling SHALL NOT require every app probe to pass.
Failures seed the PR 4 defect list.

#### Scenario: partial fail still useful
- **WHEN** Safari passes and Mail fails
- **THEN** the report records both outcomes and the tooling remains
  mergable

## Out of scope for this PR

- Fixing app-specific recognition/actuation defects (PR 4)
- Template matching or scroll/drag features
