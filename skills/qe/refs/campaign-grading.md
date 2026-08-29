---
phase_relevance: ["test", "review"]
archetype_relevance: ["build", "review", "ship"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-10, ADR 0006 "qe
     campaign"). Loaded on demand via Read() from the qe router when a
     CAMPAIGN's evidence needs grading — not a skill. The single-scenario
     acceptance pipeline this builds on is refs/accept.md. -->

# qe campaign grading — the accept trio over campaign evidence

How a campaign's evidence bundles become graded verdicts, a scoreboard, and a
terminating certification — **without a single self-graded verdict anywhere in
the flow**. This is the productized form of the grading loop the 2026-08
studio E2E campaign proved (CAMPAIGN-REPORT: 21 scenarios graded, 6 product
findings mirrored out, certification terminated).

## Separation of duties (structural, per ADR 0006)

```
executor (model-free runner, TH-4)  ──►  evidence bundles   (claims, never verdicts)
reviewer (accept trio, isolated)    ──►  verdicts rows      (grades, evidence-only view)
scoreboard glue (deterministic)     ──►  scoreboard + fork  (assembly, never judgment)
crew acceptance gate (TH-6)         ──►  "done" re-derived  (deny-dominates)
```

| Role | Writes | Never writes |
|---|---|---|
| **Executor** (`scripts/qe/runner`, or any qe executor) | evidence artifacts, `manifest.json`, an **executor claim** (manifest-2.1 `scenario_evidence.status`, or the claim parked in the manifest verdict block as `reviewer: "qe-runner/executor-claim"`) | a ledger `verdicts` row — grading is not its job, structurally: the runner creates no verdicts row at all |
| **Reviewer** (`wicked-garden-qe-acceptance-test-reviewer`) | the verdict of record (`verdicts` row) + the non-PASS classification tag | evidence — it only Reads |
| **Scoreboard glue** (`scripts/qe/lib/campaign-scoreboard.mjs`) | the scoreboard + findings/violations report; optional `tasks` mirror rows | grades — it refuses executor identities as grade sources |

## Reviewer isolation — the boundary, written down

The campaign reviewer is the SAME isolated reviewer as `refs/accept.md`
(3 layers: `allowed-tools: Read` + evidence-only dispatch + `context: fork`).
Dispatch it per scenario with **evidence paths only** — the scenario file
path, the evidence directory path, and (when one exists) the test-plan path.
Never the executor's stdout, reasoning, spec-authoring context, or the
campaign orchestrator's conversation.

**Enforcement boundary — know which tier you are on:**

| CLI | Isolation enforcement |
|-----|-----------------------|
| Claude Code | **Hard-enforced** — `allowed-tools: [Read]` is blocked at the host level; the reviewer cannot shell out, browse, or re-run anything even if prompted to |
| Gemini CLI, Codex, Cursor, Kiro | **Advisory** — the skill's dispatch contract still passes paths only, but the host does not block tools; a prompt-injected or misbehaving reviewer could technically reach beyond the evidence |

On advisory hosts the evidence-only dispatch is the only real layer, so:
never inline evidence content into the dispatch, and treat campaign
certifications produced on advisory hosts as exactly that — the environment
manifest (TH-8) records which CLI graded, so the claim is auditable. Tests
tagged `@requires-enforcement: claude-code` validate the hard tier only.

## Validate before grading (wicked-ledger manifest 2.1)

Per wicked-ledger's SCHEMA-CONTRACT (the evidence system of record):

1. **Pre-dispatch (deterministic, orchestrator-side):** validate each bundle
   before the reviewer ever sees it —

   ```bash
   node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-scoreboard.mjs" \
     --validate-only .wicked-qe/evidence/<run-id>
   # exit 0 = conformant · 5 = schema-fail · 6 = validator unavailable
   ```

   Exit 5 → do NOT dispatch the reviewer for a graded verdict; record
   **INCONCLUSIVE** (reviewer `campaign-grading/schema-preflight`) with the
   violations as the reason, classified `[scenario-defect]`. Exit 6 → the
   resolved wicked-ledger predates `validateManifest` (the manifest-2.1
   contract; published 0.3.0 predates it — the floor ships with the XC-4
   release wave): grading is blocked fail-closed, never assumed.
2. **Reviewer-side (belt and braces):** the reviewer Reads `manifest.json`
   itself and re-checks the structural floor (required trio
   `scenario/status/claim_level` when `scenario_evidence` is present;
   `claim_level` ∈ certified | machinery-verified | skipped; the honest-cap
   invariant — overall never stronger than the weakest leg). Nonconformant →
   verdict INCONCLUSIVE, never PASS/FAIL.

A nonconforming bundle therefore cannot satisfy anything: INCONCLUSIVE maps
to run status `inconclusive`, and crew's deny-dominates acceptance gate
treats it as not-satisfied.

## Grading loop (per scenario)

For each campaign run (evidence at `.wicked-qe/evidence/<run-id>/`):

1. Preflight-validate the bundle (above).
2. Dispatch the reviewer exactly as in `refs/accept.md` § 5 — paths only.
   The executor claim inside the bundle (`scenario_evidence.status`,
   `result.json` `executor_claim`) is **data the reviewer weighs, never a
   default it confirms**: the reviewer re-derives the verdict from wire/db/
   screenshot/read-back artifacts and is expected to contradict the claim
   when evidence doesn't support it (the campaign's S-scripts caught exactly
   such semantic gaps).
