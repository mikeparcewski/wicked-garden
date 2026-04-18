---
name: propose-process
description: |
  Lead-facilitator rubric. Reads a project description + priors from wicked-brain + the
  specialist roster, then proposes a full task chain (TaskCreate calls with blockedBy deps
  and metadata) plus a `process-plan.md` artifact. Replaces the v5 rule engine
  (smart_decisioning.py + phases.json + SIGNAL_TO_SPECIALISTS) with LLM reasoning over a
  small number of well-defined factors.

  Use when: starting a new crew project, re-planning after a gate finding, emitting the
  initial task chain for `/wicked-garden:crew:start`, or invoked on `TaskCompleted` to
  prune / augment / re-tier the remaining chain. Also used by
  `/wicked-garden:crew:just-finish` (yolo mode) to drive autonomous completion.
disable-model-invocation: false
---

# Propose Process (Facilitator Rubric)

This skill IS the rubric. Every section below is instructional — you (Claude) follow it
at call time. No Python. No rule tables. Reasoning about the work itself.

## Inputs

1. **`description`** — project description, issue text, or the task that just completed.
2. **`priors`** (optional) — `wicked-brain:search` output on related projects/gotchas.
   If absent, fetch them as Step 2 (see `refs/inputs.md`).
3. **`constraints`** (optional) — hard constraints (deadline, stack, compliance envelope).
4. **`mode`** — `propose` | `re-evaluate` | `yolo`; default `propose`.
5. **`current_chain`** — required for `re-evaluate`: tasks created so far, status, evidence.
6. **`auto_proceed`** — bool; set by yolo mode; suppresses user confirmation.

## Outputs

1. **`process-plan.md`** — artifact written to the project directory (template in
   `refs/plan-template.md`) with factor scoring, specialists, phases, rigor, complexity,
   open questions.
2. **Task chain** — native `TaskCreate` calls (one per task) with `blockedBy` deps and
   `metadata`: `{chain_id, event_type, source_agent:"facilitator", phase, test_required,
   test_types, evidence_required, rigor_tier}`.
3. **Open questions block** — plain-text numbered list when ambiguity is high. Shown
   BEFORE task creation. See `refs/ambiguity.md`.

## The Rubric (follow in order)

### 1. Read the description

Summarize in 2-3 sentences in your own words. Name the user-facing outcome, surface area
(UI / API / data / infra / docs), and any risk words (auth, migrate, GDPR, payment,
production, rollback). Do NOT pattern-match keywords mechanically — read for meaning.
When the description is genuinely ambiguous, note it and plan to invoke
`/wicked-garden:deliberate` + `/wicked-garden:jam:quick` BEFORE scoring factors.

### 2. Pull priors

Call `wicked-brain:search` with 3-4 salient nouns. Also `wicked-brain:query` for clear
"how do we usually do X?" questions. Prefer `source_type: memory` (prior decisions/
gotchas) over wiki and chunks for planning. Record up to 3 priors that change the plan.

### 3. Score the 9 factors (one sentence each)

Prose, not numbers. See `refs/factor-definitions.md` for meaning + calibration.

1. **Reversibility** — can we undo without customer impact?
2. **Blast radius** — if this breaks, who / how many / what is affected?
3. **Compliance scope** — regulated data or surface (GDPR, PCI, HIPAA, SOC2)?
4. **User-facing impact** — does a human see or feel this?
5. **Novelty** — have we done this before in this codebase? (use priors from Step 2)
6. **Scope effort** — how many files / services / teams?
7. **State complexity** — persistent state, migrations, schema changes?
8. **Operational risk** — production runtime behavior change?
9. **Coordination cost** — multiple specialists to agree or hand off?

### 4. Select specialists

Read `agents/**/*.md` frontmatter (descriptions + "Use when"). Pick the smallest set
that covers the factor scores. One sentence of WHY per pick. Prefer ≤5 for standard,
≤10 for full. See `refs/specialist-selection.md` for the ~70-agent roster map and
tie-breakers.

Core archetypes: `requirements-analyst`, `product-manager`, `solution-architect`,
`senior-engineer`, `backend-engineer`, `frontend-engineer`, `migration-engineer`,
`test-strategist`, `test-designer`, `security-engineer`, `compliance-officer`,
`privacy-expert`, `auditor`, `sre`, `release-engineer`, `data-engineer`,
`technical-writer`, `ux-designer`, `ui-reviewer`.

### 5. Select phases

Pick from: `ideate`, `clarify`, `design`, `test-strategy`, `build`, `test`, `review`.
Dependencies are soft — skip `design` for a trivial typo, collapse `clarify`+`design`
for a crisp bugfix, insert `migrate` between `design` and `build` when state_complexity
is high. One sentence WHY per phase + primary specialist(s). See `refs/phase-catalog.md`.

### 6. Assign evidence metadata per task

- `test_required` — bool. False only for pure docs, internal rename with no behavior
  change, or config-only flag flips with no new code paths.
- `test_types` — subset of `{unit, integration, api, ui, acceptance, migration, security,
  a11y, performance}`. Functional framing: **input → output → observable analysis**.
  Do NOT set coverage thresholds.
