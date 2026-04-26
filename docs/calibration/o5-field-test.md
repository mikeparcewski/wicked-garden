# Field Test — o5 Calibration (Issue #639)

**Date**: 2026-04-26
**Scorer version**: post-PR #638 (plugin-scope-aware weights)
**Issue**: operational_risk.o5 weight=1 cannot reach medium_threshold=2 alone, so a
50M-row migration deployed without a feature flag reads HIGH (low_risk) instead of MEDIUM.

---

## Descriptions

### D1 — SaaS-scale 50M-row migration, no feature flag (the original miscall)

A 50-million-row database migration with a 2-hour production window, deployed directly
without a feature flag. No hot-path network calls added, no queue changes, no new
external deps, no retry/timeout changes — o5 is the only operational signal.

Expected after fix: **MEDIUM** (this is the bug we are correcting).

### D2 — Single-line typo fix, deployed without a feature flag

A one-line change correcting a typo in an error message string. Deployed directly to
production without a feature flag (common for trivial fixes). No user count or row
count impact. o5 = YES under current wording.

Expected: **HIGH** — no false positive. A typo fix should not escalate to MEDIUM.

### D3 — Medium-scale plugin update (~50 files), no feature flag

A plugin update across ~50 files (new skill, updated agents, renamed commands). Deployed
via marketplace without a feature flag. Plugin userbase is well under 1M active users;
no production database rows are written.

Expected: judgment call. Documented below.

### D4 — SaaS-scale 50M-row migration WITH a feature flag

Same schema migration as D1 but the deploy is gated behind a feature flag.
o5 = NO regardless of migration size. All other operational_risk questions = NO.

Expected: **HIGH** — the flag neutralises the o5 signal entirely.

---

## Candidate Analysis

### Current rubric (baseline)

```
operational_risk:
  o1 weight=3, o2 weight=3, o3 weight=2, o4 weight=2
  o5 weight=1  ← under review
  medium_threshold=2, low_threshold=5
```

o5 alone: 1pt < medium_threshold=2 → HIGH. Cannot escalate solo.

### C1 — Bump o5 weight 1 → 2

One YES on o5 produces 2pts = medium_threshold → MEDIUM.

| Description | Reading | Notes |
|---|---|---|
| D1: 50M-row migration, no flag | MEDIUM | Bug fixed |
| D2: typo fix, no flag | MEDIUM | **FALSE POSITIVE** — trivial change escalated |
| D3: plugin update, no flag | MEDIUM | **FALSE POSITIVE** — plugin update escalated |
| D4: migration WITH flag | HIGH | Correct |

**Verdict: FAIL.** C1 fixes D1 but introduces false positives on D2 and D3. Every change
deployed without a flag — regardless of size or impact — tips to MEDIUM. That is too
aggressive: most routine changes ship without feature flags.

### C2 — Lower medium_threshold from 2 to 1

Any single YES on any operational_risk question reaches MEDIUM.

| Description | Reading | Notes |
|---|---|---|
| D1: 50M-row migration, no flag | MEDIUM | Bug fixed |
| D2: typo fix, no flag | MEDIUM | **FALSE POSITIVE** |
| D3: plugin update, no flag | MEDIUM | **FALSE POSITIVE** |
| D4: migration WITH flag | HIGH | Correct |

**Verdict: FAIL.** Same false positive profile as C1, and additionally downgrades ALL
other operational signals (o1-o4) to escalate at threshold 1 instead of 2, which was
calibrated deliberately. A more aggressive change with broader regressions.

### C3 — Reword o5 (no weight change)

New wording: "Is this change deployed without a feature flag AND expected to directly
affect more than 1M users/rows in production on day 1?"

With weight still at 1, even when the reworded question fires YES it produces 1pt
< medium_threshold=2 → still HIGH.