3. Write the `verdicts` row per `refs/accept.md` § 6 (reviewer
   `acceptance-test-reviewer`; 1:1 verdict→status mapping). This is the only
   place a campaign grade is born.
4. **Classify every non-PASS** (FAIL / PARTIAL / CONDITIONAL / INCONCLUSIVE)
   with a tag as the FIRST token of the verdict reason — the fork below.

**Never** route a campaign verdict through `wicked-garden-qe-test-designer`
(the dev-loop fast path is self-graded by design — `refs/execute.md` reserves
it away from audit/CI/sign-off, and the scoreboard glue refuses its verdicts).

## The fork: scenario-defect vs product-finding (anti-expansion rule)

Every non-PASS grade is one of exactly two things:

| Tag (verdict-reason prefix) | Meaning | What happens |
|---|---|---|
| `[scenario-defect]` | The scenario/spec/environment is wrong — drifted selector, bad fixture, wrong assertion, nonconformant bundle | Spawns a **fix lane**: re-author the spec against the live target (agentic authoring phase — the model-free runner never improvises, TH-13), re-run, re-grade. **Bounded**: at most 2 re-author cycles per rung; still failing → park as INCONCLUSIVE `[scenario-defect]` with a ledger `tasks` row and move on |
| `[product-finding]` | The product is wrong — the scenario did its job | **Mirrors out and stops**: a GitHub issue in the product repo (`gh issue create`) + a ledger `tasks` row (the durable mirror; `--mirror-tasks` below). The campaign does NOT add rungs, chase the bug, or block on the fix |

This is what makes **certification terminate**: findings leave the campaign
(mirrored out), defects loop boundedly, and nothing expands the ladder
mid-flight. A finding's GH issue URL goes into the tasks-row body once filed.

## Scoreboard (assembly, not judgment)

Deterministic glue — run it after grading; it never grades:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-scoreboard.mjs" \
  --repo-root . --scenario-prefix S --json [--mirror-tasks] [--out scoreboard.json]
```

Row shape — **verbatim** the campaign-proven contract, four keys, no more:

```json
{ "id": "S1", "grade": "PASS", "executor_claim": "…", "evidence_ok": true }
```

- `id` — stable scenario identity (ledger `scenarios.name`; TH-6's stable
  scenario_ids make flake history accrue here across re-runs).
- `grade` — the isolated reviewer's verdict of record, **born in a ledger
  `verdicts` row and nowhere else**. The glue **refuses** executor identities
  (`qe-runner/executor-claim`, `*executor*`, `*test-designer*`) as grade
  sources and reports each such verdicts row as a `self_grade_attempt`
  violation; the executor-authored manifest verdict block never sources a
  grade either (a non-executor reviewer identity in it is reported as
  `manifest_verdict_impersonation`); a run without a reviewer verdict shows
  `UNGRADED` (which blocks certification) rather than inheriting the claim.
- `executor_claim` — the claim as text beside the grade (from manifest-2.1
  `scenario_evidence.status` — the field the ledger contract itself marks
  "the EXECUTOR'S CLAIM … never the verdict of record"). Divergence between
  claim and grade is signal, not noise.
- `evidence_ok` — wicked-ledger `validateManifest()` + the major-version
  floor. Validator unavailable → `false`, fail closed. A non-INCONCLUSIVE
  grade sitting on `evidence_ok=false` is reported as a
  `graded_invalid_bundle` violation.

The envelope around the rows carries `findings` (the fork's three buckets),
`violations`, and `certification.disposition` — always `certified` or
`not-certified`, never pending: certified ⇔ every row is PASS with
`evidence_ok=true`, zero violations, zero UNGRADED, zero unclassified.
`--mirror-tasks` writes the product-finding `tasks` rows (idempotent by
title; exit 7 if the ledger store is unreachable — mirroring is not optional
before campaign teardown).

## Wiring context

- Gate announcement (`wicked.qe.gate.*`) and the crew acceptance flip are
  TH-6's seam (`scripts/qe/lib/gate.mjs`); this playbook produces the graded
  verdicts rows that seam re-derives from.
- Evidence redaction ran INSIDE the executor before anything here sees a
  byte (TH-19); vault attestation (TH-17) comes after grading, ordered
  behind redaction.
