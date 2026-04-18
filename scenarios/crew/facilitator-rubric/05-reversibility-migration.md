---
name: 05-reversibility-migration
title: Facilitator Rubric — Schema Migration (Nullable Column + Backfill)
description: Verify the facilitator picks migration-engineer and enforces a rollback plan in evidence for a schema change.
type: rubric
difficulty: intermediate
estimated_minutes: 4
---

# Nullable Column Add + Backfill on `users`

## Input

> Add a new nullable column to users and backfill from signup_date.

## Expected facilitator behavior

Schema change with a backfill. State complexity HIGH. Operational risk MEDIUM
(backfill can pressure DB). Reversibility MEDIUM (a nullable column drop is cheap;
the backfill is idempotent because signup_date is immutable). No user-facing impact
directly (internal schema change).

Rigor is `standard` (not full — no compliance surface, no cross-service coordination)
BUT the `migration-rollback-plan` is mandatory in evidence. `migration-engineer` is
the marquee specialist.

## Expected outcome

```yaml
specialists:
  - solution-architect       # decide column type, nullability, index strategy
  - migration-engineer
  - backend-engineer         # schema + backfill code
  - test-designer
  # sre optional, depending on table size
phases:
  - clarify
  - design
  - test-strategy
  - build
  - test
  - review
evidence_required:
  - unit-results
  - integration-results
  - migration-rollback-plan
test_types:
  - unit
  - integration
  - migration
complexity: 3             # ±1 tolerance
rigor_tier: standard        # can escalate to full if table is large (noted in plan)
factors:
  reversibility: MEDIUM
  blast_radius: MEDIUM
  compliance_scope: LOW
  user_facing_impact: LOW
  novelty: LOW
  scope_effort: LOW
  state_complexity: HIGH
  operational_risk: MEDIUM
  coordination_cost: LOW
open_questions: []          # reasonable to ask about table size / backfill window
re_evaluation: not-applicable
banned_specialists:
  - frontend-engineer
  - ui-reviewer
```

## Success criteria

- [ ] `migration-engineer` picked
- [ ] `migration-rollback-plan` in evidence_required
- [ ] rigor_tier is `standard` (or `full` with explicit WHY in process-plan)
- [ ] test_types includes `migration`
- [ ] no frontend/UI specialists
- [ ] complexity in [2, 4]
