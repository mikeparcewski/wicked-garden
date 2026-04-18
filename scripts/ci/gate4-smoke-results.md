# Gate 4 Phase 1 — Facilitator Smoke Results

**Run**: `python3 scripts/ci/gate4_smoke.py --capture`

**Overall verdict**: **PASS** — 3/3 inputs pass their rubrics with legacy-engine comparison captured.

---

## Per-input assessment

### smoke-01 — feature-flag-expiry-sweeper · PASS (13/13)

**Facilitator plan**: rigor=standard · complexity=2 · 4 tasks · phases=[build, test, review] · specialists=[backend-engineer, sre] · evidence=[unit-results, integration-results]

Sensible. The facilitator correctly reads a utility cron job as low-everything-except-soft-delete-warrants-a-reviewer and produces a ~minimal lifecycle (build → test → review). The inline test-in-build choice + one integration test + one reviewer is the right weight for a daily batch job. No unnecessary clarify or design ceremony.

**Legacy engine**: complexity=2 · review_tier=minimal · routing_lane=auto · signals=[product]

Legacy produces a **wrong** specialist set (`design`, `product`, `qe`) because it keyed on "feature" as a product signal and missed the actual surface (Postgres + platform team). The facilitator read "platform-owned batch job" correctly and routed to backend + sre. Legacy's complexity score matches (2) but its specialist routing is a known failure mode of keyword-based signal detection.

### smoke-02 — webhook-retry-queue · PASS (13/13)

**Facilitator plan**: rigor=standard · complexity=5 · 7 tasks · phases=[design, test-strategy, build, test, review] · specialists=[solution-architect, backend-engineer, test-strategist, sre, release-engineer] · 3 open_questions · evidence=[unit-results, integration-results, performance-baseline]

Sensible. The facilitator read state_complexity=HIGH and operational_risk=HIGH correctly, inserted the mandatory test-strategy phase before build (which the rubric requires for high-state work), and pulled in SRE + release-engineering for the canary. The 3 open questions (idempotency key source, DLQ alert routing, per-tenant vs global worker) are exactly the design-level ambiguities a real facilitator would flag before implementation.

**Legacy engine**: complexity=2 · review_tier=minimal · routing_lane=auto · signals=[product]

Legacy **badly underscores** this — complexity 2 and lane=auto means the v5 engine would have fast-tracked a durable-outbox-with-DLQ through minimal rigor. This is the kind of failure mode that justified the v6 rebuild. Keywords like "retry", "queue", "DLQ", "at-least-once", "exponential backoff" do not appear in SIGNAL_KEYWORDS with enough weight to trip complexity. The facilitator reads the meaning and gets it right.

### smoke-03 — multi-tenant-search-index-shard · PASS (16/16)

**Facilitator plan**: rigor=full · complexity=7 · 9 tasks · phases=[clarify, design, test-strategy, build, test, review] · specialists=[solution-architect, data-engineer, migration-engineer, security-engineer, backend-engineer, test-strategist, sre, release-engineer] · 4 open_questions · evidence=[unit-results, integration-results, migration-rollback-plan, security-scan, performance-baseline, compliance-traceability]

Sensible. The facilitator caught the cross-tenant leakage history and escalated to full rigor with a security-engineer review sign-off (t8). Two reviewers (security + SRE) + a full lifecycle + migration-rollback-plan evidence + the tenant-isolation adversarial test suite is exactly what the risk profile demands. The 4 open questions are design-time calls that a real facilitator must raise.

**Legacy engine**: complexity=5 · review_tier=standard · routing_lane=standard · signals=[performance, data, reversibility] · archetypes={api-backend: 0.417}

Legacy under-reads this as standard/complexity-5 — it sees "data" + "reversibility" but not the full risk profile. The `security` signal is absent because the description says "cross-tenant leakage" rather than "auth" or "encrypt". The facilitator reading "cross-tenant" and prior-incident references as security-relevant captures intent that keyword-matching misses. The archetype `api-backend: 0.417` is a weak read; the real archetype is platform + data + security simultaneously, and v5 has no vocabulary for that.

---

## Qualitative differences

| Aspect | Legacy rule engine | Facilitator rubric |
|---|---|---|
| Specialist routing (smoke-01) | `[design, product, qe]` — wrong, hit on "feature" | `[backend-engineer, sre]` — correct, matches described surface |
| Complexity (smoke-02) | 2 — catastrophically low for durable-state work | 5 — matches state+ops risk |
| Routing lane (smoke-02) | auto (would fast-track) | standard (forces design + test-strategy) |
| Security detection (smoke-03) | absent — no keyword match | `security-engineer` added via semantic read of leakage history |
| Open questions | N/A — legacy emits a fixed "low complexity" prompt | 3–4 design-time ambiguities surfaced per input where warranted |
| Rigor override | fixed by complexity + override rule | readable from factor scores; compliance/ops HIGH escalate to full |
| Archetype | discrete taxonomy, often wrong class | implicit in the summary; no misleading label |

The pattern across all three inputs: the legacy engine's keyword-based signal + complexity math fails to read *meaning* in the description. Two out of three cases (smoke-01 routing, smoke-02 complexity) show v5 producing confidently wrong outputs that would ship under its rigor gates. v6 gets all three right because the rubric rewards reading the work instead of string-matching it.

---

## Interpretation

The v5 engine is measurably worse than the rubric on inputs it wasn't hand-calibrated for. This is the failure mode the v6 rebuild was designed to fix — rubric reasoning degrades gracefully on unseen inputs; rule engines calibrated to keyword sets do not.

**Implication for Phase 2**: the cutover matrix's "NO GAP" verdict is reinforced. Deleting the rule engine does not lose quality; it removes a source of silent wrong-answers.
