# Factor Definitions (with calibration examples)

Nine factors. For each: what it means, what LOW / MEDIUM / HIGH look like, and the
smell test for "am I over- or under-scoring this?"

---

## 1. Reversibility

**Question**: If we ship this and it's wrong, how expensive is the undo?

- **LOW (hard to reverse)** — data migrations, schema drops, third-party contract
  changes, customer-visible pricing changes, public API removals.
- **MEDIUM** — config flags touching persistent behavior, email template changes that
  already sent, removed UI that users learned to rely on.
- **HIGH (easy to reverse)** — feature behind a flag, internal refactor with no
  behavior change, docs, content.

Smell test: "If we notice the bug in 24h, can we restore prior behavior by
reverting one PR?" If yes → HIGH. If data migration needed → LOW.

---

## 2. Blast Radius

**Question**: If this breaks in production, how many users / services / downstream
systems are affected?

- **LOW** — one internal endpoint, one script, one team's tooling.
- **MEDIUM** — one customer-facing surface, one service that other services depend on
  loosely.
- **HIGH** — shared infrastructure (auth, billing, storage), mass-distributed clients
  (mobile, cached CDN assets), systems other teams integrate against.

Smell test: If only the author's team notices a regression → LOW. If a paging on-call
would fire → HIGH.

---

## 3. Compliance Scope

**Question**: Does this touch regulated data, regulated surfaces, or regulated
controls?

- **LOW** — no PII, no financial data, no health data, no auth state, no audit logs.
- **MEDIUM** — adjacent to a regulated surface (e.g. logging that could accidentally
  capture PII).
- **HIGH** — directly handles PII, payment card data, PHI, authentication flows, audit
  logs, consent records, data export/deletion endpoints, cross-border transfers.

If ANY of (GDPR, CCPA, HIPAA, PCI, SOX, SOC2) verbs appear in the description or
implicit in the surface → default HIGH and justify down, not up.

---

## 4. User-Facing Impact

**Question**: Does a real human see, hear, or feel this change?

- **LOW** — purely internal tooling, dev-ops scripts, CI configuration.
- **MEDIUM** — indirect (latency, reliability, cost to serve).
- **HIGH** — direct (UI, copy, flow, notification, export format, public API).

User-facing MEDIUM+ always implies `ui-reviewer` or `ux-designer` in the specialist
list (unless a11y is being explicitly handled).

---

## 5. Novelty

**Question**: Have we done this pattern in this codebase before? Do the priors
suggest confidence or uncertainty?

- **LOW (routine)** — priors show 3+ similar completed projects with crisp outcomes.
- **MEDIUM** — priors show 1-2 similar projects, or similar patterns in a different
  domain.
- **HIGH (novel)** — no priors, or priors show failures/rollbacks, or the technique
  is new to this codebase.

HIGH novelty implies an `ideate` phase OR a `jam:quick` invocation BEFORE planning.

---

## 6. Scope Effort

**Question**: How many files, services, or teams must change?

- **LOW** — 1-3 files, one service, one team.
- **MEDIUM** — 4-20 files, 1-2 services, one team coordinating with another.
- **HIGH** — 20+ files, 3+ services, multi-team.

Scope-effort HIGH tends to co-occur with coordination-cost HIGH; they're not the same
but they often rise together.

---

## 7. State Complexity

**Question**: Does this touch persistent state — data schemas, stored procedures,
migrations, caches, queues?

- **LOW** — stateless logic, computed values, UI-only changes.
- **MEDIUM** — reads from persistent state but doesn't change shape; adds a read-only
  index; new cache layer.
- **HIGH** — schema migration, column add+backfill, data transformation, breaking
  serialization change, cache invalidation strategy change.

HIGH state_complexity always adds `migration-engineer` (if available) and forces a
rollback plan in evidence_required.

---

## 8. Operational Risk

**Question**: Does this change runtime behavior in production — throughput, error
rates, latency, memory, cost?

- **LOW** — no production deploy required, or behind a flag from day 1.
- **MEDIUM** — subtle timing, retry, or cache behavior changes.
- **HIGH** — new hot-path code, new external dependency (network call), changed
  queuing / rate-limiting / circuit-breaker behavior.

HIGH operational_risk adds `sre` and `observability-engineer` (if available) and
forces `performance-baseline` in evidence_required for the relevant task.

---

## 9. Coordination Cost

**Question**: Does this require multiple specialists to agree or hand off?

- **LOW** — one specialist owns the whole thing.
- **MEDIUM** — design + build handoff, or product + engineering handoff.
- **HIGH** — 3+ specialists must agree; contracts between services; multiple teams.

HIGH coordination_cost adds a `review` phase with multiple reviewers (not just one).

---

## Scoring discipline

- Write one sentence of reasoning per factor. No numeric scores; the prose is the signal.
- When two reasonable readings exist, record both sentences and pick the one with higher
  downside risk. Facilitator errs on the side of caution — rigor can be downgraded by
  the user, not silently by the facilitator.
- Factors are not independent. Reversibility LOW + blast radius HIGH + compliance scope
  HIGH → always full rigor, regardless of complexity.
- When priors contradict the surface read (e.g. description says "small change" but
  priors show 2 rollbacks on similar changes), go with the priors.
