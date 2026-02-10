---
description: Execute current phase work with adaptive role engagement
---

# /wicked-crew:execute

Execute work for the current phase with adaptive role selection.

## Instructions

### 1. Load Project State

Read `project.json` to get current phase, phase_plan, and status.

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

### 3. Load User Preferences (if exists)

Check for `~/.something-wicked/wicked-crew/preferences.yaml` for:
- Autonomy level (ask-first, balanced, just-finish)
- Communication style

### 4. Load Signal Analysis

Read project.json for:
- **signals_detected**: What types of work were identified
- **complexity_score**: How complex (affects autonomy)
- **specialists_recommended**: Which specialists to engage

### 4.5 Signal Re-Analysis at Checkpoints

**CRITICAL: Run after every checkpoint phase completes.**

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` and check if the current phase has `"checkpoint": true`. Checkpoint phases are: **clarify**, **design**, **build**.

When a checkpoint phase completes:

1. **Gather phase artifacts**: Read all files in `phases/{phase}/` and any deliverables produced
2. **Re-run signal analysis** on the combined project description + phase artifacts:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" analyze --project-dir . --json "{combined text summary of deliverables}"
   ```
3. **Compare signals AND complexity**: Diff new `signals` against project.json `signals_detected`, AND compare new `complexity` against `complexity_score`
4. **If new signals found OR complexity increased**:
   - Update project.json `signals_detected` with union of old + new signals
   - Update `complexity_score` if new score is higher
   - Update `specialists_recommended` with new recommendations
   - **Check for phase injection** (see below)

#### Dynamic Phase Injection

When new signals are detected OR complexity increases at a checkpoint, check if any phases NOT in the current `phase_plan` should be injected:

1. Read `${CLAUDE_PLUGIN_ROOT}/phases.json` for all phases
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

### 5. Discover Available Specialists

Run specialist discovery to find installed specialist plugins:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/specialist_discovery.py" --json
```

This returns all available specialists with their `enhances` declarations (which phases they support).

**Dynamic Routing**: Do NOT use hardcoded specialist-to-phase mappings. Instead:
1. Read `signals_detected` and `specialists_recommended` from project.json
2. Filter discovered specialists to those whose `enhances` list includes the current phase or `"*"`
3. Cross-reference with recommended specialists from signal analysis
4. Engage all matching, available specialists for the current phase

### 6. Engage Specialists for Phase

**CRITICAL: Wrap every specialist dispatch with task lifecycle tracking.**

For each specialist engagement:
1. Create a task: `TaskCreate(subject="{Phase}: {project-name} - {specialist-name} {work type}", description="Engaging {specialist} for {phase} phase work. Signals: {relevant signals}.", activeForm="Running {specialist} for {phase}", metadata={"initiative": "{project-name}", "priority": "P1", "assigned_to": "{specialist-name}"})`
2. Mark in_progress: `TaskUpdate(taskId="{id}", status="in_progress")`
3. Dispatch to specialist (skill invocation or subagent)
4. Mark completed: `TaskUpdate(taskId="{id}", status="completed", description="{original}\n\n## Outcome\n{summary of specialist findings/output}")`

**Initiative metadata**: Always include `"initiative": "{project-name}"` in task metadata. This routes the task to the crew project's kanban initiative (see start.md Section 8.5). Tasks without initiative metadata default to the repo's "Issues" initiative.

#### Specialist-to-Phase Mapping (Reference)

This table mirrors specialist.json `enhances` declarations. Always use the discovery script output as the source of truth — this table is a quick reference only.

| Specialist | Role | Enhances |
|-----------|------|----------|
| wicked-jam | ideation | clarify, design |
| wicked-product | product | clarify, design, review |
| wicked-engineering | engineering | design, build, review |
| wicked-qe | quality-engineering | test-strategy, build, test, review, * |
| wicked-platform | devsecops | build, review, * |
| wicked-data | data-engineering | design, build, * |
| wicked-agentic | agentic-architecture | design, build, review |
| wicked-delivery | project-management | *, review |

**`*` semantics**: Means "available for consultation in any phase if signals recommend it." A specialist with `*` is only actively engaged when signal analysis recommends it OR the phase explicitly needs that role. Do NOT engage every `*` specialist in every phase.

**Build phase note**: Build-phase specialists (engineering, data, agentic) provide architectural guidance and review during build, but the **implementer agent** does the actual implementation work. Engage build-phase specialists when signals indicate their domain (e.g., agentic signals → wicked-agentic for pattern guidance).

#### Specialist Dispatch

When engaging a specialist, use Task dispatch for heavy analysis work. Keep slash commands only for interactive or thin CLI operations. `-` means no direct dispatch for that phase.

**Structured context packages**: Instead of dumping prose context into subagent prompts, use the context package builder to assemble task-scoped context from session state + memory + search:

```bash
# Build a context package for the subagent
python3 "${SMAHT_PLUGIN_ROOT}/scripts/context_package.py" build \
  --task "{task description}" \
  --project "{project-name}" \
  --prompt