- `evidence_required` — subset of `{unit-results, integration-results, acceptance-report,
  screenshot-before-after, api-contract-diff, migration-rollback-plan,
  compliance-traceability, security-scan, performance-baseline, a11y-report}`. Minimum
  that proves the task did what it claims.

See `refs/evidence-framing.md` for worked examples.

### 7. Assign rigor tier

- **minimal** — factors mostly low; one reviewer; gates advisory. Typos, docs, cosmetic.
- **standard** — one or more factors medium; enforced gates; a test phase. Most bugfixes
  and small-to-mid features.
- **full** — any factor high (compliance, auth rewrite, cross-service migration,
  user-visible with low reversibility); multiple reviewers; mandatory acceptance +
  compliance traceability. `auto_proceed=true` is IGNORED for full-rigor work.

One sentence WHY.

### 8. Estimate complexity (0-7)

Judgment, not checklist. 0-1 trivial. 2-3 small self-contained. 4-5 feature with
coordination. 6-7 cross-cutting or compliance-bound. One sentence WHY. Priors from
Step 2 are a good sanity check.

### 9. Open questions

If ambiguity is high, STOP. Emit 2-5 numbered clarifying questions; do NOT create tasks.
In `yolo` mode, if questions exist, escalate to the user; never guess. See
`refs/ambiguity.md`.

## Task chain assembly

One `TaskCreate` per task. Mirror the task list inside `process-plan.md` for
auditability. Metadata schema:

```json
{
  "chain_id": "<project-slug>.root",
  "event_type": "task | coding-task | gate-finding | phase-transition",
  "source_agent": "facilitator",
  "phase": "<phase-name>",
  "test_required": true,
  "test_types": ["unit", "integration"],
  "evidence_required": ["unit-results", "integration-results"],
  "rigor_tier": "standard"
}
```

Use `blockedBy: [<ids>]` for dependencies. The chain is a DAG. Parallel-eligible tasks
within a phase share a `blockedBy` pointing to the same upstream.

## Re-evaluation mode

On `TaskCompleted` or a gate-finding, read `current_chain` + latest evidence. Then:

1. **Prune** — pending tasks now satisfied, or whose assumptions the evidence
   invalidates. One sentence WHY per pruned task.
2. **Augment** — tasks for emergent concerns (discovered migration, new compliance
   surface, blocked dependency). One sentence WHY.
3. **Re-tier** — if evidence sharpens risk, upgrade rigor. NEVER silently downgrade;
   downgrade requires user confirmation outside yolo mode.

Emit mutations as follow-up `TaskCreate` / `TaskUpdate`. Do NOT rewrite completed tasks.
Append an addendum to `process-plan.md` titled "Re-evaluation <timestamp>".

## Interaction mode — yolo / `/wicked-garden:crew:just-finish`

**Interaction mode is orthogonal to phase plan, specialist selection, rigor tier, and
evidence requirements.** Those are determined by the work itself via this rubric,
regardless of whether the user wants interactive or autonomous completion.

Interaction mode controls ONLY whether the user is prompted at gate boundaries:

- **normal** (default): user confirms the plan before task creation; reviewer verdicts
  at each gate surface to the user for approval.
- **yolo** / `auto_proceed=true` / `/wicked-garden:crew:just-finish`:
  - Skip user confirmation on the initial plan when rigor_tier is `minimal` or `standard`.
  - Auto-approve gates whose reviewer verdict is APPROVE.
  - Silently accept CONDITIONAL gates when the conditions are self-resolving spec gaps.
  - Escalate to user on REJECT verdicts with no clear fix, or CONDITIONAL requiring intent changes.
  - NEVER operate in yolo when rigor_tier is `full` — escalate to user with the plan.

"Just-finish" means **run to the end autonomously**, NOT "skip phases" or "do less
work." The facilitator already picked the phase plan based on the factors; yolo mode
does not change it. If the work genuinely needs only build + review, the facilitator
chose `minimal` rigor — not because yolo was passed.

Banned `source_agent` values (`just-finish-auto`, `fast-pass`, `auto-approve-*`) are
still banned. Use `facilitator` for all facilitator-emitted tasks even in yolo.

## Measurement hook

The measurement script (`scripts/ci/measure_facilitator.py`) invokes this rubric in
dry-run. When `output=json` is passed, emit a single JSON object matching
`refs/output-schema.md` instead of creating tasks. This is the shape scenarios compare
against.

## Navigation

- [`refs/inputs.md`](refs/inputs.md) — prior-fetch queries, session state reads
- [`refs/factor-definitions.md`](refs/factor-definitions.md) — the 9 factors + calibration
- [`refs/specialist-selection.md`](refs/specialist-selection.md) — roster map
- [`refs/phase-catalog.md`](refs/phase-catalog.md) — phase templates, soft deps
- [`refs/evidence-framing.md`](refs/evidence-framing.md) — functional evidence rubric
- [`refs/ambiguity.md`](refs/ambiguity.md) — when to stop and ask
- [`refs/plan-template.md`](refs/plan-template.md) — `process-plan.md` template
- [`refs/output-schema.md`](refs/output-schema.md) — JSON shape for measurement
