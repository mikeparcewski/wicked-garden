# Field-Test Results — Issue #628 Plugin-Scope Calibration

**Date**: 2026-04-25
**Scorer version**: post-PR #629 (u1 weight=2, cc3 reworded)
**Descriptions**: see `docs/calibration/test-descriptions.md`
**Session**: cluster-a/issue-628-plugin-scope-calibration

---

## Methodology

For each description:
1. Expert manual reading of each factor (honest first-principles scoring).
2. Constructed `answers` dict from the description content.
3. Called `score_all(answers)` programmatically.
4. Compared reading-by-reading and flagged disagreements.

---

## D1 — skill-agent-authoring

### Canned answers

| Factor | q | Answer | Rationale |
|---|---|---|---|
| reversibility | r1 | NO | skill/agent .md files, git-revertable |
| reversibility | r2 | NO | no data migration |
| reversibility | r3 | NO | all new additions, no existing surface removed |
| reversibility | r4 | NO | no production state exposure |
| blast_radius | b1 | NO | plugin-only, not shared infra |
| blast_radius | b2 | NO | no auth/billing/storage |
| blast_radius | b3 | NO | additive change, won't trigger on-call |
| blast_radius | b4 | YES | 3 agents + 1 skill = 4 new surfaces added simultaneously |
| blast_radius | b5 | YES | marketplace plugin = cached install distribution |
| compliance_scope | c1-c4 | NO | no PII, no audit records, no cross-border |
| user_facing_impact | u1 | YES | new agents/skills surface new visible commands |
| user_facing_impact | u2-u4 | NO | no existing API shape change, no reliability impact |
| novelty | n1-n4 | NO | well-established agent authoring pattern |
| scope_effort | s4a | YES | ~6-8 files, >5 files |
| scope_effort | s1,s2,s3,s4b | NO | not >20 files, single repo/team/service |
| state_complexity | sc1-sc4 | NO | agents/skills don't read DomainStore by default |
| operational_risk | o1-o5 | NO | no runtime changes |
| coordination_cost | cc1-cc4 | NO | single author, additive work |

### Results

| Factor | Manual | Scorer | Agree? | Notes |
|---|---|---|---|---|
| reversibility | HIGH | HIGH | YES | |
| blast_radius | MEDIUM | MEDIUM | YES | b4(2) + b5(1) = 3pts; b5 alone insufficient; combined is correct |
| compliance_scope | HIGH | HIGH | YES | |
| user_facing_impact | MEDIUM | MEDIUM | YES | u1(2) = 2pts; correctly MEDIUM not LOW |
| novelty | HIGH | HIGH | YES | |
| scope_effort | MEDIUM | MEDIUM | YES | |
| state_complexity | HIGH | HIGH | YES | |
| operational_risk | HIGH | HIGH | YES | |
| coordination_cost | HIGH | HIGH | YES | |

**Agreement: 9/9**

---

## D2 — code-repo (refactor)

### Canned answers

| Factor | q | Answer | Rationale |
|---|---|---|---|
| reversibility | r1-r4 | NO | pure code refactor, git-revertable, no consumer breakage |
| blast_radius | b1-b4 | NO | internal refactor, no public API change, not customer-facing |
| blast_radius | b5 | YES | still distributed via marketplace install |
| compliance_scope | c1-c4 | NO | |
| user_facing_impact | u1-u4 | NO | no visible change, no API shape change |
| novelty | n1-n4 | NO | extraction pattern is well-established |
| scope_effort | s4a | NO | exactly 5 files — "more than 5" requires 6+ |
| scope_effort | s1,s2,s3,s4b | NO | |
| state_complexity | sc1-sc3 | NO | no schema/serialization/cache changes |
| state_complexity | sc4 | NO | pure code extraction adds no new state reads |
| operational_risk | o1-o5 | NO | no runtime changes |
| coordination_cost | cc1-cc4 | NO | single author |

