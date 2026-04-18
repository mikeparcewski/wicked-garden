---
name: 02-small-bugfix
title: Facilitator Rubric — Small Bugfix
description: Verify the facilitator handles a crisp bugfix with unit + integration evidence and standard rigor.
type: rubric
difficulty: beginner
estimated_minutes: 3
---

# Small Bugfix — `/users` Endpoint 500

## Input

> The /users endpoint returns 500 on empty query string.

## Expected facilitator behavior

A clear regression with a crisp repro (empty query string). Small blast radius (one
endpoint). No compliance implications. Rigor is standard because a test gate is
non-negotiable on a production bug. The fix is small but the test must cover both
the specific edge case (empty string) and the normal path, so unit + integration
evidence is required.

## Expected outcome

```yaml
specialists:
  - backend-engineer
  - test-strategist       # or test-designer — either acceptable
  # senior-engineer as reviewer, optional
phases:
  - clarify               # crisp repro, quick clarify of expected behavior
  - build
  - test
  - review                # at least an inline review
evidence_required:
  - unit-results
  - integration-results
test_types:
  - unit
  - integration
complexity: 2             # ±1 tolerance
rigor_tier: standard
factors:
  reversibility: HIGH
  blast_radius: MEDIUM    # customer-facing endpoint
  compliance_scope: LOW
  user_facing_impact: MEDIUM  # users hit this indirectly via failing requests
  novelty: LOW
  scope_effort: LOW
  state_complexity: LOW
  operational_risk: MEDIUM
  coordination_cost: LOW
open_questions: []
re_evaluation: not-applicable
banned_specialists:
  - compliance-officer
  - migration-engineer
  - privacy-expert
```

## Success criteria

- [ ] rigor_tier is `standard`
- [ ] `unit-results` and `integration-results` both present in evidence_required
- [ ] at least one task has `test_required: true`
- [ ] `build` and `test` phases both included
- [ ] complexity in [1, 3]
- [ ] no compliance specialists picked
