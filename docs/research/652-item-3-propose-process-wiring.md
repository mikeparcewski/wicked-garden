# Research: Issue #652 Item 3 — propose-process Wiring

**Question**: Does `propose-process` invoke the skill directly, or via an agent dispatch?
**Date**: 2026-04-25
**Scope**: Read-only investigation. No code changes.

---

## Section 1: Call Path

### Primary caller — `commands/crew/start.md` (Step 5, lines 105–133)

`crew:start` invokes propose-process **skill-direct** via `Skill()`:

```
Skill(
  skill="wicked-garden:propose-process",
  args={
    "description": "{description}",
    "mode": "propose",
    "project_slug": "{slug}",
    "output": "json"
  }
)
```

There is no agent intermediary. The command calls the skill inline, then immediately runs
`validate_plan.py` on the returned JSON before doing anything else.

### All callers (non-worktree, non-test)

| Caller | File | Line(s) | Invocation style | Mode |
|---|---|---|---|---|
| `crew:start` Step 5 | `commands/crew/start.md` | 113 | `Skill(skill="wicked-garden:propose-process")` | `propose` |
| `crew:execute` Step 4.5 checkpoint re-eval | `commands/crew/execute.md` | 264 | `Skill(skill="wicked-garden:propose-process")` | `re-evaluate` |
| `crew:execute` legacy fallback | `commands/crew/execute.md` | ~249 | `Skill(skill="wicked-garden:propose-process")` | `propose` |
| `crew:just-finish` checkpoint re-eval | `commands/crew/just-finish.md` | 244 | `Skill(skill="wicked-garden:propose-process")` | `re-evaluate` |
| `phase-executor` agent (phase-start re-eval) | `agents/crew/phase-executor.md` | 148 | `Skill(skill='wicked-garden:propose-process')` | `re-evaluate` |
| `phase-executor` agent (phase-end re-eval) | `agents/crew/phase-executor.md` | ~77 | `Skill(skill='wicked-garden:propose-process')` | `re-evaluate` |
| `crew:approve` recovery path | `commands/crew/approve.md` | 344 | prose reference only — no dispatch block | `re-evaluate` |

**Conclusion**: Every invocation is `Skill()` direct. There is no `Task(subagent_type=...)` wrapping propose-process at any call site.

### Data flow (crew:start path)

```
/wicked-garden:crew:start
  │
  ├─ phase_manager.py create  (bash)
  │
  ├─ Skill("wicked-garden:propose-process", mode=propose)
  │   └─ returns JSON: { project_slug, summary, factors, specialists,
  │                       phases, rigor_tier, complexity, open_questions, tasks[] }
  │
  ├─ validate_plan.py  (bash, exit non-zero = STOP)
  │
  ├─ Open Questions Gate  (conditional STOP)
  │
  ├─ Write process-plan.md + process-plan.json
  │
  ├─ TaskCreate × N  (one per tasks[] entry, parallel where no blockedBy)
  │
  ├─ verify_chain_emission.py  (bash)
  │
  ├─ phase_manager.py update  (bash — stores facilitator_version, rigor_tier, etc.)
  │
  └─ Skill("wicked-brain:memory", store decision)
```

The skill is the rubric itself — it is Claude following the SKILL.md instructions at call
time. No Python subprocess. No separate agent task.

---

## Section 2: Migration Recommendation

### Wiring shape: skill-direct (confirmed)

Pattern A full migration applies:

1. **Extract a new agent** — `agents/crew/process-facilitator.md`
   - Move the rubric instructions (Steps 1–9, Task chain assembly, Re-evaluation mode,
     Interaction mode, Measurement hook sections) from `skills/propose-process/SKILL.md`
     into the new agent file
   - The agent's `subagent_type` should be `wicked-garden:crew:process-facilitator`
   - Risk: **medium** — the rubric is the most-exercised logic in the crew path; any
     omission or mis-copy breaks factor scoring, specialist selection, or task chain shape
   - Mitigation: the 10 facilitator-rubric scenarios become the acceptance gate

2. **Slim SKILL.md to navigation doc** — replace the full rubric text with:
   - Frontmatter (unchanged — callers key off `skill="wicked-garden:propose-process"`)
   - Short description of what the skill does
   - `## Delegate to` section pointing at `wicked-garden:crew:process-facilitator`
   - `## Inputs / Outputs` contract summary (callers need these to pass args correctly)
   - Navigation block pointing at `refs/`
   - Risk: **low** — purely subtractive after the agent is live

3. **Update all callers from `Skill()` to `Task()`** — 6 call sites (see table above):
   - `commands/crew/start.md` line ~113 — `Skill()` → `Task(subagent_type=...)`
   - `commands/crew/execute.md` lines ~264, ~249 — both `Skill()` → `Task()`
   - `commands/crew/just-finish.md` line ~244 — `Skill()` → `Task()`
   - `agents/crew/phase-executor.md` lines ~54 and ~77/148 — two bookend calls, both `Skill()` → `Task()`
   - `commands/crew/approve.md` line 344 — prose reference only, update wording
   - Risk: **high** — the `crew:start` call site is on every project creation; a broken
     dispatch here leaves the project shell created but the task chain empty

