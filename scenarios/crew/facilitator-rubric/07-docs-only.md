---
name: 07-docs-only
title: Facilitator Rubric — Docs Only
description: Verify the facilitator picks technical-writer only and produces no evidence requirements for a docs update.
type: rubric
difficulty: beginner
estimated_minutes: 2
---

# README Update for New API Key Setup

## Input

> Update the README to document the new API key setup flow.

## Expected facilitator behavior

Pure docs update. `test_required: false`. Minimal rigor. The only specialist is
`technical-writer`. No build/test phases in the engineering sense — the "build" is
the edit itself, and review is a single pass for accuracy.

If the facilitator sees "API key" and reflexively picks `security-engineer`, that's
a false positive — the docs describe setup, they don't implement auth.

## Expected outcome

```yaml
specialists:
  - technical-writer
phases:
  - build
  - review                # single reviewer for accuracy
evidence_required: []
test_types: []
complexity: 1             # ±1 tolerance
rigor_tier: minimal
factors:
  reversibility: HIGH
  blast_radius: LOW
  compliance_scope: LOW
  user_facing_impact: LOW     # docs are adjacent, not the product itself
  novelty: LOW
  scope_effort: LOW
  state_complexity: LOW
  operational_risk: LOW
  coordination_cost: LOW
open_questions: []
re_evaluation: not-applicable
banned_specialists:
  - security-engineer
  - compliance-officer
  - migration-engineer
  - backend-engineer        # docs don't need a backend
```

## Success criteria

- [ ] rigor_tier is `minimal`
- [ ] only `technical-writer` (and optionally a reviewer) in specialists
- [ ] `test_required: false` on every task
- [ ] evidence_required is empty
- [ ] NO security-engineer picked
- [ ] complexity in [0, 2]
