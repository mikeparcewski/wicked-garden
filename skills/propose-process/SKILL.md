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
Factors: **reversibility** (undo without customer impact?), **blast_radius** (who/how
many affected if broken?), **compliance_scope** (GDPR/PCI/HIPAA/SOC2?),
**user_facing_impact** (human-visible?), **novelty** (done before in this codebase —
use priors), **scope_effort** (files/services/teams), **state_complexity** (persistent
state, migrations), **operational_risk** (production runtime change),
**coordination_cost** (multiple specialists to agree/hand off?).

### 4. Select specialists

Read `agents/**/*.md` frontmatter (descriptions + "Use when"). Pick the smallest set
that covers the factor scores. One sentence of WHY per pick. Prefer ≤5 for standard,
≤10 for full. See `refs/specialist-selection.md` for the ~70-agent roster map and
tie-breakers.

Core archetypes: `requirements-analyst`, `product-manager`, `solution-architect`, `senior-engineer`, `backend-engineer`, `frontend-engineer`, `migration-engineer`, `test-strategist`, `test-designer`, `security-engineer`, `compliance-officer`, `privacy-expert`, `auditor`, `sre`, `release-engineer`, `data-engineer`, `technical-writer`, `ux-designer`, `ui-reviewer`.

### 5. Select phases

Pick from: `ideate`, `clarify`, `challenge`, `design`, `test-strategy`, `build`, `test`,
`review`. Soft deps — skip `design` for a trivial typo, collapse `clarify`+`design` for a
crisp bugfix, insert `migrate` between `design` and `build` when state_complexity is high.
**MUST**: at complexity ≥ 4, `challenge` phase MUST be included between `design` and `build`;
do not use facilitator judgment to skip it. For each phase, emit: `name`, `why` (one
sentence), `primary: [specialist-name, ...]` (owners from Step 4). See `refs/phase-catalog.md`.

### 6. Select archetype + assign evidence metadata per task

**Archetype selection (clarify time)**: Select one archetype and emit it in every
`TaskCreate` `metadata.archetype`. 7-value enum (priority order, first match wins):
`schema-migration` → `multi-repo` → `testing-only` → `config-infra` →
`skill-agent-authoring` → `docs-only` → `code-repo` (fallback). Call
`archetype_detect.detect_archetype()` when available; see `refs/evidence-framing.md`.

- `test_required` — bool. False only for pure docs, rename with no behavior change, or
  config flag flips with no new code paths.
- `test_types` — subset of `{unit, integration, api, ui, acceptance, migration, security,
  a11y, performance}`. Functional framing: **input → output → observable analysis**.
  Do NOT set coverage thresholds.
- `evidence_required` — subset of `{unit-results, integration-results, acceptance-report,
  screenshot-before-after, api-contract-diff, migration-rollback-plan,
  compliance-traceability, security-scan, performance-baseline, a11y-report}`. Minimum
  that proves the task did what it claims. Per-archetype defaults in
  `refs/evidence-framing.md`.

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
auditability. Each task has top-level `phase` AND `specialist` (idiomatic) plus a
`metadata` dict that repeats `phase`. Example phase + task:

```json
{"name": "clarify", "why": "nail ambiguous scope", "primary": ["requirements-analyst"]}
```

```json
{
  "id": "t1",
  "title": "...",
  "phase": "clarify",
  "specialist": "requirements-analyst",
  "blockedBy": [],
  "metadata": {
    "chain_id": "<project-slug>.root",
    "event_type": "task | coding-task | gate-finding | phase-transition",
    "source_agent": "facilitator",
    "phase": "clarify",
    "test_required": true,
    "test_types": ["unit", "integration"],
    "evidence_required": ["unit-results", "integration-results"],
    "rigor_tier": "standard"
  }
}
```

`blockedBy: [<ids>]` sets dependencies; the chain is a DAG. Parallel-eligible tasks
within a phase share a `blockedBy` pointing to the same upstream.

## Phase-boundary gates

Every phase has one named gate. All six must appear in the plan's task chain as
`event_type: "gate-finding"` tasks. Reviewer assignment comes from `gate-policy.json`
(codified per D1) — the facilitator does NOT choose reviewers; `phase_manager.py`
reads the policy at approve time.

Gates by phase: clarify→requirements-quality, design→design-quality, test-strategy→testability, build→code-quality, test→evidence-quality, review→final-audit.

Gate verdicts: **APPROVE** → phase advances. **CONDITIONAL** → conditions written to
`conditions-manifest.json`, must be cleared before next phase. **REJECT** → phase
blocked, mandatory rework.

See `refs/gate-policy.md` for the human-readable reviewer matrix.

## Re-evaluation mode (bidirectional, v6)

Phase-start heuristic + phase-end full re-eval with bidirectional mutation (prune / augment / re-tier). Addendum is JSONL (blocks approve when missing or invalid). Full spec + D7 mutation truth table in [`refs/re-evaluation.md`](refs/re-evaluation.md). Schema: [`refs/re-eval-addendum-schema.md`](refs/re-eval-addendum-schema.md).

## Interaction mode

Interaction mode (`normal` | `yolo` / `auto_proceed=true` / `/wicked-garden:crew:just-finish`) is orthogonal to the plan — controls only gate-boundary prompts. Yolo is allowed at full rigor only when the user explicitly grants it (via `/wicked-garden:crew:yolo {project} --approve` or explicit instruction), tracked as `yolo_approved_by_user` + appended to `yolo-audit.jsonl`; auto-revoked if phase-boundary re-eval detects scope increase or re-tier-up. Default: refused. Banned `source_agent` values remain banned. D7 rules apply in all modes (re-tier UP auto, re-tier DOWN defers on user override). Full matrix in [`refs/interaction-mode.md`](refs/interaction-mode.md).

## Measurement hook

`scripts/ci/measure_facilitator.py` invokes this rubric in dry-run. With `output=json`, emit one JSON object matching `refs/output-schema.md` instead of creating tasks. Before Step 3 (factor scoring), read per-project process memory — unresolved retro AIs + open kaizen hypotheses change the plan. See [`refs/process-memory.md`](refs/process-memory.md).

## Navigation

- [`refs/inputs.md`](refs/inputs.md) — prior-fetch queries, session state reads; [`refs/process-memory.md`](refs/process-memory.md) — process memory + uncertainty gate
- [`refs/factor-definitions.md`](refs/factor-definitions.md) — the 9 factors + calibration
- [`refs/specialist-selection.md`](refs/specialist-selection.md) — roster map
- [`refs/phase-catalog.md`](refs/phase-catalog.md) — phase templates, soft deps
- [`refs/evidence-framing.md`](refs/evidence-framing.md) — functional evidence rubric + per-archetype contracts
- [`refs/ambiguity.md`](refs/ambiguity.md) — when to stop and ask
- [`refs/plan-template.md`](refs/plan-template.md) — `process-plan.md` template; [`refs/output-schema.md`](refs/output-schema.md) — JSON shape for measurement
- [`refs/interaction-mode.md`](refs/interaction-mode.md) — normal vs. yolo, banned values; [`refs/gate-policy.md`](refs/gate-policy.md) — Gate × Rigor reviewer matrix
- [`refs/re-eval-addendum-schema.md`](refs/re-eval-addendum-schema.md) — JSONL addendum schema; [`refs/spec-quality-rubric.md`](refs/spec-quality-rubric.md) — spec quality rubric
