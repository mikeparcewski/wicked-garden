---
phase_relevance: ["test", "review"]
archetype_relevance: ["build", "review", "ship"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-21, ADR 0006 "qe
     campaign"). Loaded on demand via Read() when a campaign verdict flips,
     a known-flaky scenario reaches the gate, or a quarantine needs to be
     honored at certification — not a skill. The grading loop this plugs
     into is refs/campaign-grading.md. -->

# qe campaign flake policy — flaky verdicts at the acceptance gate

Deny-dominates plus a 20+ scenario nightly corpus means **one flaky scenario
denies every campaign** — and the reflexive countermeasure, silent
retry-to-green, launders real bugs. This policy makes both failure modes
impossible: a flaky scenario can neither silently deny nor silently pass a
campaign, and every exclusion carries a reason, an owner, and a deadline.

The deterministic half lives in `scripts/qe/lib/flake-policy.mjs` and is
applied by `campaign-scoreboard.mjs` on **every** assembly (no opt-in flag);
`gate.mjs --exclusions-from` carries the result into the acceptance payload.
The judgment half — root-causing and the quarantine decision — belongs to
`wicked-garden-qe-flaky-test-hunter` and never to this glue.

## Rule 1 — diagnostic re-runs are bounded, and BOTH verdicts are recorded

A re-run is a **diagnostic, never a mulligan**:

- **Trigger**: a rung's graded verdict contradicts its recent history (the
  ledger's flake history per stable scenario id — TH-6 makes it accrue across
  re-runs) or the reviewer suspects nondeterminism.
- **Path**: every re-run goes through the normal § execute path — a NEW
  `runs` row + evidence bundle + isolated-reviewer `verdicts` row under the
  SAME scenario id. Both verdicts therefore stand in the ledger and on the
  scoreboard; this is exactly the history the hunter's 14d window consumes.
- **Bound**: at most **2 diagnostic re-runs per rung per campaign**
  (`MAX_DIAGNOSTIC_RERUNS` — same bound as the fix lane in
  refs/campaign-grading.md). Beyond 1 original + 2 diagnostics the scoreboard
  reports a `rerun_bound_exceeded` violation: re-running until green is
  pass-laundering even when every verdict is recorded. Park the rung and
  dispatch the hunter.
- **The gate is never best-of-N**: a PASS re-run never replaces the FAIL.
  Mixed graded outcomes (PASS next to FAIL/PARTIAL/CONDITIONAL) for one
  scenario inside a campaign become a `flake_signal` **blocker** naming the
  hunter as the remedy — certification is denied loudly, with the next step
  attached, never silently.
- **Laundering guard**: assembling the scoreboard with a `--runs` selection
  that shows a scenario as PASS while a same-window sibling run of that
  scenario sits outside the selection with a deny grade is a
  `pass_laundering_risk` violation. Older history (previous campaigns) is
  legitimately out of scope; same-window omissions are not.

## Rule 2 — the quarantine lane: owner + deadline via the hunter's taxonomy