| Description | Conceptual fire | Reading | Notes |
|---|---|---|---|
| D1: 50M-row migration, no flag | YES | HIGH | **BUG NOT FIXED** — still 1pt |
| D2: typo fix, no flag | NO | HIGH | Correct |
| D3: plugin update, no flag | NO | HIGH | Correct |
| D4: migration WITH flag | NO | HIGH | Correct |

**Verdict: FAIL.** Eliminates false positives but does not fix D1. A reword without a
weight adjustment is insufficient because the scoring arithmetic is unchanged.

### C4 (chosen) — Reword o5 AND bump weight 1 → 2

New wording: "Is this change deployed without a feature flag AND expected to directly
affect more than 1M users/rows in production on day 1?"
Weight: 2 (from 1).

The reword restricts the question to genuinely high-impact deploys.
The weight bump ensures that when it fires, it reaches medium_threshold=2.

| Description | Conceptual fire | Points | Reading | Meets criterion? |
|---|---|---|---|---|
| D1: 50M-row migration, no flag | YES | 2 | MEDIUM | YES — bug fixed |
| D2: typo fix, no flag | NO | 0 | HIGH | YES — no false positive |
| D3: plugin update, no flag | NO | 0 | HIGH | YES — judgment correct |
| D4: migration WITH flag | NO | 0 | HIGH | YES — flag present |

**Verdict: PASS.**

**D3 judgment rationale**: A plugin update with ~50 files does not affect > 1M users/rows
on day 1. Plugin marketplace installs are opt-in and gradual; there is no production
database row count involved. The reworded question correctly fires NO, and HIGH is the
right reading. If a future plugin were installed in a SaaS platform serving > 1M active
users with a breaking change, the question would fire YES and reach MEDIUM — which is
also correct.

**All-YES sanity check**: o1(3)+o2(3)+o3(2)+o4(2)+o5(2)=12pts ≥ low_threshold=5 → LOW.
LOW remains reachable. The weight bump does not break the scoring range.

**Cluster-A regression check**: cluster-A answers o5=NO (skill files, not a production
deploy). All-NO → HIGH. No impact on existing AC-5 tests.

---

## Decision Rationale

The root issue is that o5 is a blunt instrument under the current wording: any change
shipped without a feature flag fires YES, regardless of whether the deploy actually
carries meaningful operational risk. A typo fix in an error string and a 50M-row
migration are both "deployed without a flag" — but they are not comparable risks.

The reword anchors o5 to scale: it fires only when the no-flag deploy is expected to
directly affect > 1M users/rows. This is the distinguishing property of genuinely
elevated operational risk from a no-flag deploy. Weight=2 then ensures that a confirmed
high-scale, no-flag deploy reaches medium_threshold without requiring corroboration from
o1-o4 (which measure different operational dimensions).

Candidate C1/C2 produce clean fixes on D1 but cannot distinguish D2. Candidate C3
eliminates false positives but leaves D1 broken. C4 combines the selectivity of C3 with
sufficient weight to fix D1 — the only candidate that satisfies all three criteria.

**Known accepted trade-off — the 999K boundary cliff**: The "> 1M users/rows" criterion
creates a discrete cliff at exactly 1,000,000. A 999K-row migration without a feature
flag will read HIGH (o5=NO under the strict reading of ">1M"), while a 1,000,001-row
migration without a flag reads MEDIUM. This boundary is sharp but the abrupt jump is
preferred over C1/C2's broader false-positive regime where every typo fix without a
flag would escalate. Future calibration may smooth this with a sliding scale, but for
v8.x the cliff is the accepted design trade-off — most consequential migrations have
clearly-known scale and the in-betweens are rare.

---

## Chosen calibration

**Candidate 4 (C4)**: reword o5 + weight 1 → 2.

Applied to `scripts/crew/factor_questionnaire.py` with inline comment:
`# calibrated 2026-04-26 per issue #639 — reword restricts to scale criterion, weight=2 allows solo MEDIUM`
