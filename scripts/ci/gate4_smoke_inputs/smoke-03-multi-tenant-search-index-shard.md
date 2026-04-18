# smoke-03 — multi-tenant-search-index-shard

## description

Our search is shared across all tenants today — a single Elasticsearch cluster, documents tagged with `tenant_id`, filtering at query time. Two incidents this quarter leaked cross-tenant results when query filters were misapplied. Split the index so each tenant has its own physical shard, route queries by tenant from the gateway, and prevent the shared-index code path from being reachable after cutover. Plan must cover data migration for existing documents, query-path rewrite, an authz check between request identity and shard selection, tenant metrics isolation, and a rollback path in case performance regresses for small tenants. Affected teams: search, platform, data. UX is unchanged but latency SLOs still need to hold.

## expected_outcome (rubric)

```yaml
rigor_tier: "full"
complexity_range: [6, 7]
tasks_min: 7
phases_subset:
  - clarify
  - design
  - build
  - test
  - review
phases_strongly_preferred:
  - test-strategy
specialists_subset:
  - backend-engineer
  - data-engineer
specialists_candidate_ok:
  - solution-architect
  - security-engineer
  - compliance-officer
  - sre
  - platform
  - migration-engineer
  - test-strategist
  - test-designer
  - release-engineer
evidence_subset:
  - unit-results
  - integration-results
evidence_candidate_ok:
  - migration-rollback-plan
  - security-scan
  - performance-baseline
  - api-contract-diff
test_types_subset:
  - integration
test_types_candidate_ok:
  - unit
  - api
  - performance
  - security
  - migration
factors:
  reversibility: ["LOW"]
  blast_radius: ["HIGH"]
  user_facing_impact: ["MEDIUM", "HIGH"]
  scope_effort: ["HIGH"]
  state_complexity: ["HIGH"]
  operational_risk: ["HIGH"]
  coordination_cost: ["HIGH"]
  compliance_scope: ["LOW", "MEDIUM", "HIGH"]
open_questions_allowed: true
```

## notes

Cross-tenant leakage incidents already happened → security_engineer must appear. Data migration + rollback + perf SLO + authz = full rigor. Correct shape is the full lifecycle (clarify through review) with ≥7 tasks and migration-rollback-plan evidence. Wrong outcomes: standard rigor (ignores tenant isolation risk), missing migration/rollback evidence, or complexity <=5 (under-reads the coordination + state).
