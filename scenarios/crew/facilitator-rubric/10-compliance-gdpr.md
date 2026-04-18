---
name: 10-compliance-gdpr
title: Facilitator Rubric — GDPR Data Export Endpoint
description: Verify the facilitator invokes compliance + privacy + audit specialists, mandates traceability, and forbids yolo mode.
type: rubric
difficulty: advanced
estimated_minutes: 5
---

# GDPR Data Export Endpoint

## Input

> Add GDPR data export endpoint (user requests all their data as JSON).

## Expected facilitator behavior

The words "GDPR" and "user requests all their data" name the compliance surface
explicitly. Even though the implementation is "just a handler," the compliance scope
is HIGH: data subject right to access (GDPR Art. 15), audit logging, consent
verification, identity verification, possibly rate-limiting to prevent abuse.

Rigor is `full`. Yolo mode is FORBIDDEN. Mandatory specialists: `compliance-officer`,
`privacy-expert`, `auditor`, `security-engineer`. Mandatory evidence:
`compliance-traceability`, `security-scan`, `acceptance-report`, `api-contract-diff`.

## Expected outcome

```yaml
specialists:
  - requirements-analyst
  - product-manager
  - solution-architect
  - backend-engineer
  - security-engineer
  - compliance-officer
  - privacy-expert
  - auditor
  - test-strategist
  - test-designer
  - technical-writer          # user-facing docs for the endpoint
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
  - security-scan
  - acceptance-report
  - compliance-traceability
test_types:
  - unit
  - integration
  - api
  - security
  - acceptance
complexity: 5             # ±1 tolerance
rigor_tier: full
factors:
  reversibility: MEDIUM      # endpoint can be disabled, data already sent cannot
  blast_radius: MEDIUM        # new endpoint, not core auth
  compliance_scope: HIGH
  user_facing_impact: HIGH
  novelty: MEDIUM
  scope_effort: MEDIUM
  state_complexity: LOW
  operational_risk: MEDIUM    # abuse potential, rate-limiting required
  coordination_cost: MEDIUM
open_questions: []            # 1-2 permitted (identity verification method, retention?)
re_evaluation: not-applicable
yolo_forbidden: true
requires_compliance_traceability: true
```

## Success criteria

- [ ] rigor_tier is `full`
- [ ] `compliance-officer`, `privacy-expert`, `auditor`, `security-engineer` ALL picked
- [ ] `compliance-traceability` in evidence_required
- [ ] `security-scan` in evidence_required
- [ ] `api-contract-diff` in evidence_required
- [ ] `acceptance-report` in evidence_required
- [ ] `yolo_forbidden: true` (facilitator refuses `auto_proceed: true`)
- [ ] complexity in [4, 6]
