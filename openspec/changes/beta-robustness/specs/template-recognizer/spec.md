# Spec: Template Recognizer

**PR:** 2 — `feat/template-recognizer`

## Requirements

### Requirement: Opt-in template matching via Recognizer plugin

Open Frame SHALL provide a template/image matcher implementing the
existing `Recognizer` interface, installed behind an optional extra, and
invoked only when a caller supplies a `template` image path.

#### Scenario: default callers unchanged
- **WHEN** find/click runs without a `template` param
- **THEN** recognition uses the existing a11y + OCR locator chain only

#### Scenario: template hit
- **WHEN** find/click is given a template crop that appears once on screen
- **THEN** a target is returned with usable bounds and confidence derived
  from the match score

### Requirement: Fail-closed and scale-aware selection

Template matches SHALL participate in the same fail-closed multi-match
and scale-aware selector semantics as OCR/a11y targets.

#### Scenario: ambiguous templates
- **WHEN** a template matches more than once and no selector is provided
- **THEN** side-effecting actions fail closed with an ambiguous-target
  error

#### Scenario: Retina parity
- **WHEN** the same template is evaluated on 1x and 2x fixtures
- **THEN** selected click points agree after `scale_factor` normalization

### Requirement: Live proof on an icon-only target

A live probe SHALL demonstrate a target that OCR cannot read but template
matching can.

#### Scenario: icon probe
- **WHEN** the live template probe runs on the audited Mac
- **THEN** OCR find for the icon fails or returns no usable text match
- **AND** template find succeeds with non-zero bounds

## Out of scope for this PR

- Vision/VLM recognizers
- Auto-generating templates from recordings
