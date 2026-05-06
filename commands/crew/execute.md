---
description: Execute current phase work with adaptive role engagement
phase_relevance: ["build", "test"]
archetype_relevance: ["*"]
argument-hint: "[--autonomy=ask|balanced|full]"
---

# /wicked-garden:crew:execute

Execute one phase to completion. For all remaining phases, use `crew:just-finish`.

## 1. Resolve autonomy + load state

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew.autonomy import get_mode
print(get_mode(cli_arg='<arg-or-None>').value)
"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
```

Modes (resolved by `scripts/crew/autonomy.py`): `ask` (default — every gate halts), `balanced` (HITL judge), `full` (auto-proceeds, halts on destructive ops). Pass the resolved mode into `apply_policy(mode, gate_type, context)` at every gate site.

## 2. Pre-flight (always run, in order)

1. **Bus poll** — `process_pending_events()` from `scripts/_bus_consumers.py`. Surfaces side-effect actions (e.g., REJECT-event → rework-task creation). Fail-open.
2. **Brain-store sentinel flush** — if `${project_dir}/.pending-brain-store.json` exists (queued by `crew:start` when brain was unreachable), invoke `Skill('wicked-brain:memory', ...)` with the queued payload, delete on success, increment `attempts` on failure. Don't block.
3. **Phase-start gate (AC-11)** — call `phase_start_gate.check(state, chain_snapshot)` from `scripts/crew/phase_start_gate.py`. Reads `state.last_reeval_ts` / `last_reeval_task_count` (producer wired in `prompt_submit.py::_consume_facilitator_reeval`, v9.2.6) to detect material change since the last re-eval. On non-empty `systemMessage`, emit verbatim and **do not proceed until re-eval completes** (override: `--skip-reeval --reason "..."`).

## 3. Recall + context + task recovery

```
Skill('wicked-brain:memory', args="recall crew learnings and user preferences --limit 10")
Skill('wicked-garden:smaht:context', args="build --task '<phase> for <project>' --project '<project>' --dispatch --prompt")
```

Apply recalled learnings. Include the smaht context package output in every subagent `Task()` dispatch — never raw deliverable text.

**Task lifecycle recovery**: `TaskList` filtered by project name in subject. For tasks `in_progress` > 30 min: classify stale, follow `task_lifecycle.recovery_mode` from project.json (`auto` → `TaskUpdate(status="pending")`; `manual` → ask user). Read `phases/{phase}/status.md` for fallback if no native tasks found.

## 4. Facilitator plan + checkpoint re-analysis

`process-plan.json` is the source of truth (v6+ — replaces the old signal-analysis block). Read from `${project_dir}/process-plan.json`:

- **factors** — 9 entries `{reading: LOW|MEDIUM|HIGH, risk_level: low_risk|medium_risk|high_risk, why}`. `reading` is internal-canonical (HIGH=safest, #627); `risk_level` is user-facing — never drop.
- **specialists** — facilitator's picks `{name, why}`.
- **phases[]** — ordered, each `{name, why, primary: [specialist names]}`.
- **rigor_tier** — `minimal | standard | full`.
- **complexity** — 0-7.

If missing (legacy projects), invoke `wicked-garden:propose-process` in `propose` mode and persist before continuing.

### 4.5 Signal re-analysis at checkpoints

**Run after every phase whose `phases.json::{phase}.checkpoint == true`** (clarify, design, build).

1. Read deliverables under `phases/{phase}/`.
2. Re-invoke the facilitator in `re-evaluate` mode:
   ```
   Skill('wicked-garden:propose-process', args={
     "description": "<original + summary of new deliverables>",
     "mode": "re-evaluate",
     "project_slug": "<slug>",
     "prior_plan_path": "${project_dir}/process-plan.json",
     "output": "json"
   })
   ```
3. **Compare on `reading`** (the internal canonical key). If readings shift OR complexity increased: update project.json `factors` (persist BOTH `reading` AND `risk_level` — never drop `risk_level`, downstream UI depends on it), update `complexity_score` if higher, update `specialists`.
4. **Phase injection**: for each phase in `phases.json` NOT in current `phase_plan` (normalize legacy alias `qe` → `test-strategy` first), inject if its `triggers` match new signals OR its `complexity_range` includes the updated score. Place per `depends_on`. **Max 2 injections per checkpoint**. Skip rejected phases (`rejected_phases` in project.json). User override: `phase_plan_mode: "static"` skips re-analysis entirely.
5. **Memory**: store the diff via `Skill('wicked-brain:memory', ...)` with `type: decision`, fail-open. The plan addendum on disk is the system of record.

## 5. Orchestrator-only principle (CRITICAL)

The main agent is an **orchestrator only** — never inline implementation, analysis, or review. ALL processing dispatches via `Task()` to specialist or fallback subagents. The orchestrator only: reads state, routes, dispatches, tracks task lifecycle (`TaskCreate` → `in_progress` → `completed`), reports.

**Fresh-start dispatch**: each phase executes via a fresh `Task()` so context does not accumulate. Subagent bootstrap order: (1) `phase_manager.py status --json`, (2) `outcome.md`, (3) `phases/{prev}/` deliverables, (4) `TaskList` filtered to project, (5) smaht context (if available).

## 6. Discover + engage specialists

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/specialist_discovery.py --json
```

