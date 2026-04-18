---
name: 09-emergent-complexity
title: Facilitator Rubric — Emergent Complexity (Re-evaluation)
description: Verify the facilitator re-evaluates the task chain mid-project when design surfaces a migration + indexing need.
type: rubric
difficulty: advanced
estimated_minutes: 5
---

# Saved Searches Feature — Emergent Complexity

## Input (initial)

> Add a 'saved searches' feature.

## Input (re-evaluation trigger)

Simulated: task-1 (`clarify`) and task-2 (`design`) have completed. The design task's
evidence reveals:

- Saved searches are free-text; existing storage has no full-text index.
- Queries will scan a table that will reach ~1M rows within the year.
- Per-user lists require a new table with foreign keys and a backfill migration
  (existing search events need to be categorized).

## Expected facilitator behavior (two-pass)

**Pass 1 (initial propose)**: mid-scale feature, standard rigor, straightforward chain
(clarify → design → test-strategy → build → test → review). No migration-engineer in
the initial pick.

**Pass 2 (re-evaluate on task-2 completion)**: facilitator reads the design evidence,
recognizes the emergent migration + indexing requirements, and:

1. Augments the chain with a `migration-engineer` task and a `data-engineer` task.
2. Adds `migration-rollback-plan` and performance baseline to evidence_required.
3. Re-tiers rigor from `standard` to `standard-with-migration` (or `full` if scope
   grew significantly).
4. Does NOT rewrite completed tasks.
5. Appends a "Re-evaluation <timestamp>" section to process-plan.md.

## Expected outcome — Pass 1 (initial)

```yaml
specialists:
  - requirements-analyst
  - product-manager
  - solution-architect
  - backend-engineer
  - frontend-engineer
  - test-designer
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
  - api-contract-diff
  - acceptance-report
  - screenshot-before-after
test_types:
  - unit
  - integration
  - api
  - ui
  - acceptance
complexity: 4             # ±1 tolerance
rigor_tier: standard
factors:
  state_complexity: LOW     # will flip to HIGH in pass 2
  scope_effort: MEDIUM
  reversibility: HIGH
  user_facing_impact: HIGH
```

## Expected outcome — Pass 2 (re-evaluation)

```yaml
mode: re-evaluate
trigger: task-2 completion (design phase)
augmented:
  - specialist: migration-engineer
    reason: design revealed new table + foreign keys + backfill
  - specialist: data-engineer
    reason: full-text index decision needs data pipeline owner
evidence_added:
  - migration-rollback-plan
  - performance-baseline
test_types_added:
  - migration
  - performance
rigor_retiered_to: standard   # or full — acceptable either way, WITH explicit WHY
pruned: []                    # nothing to prune — the design sharpened scope
complexity_after: 5           # ±1 tolerance — emergent scope bumped it up
factors_changed:
  state_complexity: HIGH
  operational_risk: MEDIUM
```

## Success criteria

- [ ] Pass 1: no migration-engineer, no migration-rollback-plan in initial plan
- [ ] Pass 2: migration-engineer added
- [ ] Pass 2: migration-rollback-plan added to evidence
- [ ] Pass 2: performance-baseline added (due to indexing + 1M rows)
- [ ] Pass 2: process-plan has an appended "Re-evaluation" section
- [ ] Pass 2: completed tasks are NOT modified
- [ ] Pass 2: re_evaluation.augmented has ≥1 entry
- [ ] Complexity bumps by ≥1 from pass 1 to pass 2