```

Where `SMAHT_PLUGIN_ROOT` is discovered via:
```bash
# Find wicked-smaht plugin root (check cache, then local)
SMAHT_PLUGIN_ROOT=$(find ~/.claude/plugins/cache/wicked-garden/wicked-smaht -maxdepth 1 -type d | sort -V | tail -1)
```

The context package outputs a structured prompt section with: task, decisions, constraints, file scope, relevant code, memories, and project state. Include this in the subagent prompt instead of raw deliverable text.

For each specialist engagement, the dispatch pattern is:

```
TaskCreate(subject="{Phase}: {project-name} - {specialist} analysis", ...)
TaskUpdate(taskId="{id}", status="in_progress")
Task(
  subagent_type="wicked-{specialist}:{agent}",
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
| wicked-jam | `/wicked-jam:brainstorm` (interactive) | `/wicked-jam:perspectives` (interactive) | - | - |
| wicked-product | `Task(subagent_type="wicked-product:requirements-analyst", ...)` | `Task(subagent_type="wicked-product:business-strategist", ...)` | - | `Task(subagent_type="wicked-product:ux-designer", ...)` |
| wicked-engineering | - | `Task(subagent_type="wicked-engineering:solution-architect", ...)` | `Task(subagent_type="wicked-engineering:senior-engineer", ...)` | `Task(subagent_type="wicked-engineering:senior-engineer", ...)` |
| wicked-qe | - | - | `/wicked-crew:gate` (quality gate) | `/wicked-crew:gate` (quality gate) |
| wicked-platform | - | - | `Task(subagent_type="wicked-platform:security-engineer", ...)` | `Task(subagent_type="wicked-platform:security-engineer", ...)` |
| wicked-data | - | `Task(subagent_type="wicked-data:data-analyst", ...)` | `Task(subagent_type="wicked-data:data-engineer", ...)` | - |
| wicked-agentic | - | `Task(subagent_type="wicked-agentic:architect", ...)` | `Task(subagent_type="wicked-agentic:pattern-advisor", ...)` | `Task(subagent_type="wicked-agentic:safety-reviewer", ...)` |
| wicked-delivery | `/wicked-delivery:report` (thin CLI) | - | `/wicked-delivery:report` (thin CLI) | `/wicked-delivery:report` (thin CLI) |

**What stays as slash commands**:
- `wicked-jam`: Brainstorm/perspectives are interactive and need user back-and-forth
- `wicked-delivery:report`: Thin CLI wrapper, no heavy analysis
- `wicked-crew:gate`: Already uses correct Task dispatch internally (gate.md is gold standard)

#### Phase Execution Pattern

For each phase, follow this pattern:

1. **Determine eligible specialists**: Filter by `enhances` containing current phase or `"*"`
2. **Prioritize by signals**: Engage signal-recommended specialists first
3. **Engage each specialist** with task wrapping (TaskCreate → in_progress → dispatch → completed)
4. **Fall back to built-in agent** if no specialists available for the phase

**Built-in fallback agents by phase:**

| Phase | Fallback Agent | Prompt Pattern |
|-------|---------------|----------------|
| clarify | `wicked-crew:facilitator` | "Guide outcome clarification for: {description}" |
| design | `wicked-crew:researcher` | "Research existing patterns and design approaches for: {outcome}" |
| test-strategy | (inline) | Create test strategy from outcome.md success criteria |
| build | `wicked-crew:implementer` | "Implement according to design: {design summary}" |
| test | `wicked-crew:reviewer` | "Execute tests and verify against test strategy: {test-strategy summary}" |
| review | `wicked-crew:reviewer` | "Review implementation against outcome: {outcome summary}" |

#### Build Phase: Task Creation

In the build phase, create rich tasks for implementation work:

```
TaskCreate(
  subject="{Phase}: {project-name} - {task description}",
  description="WHY this task exists. What problem it solves. Acceptance criteria.",
  activeForm="{Phase-verb}ing {task description}",
  metadata={
    "initiative": "{project-name}",  // routes to crew project kanban initiative
    "priority": "P1",               // P0-P3, set explicitly
    "assigned_to": "agent-name"      // who owns this
  }
)
```

**Subject uniqueness**: Each task subject MUST be unique within the project. The combination of `{Phase}: {project-name} - {specific description}` ensures this.

**Task enrichment**: Use `addBlockedBy`/`addBlocks` on TaskUpdate to set dependencies. When completing a task, update its description with the outcome.

**Task Subject Prefix Filtering** (case-insensitive):
- Match pattern: `(?i)^(build|clarify|design|ideate|test-strategy|test|review)[\s:-]`

Tasks created via TaskCreate are automatically synced to kanban (if installed) via PostToolUse hooks. No manual kanban CLI calls needed.

#### Phase Deliverables

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` for the current phase's `required_deliverables` and `optional_deliverables`. Each phase defines what it needs to produce. Common patterns:

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

   Read `${CLAUDE_PLUGIN_ROOT}/phases.json` for the canonical phase list. These are defaults.

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

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` for the current phase's `gate_required` and `gate_type`.

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
   /wicked-crew:gate phases/{phase}/ --gate {gate_type}
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
   - **CONDITIONAL**: Log conditions in status.md, proceed to sign-off but include conditions
   - **REJECT**: Do NOT proceed. Report findings. Re-execute phase work to address issues.

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

**EVERY phase MUST have sign-off before advancing.** Use this priority chain — try each level in order and use the first available:

#### Sign-Off Priority Chain

| Priority | Reviewer | How | When to Use |
|----------|----------|-----|-------------|
| 1 (best) | **Third-party CLI** | Codex, Gemini, or OpenCode | Always preferred — independent AI review |
| 2 | **Specialist plugin** | wicked-engineering:review, wicked-qe:gate, etc. | If no CLI available |
| 3 | **Generic crew agent** | `Task(subagent_type="wicked-crew:reviewer", ...)` | Last resort automated |
| 4 | **Human** | Show deliverables, ask for approval | Always offer if human is in the loop |

#### Third-Party CLI Sign-Off (Priority 1)

Copy phase artifacts to `/tmp/` and invoke a CLI reviewer:

**Codex** (preferred):
```bash
# Copy deliverables to tmp for sandbox access
cp -r phases/{phase}/ /tmp/crew-signoff/
# Pipe review prompt
cat /tmp/crew-signoff/REVIEW_PROMPT.md | codex exec "Review these phase deliverables..."
```

**Gemini** (fallback):
```
/wicked-startah:gemini-cli "Review the {phase} phase deliverables for project {name}..."
```

**OpenCode** (fallback):
```
/wicked-startah:opencode-cli "Review the {phase} phase deliverables for project {name}..."
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

#### Specialist Sign-Off (Priority 2)

If no third-party CLI is available, use the most relevant specialist:

| Phase | Specialist Sign-Off |
|-------|-------------------|
| clarify | `/wicked-product:elicit` (validate requirements) |
| design | `/wicked-engineering:arch` (validate architecture) |
| test-strategy | `/wicked-crew:gate strategy` (validate test strategy) |
| build | `/wicked-engineering:review` (validate implementation) |
| review | `/wicked-crew:gate execution` (validate release readiness) |

#### Generic Sign-Off (Priority 3)

If no specialist available:
```
Task(subagent_type="wicked-crew:reviewer",
     prompt="Sign-off review for {phase} phase of {project-name}.
     Deliverables: {list deliverables}
     Success criteria: {from outcome.md}
     Verify deliverables meet criteria and flag any gaps.")
```

#### Human Sign-Off (Priority 4)

If human is still in the loop (not in just-finish mode), always present deliverables for human review after automated sign-off:

```markdown
## Phase Sign-Off: {phase}

### Automated Review
- **Reviewer**: {codex|gemini|specialist|generic}
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
{What to do next - usually /wicked-crew:approve {phase}}
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

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` — phases with `is_skippable: false` can NEVER be skipped.

For skippable phases:
1. **User Override** (highest priority)
   - `task_lifecycle.user_overrides.skip_phase = true`
2. **Phase Plan** — if the phase isn't in project.json `phase_plan`, skip it
3. **Signals** — detected signals require execution; missing specialists may suggest skip
4. **Complexity** — check the phase's `complexity_range` against project complexity score

When skipping a phase, use phase_manager which auto-creates a status.md record:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_manager.py" {project} skip --phase {phase} --reason "{reason}" --approved-by "{who}"
```

**Legacy alias**: `qe` maps to `test-strategy` in phases.json. Both names work. When checking phase_plan for injection or skip decisions, always normalize `qe` → `test-strategy` first to prevent duplicate phases.

**Testing default**: test-strategy and test phases should be in the plan for all projects with complexity >= 2. If they're absent from phase_plan but complexity warrants them, they should be injected at the next checkpoint (or at plan initialization in start.md). Only skip with explicit user override.