Filter to specialists whose `enhances` includes the current phase or `*`. Intersect with `process-plan.json::specialists` and `phases[].primary`. Engage matched specialists; fall back to built-in agents only when no specialist available.

**Built-in fallback agents per phase**: clarify → `crew:facilitator`, design → `crew:researcher`, test-strategy → `crew:gate-adjudicator`, build → `crew:implementer`, test → `crew:reviewer`, review → `crew:reviewer`.

**Dispatch wrapper** (every specialist engagement):
```
TaskCreate(subject="{Phase}: {project} - {specialist} {work}", description="...", activeForm="Running {specialist}",
           metadata={"initiative": "{project}", "priority": "P1", "assigned_to": "{specialist}"})
TaskUpdate(taskId="{id}", status="in_progress")
Task(subagent_type="wicked-garden:{specialist}:{agent}", prompt="<smaht context package> + <phase prompt>")
TaskUpdate(taskId="{id}", status="completed", description="{original}\n\n## Outcome\n<summary>")
```

**`*`-enhances semantics**: a specialist with `enhances: ["*"]` is consulted only when signals recommend it OR the phase explicitly needs the role. Do not engage every `*` specialist in every phase.

### Clarify phase: deliberation

For every issue in scope, run `Skill('wicked-garden:deliberate', args="<issue>")` before producing `objective.md` / `acceptance-criteria.md` / `complexity.md`. If the deliberator returns **Close** or **Defer**, surface to the user even in just-finish mode. Store briefs at `phases/clarify/deliberations/{issue-id}.md`.

### Build phase: TDD enforcement (Issue #255)

For tasks with complexity ≥ 3 — three-step dispatch (red → green → refactor):
1. Red: `Task(crew:implementer, "Write failing tests for <task>...")`
2. Green: `Task(crew:implementer, "Implement to pass tests...")`
3. Refactor: `Task(crew:reviewer, "Verify refactor without breaking tests...")`

Complexity < 3: include TDD guidance inline in implementer prompt.

### Build phase: parallel via worktrees (Issue #252)

Capability check via `scripts/crew/worktree_manager.py check-capability` — if not capable (dirty repo, detached HEAD), fall back to sequential. Otherwise:
1. `build_dependency_analyzer.py --stdin --max-parallelism 3` for batches.
2. For each `parallel: true` batch with ≥ 2 tasks: create one worktree per task via `worktree_manager.py create-worktree`, dispatch implementers in parallel (one `Task()` per task in the same message), each prompt prefixed with the worktree path and instruction to NOT touch the main worktree.
3. **Merge SEQUENTIALLY** (concurrent merges corrupt the repo). On any conflict: STOP, do NOT auto-resolve, escalate to user.
4. Cleanup: `worktree_manager.py cleanup-worktree --path "{worktree}"`.

### Build phase: change-type detection + test tasks (Issue QE-001)

Required at complexity ≥ 2; suggested otherwise. Per implementation task:
1. Apply `skills/crew/change-type-detector` rules → `{change_type: ui|api|both|unknown, ui_files, api_files, ambiguous_files}`.
2. Persist to `phases/build/change-type.json` keyed by impl-task-id (read-merge-write — multiple tasks share this file).
3. If not `unknown`: apply `skills/crew/test-task-factory` to generate test tasks; create each via `TaskCreate`; wire dependency `TaskUpdate(impl-task-id, addBlockedBy=[test-task-id])`.

