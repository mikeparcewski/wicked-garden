# smoke-01 — feature-flag-expiry-sweeper

## description

Write a small internal maintenance job that runs once a day and deletes feature flags whose `expires_at` timestamp is in the past. Flags live in our Postgres `feature_flags` table; expired flags should be soft-deleted (set `deleted_at`), not hard-deleted, so we can audit. Emit a structured log line per sweep with counts and skipped flags. No UI. No customer-visible effect. Owner is the platform team.

## expected_outcome (rubric)

```yaml
rigor_tier_one_of: ["minimal", "standard"]
complexity_range: [1, 3]
tasks_max: 4
phases_subset:
  - build
phases_must_not_include:
  - ideate
specialists_subset:
  - backend-engineer
specialists_candidate_ok:
  - platform
  - sre
  - database-engineer
evidence_one_of:
  - unit-results
  - integration-results
test_types_one_of:
  - unit
  - integration
factors:
  compliance_scope: ["LOW"]
  user_facing_impact: ["LOW"]
  blast_radius: ["LOW", "MEDIUM"]
  state_complexity: ["LOW", "MEDIUM"]
open_questions_allowed: false
```

## notes

A simple utility job. Soft-delete semantics keep reversibility HIGH. No auth, no PII, no UX surface. The one trap the facilitator could fall into: over-specifying a test strategy for a cron job that's trivially unit-testable. Watch for rigor=full (wrong) or a 6-phase plan (wrong). Correct shape is build + maybe test, with one backend or platform engineer. A conservative `clarify` is acceptable if it's one sentence; full clarify phase would be overkill.
