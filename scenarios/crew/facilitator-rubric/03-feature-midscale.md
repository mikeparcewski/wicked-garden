---
name: 03-feature-midscale
title: Facilitator Rubric — Mid-scale Feature (CSV Export)
description: Verify the facilitator plans api + ui + acceptance evidence and standard rigor for a typical user-visible feature.
type: rubric
difficulty: intermediate
estimated_minutes: 4
---

# CSV Export on User List Page

## Input

> Add CSV export to the user list page.

## Expected facilitator behavior

A typical mid-scale feature spanning a new API endpoint, a UI affordance, and
end-to-end verification. Compliance scope is LOW by default BUT if the user list
contains PII, a thoughtful facilitator flags the export as a compliance-adjacent
surface. For this baseline scenario, treat the data as internal (not GDPR-scoped);
the GDPR variant is scenario 10.

User-facing impact is HIGH (new UI button + download flow). Operational risk is LOW
(export is a read-only path). Standard rigor with a full test pyramid.

## Expected outcome

```yaml
specialists:
  - product-manager          # scope + AC
  - solution-architect       # design: sync export vs async, pagination
  - backend-engineer         # API endpoint
  - frontend-engineer        # button + download flow
  - ui-reviewer              # visual polish
  - test-designer            # or test-strategist + test-automation-engineer
phases:
  - clarify
  - design
  - test-strategy
  - build
  - test
  - review
evidence_required:
  - api-contract-diff
  - unit-results
  - integration-results
  - acceptance-report
  - screenshot-before-after
test_types:
  - unit
  - integration
  - api
  - ui
  - acceptance
complexity: 3             # ±1 tolerance
rigor_tier: standard
factors:
  reversibility: HIGH
  blast_radius: MEDIUM
  compliance_scope: LOW    # default assumption; would flip to MED/HIGH if PII
  user_facing_impact: HIGH
  novelty: LOW
  scope_effort: MEDIUM
  state_complexity: LOW
  operational_risk: LOW
  coordination_cost: MEDIUM
open_questions: []          # reasonable to emit 1-2 (sync vs async?) — tolerated
re_evaluation: not-applicable
banned_specialists:
  - migration-engineer
  - chaos-engineer
```

## Success criteria

- [ ] rigor_tier is `standard`
- [ ] `api-contract-diff`, `acceptance-report`, `screenshot-before-after` all present
- [ ] `frontend-engineer` AND `backend-engineer` both picked
- [ ] at least 5 phases selected
- [ ] complexity in [2, 4]