Only `wicked-garden-qe-flaky-test-hunter` quarantines (its SKILL.md § 6
strict policy: real fix > 14 days away AND blast radius < 1%; never "add
retry"). The campaign gate only **consumes** its machine-readable record — a
ledger `tasks` row:

```jsonc
// tasks row (written by the hunter — SKILL.md § 5)
{
  "assignee_skill": "flaky-test-hunter:<cause>",   // cause ∈ the fixed taxonomy
  "status": "blocked",                              // any non-closed status is live
  "body": {                                         // JSON string
    "quarantined": true,                            // exactly true
    "scenario_id": "<ledger scenarios UUID>",       // or "scenario_name": "<stable id>"
    "cause": "timing|order-dep|env|resource|external-dep",
    "owner": "<person/team owning the fix>",        // REQUIRED — no owner, no exclusion
    "quarantine_expires": "<ISO deadline>",         // REQUIRED — no deadline, no exclusion
    "reason": "<optional prose>",                   // else synthesized from cause + proposed_fix
    "proposed_fix": "…", "flake_rate": 0.12
  }
}
```

Consumption is **fail-closed** (`loadQuarantineState`):

| Record state | Gate behavior |
|---|---|
| **Active** (all fields valid, deadline in the future) | Scenario excluded-with-reason (Rule 3); newest record per scenario wins |
| **Invalid** (missing owner, cause outside the taxonomy, no deadline, unresolvable scenario binding) | **Not honored** — the scenario stays in the gate and still denies; the refusal is reported under `flake_policy.quarantine.invalid` |
| **Expired** (deadline passed) | **Not honored** — reported under `flake_policy.quarantine.expired`; the hunter auto-reopens expired quarantines as open tasks |
| Closed task / non-quarantine hunter task / unparseable body | Ignored — not a quarantine record at all |

A quarantine can therefore never be vague: no owner or no deadline simply
means the campaign stays red, which is the honest state.

## Rule 3 — gate representation: excluded-with-reason, never dropped, never naked-conditional

An honored quarantine removes the scenario from the **certification
calculus** but never from sight:

- **Scoreboard**: the scenario's rows keep their verbatim 4-key shape
  (`{id, grade, executor_claim, evidence_ok}`) on the board; row-level
  blockers (non-PASS, UNGRADED, evidence_ok) skip them. The exclusion —
  `{id, cause, owner, deadline, reason, observed_grades}` — rides
  `certification.excluded`, and `certification.gate_summary` is a ready-made
  one-liner embedding every exclusion with its reason.
- **Acceptance payload**: pass the envelope to the gate CLI —

  ```bash
  node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-scoreboard.mjs" \
    --repo-root . --json --out scoreboard.json
  node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/gate.mjs" \
    --project-id <id> --run-id <id> --verdict PASS \
    --verdict-summary "$(node -e 'console.log(require("./scoreboard.json").certification.gate_summary)')" \
    --exclusions-from scoreboard.json
  ```

  `--exclusions-from` appends the canonical
  `quarantined excluded-with-reason (…)` clause to the verdict summary, so
  the exclusions land in the ledger `verdicts` row AND the
  `wicked.qe.gate.*` event's `verdict_summary` — crew's
  `GET /runs/:id/acceptance` re-derives from both. The 8-field gate wire
  contract is untouched; the clause rides the existing field. Fail-closed:
  an exclusion missing id/reason/owner/deadline exits 3 — an exclusion
  without a reason structurally cannot reach the acceptance payload.
- **Never a naked CONDITIONAL**: a quarantine is not a downgrade-to-
  CONDITIONAL — the gated rows certify (or don't) on their own merits and
  the exclusions are itemized beside the disposition.
- **Boundaries**: a fully-quarantined campaign cannot certify ("all rows
  excluded by quarantine — nothing gated"); a quarantined scenario's PASS is
  excluded too (counting passes while excluding failures would itself be
  laundering); structural violations (`self_grade_attempt`,
  `manifest_verdict_impersonation`, `graded_invalid_bundle`) always block —
  quarantine excuses flakiness, never cheating.

## What this makes impossible (the TH-21 acceptance criteria)

| Failure mode | Countermeasure |
|---|---|
| One flaky scenario silently **denies** the nightly | Its deny is loud and actionable (flake_signal blocker names the hunter); once the hunter quarantines it with owner+deadline, it is excluded-with-reason — the gate stays honest without being permanently red |
| One flaky scenario silently **passes** the nightly | Both verdicts of a diagnostic re-run stand (never best-of-N); mixed outcomes block; `--runs` cherry-picking is a `pass_laundering_risk` violation; a quarantined scenario's PASS is excluded, not counted |
| Exclusion without a reason | Structurally refused at both seams: an invalid quarantine record is not honored (scoreboard), and `buildExclusionsClause` / `--exclusions-from` exit 3 on a reason-less exclusion (gate) |
| Retry-until-green | `rerun_bound_exceeded` violation past 1 + 2 runs; the hunter never proposes "add retry" |

## Wiring

- `scripts/qe/lib/flake-policy.mjs` — pure policy engine (exported, tested)
- `scripts/qe/lib/campaign-scoreboard.mjs` — applies the policy on every
  assembly; envelope keys `flake_policy`, `certification.excluded`,
  `certification.gate_summary`
- `scripts/qe/lib/gate.mjs --exclusions-from` — exclusions into the
  acceptance payload
- `wicked-garden-qe-flaky-test-hunter` — root cause + the quarantine
  decision (dispatch through the guard, refs/campaign.md); § insight answers
  flake-rate questions read-only
- Nightly CI (TH-23) consumes this policy as-is: the nightly recipe runs the
  scoreboard, passes `--exclusions-from`, and stays green-with-exclusions
  instead of permanently red

## References

[refs/campaign-grading.md](campaign-grading.md) · [refs/execute.md](execute.md) ·
[refs/insight.md](insight.md) ·
`${CLAUDE_PLUGIN_ROOT}/skills/qe-flaky-test-hunter/SKILL.md` · ADR 0006 (`docs/adr/`)
