# Plugin-Scope Calibration Guide — factor_questionnaire.py

**Issue**: #628
**Status**: Field-tested 2026-04-25 — no weight or wording changes required
**Source of truth**: `docs/calibration/field-test-results.md`

---

## Purpose

Some questions in the questionnaire were designed for SaaS-scale production
services — shared auth infra, CDN distribution, multi-team schema migrations.
When applied to a Claude Code plugin (a collection of markdown files + Python
scripts installed locally via `claude install`), several questions read
differently at first glance.

This document explains the plugin-scope reading for each flagged question so
future facilitators can answer accurately without overcalling risk.

---

## How the installer context works

A Claude Code plugin is distributed via the marketplace and cached on the
user's local machine. This means:

- There is no CDN, no hot-path server, no database, no production runtime.
- "Deploy" = a new commit to main + marketplace sync. Users receive the update
  when their Claude Code session restarts or they run `claude update`.
- "Customer-facing surface" = slash commands, agents, skills visible to the
  user in their Claude Code session.
- DomainStore = local JSON files at `~/.something-wicked/`. Reads do not hit
  a shared database or external API.

---

## Per-question plugin-scope guidance

| Question ID | Original text | Plugin-scope reading guidance |
|---|---|---|
| **b4** | "Does this change affect more than one customer-facing surface simultaneously?" | In plugin context, "surface" = a command, agent, or skill the user interacts with. Adding 3 agents at once → YES (correctly MEDIUM). A pure internal refactor with no public API change → NO (correctly HIGH). Docs-only → NO (reference material is not an interactive surface). |
| **b5** | "Is this change distributed via CDN, mobile app, or other cached client artifact?" | Always YES for any plugin change — marketplace install is a cached local artifact. However, b5 weight (1pt) is intentionally low: it cannot reach medium_threshold=2 alone. It adds a signal boost only when other questions fire. b5-only blast_radius stays HIGH. This is correct. |
| **sc4** | "Does this change read from persistent state without altering its shape (read-only index, new query)?" | Fire YES only when the change _introduces_ a new read from DomainStore or another persistent source. Moving existing code to a new file (pure extraction) does NOT introduce a new read — answer NO. Adding a new lookup (e.g., a new `store.get()` call) → YES. |
| **o5** | "Is this change deployed without a feature flag AND expected to directly affect more than 1M users/rows in production on day 1?" | Fire YES only when BOTH conditions hold: (1) no feature flag AND (2) the deploy directly affects > 1M users/rows on day 1. A plugin update or a typo fix deployed without a flag fires NO — the plugin userbase is under 1M and there is no production row write. A 50M-row schema migration with no flag fires YES → MEDIUM (weight=2 = medium_threshold=2). A migration gated behind a feature flag fires NO regardless of size. |

---

## b5 is not a miscall — it is a low-weight signal

A common concern: "b5 always fires YES for plugin work, so it overcalls blast_radius."

The data shows this is not the case:
- b5 weight = 1pt
- `blast_radius.medium_threshold` = 2pt

A plugin change where ONLY b5 fires produces 1pt < 2pt → stays HIGH (low blast).
b5 escalates a reading only when a riskier signal (b1, b2, b3, or b4) already fires.
This matches the intent: a cached distribution channel is a real amplifier, but not
a standalone reason for elevated blast risk.

---

## When NO calibration is needed

A future facilitator should answer the questions honestly from the description
and let the thresholds do their job. Calibration is only warranted when:

1. A question consistently fires YES for plugin-scope work where the risk is
   clearly absent (not just lower than SaaS-scale).
2. The miscall changes a factor reading (not just adds points that stay below
   the next threshold).
3. The miscall is confirmed on ≥2 of 3 independent plugin-scope descriptions.

All three conditions must hold. The 2026-04-25 field test found zero questions
meeting all three conditions.

---

## When to add a new SaaS-scale signal

Add a new question (not a new factor — the 9 canonical factors are frozen) if:

- A new risk pattern appears in ≥2 real incidents that the existing questions
  would not have caught.
- The pattern is orthogonal to existing questions (not covered by b1-b5 combined).
- The new question can be answered YES/NO from a description without requiring
  runtime knowledge.

Do NOT add questions to model plugin-specific risk that is already LOW by
threshold arithmetic. Use the per-question guidance above instead.

---

## Calibration history

| Date | Change | Rationale | PR |
|---|---|---|---|
| 2026-04-25 | u1 weight 3→2 | Single visible plugin change should land MEDIUM not LOW | #629 |
| 2026-04-25 | cc3 rewording | Coordination cost is about human handoffs, not agent dispatch count | #629 |
| 2026-04-25 | b4, b5, sc4 reviewed — NO CHANGE | Field test on 3 plugin + 1 SaaS descriptions confirmed all three behave correctly at current weights | #628 (this PR) |
| 2026-04-26 | o5 reword + weight 1→2 | C1/C2 (weight bump / threshold lower) introduced false positives on trivial no-flag deploys; C3 (reword only) eliminated false positives but couldn't reach MEDIUM at weight=1; C4 (reword + weight=2) is the only candidate that fixes D1 without overcalling D2/D3 | #639 |

---

## Cross-references

- Field-test descriptions: `docs/calibration/test-descriptions.md`
- Field-test results (issue #628): `docs/calibration/field-test-results.md`
- Field-test results (issue #639, o5): `docs/calibration/o5-field-test.md`
- Calibration tests: `tests/crew/test_factor_questionnaire.py` (search for "Issue #628", "Issue #639")
- Prior calibration: PR #629, PR #638