**Key sc4 note**: sc4 asks about reading persistent state "without altering its
shape". A pure structural extraction that moves code to a new file — with no new
queries added — correctly answers NO. The existing state reads move to the new
module but no _new_ reads are introduced. If a refactor does add new read-only
queries, sc4 = YES, but this description explicitly states identical behavior.

### Results

| Factor | Manual | Scorer | Agree? | Notes |
|---|---|---|---|---|
| reversibility | HIGH | HIGH | YES | |
| blast_radius | HIGH | HIGH | YES | b5(1) = 1pt < medium_threshold=2 → HIGH; correct |
| compliance_scope | HIGH | HIGH | YES | |
| user_facing_impact | HIGH | HIGH | YES | |
| novelty | HIGH | HIGH | YES | |
| scope_effort | HIGH | HIGH | YES | |
| state_complexity | HIGH | HIGH | YES | sc4=NO for pure extraction |
| operational_risk | HIGH | HIGH | YES | |
| coordination_cost | HIGH | HIGH | YES | |

**Agreement: 9/9**

---

## D3 — docs-only

### Canned answers

| Factor | q | Answer | Rationale |
|---|---|---|---|
| reversibility | r1-r4 | NO | markdown docs, git-revertable, no consumer surface |
| blast_radius | b1-b4 | NO | no shared infra, no auth/billing, no on-call, docs are not interactive surfaces |
| blast_radius | b5 | YES | distributed via marketplace install |
| compliance_scope | c1-c4 | NO | |
| user_facing_impact | u1-u4 | NO | composition maps are reference material, not interactive UI |
| novelty | n1-n4 | NO | team has authored composition maps before |
| scope_effort | s1-s4b | NO | 3 files, single repo/team |
| state_complexity | sc1-sc4 | NO | docs don't read persistent state |
| operational_risk | o1-o5 | NO | |
| coordination_cost | cc1-cc4 | NO | single author |

**Key b4 note**: the question asks about "customer-facing surfaces." Composition
maps are reference documentation — they do not constitute interactive customer-facing
surfaces in the same sense as commands, agents, or API endpoints. b4=NO is correct.

### Results

| Factor | Manual | Scorer | Agree? | Notes |
|---|---|---|---|---|
| reversibility | HIGH | HIGH | YES | |
| blast_radius | HIGH | HIGH | YES | b5(1) = 1pt < medium_threshold=2 → HIGH; correct |
| compliance_scope | HIGH | HIGH | YES | |
| user_facing_impact | HIGH | HIGH | YES | |
| novelty | HIGH | HIGH | YES | |
| scope_effort | HIGH | HIGH | YES | |
| state_complexity | HIGH | HIGH | YES | |
| operational_risk | HIGH | HIGH | YES | |
| coordination_cost | HIGH | HIGH | YES | |

**Agreement: 9/9**

---

## D4 — SaaS-scale control (schema-migration)

### Canned answers

| Factor | q | Answer | Rationale |
|---|---|---|---|
| reversibility | r1 | YES | backfill transforms rows — not cleanly reversible |
| reversibility | r2 | YES | 50M-row data migration with transformation |
| reversibility | r3 | YES | breaking change for session-cookie consumers |
| reversibility | r4 | YES | 2-hour migration window = users experience it |
| blast_radius | b1-b5 | YES | user_sessions = shared auth infra; MFA affects auth+session+UI simultaneously; cached web/mobile distribution |
| compliance_scope | c1 | YES | user_sessions = authentication credentials |
| compliance_scope | c2 | YES | MFA enforcement modifies auth records (audit implications) |
| compliance_scope | c3 | NO | not explicitly cross-border |
| compliance_scope | c4 | YES | session objects serialized into logs/traces |
| user_facing_impact | u1 | YES | MFA enforcement = visible user flow change |
| user_facing_impact | u2 | YES | session API response shape changes |
| user_facing_impact | u3 | NO | not email/export format |
| user_facing_impact | u4 | YES | 2-hour migration window affects reliability |
| novelty | n1 | YES | schema migrations commonly have rollback history |
| novelty | n2-n4 | NO | team has done migrations before |
| scope_effort | s3 | YES | auth + DBA + SRE + product = 2+ teams |
| scope_effort | s4a | YES | >5 files (migration + model + service + tests + runbook) |
| scope_effort | s1,s2,s4b | NO | few files, single service |
| state_complexity | sc1 | YES | schema migration + column backfill = exactly this question |
| state_complexity | sc2-sc3 | NO | adding column doesn't break existing serialization |
| state_complexity | sc4 | YES | new read-only MFA status checks during migration |
| operational_risk | o5 | YES | no feature flag — migration window IS the deploy |
| operational_risk | o1-o4 | NO | batch migration, no hot-path calls, no new deps |
| coordination_cost | cc1-cc4 | YES | all 4: ≥3 specialists + contract negotiation + multi-human handoff + product alignment |

