# Spec: Robustness Gates

**PR:** 4 — `chore/robustness-gates` (depends on PRs 1–3)

## Requirements

### Requirement: Matrix defects are triaged and timeboxed

Defects discovered by the app matrix SHALL be triaged. Fixable local
defects land in this PR; structural follow-ups are recorded as separate
future work rather than silently ignored.

#### Scenario: triage record
- **WHEN** PR 4 opens
- **THEN** it references the matrix baseline report and lists which
  defects were fixed vs deferred

### Requirement: MCP server hardens under agent load

The stdio MCP server SHALL enforce per-tool timeouts (especially
`run_flow`), keep large results artifact-referenced rather than
unbounded inline payloads, and document single-client sequential use.

#### Scenario: long flow timeout
- **WHEN** `run_flow` exceeds the configured wall-clock timeout
- **THEN** the tool returns an in-band error envelope rather than hanging
  the stdio session indefinitely

### Requirement: Full evidence before version decision

Version/`MCP_CONTRACT_VERSION` changes SHALL land only after CI, the
macOS live gate, the app matrix, MCP dry-run repeatability, and agent
acceptance are green on the candidate SHA, plus a short dogfooding log.

#### Scenario: hold on red gates
- **WHEN** any required gate fails
- **THEN** the version bump does not merge until the failure is fixed
  and the gate rerun

## Out of scope for this PR

- New recognizers or platforms
- Publishing without green gates