### Recommended sequencing

```
Step 1 (low risk):   Write agents/crew/process-facilitator.md — content copy + new frontmatter
Step 2 (low risk):   Slim skills/propose-process/SKILL.md to navigation doc
Step 3 (medium):     Update phase-executor.md (agent-to-agent, contained blast radius)
Step 4 (medium):     Update execute.md and just-finish.md re-eval paths
Step 5 (high):       Update start.md primary path — do this LAST, after scenarios pass on steps 1-4
```

Step 5 last because `crew:start` is the most-exercised path. Running scenarios after each
step catches regressions before the hot path is touched.

---

## Section 3: Safety Net

### Existing coverage

The `scenarios/crew/facilitator-rubric/` directory contains **10 scenarios** that directly
exercise the propose-process output shape:

| Scenario | What it tests |
|---|---|
| `01-trivial-typo.md` | minimal rigor, 1-2 tasks, no test evidence |
| `02-small-bugfix.md` | standard rigor |
| `03-feature-midscale.md` | standard rigor, multiple specialists |
| `04-auth-rewrite.md` | full rigor, security specialist, compliance |
| `05-reversibility-migration.md` | standard/full rigor, migration evidence |
| `06-internal-refactor.md` | standard/minimal rigor |
| `07-docs-only.md` | minimal rigor, docs-only archetype |
| `08-ambiguous-ask.md` | open questions emitted, no tasks created |
| `09-emergent-complexity.md` | complexity escalation |
| `10-compliance-gdpr.md` | full rigor, compliance_scope HIGH |

These scenarios check: `rigor_tier`, `complexity`, `task` count, `test_required`,
`evidence_required`, `specialists` picked, `open_questions` shape. They cover the
output schema contract.

Additional scenario coverage touching propose-process:
- `scenarios/crew/phase-boundary-reeval.md` — re-evaluate mode
- `scenarios/qe/qe-lifecycle-expansion.md` — QE specialist selection via facilitator

**Total scenarios with propose-process coverage: ~12**

### Gaps before migration starts

1. **No scenario tests the `Task()` dispatch path** — all 10 rubric scenarios exercise
   the skill directly. After migration, at least one scenario should verify that calling
   the new agent via `Task(subagent_type="wicked-garden:crew:process-facilitator")` and
   calling it via `Skill("wicked-garden:propose-process")` produce equivalent output.

2. **No scenario exercises the `just-finish.md` re-eval call site** explicitly. The
   `02-autonomous-completion.md` scenario covers the yolo path broadly but does not
   assert the re-eval bookend output shape.

3. **`phase-executor` re-eval bookends** are tested by `scenarios/crew/phase-boundary-reeval.md`
   but that scenario does not assert the full addendum JSONL contents post-migration.

**Minimum new scenarios before step 5**: one smoke scenario that dispatches the new agent
via `Task()` and asserts the same output contract as the existing rubric scenarios.

---

## Section 4: Open Questions

1. **Should `Skill("wicked-garden:propose-process")` continue to work post-migration?**
   The SKILL.md frontmatter declares the skill name that callers bind to. If slimmed to
   a navigation doc that re-delegates to the agent, the skill call is still valid but adds
   one hop. The alternative is to keep the full rubric in SKILL.md and only add an agent
   alias — which is Pattern B (partial), not Pattern A. Needs explicit design decision.

2. **`output=json` flag handling** — `crew:start` passes `output: "json"` to suppress
   task creation and return a JSON blob instead (used by `measure_facilitator.py` and the
   validate path). A Task-dispatched agent cannot return a structured JSON blob to the
   caller the same way a Skill can. The migration must decide how the JSON contract is
   preserved — options: (a) agent writes JSON to a file and caller reads it; (b) agent
   returns a structured result via TaskCreate metadata; (c) keep `output=json` as a
   Skill-only path and only migrate the normal `propose` path to Task dispatch.

3. **`validate_plan.py` timing** — currently `crew:start` runs `validate_plan.py` on the
   returned JSON immediately after the Skill call. If migrated to Task dispatch, the
   validate step must wait for the agent to complete and write its output. The handoff
   mechanism (file vs metadata) drives the validate integration point.

4. **Re-eval bookend in `phase-executor.md`** — the agent calls propose-process twice per
   phase (phase-start and phase-end). If both become Task dispatches, the phase-executor
   becomes a dispatcher of another agent — nesting that may conflict with the
   orchestrator-no-inline-work scenario contract. Needs review of
   `scenarios/crew/orchestrator-no-inline-work.md`.

---

## Summary

- **Wiring shape**: skill-direct at every call site — no existing agent intermediary
- **Migration type**: full Pattern A (extract agent + slim SKILL + update 6 callers)
- **Hot-path risk**: `crew:start` Step 5 is the highest-risk change; update it last
- **Open question count**: 4, with questions 2 and 3 (JSON contract + validate timing) being blockers for the `start.md` caller update
- **Safety net**: 10 existing rubric scenarios cover output shape; 1 new smoke scenario needed before step 5