### Results

| Factor | Manual | Scorer | Agree? | Notes |
|---|---|---|---|---|
| reversibility | LOW | LOW | YES | |
| blast_radius | LOW | LOW | YES | |
| compliance_scope | LOW | LOW | YES | |
| user_facing_impact | LOW | LOW | YES | |
| novelty | MEDIUM | MEDIUM | YES | |
| scope_effort | MEDIUM | MEDIUM | YES | |
| state_complexity | LOW | LOW | YES | sc4 fires correctly alongside sc1 |
| operational_risk | MEDIUM | HIGH | NO | see note below |
| coordination_cost | LOW | LOW | YES | |

**Agreement: 8/9**

**Operational risk note (non-candidate question)**: scorer reads HIGH (o5=YES →
1pt < medium_threshold=2). Manual reading: a 2-hour migration window on 50M rows
deployed without a feature flag warrants at least MEDIUM operational risk. This is
a finding against `operational_risk` (possibly o5 weight is too low for this scenario)
but it is OUT OF SCOPE for issue #628 — not one of the three candidate questions.
Noted for a future calibration pass.

---

## Divergence Analysis — Candidate Questions b4, b5, sc4

### Summary table

| Question | D1 plug scope | D2 plug scope | D3 plug scope | D4 SaaS control | Miscall count |
|---|---|---|---|---|---|
| b4 | Fires YES, reading MEDIUM — correct | NO, reading HIGH — correct | NO, reading HIGH — correct | YES, reading LOW — correct | 0/3 |
| b5 | Fires YES; 1pt insufficient alone; combined reading correct | Fires YES; 1pt alone = HIGH — correct | Fires YES; 1pt alone = HIGH — correct | Fires YES; part of larger LOW — correct | 0/3 |
| sc4 | NO (agents don't read state) — correct | NO (pure extraction, no new reads) — correct | NO (docs) — correct | YES (read-only MFA checks) — correct | 0/3 |

### Conclusion

**No calibration needed for b4, b5, or sc4.**

The field test does not support the premise of issue #628. Specifically:

- **b4** only fires when genuinely affecting multiple surfaces. For additive
  plugin work (new agents/skills), it correctly fires and produces MEDIUM.
  For internal refactors and docs-only changes, it correctly stays silent.

- **b5** always fires YES for any marketplace-distributed change, but its
  weight (1pt) is deliberately low — it provides a signal boost only when
  other questions corroborate. A b5-only blast_radius stays below
  medium_threshold=2 and reads HIGH. This is correct behavior.

- **sc4** requires the change to actively introduce or rely on a new
  read-only state access. Pure structural work (no new queries) correctly
  answers NO. The question wording ("without altering its shape") is clear
  enough that an honest reader answers correctly.

The theoretical concern from issue #628 was that b5 would overcall by
always firing YES. In practice, the 1-point weight means b5 alone never
tips the reading past HIGH. It only escalates the reading when combined
with genuinely riskier signals, which is architecturally correct.

---

## Non-candidate observation

`operational_risk` for D4 reads HIGH (o5=YES → 1pt) despite a 50M-row live
migration with a 2-hour production window. Potential o5 weight undercall.
This is a separate concern from plugin-scope calibration — not addressed here.
File a new issue if further investigation warranted.
