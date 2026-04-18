---
name: 01-trivial-typo
title: Facilitator Rubric — Trivial Typo
description: Verify the facilitator produces minimal rigor, no test evidence, and a 1-2 task chain for a pure typo fix.
type: rubric
difficulty: beginner
estimated_minutes: 2
---

# Trivial Typo

## Input

> Fix the typo in the login button label.

## Expected facilitator behavior

The facilitator reads this as a pure copy change on a user-facing surface, with no
behavior change and no risk surface. Even though the word "login" appears, there is
no auth change — only a text label. No priors should change the plan. Open questions
should be empty; the ambiguity triggers do not fire.

## Expected outcome

```yaml
specialists:
  - frontend-engineer     # the only real hand needed
  # ui-reviewer is OPTIONAL for copy-only change; may or may not be included
phases:
  - build
evidence_required: []
test_types: []
complexity: 0             # ±1 tolerance
rigor_tier: minimal
factors:
  reversibility: HIGH
  blast_radius: LOW
  compliance_scope: LOW
  user_facing_impact: HIGH    # text IS user-facing, even if small
  novelty: LOW
  scope_effort: LOW
  state_complexity: LOW
  operational_risk: LOW
  coordination_cost: LOW
open_questions: []
re_evaluation: not-applicable
banned_specialists:
  - security-engineer     # would be wrong to pick here
  - compliance-officer
  - migration-engineer
```

## Success criteria

- [ ] rigor_tier is `minimal`
- [ ] 1-2 tasks in the chain
- [ ] `test_required: false` on every task
- [ ] `evidence_required` is empty
- [ ] `security-engineer`, `compliance-officer`, `migration-engineer` are NOT picked
- [ ] complexity in [0, 1]
- [ ] no open questions emitted
