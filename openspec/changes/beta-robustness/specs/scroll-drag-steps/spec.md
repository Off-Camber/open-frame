# Spec: Scroll and Drag Steps

**PR:** 3 — `feat/scroll-drag-steps`

## Requirements

### Requirement: Scroll and drag are first-class flow steps

The flow runner SHALL support `scroll` and `drag` step kinds backed by
the actuator (extending pyautogui).

#### Scenario: scroll step
- **WHEN** a flow runs a `scroll` step with a bounded amount
- **THEN** the actuator scrolls and the step records success details
  (including dry-run)

#### Scenario: drag step
- **WHEN** a flow runs a `drag` step between two points or resolved
  targets
- **THEN** the actuator performs the drag (or dry-run logs the path)

### Requirement: Bounded scroll-until-found on find/click

`find` and `click` steps SHALL accept optional scroll-until-found
parameters with a hard maximum attempt count.

#### Scenario: below-fold target
- **WHEN** a target is off-screen below the fold and scroll-until-found
  is enabled with a sufficient attempt budget
- **THEN** the step scrolls and eventually finds the target, or fails
  after exhausting attempts with artifacts

#### Scenario: no infinite loop
- **WHEN** the target never appears
- **THEN** the step stops at max attempts and fails closed

### Requirement: MCP exposes scroll

The MCP adapter and stdio server SHALL register a `scroll` tool with an
explicit JSON schema, returning the standard envelope.

#### Scenario: tool listing
- **WHEN** a client lists MCP tools after this PR
- **THEN** `scroll` appears alongside the existing tools

## Out of scope for this PR

- Contract version promotion (deferred to PR 4 decision)
- Gesture recognition beyond scroll/drag