Implementation tasks complete at end of build phase. Test tasks render impl as blocked until QE finishes — that is intentional UX, not a completion gate.

### Build phase: traceability

After all build tasks: `traceability_generator.py --phases-dir phases/ --project "{project}" --output phases/build/traceability-matrix.md`.

### Test phase: product-level testing first (Issue #291, never optional)

**The test phase is never skipped. Visual verification is not a substitute. UI changes test every feature; API changes hit every endpoint.**

Step 1 — detect infra: `playwright.config.*`, `cypress.config.*`, live `localhost:*/health`, `scenarios/*.md`. Persist findings to `phases/test/test-infra.json`.

Step 2 — load `phases/build/change-type.json` for aggregate change_type + test_task_ids. Missing or all-`unknown` → fall back to generic dispatch.

Step 3 — dispatch in product-first order:
- **Group P (first)**: Layer 5 (E2E/scenario — Playwright/Cypress, live curl, or `wicked-testing:execution`; at least one MUST execute), Layer 3 (visual — UI screenshots + a11y).
- **Group I (parallel after P)**: Layer 2 (integration/contract), Layer 4 (security boundary).
- **Group R (last, regression baseline)**: Layer 1 (existing unit suite — do NOT write new unit tests here), Layer 6 (full regression).

Layer dispatch rules and pyramid live in `.claude-plugin/gate-policy.json`. Every test task MUST produce artifacts under `phases/test/evidence/`.

Step 4 — aggregate to `phases/test/test-matrix.md`. All applicable layers PASS for gate clearance; `N-A` requires justification.

Step 5 — compile `phases/test/evidence/report.md` with: summary, product-level evidence (E2E results, screenshots, execution trace), spec comparison table (each AC → method → result → artifact), integration evidence, regression evidence, artifacts index.

### Review phase: evidence-package evaluation (Issue #292)

Load `phases/test/evidence/report.md`. Score on three 0-2 dimensions: visual proof, execution trace, spec comparison. **5-6**: full evidence; **3-4**: partial (note gaps in `phases/review/review-findings.md`); **0-2**: insufficient — CONDITIONAL gate minimum, recommend re-run.

Include the evidence package in every reviewer prompt. Reviewers evaluate visual match, execution-trace coverage of every AC, and spec gaps. Record evidence quality + gaps in `review-findings.md`.

### Phase deliverables

Read `phases.json::{phase}.required_deliverables` and `optional_deliverables`. After deliverables exist, mark `awaiting_approval`.

## 7. Phase completion validation

Before sign-off:

1. **Task count** — `TaskList` filtered case-insensitive `^{phase}[\s:-].*{project-name}`. Each phase has min/max in `phases.json` (defaults: clarify 1-3, design 2-5, test-strategy 1-3, build 3-10, test 1-3, review 1-3). **Min is enforced (blocks)**, **max is advisory (warns)**. Override: `task_lifecycle.user_overrides.skip_min_task_validation: true`.
2. **State** — all phase tasks must be `completed`, `blocked`, or have explicit skip reason. `in_progress` / `pending` block completion (override: `allow_partial_completion: true`).
3. **Atomic transition** — read status, validate no incomplete tasks, validate min-task count, then write `awaiting_approval`. File-lock the status.md write.

## 7.5 Mandatory quality gate

**Run after deliverables, before sign-off.** Read `phases.json::{phase}.gate_required` and `gate_type` (`value` after clarify, `strategy` after design/test-strategy, `execution` after build/test/review).

Fast-pass — `complexity_score ≤ 1` AND no security/compliance signals AND phase ≠ review: use generic `crew:reviewer`; still record `gate: {type: fast-pass, result: approved}` in `phases/{phase}/status.md`.

Otherwise: `/wicked-garden:crew:gate phases/{phase}/ --gate {gate_type}`, wrapped with `TaskCreate` → `in_progress` → `completed` lifecycle.

**Outcome handling**:
- **APPROVE** → sign-off.
- **CONDITIONAL** → AC-4.4 auto-resolution (below).
- **REJECT** → STOP, report findings, re-execute phase.

