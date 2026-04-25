# Questionnaire Render — Sample Output

This is what `render_questionnaire()` produces when presented to the model.
Generated from `scripts/crew/factor_questionnaire.py`.

---

## Facilitator Scorer Questionnaire

Answer each question YES (true) or NO (false) based on the project description
and any priors you have fetched. When uncertain, call `wicked-garden:ground`
before answering. Respond with a YAML block in the exact format shown.

```yaml
answers:
  reversibility:
    r1: false  # Does this work modify production state that can't be undone via git revert?
    r2: false  # Does this work involve data migration that drops or transforms existing rows?
    r3: false  # Are there external API consumers (other plugins, end-users with cached responses) depending on a surface being removed/renamed?
    r4: false  # Could a customer experience the change in production before we'd notice and roll back?
  blast_radius:
    b1: false  # Does this change touch shared infrastructure used by more than one team?
    b2: false  # Does this change affect an auth, billing, or storage subsystem?
    b3: false  # Could a bug in this change trigger a page or on-call alert?
    b4: false  # Does this change affect more than one customer-facing surface simultaneously?
    b5: false  # Is this change distributed via CDN, mobile app, or other cached client artifact?
  compliance_scope:
    c1: false  # Does this work directly handle PII, PHI, payment card data, or authentication credentials?
    c2: false  # Does this work create or modify audit logs, consent records, or data export/deletion endpoints?
    c3: false  # Does this work involve cross-border data transfer or data residency constraints?
    c4: false  # Could this work accidentally capture PII in logs or traces as a side effect?
  user_facing_impact:
    u1: false  # Does this change produce a visible UI change, copy change, or new user-visible flow?
    u2: false  # Does this change affect a public API response shape that callers consumers directly?
    u3: false  # Does this change affect an email, notification, or export format seen by end-users?
    u4: false  # Does this change affect perceived latency, reliability, or cost in a way users will notice?
  novelty:
    n1: false  # Have there been rollbacks or failures on similar changes in this codebase's history?
    n2: false  # Is this the first time this team is applying this pattern in this codebase?
    n3: false  # Are there fewer than 2 strong prior examples (memory/wiki) for this type of change?
    n4: false  # Does this require integrating a library or service new to this stack?
  scope_effort:
    s1: false  # Does this change touch more than 20 files?
    s2: false  # Does this change span 3 or more services or repos?
    s3: false  # Does this change require coordination across 2 or more teams?
    s4: false  # Does this change touch 4-20 files or 1-2 services?
  state_complexity:
    sc1: false  # Does this change add a schema migration, column backfill, or data transformation?
    sc2: false  # Does this change break or change an existing serialization format stored on disk or in a DB?
    sc3: false  # Does this change alter a cache invalidation strategy or introduce a new cache layer?
    sc4: false  # Does this change read from persistent state without altering its shape (read-only index, new query)?
  operational_risk:
    o1: false  # Does this change add a new network call on a hot path that runs synchronously in production?
    o2: false  # Does this change modify queuing, rate-limiting, or circuit-breaker behavior?
    o3: false  # Does this change introduce a new external dependency (API, library) into the production runtime?
    o4: false  # Does this change alter retry, timeout, or backoff parameters?
    o5: false  # Is this change deployed without a feature flag on day 1?
  coordination_cost:
    cc1: false  # Does this change require 3 or more specialists to agree before it can ship?
    cc2: false  # Does this change require a contract negotiation between two services or teams?
    cc3: false  # Does this change require a design + build handoff across different specialists?
    cc4: false  # Does this change require a product + engineering alignment on scope or acceptance criteria?
```

_Tip: if you are uncertain about any answer, invoke `wicked-garden:ground` with the question text before answering._
