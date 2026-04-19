---
description: Execute current phase work with adaptive role engagement
---

# /wicked-garden:crew:execute

Execute work for the current phase with adaptive role selection.

## When to use this vs the others

| Command | What it does |
|---------|-------------|
| `crew:execute` | Run a **single phase** to completion |
| `crew:just-finish` | Run **ALL remaining phases** to completion |
| `crew:auto-approve` | Toggle the APPROVE-auto-advance flag (**no execution**) |

## Instructions

### 0. Poll Bus Events (poll-on-invoke)

Check for pending bus events before starting work. This enables side-effect consumers
(e.g., auto-creating rework tasks from gate REJECT events). Silently skips if bus is unavailable.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from _bus_consumers import process_pending_events
actions = process_pending_events()
for a in actions: print(f'[bus] {a}')
" 2>/dev/null || true
```

If any actions are reported, briefly mention them to the user before proceeding.

### 0.5 Flush Pending Brain-Store Sentinel (issue #433)

If the current project directory contains `.pending-brain-store.json` (written by
`crew:start` Step 10 when wicked-brain was unreachable), attempt to flush it now:

1. Read and parse the sentinel JSON.
2. Invoke `Skill(skill="wicked-brain:memory", args={"action": "store", ...})` with
   the queued fields.
3. On success: delete the sentinel, mention to the user
   `[brain] Flushed queued crew:start decision for {slug}`.
4. On failure: update `attempts` on the sentinel and leave it in place. Mention
   `[brain] Sentinel flush attempt {N} failed — will retry next run`. Do NOT block
   execute.

Silently skip if the sentinel is absent. Fail-open on parse errors.

### 0.6 Phase-Start Gate (AC-11)

**REQUIRED: Run after the bus-events poll (0) and brain-store flush (0.5), before loading project state.**

Before engaging ANY specialist for a new phase, invoke the phase-start heuristic gate to check whether material changes occurred since the last full re-evaluation:

```bash
# phase_start_gate.check() is called inline by prompt_submit.py when
# task_completed.py sets phase_start_gate_due=True on phase-transition events.
# The gate is also available for direct invocation within execute.md:
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from phase_start_gate import check

# Populate from session state / current_chain snapshot
state = {
    'last_reeval_ts': '{last_reeval_ts_from_session}',
    'last_reeval_task_count': {completed_count_at_last_reeval}
}
# chain_snapshot from current_chain.py (fail-open if unavailable)
chain_snapshot = json.loads(open('/tmp/chain-snapshot.json').read()) if __import__('pathlib').Path('/tmp/chain-snapshot.json').exists() else {}

result = check(state, chain_snapshot)
print(json.dumps(result))
"
```

**On a non-empty `systemMessage` response**: emit the directive verbatim before proceeding. The directive instructs Claude to invoke `wicked-garden:propose-process` in `re-evaluate` mode with the `current_chain` data before engaging specialists. **Do not proceed to Step 1 until re-eval completes** (or the user explicitly bypasses with `--skip-reeval --reason`).

**Fail-open**: if `phase_start_gate.check()` returns `{"ok": true}` with no `systemMessage`, proceed normally. If the script is unavailable or errors, proceed with a stderr warning.

### 1. Load Project State

Load current project state via phase_manager:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
```

This returns current phase, phase_plan, signals, complexity, and phase statuses via DomainStore.

### 1.5 Recall Prior Learnings (AC-4.6)

Before starting any phase work, recall relevant crew learnings:

```
/wicked-garden:mem:recall "crew learnings and user preferences" --limit 10
```

Apply recalled learnings to current work. For example:
- If a learning says "avoid grep-based testing", ensure test phase uses real runners
- If a user preference says "prefers bundled PRs", adjust commit strategy
- If an anti-pattern says "don't skip design for complexity > 3", enforce it

### 2. Task Lifecycle Recovery

**CRITICAL: Run at phase start before any work begins.**

#### 2.1 Detect Stale Tasks

Check for tasks stuck in `in_progress` state using Claude's native task tools:

Call `TaskList` to get all current tasks. Filter by project name in subject (match `{project-name}` from project.md). For each matching task with status `in_progress`:
- Calculate age from when it was last updated
- If age > 30 minutes: mark as **stale**
- Check task_lifecycle.user_overrides for custom thresholds

#### 2.2 Recover Orphaned Tasks

Orphaned tasks = tasks without recent activity that are blocking phase completion.

**Recovery Strategy:**
1. Check project.json for `task_lifecycle.recovery_mode`:
   - `"auto"`: Automatically move stale tasks to `pending` and log warning
   - `"manual"`: Report stale tasks and ask user for action
   - `"ignore"`: Skip recovery (not recommended)

2. For each stale task:
   - Log activity: `task_recovered` with reason
   - If recovery_mode = "auto":
     Call `TaskUpdate` with `status: "pending"` to move the stale task back to pending
   - If recovery_mode = "manual": prompt user with task details

3. Report recovered tasks:
   ```markdown
   ### Recovered Stale Tasks
   - [TASK-123] Task name - stuck for 45 min → moved to pending
   - [TASK-456] Another task - stuck for 2 hrs → moved to pending
   ```

#### 2.3 Fallback

If no tasks found via TaskList, check for manual TODO tracking in phase status files and recover accordingly.

### 2.5 Gather Context via wicked-smaht (if available)

Before starting phase work, assemble structured context from the ecosystem. This ensures specialists and fallback agents receive rich context — not just raw deliverable text.

```
Skill(skill="wicked-garden:smaht:context", args="build --task \"Execute {current_phase} phase for {project-name}\" --project \"{project-name}\" --dispatch --prompt")
```

If the command fails, proceed with project.json signals and deliverable text only.

Include the context package output in ALL subagent Task() dispatches. If wicked-smaht is not available, proceed with project.json signals and deliverable text only.

### 2.6 Orchestrator-Only Principle

**CRITICAL: The main agent is an ORCHESTRATOR only.** It must NOT perform complex analysis, implementation, or review work inline. Instead:

- **ALL processing** goes through subagent `Task()` dispatches to specialists or fallback agents
- The main agent ONLY: reads project state, makes routing decisions, dispatches subagents, tracks task lifecycle, and reports progress
- Manage context through tools (TaskList, TaskGet, Read) — do NOT accumulate large working state in the main conversation
- When in doubt, delegate to a subagent rather than doing work inline

This principle applies to EVERY phase. Even "simple" tasks should be dispatched to a subagent so the main agent stays lean and can always access the latest state via tools.

### 2.7 Fresh-Start Phase Dispatch

**CRITICAL: Each phase MUST execute via a fresh `Task()` dispatch (subagent) so context does not accumulate across phases.** The main orchestrator loop stays lean and never carries forward phase-specific working state.

The orchestrator loop for each phase:

1. **Load project state** via phase_manager:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
   ```

2. **Dispatch the phase** as a fresh subagent via `Task()`. The subagent bootstraps its own context from persistent state rather than inheriting the orchestrator's conversation history. Include bootstrap instructions in the Task prompt so the subagent knows how to self-orient.

3. **After the Task() returns**, the orchestrator verifies completion (deliverables exist, task counts met), runs checkpoint analysis if the phase has `checkpoint: true`, and approves the phase.

**Context bootstrap order** (for the subagent to follow inside the Task):

1. **Project metadata** — phase_manager status --json (current phase, signals, complexity, phase plan)
2. **Outcome** — outcome.md (desired outcome, success criteria)
3. **Prior phase deliverables** — read deliverables from the immediately preceding phase(s) in `phases/{prev-phase}/`
4. **Task evidence** — TaskList filtered to project name for in-progress and completed tasks
5. **Smaht context** — if available, `Skill(skill="wicked-garden:smaht:context", args="build --task \"...\" --project \"...\" --dispatch --prompt")` for ecosystem-wide context

**Why fresh dispatch matters:**

- Prevents context window bloat — each subagent starts with only the state it needs
- Enables parallel phase execution for independent phases
- Makes phase retries clean — a failed phase can be re-dispatched without leftover state
- The orchestrator remains stateless and can always reconstruct progress from phase_manager + TaskList

### 3. Load User Preferences (if exists)

Resolve preferences path: `CREW_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-crew)`
Check for `${CREW_ROOT}/preferences.yaml` or project-level preferences for:
- Autonomy level (ask-first, balanced, just-finish)
- Communication style

### 4. Archetype Pre-Analysis — REMOVED IN V6

The old "dynamic archetype pre-analysis" phase (discover project context → classify archetypes → cache `archetype_hints` on `project.json`) has been **removed** in v6. Its job is now owned by `wicked-garden:propose-process` (run during `/wicked-garden:crew:start`), which folds project-type readings into its 9 factor scores and specialist picks. No standalone archetype step runs here — skip straight to 4.4 to load the facilitator's plan. Checkpoint re-evaluation (Section 4.5) re-invokes the facilitator in `re-evaluate` mode when phase artifacts change the picture.

### 4.4 Load Facilitator Plan

Locate the active project and read the facilitator's plan (v6 — replaces the old signal-analysis block that lived on `project.json`):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

This returns `{project, project_dir}`. Read `${project_dir}/process-plan.json` for the canonical plan written by `wicked-garden:propose-process`. Pull the following fields (schema: `skills/propose-process/refs/output-schema.md`):

- **factors** — 9 factor readings (reversibility, blast_radius, compliance_scope, user_facing_impact, novelty, scope_effort, state_complexity, operational_risk, coordination_cost), each `{reading: LOW|MEDIUM|HIGH, why: "..."}`. These replace `signals_detected`.
- **specialists** — list of `{name, why}` the facilitator picked. Replaces `specialists_recommended`.
- **phases** — ordered list of `{name, why, primary: [specialist names]}`. Replaces the old `phase_plan`.
- **rigor_tier** — `minimal | standard | full` (gate enforcement level).
- **complexity** — integer 0-7 (drives autonomy and gate thresholds).

If `process-plan.json` is missing (legacy project), invoke `wicked-garden:propose-process` in `propose` mode now and persist the plan before continuing.

### 4.5 Signal Re-Analysis at Checkpoints

**CRITICAL: Run after every checkpoint phase completes.**

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` and check if the current phase has `"checkpoint": true`. Checkpoint phases are: **clarify**, **design**, **build**.

When a checkpoint phase completes:

1. **Gather phase artifacts**: Read all files in `phases/{phase}/` and any deliverables produced
2. **Re-invoke the facilitator** in `re-evaluate` mode with the combined project
   description + phase artifacts:
   ```
   Skill(
     skill="wicked-garden:propose-process",
     args={
       "description": "{original description + combined text summary of deliverables}",
       "mode": "re-evaluate",
       "project_slug": "{slug}",
       "prior_plan_path": "${project_dir}/process-plan.json",
       "output": "json"
     }
   )
   ```
   The skill reads the prior plan + new context and emits a diff plan (new factor
   readings, any phase additions/demotions, any rigor_tier change). See
   `skills/propose-process/SKILL.md#Re-evaluation mode`.
3. **Compare factors AND complexity**: Diff new `factors` against project.json
   `factors`, AND compare new `complexity` against `complexity_score`
4. **If factor readings shift OR complexity increased**:
   - Update project.json `factors` with new readings
   - Update `complexity_score` if new score is higher
   - Update `specialists` with any new recommendations
   - **Check for phase injection** (see below)

#### Dynamic Phase Injection

When new signals are detected OR complexity increases at a checkpoint, check if any phases NOT in the current `phase_plan` should be injected:

1. Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` for all phases
2. **Normalize legacy aliases**: `qe` in `phase_plan` = `test-strategy`. Before checking, normalize all plan entries to canonical names to prevent duplicate injection.
3. For each phase NOT currently in `phase_plan` (after normalization):
   - Check if any new signal matches the phase's `triggers` (or triggers is `["*"]` and complexity is in range)
   - Check if updated `complexity_score` falls within phase's `complexity_range`
   - If EITHER condition met → **candidate for injection**
4. Injection placement rules:
   - Determine correct position based on `depends_on` — the injected phase must come AFTER all its dependencies
   - If a dependency is a future phase (not yet completed), insert the new phase AFTER that dependency in the plan
   - If all dependencies are already completed, insert AFTER the current checkpoint phase
   - Never insert a phase BEFORE a phase that's already completed or in progress
   - Never inject a phase that was explicitly skipped by the user (check `rejected_phases` in project.json)
   - Maximum 2 injections per checkpoint to prevent runaway replanning
5. Report injection to user:
   ```markdown
   ### Phase Plan Updated

   {New signals / complexity change} detected after {phase}

   **Injected phases:**
   - {phase_name}: Triggered by {signal} signal (complexity {score} in range {range})

   **Updated plan**: {old_plan} → {new_plan}
   ```

6. Update project.json `phase_plan` with the new plan (using canonical names only)

**User override**: If project.json contains `"phase_plan_mode": "static"`, skip re-analysis and injection entirely.

#### Re-Evaluation Memory Storage

The facilitator's `re-evaluate` mode writes an addendum to `${project_dir}/process-plan.md`
(the durable artifact) AND stores a wicked-brain memory describing the plan diff:

```
Skill(
  skill="wicked-brain:memory",
  args={"action": "store", "type": "decision",
        "title": "crew:execute checkpoint re-eval for {slug}",
        "content": "<summary of factor deltas + any phase injections + rigor change>",
        "tags": ["crew", "facilitator", "re-evaluate", "{slug}"],
        "importance": 5}
)
```

Fail-open: if the brain is unavailable, skip silently. The plan addendum is the
system of record. The same pattern applies to `feedback.py record --json`, which
still returns a `memory_payload` field that this command stores via
`/wicked-garden:mem:store`.

**Rationale**: Scripts run as subprocesses and should never call other plugins
directly. Claude's tool system (skills, Task tool) IS the universal API for
cross-plugin communication.

### 5. Discover Available Specialists

Run specialist discovery to find installed specialist plugins:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/specialist_discovery.py --json
```

This returns all available specialists with their `enhances` declarations (which phases they support).