### AC-4.4 CONDITIONAL auto-resolution

Classify each condition by **"Does resolving this change what we're building or how we measure success?"** — no → auto-resolve; yes or uncertain → escalate.

- **Auto-resolvable** (interactive mode): fix inline, document in `phases/{phase}/conditions-manifest.json` with `auto_resolved: true` + resolution, re-run gate.
- **Escalate** (interactive mode): surface to user with options (resolve as proposed / keep current spec / defer).
- **Escalate** (just-finish mode): `Skill('wicked-garden:jam:council', args="Gate condition requires intent decision: <condition>. Options: A) ... B) ... C) Defer")`.

Log conditions + resolutions in status.md before sign-off. Override: `task_lifecycle.user_overrides.skip_gates: true` skips with warning.

## 8. Phase sign-off via Gate Reviewer Policy

Reviewer is determined by `.claude-plugin/gate-policy.json` — gate type × complexity. Quick map:

| Gate type | Complexity 0-2 | 3-4 | 5-7 |
|---|---|---|---|
| generic (ideate) | Fast-pass | Single specialist | Single specialist |
| value (clarify) | `qe-orchestrator` | + value-orchestrator | + council |
| strategy (design, test-strategy) | Single specialist | + senior-engineer | Council |
| execution (build, test, review) | `crew:reviewer` | Signal-matched specialist | Council + human |

**Escalation overrides** (force council even at low complexity): security/compliance signals, CONDITIONAL verdict, prior REJECT. **Review phase is never fast-passed.** **Human sign-off required at complexity ≥ 6 execution gates.**

**Fallback chain** when policy reviewer unavailable: (1) Council via `Skill('wicked-garden:jam:council', ...)`, (2) third-party CLI (codex/gemini/opencode), (3) signal-matched specialist via `Task()`, (4) `crew:reviewer` generic, (5) human.

**Reviewer separation**: reviewer `subagent_type` MUST differ from phase implementer's. Include `implementer_type: <type>` in every gate dispatch prompt with: "If your subagent_type matches `{implementer_type}`, REJECT with reason `reviewer_separation_violation`." If no different specialist available, escalate to council.

**Approve via phase_manager** (verify gate first, no auto-skip):
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} approve --phase {phase}
```
If approve fails on missing deliverables, STOP — autonomous overrides are not permitted.

## 9. Learning capture (AC-4.6)

At every CONDITIONAL/REJECT gate: store one `procedural` memory describing what went wrong. At review-phase approval: store any new user preferences (`preference`), patterns that worked (`procedural`, importance medium), anti-patterns discovered (`procedural`, importance high). All via `Skill('wicked-brain:memory', ...)` — generalisable lessons, not project-specific.

## 10. Phase status + report

Write `phases/{phase}/status.md`:
```yaml
status: awaiting_approval
tasks_created: N
tasks_completed: N
tasks_blocked: N
tasks_recovered: N
gate: {type: <type>, result: approved|conditional|rejected, findings: "..."}
signoff: {reviewer: <who>, result: <result>, findings: "...", date: <ISO>}
```

`phase_manager.py complete|skip` auto-creates a minimal status.md if absent — write a meaningful one anyway.

Final report: phase + task lifecycle counts, completed deliverables, sign-off outcome, validation status (min met / all resolved / approved), next steps (usually `/wicked-garden:crew:approve {phase}`).

## Reference

**Status vocabulary**: `pending`, `in_progress`, `completed`. Stale = `in_progress` + no updates > 30 min (configurable via `task_lifecycle.staleness_threshold_minutes`).

**should_skip_phase priority** (skippable phases only — `is_skippable: false` in `phases.json` blocks all skips):
1. `task_lifecycle.user_overrides.skip_phase: true` (highest)
2. Phase absent from `phase_plan`
3. Signals require execution; missing specialist may suggest skip
4. `complexity_range` mismatch

When skipping: `phase_manager.py skip --phase {phase} --reason "{reason}" --approved-by "{who}"`.

**Legacy alias**: `qe` → `test-strategy`. Normalize before injection/skip checks to prevent duplicates. Test phases default-on for complexity ≥ 2; only skip with explicit user override (test-strategy phase has `is_skippable: false` regardless).
