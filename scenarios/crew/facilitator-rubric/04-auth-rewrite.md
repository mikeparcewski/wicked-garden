---
name: 04-auth-rewrite
title: Facilitator Rubric — Auth Rewrite (Session → JWT, 3 Services)
description: Verify the facilitator produces full rigor, full test pyramid, compliance traceability, and council invocation for an auth migration.
type: rubric
difficulty: advanced
estimated_minutes: 6
---

# Auth Migration: Session Cookies → JWT Across 3 Services

## Input

> Migrate authentication from session cookies to JWT across 3 services.

## Expected facilitator behavior

This is the canonical HIGH-rigor case. Every factor points toward risk: auth is the
textbook compliance surface (SOC2, potentially PCI/HIPAA depending on data), cross-
service coordination, state migration (active sessions), reversibility is LOW
(mid-migration rollback is painful), blast radius is HIGH (all users, all services).

Expected to invoke `/wicked-garden:jam:council` as part of design (multi-model review
for irreversible decisions). `migration-engineer` mandatory. Compliance traceability
mandatory. Test pyramid full (unit + integration + api + security + acceptance +
performance).

Yolo mode is FORBIDDEN for this class of work.

## Expected outcome

```yaml
specialists:
  - requirements-analyst
  - product-manager
  - solution-architect
  - senior-engineer
  - backend-engineer
  - security-engineer
  - compliance-officer
  - migration-engineer
  - sre
  - release-engineer
  - test-strategist
  - test-designer
  - independent-reviewer
phases:
  - clarify
  - design           # includes council invocation
  - test-strategy
  - build
  - test
  - review
evidence_required:
  - api-contract-diff
  - unit-results
  - integration-results
  - security-scan
  - acceptance-report
  - compliance-traceability
  - migration-rollback-plan
  - performance-baseline
test_types:
  - unit
  - integration
  - api
  - security
  - acceptance
  - performance
  - migration
complexity: 6             # ±1 tolerance
rigor_tier: full
factors:
  reversibility: LOW
  blast_radius: HIGH
  compliance_scope: HIGH
  user_facing_impact: HIGH
  novelty: MEDIUM
  scope_effort: HIGH
  state_complexity: HIGH
  operational_risk: HIGH
  coordination_cost: HIGH
open_questions: []          # tolerated if 2-3; should NOT stop plan for full-rigor
re_evaluation: not-applicable
yolo_forbidden: true
requires_council: true
```

## Success criteria

- [ ] rigor_tier is `full`
- [ ] `security-engineer`, `compliance-officer`, `migration-engineer`, `sre` all picked
- [ ] `independent-reviewer` or equivalent multi-reviewer structure
- [ ] `compliance-traceability`, `migration-rollback-plan`, `security-scan`,
      `performance-baseline` ALL in evidence_required
- [ ] complexity in [5, 7]
- [ ] process-plan notes council invocation OR justifies skipping it
- [ ] yolo mode explicitly refused (if `auto_proceed: true` was passed)
