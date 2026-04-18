---
name: 06-internal-refactor
title: Facilitator Rubric — Internal Refactor (No Behavior Change)
description: Verify the facilitator picks unit-only evidence, standard rigor, and no UI specialists for a pure internal refactor.
type: rubric
difficulty: beginner
estimated_minutes: 3
---

# Refactor Pricing Calculator into Smaller Functions

## Input

> Refactor the pricing calculator into smaller functions with better names.

## Expected facilitator behavior

Pure internal refactor. The claim is "behavior is unchanged" — which is precisely
what unit tests must prove (existing tests should pass unchanged, and the refactor
itself is the evidence that the structure is better).

No user-facing impact. No state change. No UI. Rigor is `standard` because pricing
calculators tend to be risky surfaces (money!), but there's no compliance surface.
Reviewer must confirm behavior parity.

## Expected outcome

```yaml
specialists:
  - senior-engineer       # refactor + mentor
  - backend-engineer      # execute the refactor
  - test-designer         # ensure existing coverage holds
phases:
  - design                # decide decomposition shape
  - build
  - test
  - review                # parity check
evidence_required:
  - unit-results
test_types:
  - unit
complexity: 2             # ±1 tolerance
rigor_tier: standard
factors:
  reversibility: HIGH
  blast_radius: MEDIUM    # pricing — money — not trivial
  compliance_scope: LOW
  user_facing_impact: LOW
  novelty: LOW
  scope_effort: LOW
  state_complexity: LOW
  operational_risk: LOW
  coordination_cost: LOW
open_questions: []
re_evaluation: not-applicable
banned_specialists:
  - frontend-engineer
  - ui-reviewer
  - migration-engineer
  - compliance-officer
```

## Success criteria

- [ ] rigor_tier is `standard` or `minimal` with explicit WHY
- [ ] `unit-results` in evidence_required
- [ ] NO UI specialists picked
- [ ] NO migration-engineer picked
- [ ] complexity in [1, 3]