**Dynamic Routing**: Do NOT use hardcoded specialist-to-phase mappings. Instead:
1. Read `specialists` and per-phase `phases[].primary` from `${project_dir}/process-plan.json` (the facilitator's plan)
2. Filter discovered specialists to those whose `enhances` list includes the current phase or `"*"`
3. Intersect with the facilitator's picks — engage the specialists the plan named for this phase, falling back to any `enhances`-compatible specialist if a pick is unavailable
4. Engage all matching, available specialists for the current phase

### 6. Engage Specialists for Phase

**CRITICAL: Wrap every specialist dispatch with task lifecycle tracking.**

For each specialist engagement:
1. Create a task: `TaskCreate(subject="{Phase}: {project-name} - {specialist-name} {work type}", description="Engaging {specialist} for {phase} phase work. Signals: {relevant signals}.", activeForm="Running {specialist} for {phase}", metadata={"initiative": "{project-name}", "priority": "P1", "assigned_to": "{specialist-name}"})`
2. Mark in_progress: `TaskUpdate(taskId="{id}", status="in_progress")`
3. Dispatch to specialist (skill invocation or subagent)
4. Mark completed: `TaskUpdate(taskId="{id}", status="completed", description="{original}\n\n## Outcome\n{summary of specialist findings/output}")`

**Initiative metadata**: Always include `"initiative": "{project-name}"` in task metadata. This groups the task under the crew project's initiative (see start.md Section 8.5). Tasks without initiative metadata default to the repo's generic "Issues" initiative.

#### Specialist-to-Phase Mapping (Reference)

This table mirrors specialist.json `enhances` declarations. Always use the discovery script output as the source of truth — this table is a quick reference only.

| Specialist | Role | Enhances |
|-----------|------|----------|
| jam | ideation | clarify, design |
| product | product | clarify, design, review |
| engineering | engineering | design, build, review |
| qe | quality-engineering | test-strategy, build, test, review, * |
| platform | devsecops | build, review, * |
| data | data-engineering | design, build, * |
| agentic | agentic-architecture | design, build, review |
| delivery | project-management | *, review |

**`*` semantics**: Means "available for consultation in any phase if signals recommend it." A specialist with `*` is only actively engaged when signal analysis recommends it OR the phase explicitly needs that role. Do NOT engage every `*` specialist in every phase.

**Build phase note**: Build-phase specialists (engineering, data, agentic) provide architectural guidance and review during build, but the **implementer agent** does the actual implementation work. Engage build-phase specialists when signals indicate their domain (e.g., agentic signals → agentic for pattern guidance).

#### Specialist Dispatch

When engaging a specialist, use Task dispatch for heavy analysis work. Keep slash commands only for interactive or thin CLI operations. `-` means no direct dispatch for that phase.

**Structured context packages**: Instead of dumping prose context into subagent prompts, use the smaht context command:

```
Skill(skill="wicked-garden:smaht:context", args="build --task \"{task description}\" --project \"{project-name}\" --dispatch --prompt")
```

The context package outputs a structured prompt section with: task, decisions, constraints, file scope, relevant code, memories, and project state. Include this in the subagent prompt instead of raw deliverable text.

For each specialist engagement, the dispatch pattern is:

```
TaskCreate(subject="{Phase}: {project-name} - {specialist} analysis", ...)
TaskUpdate(taskId="{id}", status="in_progress")
Task(
  subagent_type="wicked-garden:{specialist}:{agent}",
  prompt="""
  {Phase-appropriate analysis prompt}.
  Project: {project-name}

  {Output from context_package.py --task "{task}" --project "{project-name}" --prompt}

  Signals: {relevant signals from project.json}
  """
)
TaskUpdate(taskId="{id}", status="completed")
```

| Specialist | Clarify | Design | Build | Review |
|-----------|---------|--------|-------|--------|
| jam | `/wicked-garden:jam:brainstorm` (interactive) | `/wicked-garden:jam:perspectives` (interactive) | - | - |
| product | `Task(subagent_type="wicked-garden:product:requirements-analyst", ...)` | `Task(subagent_type="wicked-garden:product:market-strategist", ...)` | - | `Task(subagent_type="wicked-garden:product:ux-designer", ...)` |
| engineering | - | `Task(subagent_type="wicked-garden:engineering:solution-architect", ...)` | `Task(subagent_type="wicked-garden:engineering:senior-engineer", ...)` | `Task(subagent_type="wicked-garden:engineering:senior-engineer", ...)` |
| qe | - | - | `/wicked-garden:crew:gate` (quality gate) | `/wicked-garden:crew:gate` (quality gate) |
| platform | - | - | `Task(subagent_type="wicked-garden:platform:security-engineer", ...)` | `Task(subagent_type="wicked-garden:platform:security-engineer", ...)` |
| data | - | `Task(subagent_type="wicked-garden:data:data-analyst", ...)` | `Task(subagent_type="wicked-garden:data:data-engineer", ...)` | - |
| agentic | - | `Task(subagent_type="wicked-garden:agentic:architect", ...)` | `Task(subagent_type="wicked-garden:agentic:pattern-advisor", ...)` | `Task(subagent_type="wicked-garden:agentic:safety-reviewer", ...)` |
| delivery | `/wicked-garden:delivery:report` (thin CLI) | - | `/wicked-garden:delivery:report` (thin CLI) | `/wicked-garden:delivery:report` (thin CLI) |

**What stays as slash commands**:
- `jam`: Brainstorm/perspectives are interactive and need user back-and-forth
- `wicked-garden:delivery:report`: Thin CLI wrapper, no heavy analysis
- `wicked-garden:crew:gate`: Already uses correct Task dispatch internally (gate.md is gold standard)

#### Step 0: Issue Deliberation Analysis (Clarify Phase)

REQUIRED for clarify phase when the project involves issues, bugs, or feature requests.
Run before engaging specialists or producing deliverables.

For each issue in scope:
```
Skill(skill="wicked-garden:deliberate", args="{issue description or GH# for each issue}")
```

If processing multiple issues, run in batch mode or dispatch parallel deliberate calls.
Store each deliberation brief in `{project_dir}/phases/clarify/deliberations/{issue-id}.md`.

Deliberation briefs inform the clarify deliverables:
- `objective.md` should reflect any scope changes recommended by the deliberator
- `acceptance-criteria.md` should incorporate tech debt opportunities identified
- `complexity.md` should account for any redesign work the deliberator recommends

If the deliberator recommends **Close** or **Defer** for any issue, surface it to the user before proceeding — even in just-finish mode. Removing scope is a decision that deserves visibility.

#### Design Phase: Conditional Deliberate

If new issues surface during design (scope expansion, tech debt found, new bugs uncovered):
```
Skill(skill="wicked-garden:deliberate", args="{new issue description}")
```
Run deliberate on any new items before including them in the architecture document.

#### Phase Execution Pattern

For each phase, follow this pattern:

1. **Determine eligible specialists**: Filter by `enhances` containing current phase or `"*"`
2. **Prioritize by signals**: Engage signal-recommended specialists first
3. **Engage each specialist** with task wrapping (TaskCreate → in_progress → dispatch → completed)
4. **Fall back to built-in agent** if no specialists available for the phase

**Built-in fallback agents by phase:**

| Phase | Fallback Agent | Prompt Pattern |
|-------|---------------|----------------|
| clarify | `wicked-garden:crew:facilitator` | "Guide outcome clarification for: {description}" |
| design | `wicked-garden:crew:researcher` | "Research existing patterns and design approaches for: {outcome}" |
| test-strategy | `wicked-garden:qe:test-strategist` | "Generate test strategy from outcome criteria: {outcome summary}. Project: {project-name}." |
| build | `wicked-garden:crew:implementer` | "Implement according to design: {design summary}" |
| test | `wicked-garden:crew:reviewer` | "Execute product-level tests (E2E first, then integration, then regression). Verify against test strategy: {test-strategy summary}. Compile evidence package to phases/test/evidence/report.md." |
| review | `wicked-garden:crew:reviewer` | "Review implementation against outcome: {outcome summary}. MUST evaluate evidence package at phases/test/evidence/report.md — check screenshots, execution traces, and spec comparison. Missing evidence = gate failure." |

#### Test Phase: Product-Level Testing First (Issues QE-001, #291)

**Run at the start of the test phase, before dispatching any QE agents.**

**THE TEST PHASE IS NEVER OPTIONAL.** Do not skip it. Do not suggest the user test manually. Do not claim "visual verification" replaces automated testing. If the change touches UI, test every feature and check for JS errors. If the change touches APIs, test every endpoint directly. The test phase exists to catch bugs — skipping it means shipping bugs.

**CRITICAL: The test phase tests like a product owner, not a unit test runner.** The primary goal is verifying the product works end-to-end from a user's perspective. Unit test suites run as regression baseline only — they are NOT the primary verification.

**Testing priority order** (highest to lowest):

1. **E2E / Product-level tests** — Playwright, Cypress, or browser-based tests that verify real user flows
2. **Live endpoint verification** — curl/fetch against running services to verify API contracts
3. **Scenario validation** — `/wicked-garden:qe:run` or `/wicked-garden:qe:acceptance` for structured E2E
4. **Integration tests** — contract/schema validation between services
5. **Unit test suite** — run existing suite as regression baseline (do NOT write new unit tests in this phase)

Layer definitions, agent routing, parallel dispatch rules, and evidence collection details are defined in the canonical source: **`skills/qe/qe-strategy/refs/test-type-taxonomy.md` → "Testing Pyramid Execution Layers"**.

**Step 1: Detect available E2E infrastructure.**

Before loading change-type data, detect what product-level testing tools are available:

```bash
# Check for project-level test config
ls playwright.config.* 2>/dev/null || ls e2e/ 2>/dev/null
ls cypress.config.* 2>/dev/null || ls cypress/ 2>/dev/null

# Check for running services (live endpoint testing)
curl -sf http://localhost:3000/health 2>/dev/null || curl -sf http://localhost:8080/health 2>/dev/null

# Check for wicked-scenarios
ls scenarios/*.md 2>/dev/null
```

Record findings in `phases/test/test-infra.json`:
```json
{
  "playwright": true|false,
  "cypress": true|false,
  "live_endpoints": ["http://localhost:3000"],
  "scenarios_available": true|false,
  "detected_at": "ISO 8601"
}
```

**Before claiming you can't test something:** review your available skills and tools. The plugin provides capabilities for browser automation, visual testing, accessibility auditing, API testing, and more — even when the project has no test config of its own.

**Step 2: Load change-type data.**

Read `phases/build/change-type.json` to retrieve:
- `tasks`: map of impl-task-id → `{change_type, test_task_ids, ...}`
- Aggregate `change_type` across all tasks: if any task has "both", aggregate is "both"; if mix of "ui" and "api", aggregate is "both"; otherwise take the single type.
- Collect all `test_task_ids` across all tasks.

If `phases/build/change-type.json` does not exist OR all tasks have `change_type: "unknown"`:
- Fall back to generic dispatch (existing behavior).
- Log: "No change-type detection file found — using generic QE dispatch."

**Step 3: Select and dispatch layers (product-first order).**

Use the **Layer → Change Type Mapping** table from the taxonomy to determine which layers are required. Then dispatch in **product-first order**:

**Group P (Product-level — run FIRST):**
- Layer 5 (Scenario/E2E): If Playwright/Cypress detected → run E2E suite. If live endpoints detected → curl/fetch verification. If scenarios available → `/wicked-garden:qe:acceptance`. At least ONE of these must execute.
- Layer 3 (Visual): If UI changes detected → screenshots + a11y checks.

**Group I (Integration — run SECOND, parallel):**
- Layer 2 (Integration/Contract): API contract validation.
- Layer 4 (Security): Auth boundary + input validation.

**Group R (Regression baseline — run LAST):**
- Layer 1 (Unit): Run existing unit test suite. Do NOT generate new unit tests.
- Layer 6 (Regression): Run full existing test suite.

For each required layer:
1. Dispatch a `Task()` to the specified agent with the layer's execution steps as the prompt.
2. Include: project name, change type, test task IDs, changed files, test strategy path, and test-infra.json findings.
3. **Require evidence collection**: Every test task MUST produce artifacts in `phases/test/evidence/` (see Step 5).

Agent fallbacks:
- If `test-automation-engineer` is unavailable → include instructions in generic reviewer prompt.
- If `security-engineer` is unavailable → include security steps in integration test prompt.
- If `test-designer` is unavailable → include scenario steps in generic reviewer prompt.

**Step 4: Aggregate results.**

After all layers complete, write `phases/test/test-matrix.md` using the **Output: Test Requirement Matrix** format from the taxonomy. All applicable types must be PASS for the test phase gate to clear. Mark N-A (with justification) for layers not applicable to the change type.

**Step 5: Compile evidence package.**

After all test layers complete, compile `phases/test/evidence/report.md` for the review phase:

```markdown
# Test Evidence Package

## Summary
- **Project**: {project-name}
- **Test date**: {ISO 8601}
- **Change type**: {ui|api|both|unknown}
- **Layers executed**: {list}
- **Overall verdict**: {PASS|FAIL}

## Product-Level Evidence

### E2E Test Results
{Playwright/Cypress output, or curl verification results, or scenario verdicts}
- Screenshots: {list of screenshot paths in phases/test/evidence/}
- Execution trace: {step-by-step log of what was tested and observed}

### Spec Comparison
| Acceptance Criterion | Test Method | Result | Evidence |
|---|---|---|---|
| {criterion from outcome.md} | {how tested} | PASS/FAIL | {artifact ref} |

## Integration Evidence
{Contract validation results, security scan results}

## Regression Evidence
{Unit test suite output, coverage delta}

## Artifacts Index
| Artifact | Type | Path |
|---|---|---|
| {name} | screenshot/log/payload/report | phases/test/evidence/{file} |
```

All screenshots, execution logs, and test outputs MUST be saved to `phases/test/evidence/`. The review phase depends on this directory for evidence evaluation.

**Dispatch is deterministic**: same `change_type` value always produces the same layer selection and dispatch pattern.

#### Review Phase: Evidence Package Evaluation (Issue #292)

**Run at the start of the review phase, before dispatching any reviewers.**

The review phase MUST evaluate the evidence package produced by the test phase. Pass/fail alone is insufficient — reviewers need visual proof, execution traces, and spec comparison to make informed sign-off decisions.

**Step 1: Load evidence package.**

Check for `phases/test/evidence/report.md`. If it exists, load it. If it does not exist:
- Check if `phases/test/test-matrix.md` exists (test phase ran but no evidence package compiled).
- If neither exists, flag as **evidence gap** — the test phase did not produce adequate evidence.
- Log: "WARNING: No evidence package found. Review proceeds with reduced confidence."

**Step 2: Evaluate evidence quality.**

Score the evidence package on three dimensions:

| Dimension | What to check | Score |
|---|---|---|
| **Visual proof** | Screenshots present for UI changes? Screen recordings for flows? | 0-2 |
| **Execution trace** | Step-by-step log of what was tested? Timestamps? Duration? | 0-2 |
| **Spec comparison** | Each acceptance criterion mapped to test result? | 0-2 |

- Score 5-6: Full evidence — high confidence review
- Score 3-4: Partial evidence — proceed but note gaps in review-findings.md
- Score 0-2: Insufficient evidence — CONDITIONAL gate at minimum, recommend re-running test phase

**Step 3: Include evidence in reviewer prompt.**

When dispatching reviewers (specialist or generic), include the evidence package contents:

```
Task(subagent_type="{reviewer-agent}",
     prompt="Review implementation for {project-name}.

     ## Evidence Package
     {contents of phases/test/evidence/report.md}

     ## Acceptance Criteria
     {from outcome.md / acceptance-criteria.md}

     Evaluate:
     1. Do screenshots/visual evidence match expected behavior?
     2. Does the execution trace show all acceptance criteria were verified?
     3. Are there gaps between spec and test coverage?
     4. Evidence quality score: {score}/6

     Return: APPROVE, CONDITIONAL, or REJECT with evidence-based reasoning.")
```

**Step 4: Record evidence evaluation in review findings.**

Write evidence quality assessment to `phases/review/review-findings.md`:

```markdown
## Evidence Evaluation

**Evidence quality score**: {score}/6
**Visual proof**: {present|partial|missing}
**Execution trace**: {present|partial|missing}
**Spec comparison**: {present|partial|missing}

### Evidence Gaps
{List any missing evidence and impact on review confidence}
```

If using `/wicked-garden:qe:report` for structured evidence, include its output in the evidence evaluation.

#### Build Phase: TDD Enforcement (Issue #255)

**CRITICAL: All build tasks with complexity >= 2 MUST follow the red-green-refactor cycle.**

For each build task, check its complexity (from the task description or the project's complexity_score):

**If task complexity >= 3** — three-step TDD dispatch (full red-green-refactor):

1. **Red phase** (write failing tests first):
   ```
   Task(
     subagent_type="wicked-garden:qe:test-strategist",
     prompt="Write failing tests (red phase) for: {task description}.
     Project: {project-name}. Design: {relevant design excerpt}.
     Output: failing test files that define the acceptance criteria.
     Do NOT implement the feature yet."
   )
   ```
   If `wicked-garden:qe:test-strategist` is unavailable, include TDD red-phase instructions in the implementer prompt instead.

2. **Green phase** (implement to pass tests):
   ```
   Task(
     subagent_type="wicked-garden:crew:implementer",
     prompt="Implement the feature to make failing tests pass (green phase).
     Task: {task description}. Project: {project-name}.
     Failing tests from red phase: {test file paths}.
     Design: {design summary}. Do not refactor yet — just make tests pass."
   )
   ```

3. **Refactor verification** (clean up without breaking tests):
   ```
   Task(
     subagent_type="wicked-garden:qe:test-strategist",
     prompt="Verify and guide the refactor phase for: {task description}.
     Project: {project-name}. Tests should remain passing after refactor.
     Check: code quality, duplication, naming, test coverage completeness."
   )
   ```

**If task complexity < 3** — include TDD guidance in the implementer prompt (lighter touch):
```
Task(
  subagent_type="wicked-garden:crew:implementer",
  prompt="Implement: {task description}. Project: {project-name}.
  TDD guidance: Write a minimal test first to verify your change works,
  then implement. Even for simple changes, a test proves correctness."
)
```

#### Build Phase: Parallel Execution via Git Worktrees (Issue #252)

Before dispatching build tasks, check whether parallel execution is feasible:

**Step 1: Capability check**

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/worktree_manager.py check-capability
```

If capability check returns `not capable` (dirty repo, detached HEAD, git not available), skip to sequential dispatch.

**Step 2: Dependency analysis**

If worktrees are available, analyze task dependencies to determine parallel batches:

```bash
# Pass current task list as JSON (from TaskList output)
echo '{TASK_LIST_JSON}' | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/build_dependency_analyzer.py \
  --stdin --max-parallelism 3
```

This outputs batches: `[{"batch": 1, "tasks": ["id-1","id-2"], "parallel": true}, ...]`

**Step 3: Parallel dispatch with worktrees**

For each batch that has `"parallel": true` AND contains >= 2 tasks:

1. Create a worktree per task:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/worktree_manager.py \
     create-worktree --project "{project-name}" --task-id "{task_id}" --json
   ```

2. Dispatch implementer subagents in parallel (one Task() call per task, all in the same message):
   ```
   Task(
     subagent_type="wicked-garden:crew:implementer",
     prompt="""
     WORKTREE: You are working in an isolated git worktree at {worktree_path}.
     All file reads and writes MUST occur within this path — do NOT touch the
     main repository directory at {repo_root}. Your changes will be merged back
     after this subagent completes. Do not run git commands that operate on the
     main worktree (e.g., git checkout, git reset on the parent). Treat
     {worktree_path} as your repository root for all tool calls.

     Task: {task description}
     Project: {project-name}
     Design: {relevant design excerpt}
     """
   )
   Task(
     subagent_type="wicked-garden:crew:implementer",
     prompt="""
     WORKTREE: You are working in an isolated git worktree at {worktree_path}.
     All file reads and writes MUST occur within this path — do NOT touch the
     main repository directory at {repo_root}. Your changes will be merged back
     after this subagent completes. Do not run git commands that operate on the
     main worktree (e.g., git checkout, git reset on the parent). Treat
     {worktree_path} as your repository root for all tool calls.

     Task: {task description}
     Project: {project-name}
     Design: {relevant design excerpt}
     """
   )
   ```

3. After all parallel subagents complete, merge each worktree back **SEQUENTIALLY** (one at a time, never in parallel — concurrent merges can corrupt the repository):
   ```bash
   # Merge worktrees ONE AT A TIME in dependency order (leaf tasks first)
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/worktree_manager.py \
     merge-worktree --path "{worktree_path}" --json
   ```

**Step 4: Conflict escalation guardrail**

If any merge returns `"success": false` with `"conflicts"`:

- **DO NOT auto-resolve conflicts** — escalate to human review
- Report the conflicted files and task pair
- Ask user to choose: resolve manually, re-sequence the conflicting tasks, or abort
- Clean up the worktree after escalation:
  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/worktree_manager.py \
    cleanup-worktree --path "{worktree_path}"
  ```

**Step 5: Cleanup**

After successful merge, clean up each worktree:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/worktree_manager.py \
  cleanup-worktree --path "{worktree_path}"
```

**Fallback: Sequential dispatch**

When worktrees are unavailable or the batch has `"parallel": false`, dispatch tasks sequentially using the standard implementer Task() pattern without worktrees.

#### Build Phase: Traceability

After all build tasks complete, generate the traceability matrix to link test-strategy criteria to build outcomes:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/traceability_generator.py \
  --phases-dir phases/ \
  --project "{project-name}" \
  --output phases/build/traceability-matrix.md
```

This maps acceptance criteria from `phases/test-strategy/` to completed build tasks. Include `traceability-matrix.md` in the build phase deliverables.

#### Build Phase: Task Creation

In the build phase, create rich tasks for implementation work:

```
TaskCreate(
  subject="{Phase}: {project-name} - {task description}",
  description="WHY this task exists. What problem it solves. Acceptance criteria.",
  activeForm="{Phase-verb}ing {task description}",
  metadata={
    "initiative": "{project-name}",  // groups task under crew project initiative
    "priority": "P1",               // P0-P3, set explicitly
    "assigned_to": "agent-name"      // who owns this
  }
)
```

**Subject uniqueness**: Each task subject MUST be unique within the project. The combination of `{Phase}: {project-name} - {specific description}` ensures this.

**Task enrichment**: Use `addBlockedBy`/`addBlocks` on TaskUpdate to set dependencies. When completing a task, update its description with the outcome.

#### Task Acceptance Criteria (AC-4.5)

Every build task MUST include structured acceptance criteria in its description:

```
TaskCreate(
  subject="Build: {project} - {description}",
  description="""
  {WHY this task exists}

  ## Acceptance Criteria
  - [ ] AC-1: {specific, testable criterion}
  - [ ] AC-2: {specific, testable criterion}

  ## Evidence Required
  For each AC, provide: what was done, what was observed, artifact reference.
  """
)
```

When completing a task, the description MUST be updated with evidence mapping:

```
TaskUpdate(taskId="{id}", status="completed",
  description="{original}\n\n## Evidence\n- AC-1: {evidence}\n- AC-2: {evidence}")
```

**Validation**: Before marking a task completed, verify:
1. Every AC has a corresponding evidence entry
2. Evidence entries reference concrete artifacts (file paths, test output, diffs)
3. Assertions like "it works" or "verified" without specifics are insufficient

**Task Subject Prefix Filtering** (case-insensitive):
- Match pattern: `(?i)^(build|clarify|design|ideate|test-strategy|test|review)[\s:-]`

Tasks created via TaskCreate are validated at PreToolUse against the event envelope contract (see scripts/_event_schema.py) and persist natively under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/`.

#### Build Phase: Change-Type Detection (Issue QE-001)

**REQUIRED for complexity >= 2. Skip with a logged suggestion for complexity < 2.**

Run immediately after each implementation task is created, before test task creation. The detector classifies the files touched by the task into a change type used to create the appropriate test tasks.

**Complexity guard** — check before running:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
```
- If `complexity_score < 2`: log "QE test task creation is suggested but not mandatory for low-complexity projects (complexity {score})" and skip to the next task.
- If `complexity_score >= 2`: change-type detection and test task creation are REQUIRED, not optional. Do not skip even if no QE specialist is engaged.

**Run detection for each implementation task:**

Read the change-type-detector skill for classification rules:
- `skills/crew/change-type-detector/SKILL.md` — routing and algorithm
- `skills/crew/change-type-detector/refs/file-classification-rules.md` — decision tables

Apply the classification rules to the files touched by the task. Produce a JSON result:
```json
{"change_type": "ui|api|both|unknown", "ui_files": [...], "api_files": [...], "ambiguous_files": [...]}
```

If files are not yet known at task creation time, set `change_type: "unknown"`, which suppresses test task creation and logs a warning.

**Persist detection results** by writing `phases/build/change-type.json` (create or update using the Write tool):
```json
{
  "tasks": {
    "{impl-task-id}": {
      "change_type": "ui|api|both|unknown",
      "ui_files": [...],
      "api_files": [...],
      "ambiguous_files": [...],
      "test_task_ids": []
    }
  },
  "detected_at": "{ISO timestamp}"
}
```

Note: The file is keyed by task ID (not a flat file) so multiple tasks in the same build phase do not overwrite each other. When adding a new task's detection result, read the existing file first and merge the new entry into the `tasks` object.

#### Build Phase: Test Task Creation (Issue QE-001)

Run immediately after change-type detection for each implementation task.

**Skip if `change_type` is "unknown"**: Log "No UI or API files detected for task {impl-task-id} — test task creation skipped" and continue.

**Generate test task parameters:**

Read the test-task-factory skill for templates and routing:
- `skills/crew/test-task-factory/SKILL.md` — routing rules and subject construction
- `skills/crew/test-task-factory/refs/test-task-templates.md` — template definitions per change type
- `skills/crew/test-task-factory/refs/test-evidence-taxonomy.md` — evidence requirements

Apply the skill's algorithm using the `change_type` and `impl-subject` to generate test task parameters as a JSON `test_tasks` array.

**For each entry in `test_tasks` array**, execute task creation:
```
TaskCreate(
  subject="{task.subject}",
  description="{task.description}",
  activeForm="Testing {impl task description}",
  metadata=task.metadata  // includes test_type, evidence_required, assigned_to, initiative
)
```

After creating each test task, **wire the dependency** so the implementation task is blocked by the test task:
```
TaskUpdate(taskId="{impl-task-id}", addBlockedBy=["{test-task-id}"])
```

This means the implementation task will appear as blocked in task views until the test task is completed. This is the intended UX: "work is done, but testing is pending."

**Update `phases/build/change-type.json`** to record the test task IDs under the impl task entry:
```json
{
  "tasks": {
    "{impl-task-id}": {
      "change_type": "ui",
      "test_task_ids": ["{test-task-id}"]
    }
  }
}
```

**Implementation tasks are marked complete at the end of the build phase** (design decision CONDITION-1): the implementation work is done, but the task will render as blocked until QE completes. This is correct — "blocked" is a visibility state, not a completion gate.

#### Phase Deliverables

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` for the current phase's `required_deliverables` and `optional_deliverables`. Each phase defines what it needs to produce. Common patterns:

- **clarify**: objective.md, complexity.md, acceptance-criteria.md
- **design**: architecture.md, optional task-breakdown.md and ADRs
- **build**: Implementation files (no specific docs required)
- **review**: review-findings.md

The phases.json file is the source of truth — not this table.

After deliverables are complete, mark phase as `awaiting_approval`.

### 7. Phase Completion Validation

**CRITICAL: Validate before marking phase complete.**

#### 7.1 Task Count Validation

Check minimum expected task count to prevent premature completion:

Call `TaskList` and filter tasks by phase AND project name in their subject (case-insensitive match on `(?i)^{phase}[\s:-].*{project-name}`). This ensures multi-project isolation.

**Validation Rules:**
1. Check project.json for `task_lifecycle.user_overrides.min_tasks_per_phase`
2. Default task count ranges per phase:
   - clarify: 1-3 (outcome definition)
   - design: 2-5 (architecture + design docs)
   - test-strategy: 1-3 (test strategy)
   - build: 3-10 (actual implementation tasks)
   - test: 1-3 (test execution)
   - review: 1-3 (review completion)

   Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` for the canonical phase list. These are defaults.

   **Note**: Minimum is enforced (blocks completion). Maximum is advisory (warns but doesn't block).

3. If task count < minimum:
   - **BLOCK completion**
   - Report warning: "Phase has {count} tasks, expected minimum {min}. Create more tasks or override in project.json."
   - Do NOT set status to awaiting_approval

4. If user override present:
   ```json
   {
     "task_lifecycle": {
       "user_overrides": {
         "skip_min_task_validation": true
       }
     }
   }
   ```
   - Skip validation
   - Log override in activity

#### 7.2 Race Condition Prevention

Prevent phase completion race conditions:

1. **Atomic Status Check:**
   ```python
   # Pseudo-code for status transition
   with file_lock(phases/{phase}/status.md):
       current_status = read_status()
       if current_status == "in_progress":
           # Validate all tasks complete/blocked
           incomplete_tasks = get_incomplete_tasks(phase)
           if incomplete_tasks:
               return "Cannot complete: {len(incomplete_tasks)} tasks still in progress"

           # Check minimum task count
           if not validate_min_tasks(phase):
               return "Cannot complete: insufficient tasks"

           # Safe to transition
           update_status("awaiting_approval")
   ```

2. **Task State Validation:**
   - All tasks must be in `completed`, `blocked`, or have explicit skip reason
   - Tasks in `in_progress` or `pending` block completion
   - Exception: If user_overrides.allow_partial_completion = true

### 7.5 Mandatory Quality Gate

**CRITICAL: Run AFTER deliverables are complete, BEFORE sign-off.**

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` for the current phase's `gate_required` and `gate_type`.

If `gate_required` is `true` (all phases except ideate):

1. **Determine gate type** from phases.json `gate_type`:
   - `value` (after clarify): "Should we build this?"
   - `strategy` (after design, test-strategy): "Can we build it well?"
   - `execution` (after build, test, review): "Does it work?"

2. **Fast-pass check**: If `complexity_score` <= 1 AND no security/compliance signals detected AND phase is NOT review:
   - Use generic crew reviewer instead of full gate invocation (Priority 3 from sign-off chain)
   - Still record a gate result in status.md: `gate: {type: fast-pass, result: approved, findings: "Low complexity, no security signals"}`
   - This ensures the gate outcome is always documented even for simple work

3. **Run the full quality gate** (when fast-pass does NOT apply):
   ```
   /wicked-garden:crew:gate phases/{phase}/ --gate {gate_type}
   ```
   Wrap with task lifecycle:
   ```
   TaskCreate(subject="{Phase}: {project-name} - Quality gate ({gate_type})",
              description="Mandatory {gate_type} gate for {phase} phase",
              activeForm="Running {gate_type} quality gate")
   TaskUpdate(taskId="{id}", status="in_progress")
   # ... run gate ...
   TaskUpdate(taskId="{id}", status="completed")
   ```

4. **Handle gate outcome**:
   - **APPROVE**: Proceed to sign-off
   - **CONDITIONAL**: Classify each condition and handle accordingly (see AC-4.4 below)
   - **REJECT**: Do NOT proceed. Report findings. Re-execute phase work to address issues.

#### AC-4.4 CONDITIONAL Gate Auto-Resolution

When a gate returns CONDITIONAL, classify each condition before proceeding:

**Auto-resolvable** — condition is a specification gap, arithmetic error, missing definition, or mechanical fix that does NOT change acceptance criteria or project intent. Examples: undefined function referenced in design, incorrect line count, missing fallback constant value.

**Escalate** — condition requires changing acceptance criteria, altering the definition of done, shifting architectural approach, or making a tradeoff decision that affects project intent. Examples: "change the testing strategy from E2E to unit-only", "remove a workstream", "lower the quality bar".

**Classification rule**: For each condition, ask "Does resolving this change what we're building or how we measure success?" If uncertain — escalate (err on the side of caution).

**Auto-resolution flow** (interactive mode):
- For each auto-resolvable condition: make the fix inline, document it in `phases/{phase}/conditions-manifest.json` with `"auto_resolved": true` and the resolution, then re-run the gate
- For each escalate condition: surface to user with options to resolve as proposed, keep current spec, or defer

**Council escalation flow** (just-finish mode):
When a condition is classified as escalate and the session is in just-finish mode, dispatch to council:
```
Skill(skill="wicked-garden:jam:council",
      args="Gate condition requires intent decision: {condition}. Options: A) Resolve as proposed B) Reject resolution, keep current spec C) Defer")
```

Log all conditions and resolutions in status.md before proceeding to sign-off.

5. **Record gate result** in `phases/{phase}/status.md`:
   ```yaml
   gate:
     type: {gate_type}
     result: approved  # or conditional, rejected
     findings: "Summary"
     date: {date}
   ```

**User override**: If project.json contains `"skip_gates": true` in `task_lifecycle.user_overrides`, skip gates but log a warning.

### 8. Phase Sign-Off

**EVERY phase MUST have sign-off before advancing.** Reviewer selection is determined by the **Gate Reviewer Policy** (see `skills/qe/qe-strategy/SKILL.md`) which routes based on gate type and complexity score.

#### Gate Reviewer Policy (Quick Reference)

| Gate Type | Complexity 0-2 | Complexity 3-4 | Complexity 5-7 |
|-----------|----------------|----------------|----------------|
| generic (ideate) | Fast-pass | Single specialist subagent | Single specialist subagent |
| value (clarify) | `qe-orchestrator` | `qe-orchestrator` + `value-orchestrator` | `qe-orchestrator` + council |
| strategy (design, test-strategy) | Single specialist subagent | Specialist + `senior-engineer` | Council (multi-model) |
| execution (build, test, review) | `crew:reviewer` subagent | Signal-matched specialist subagent | Council + human sign-off |

**Escalation triggers** (override the table above — escalate to council even at low complexity):
- Security or compliance signals detected
- Gate returns CONDITIONAL (council validates conditions)
- Previous gate in same project was REJECTED

**Review phase is never fast-passed** — always at least a specialist subagent.

#### Sign-Off Fallback Chain

When the policy-selected reviewer is unavailable, fall back in order:

| Priority | Reviewer | How |
|----------|----------|-----|
| 1 (best) | **Council** (`/wicked-garden:jam:council`) | Multi-model evaluation — required at high complexity |
| 2 | **Third-party CLI** | Codex, Gemini, or OpenCode — independent single-model review |
| 3 | **Specialist subagent** | Signal-matched specialist via `Task()` dispatch |
| 4 | **Generic crew agent** | `Task(subagent_type="wicked-garden:crew:reviewer", ...)` |
| 5 | **Human** | Show deliverables, ask for approval |

#### Council Sign-Off (Priority 1)

Use when the Gate Reviewer Policy calls for council (complexity >= 5 execution, >= 4 strategy, or escalation trigger hit):

```
Skill(skill="wicked-garden:jam:council",
      args="Review {phase} phase deliverables for {project-name}. Evaluate: correctness, risk, completeness. Options: A) Approve B) Conditional C) Reject")
```

#### Third-Party CLI Sign-Off (Priority 2)

Copy phase artifacts to `/tmp/` and invoke a CLI reviewer:

```bash
# Codex (preferred)
cp -r phases/{phase}/ /tmp/crew-signoff/
cat /tmp/crew-signoff/REVIEW_PROMPT.md | codex exec "Review these phase deliverables..."

# Gemini (fallback)
cat /tmp/crew-signoff/REVIEW_PROMPT.md | gemini "Review the {phase} phase deliverables for project {name}..."

# OpenCode (fallback)
opencode run "Review the {phase} phase deliverables for project {name}..." -f /tmp/crew-signoff/REVIEW_PROMPT.md
```

Create a task for the sign-off:
```
TaskCreate(subject="{Phase}: {project-name} - Sign-off review",
           description="Independent review of phase deliverables",
           activeForm="Getting sign-off on {phase} phase")
TaskUpdate(taskId="{id}", status="in_progress")
# ... run CLI review ...
TaskUpdate(taskId="{id}", status="completed",
           description="{original}\n\n## Outcome\n{reviewer}: {findings summary}")
```

#### Specialist Sign-Off (Priority 3)

**CRITICAL: Always check specialist discovery before falling back to generic.**

1. **Discover available specialists**:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/specialist_discovery.py --json
   ```

2. **Filter to reviewers**: Select specialists whose `enhances` list includes the current phase or `"*"`

3. **Cross-reference facilitator plan**: Prioritize specialists the facilitator named in `${project_dir}/process-plan.json` — the `specialists[]` roster and the `phases[].primary` list for this phase (replaces the v5 `signals_detected` lookup)

4. **Dispatch matching specialists in parallel**:
   ```
   Task(subagent_type="wicked-garden:engineering:senior-engineer",
        prompt="Review {phase} phase deliverables for {project-name}. {deliverables}")
   Task(subagent_type="wicked-garden:platform:security-engineer",
        prompt="Security review of {phase} deliverables. Signals: {signals}")
   ```

5. **Aggregate results**: If ANY specialist returns REJECT, overall result is REJECT.

**Phase-to-specialist dispatch reference** (use discovery as source of truth):

| Phase | Primary Specialist Agent | Signal-Based Additions |
|-------|------------------------|----------------------|
| clarify | `wicked-garden:product:requirements-analyst` | — |
| design | `wicked-garden:engineering:solution-architect` | `wicked-garden:agentic:architect` (if agentic signals) |
| test-strategy | `wicked-garden:qe:test-strategist` | — |
| build | `wicked-garden:engineering:senior-engineer` | `wicked-garden:platform:security-engineer` (if security signals) |
| test | `wicked-garden:qe:test-automation-engineer` | — |
| review | `wicked-garden:engineering:senior-engineer` + `wicked-garden:qe:code-analyzer` | `wicked-garden:platform:security-engineer` (if security signals) |

#### Reviewer Separation Enforcement

When dispatching any gate reviewer (specialist, generic, or council), enforce that the reviewer differs from the phase implementer:

The reviewer subagent_type MUST differ from the phase executor's subagent_type. If the phase was executed by `wicked-garden:engineering:senior-engineer`, the gate reviewer CANNOT also be `wicked-garden:engineering:senior-engineer`.

Include in every gate dispatch prompt:
- `implementer_type`: the subagent_type that executed this phase
- Instruction: "You MUST NOT be the same agent type as the implementer. If your subagent_type matches `{implementer_type}`, REJECT this assignment and report that reviewer separation is violated."

If no specialist is available that differs from the implementer, escalate to council (Priority 1) or third-party CLI (Priority 2).

### 9. Learning Capture (AC-4.6)

**At every gate that returns CONDITIONAL or REJECT**, store the learning:

```
/wicked-garden:mem:store "Crew learning: {what went wrong and why}" --type procedural --tags "crew,learning" --importance medium
```

**At project completion (review phase approved)**, the orchestrator stores:

1. **User preferences observed** (if any new patterns noticed):
   ```
   /wicked-garden:mem:store "{preference observed}" --type preference --tags "crew,user-preference" --importance medium
   ```

2. **What worked well** (reusable patterns):
   ```
   /wicked-garden:mem:store "Crew pattern: {what worked and why}" --type procedural --tags "crew,pattern,success" --importance medium
   ```

3. **What to avoid** (anti-patterns discovered):
   ```
   /wicked-garden:mem:store "Crew anti-pattern: {what failed and why}" --type procedural --tags "crew,anti-pattern" --importance high
   ```

These are GENERAL learnings, not project-specific. They inform future projects.

#### Generic Sign-Off (Priority 4)

If no specialist is installed for the current phase, fall back to generic:
```
Task(subagent_type="wicked-garden:crew:reviewer",
     prompt="Sign-off review for {phase} phase of {project-name}.
     Implementer type: {implementer_type — the subagent_type that executed this phase}
     You MUST NOT be the same agent type as the implementer. If your subagent_type
     matches the implementer_type, REJECT this assignment with reason
     'reviewer_separation_violation'.
     Deliverables: {list deliverables}
     Success criteria: {from outcome.md}
     Verify deliverables meet criteria and flag any gaps.")
```

#### Human Sign-Off (Priority 5)

Required at complexity >= 6 execution gates. Optional but offered for complexity 3-5 when not in just-finish mode.

```markdown
## Phase Sign-Off: {phase}

### Automated Review
- **Reviewer**: {council|codex|gemini|specialist|generic}
- **Result**: {APPROVE|CONDITIONAL|REJECT}
- **Findings**: {summary}

### Deliverables
{list of phase deliverables}

### Human Review
Please review the above. Approve to advance to {next_phase}? (Y/n)
```

#### Recording Sign-Off

Record the sign-off in `phases/{phase}/status.md`:
```yaml
signoff:
  reviewer: codex  # or gemini, opencode, specialist:{name}, generic, human
  result: approved  # or conditional, rejected
  findings: "Summary of review findings"
  date: {date}
```

If sign-off result is `rejected`, do NOT advance. Report findings and re-execute.
If `conditional`, list conditions and ask user whether to proceed or address them first.

### 9. Update Phase Status

**REQUIRED: Every phase MUST have a `phases/{phase}/status.md`** — this is non-negotiable.

After execution, validation, and sign-off, update `phases/{phase}/status.md`:
- List completed deliverables
- Note any issues or blockers
- Include sign-off results
- Include task statistics:
  ```yaml
  status: awaiting_approval
  tasks_created: 5
  tasks_completed: 4
  tasks_blocked: 1
  tasks_recovered: 0
  signoff:
    reviewer: codex
    result: approved
    findings: "No critical issues found"
  ```
- Set status to `awaiting_approval` if complete

The `phase_manager.py complete` and `skip` actions auto-create a minimal status.md if none exists, but you should always write a meaningful summary of what was done or why it was skipped.

### 10. Report Results

```markdown
## Phase Execution: {phase}

### Task Lifecycle Summary
- Stale tasks recovered: {count}
- Tasks created: {count}
- Tasks completed: {count}
- Tasks blocked: {count}
- Phase minimum met: {yes/no}

### Completed Deliverables
- {Deliverable 1}
- {Deliverable 2}

### Integration Mode
Level {n}: {description of what's available}

### Task State
- Total tasks: {count}
- In progress: {count}
- Completed: {count}
- Blocked: {count with reasons}

### Sign-Off
- Reviewer: {codex|gemini|specialist|generic|human}
- Result: {APPROVE|CONDITIONAL|REJECT}
- Findings: {summary}

### Validation Status
- Minimum task count: ✓ Met ({count}/{min})
- All tasks resolved: ✓ Yes
- Sign-off: ✓ Approved
- Ready for approval: ✓ Yes

### Next Steps
{What to do next - usually /wicked-garden:crew:approve {phase}}
```

## Task Lifecycle Reference

### State Transitions
```
pending → in_progress → completed
  ↓            ↓
blocked   stale (30min) → recovered → pending
```

> **Status vocabulary**: Claude's native task tools use `pending`, `in_progress`, `completed`. All crew docs should use these terms (not `todo`/`done`).

### Staleness Detection
- Threshold: 30 minutes (configurable)
- Triggers: Task in `in_progress` with no updates
- Recovery: Auto-move to `pending` or manual intervention

### User Overrides
Available in `project.json`:
```json
{
  "task_lifecycle": {
    "staleness_threshold_minutes": 60,
    "recovery_mode": "manual",
    "user_overrides": {
      "skip_phase": false,
      "adaptive_task_creation": "enabled",
      "min_tasks_per_phase": 5,
      "skip_min_task_validation": false,
      "allow_partial_completion": false
    }
  }
}
```

### should_skip_phase Priority Order

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` — phases with `is_skippable: false` can NEVER be skipped.

For skippable phases:
1. **User Override** (highest priority)
   - `task_lifecycle.user_overrides.skip_phase = true`
2. **Phase Plan** — if the phase isn't in project.json `phase_plan`, skip it
3. **Signals** — detected signals require execution; missing specialists may suggest skip
4. **Complexity** — check the phase's `complexity_range` against project complexity score

When skipping a phase, use phase_manager which auto-creates a status.md record:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} skip --phase {phase} --reason "{reason}" --approved-by "{who}"
```

**Legacy alias**: `qe` maps to `test-strategy` in phases.json. Both names work. When checking phase_plan for injection or skip decisions, always normalize `qe` → `test-strategy` first to prevent duplicate phases.

**Testing default**: test-strategy and test phases should be in the plan for all projects with complexity >= 2. If they're absent from phase_plan but complexity warrants them, they should be injected at the next checkpoint (or at plan initialization in start.md). Only skip with explicit user override.
