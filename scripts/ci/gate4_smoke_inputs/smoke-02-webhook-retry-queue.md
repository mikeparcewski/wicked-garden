# smoke-02 — webhook-retry-queue

## description

Build a durable retry queue for outbound webhooks. Today we send webhook calls inline from the request handler; when a subscriber is down we drop them. Replace this with an async queue: persist the outbound message, worker picks it up, sends the call, on 5xx retries with exponential backoff up to 24 hours, and on final failure lands in a dead-letter with an operator alert. Messages need to survive process restarts. Subscribers expect at-least-once. We want to ship to our top 10 enterprise accounts behind a feature flag first.

## expected_outcome (rubric)

```yaml
rigor_tier_one_of: ["standard", "full"]
complexity_range: [4, 6]
tasks_min: 5
phases_subset:
  - design
  - build
  - test
phases_strongly_preferred:
  - test-strategy
  - review
specialists_subset:
  - backend-engineer
specialists_candidate_ok:
  - solution-architect
  - test-strategist
  - test-designer
  - sre
  - platform
  - data-engineer
  - release-engineer
evidence_subset:
  - unit-results
  - integration-results
evidence_candidate_ok:
  - performance-baseline
  - api-contract-diff
test_types_subset:
  - unit
  - integration
test_types_candidate_ok:
  - performance
  - api
factors:
  reversibility: ["MEDIUM", "LOW"]
  blast_radius: ["MEDIUM", "HIGH"]
  state_complexity: ["MEDIUM", "HIGH"]
  operational_risk: ["MEDIUM", "HIGH"]
  user_facing_impact: ["MEDIUM", "LOW"]
open_questions_allowed: true
```

## notes

State complexity (durability + at-least-once) and operational risk (retry storms, DLQ alerting) are the real drivers. The 24h backoff window and enterprise-account rollout give reviewability knobs (feature flag = reversibility mitigant, canary subscribers = blast-radius mitigant). Rigor full is defensible if the facilitator reads tenant-enterprise as high-stakes; standard is fine if the flag is trusted. Wrong outcomes: minimal rigor (dangerous — this is durable-state work), missing test-strategy (you need retry-policy test cases before coding), or complexity <=3 (under-reads state + ops).
