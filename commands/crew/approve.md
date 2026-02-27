---
description: Approve a phase and advance to next stage
argument-hint: <phase> [project-name]
---

# /wicked-garden:crew:approve

Review and approve a completed phase to advance the project.

## Instructions

### 1. Parse Arguments

- `phase` (required): any phase from the project's `phase_plan` (e.g., clarify, design, build, review)
- `project-name` (optional): defaults to most recent project

### 2. Find Project

If no project specified, use most recent:

```bash
ls -t ~/.something-wicked/wicked-crew/projects/ 2>/dev/null | head -1
```

### 3. Verify Phase State

Read `phases/{phase}/status.md` and verify:
- Phase is in `awaiting_approval` or `complete` state
- Phase has deliverables

If phase is `pending` or `in_progress`, inform user they need to run `/wicked-garden:crew:execute` first.

### 3.1 Task Lifecycle Validation

**CRITICAL: Perform comprehensive validation before approval.**

#### 3.1.1 Check for Stale Tasks

Call `TaskList` to get all current tasks. For each task with status `in_progress`:
- Calculate age from `updated_at`
- If age > staleness_threshold: **BLOCK approval**
- Report: "Cannot approve: {count} stale tasks detected. Run /wicked-garden:crew:execute to recover."

**Override:** User can set `task_lifecycle.user_overrides.allow_stale_approval = true` to bypass.

#### 3.1.2 Verify Minimum Task Count

Read expected minimums from project.json or use defaults:

```python
expected_minimums = {
    "clarify": 1,
    "design": 2,
    "test-strategy": 1,
    "build": 3,
    "test": 1,
    "review": 1
}

# Check override
min_tasks = project.task_lifecycle.user_overrides.get("min_tasks_per_phase") or expected_minimums[phase]

# Count phase tasks (case-insensitive subject match)
phase_tasks = [t for t in all_tasks if matches_phase_prefix(t.name, phase)]

if len(phase_tasks) < min_tasks:
    if not user_overrides.skip_min_task_validation:
        BLOCK_APPROVAL("Minimum task count not met: {len(phase_tasks)}/{min_tasks}")
```

**Case-Insensitive Matching:**
- Pattern: `(?i)^{phase}[\s:-]`
- Handles: "Build: X", "build - Y", "BUILD task"

#### 3.1.3 Validate Task Completion

All phase tasks must be in terminal state:
- `completed`: Completed successfully
- `blocked`: Explicitly blocked with reason
- Exception: `user_overrides.allow_partial_completion = true`

```bash
# Check for incomplete tasks
incomplete_tasks = tasks in (pending, in_progress) for current phase

if incomplete_tasks and not allow_partial_completion:
    BLOCK_APPROVAL("Phase has {count} incomplete tasks")
    for task in incomplete_tasks:
        report task.id, task.name, task.swimlane
```

#### 3.1.4 Verify Sign-Off

**CRITICAL: Every phase must have sign-off recorded before approval.**

Read `phases/{phase}/status.md` and check for `signoff:` section:

```python
signoff = status.get("signoff", {})
if not signoff:
    BLOCK_APPROVAL("No sign-off recorded. Run /wicked-garden:crew:execute to get phase reviewed.")

if signoff.get("result") == "rejected":
    BLOCK_APPROVAL("Sign-off was REJECTED. Address findings and re-execute.")
```

**Sign-off priority chain** (from execute.md):
1. Third-party CLI (Codex, Gemini, OpenCode) — independent AI review
2. Specialist plugin — domain-specific review
3. Generic crew reviewer — basic validation
4. Human — always offered if in the loop

If sign-off is `conditional`, display conditions and ask user to confirm before proceeding.

**Override:** User can set `task_lifecycle.user_overrides.skip_signoff = true` to bypass (not recommended).

#### 3.1.5 Race Condition Prevention

Use atomic file operations for approval:

```python
# Pseudo-code
with file_lock(phases/{phase}/status.md):
    # Re-verify state (prevent TOCTOU)
    current_state = read_status()
    if current_state != "awaiting_approval":
        return ERROR("State changed during approval")

    # Validate tasks again
    if not validate_all_tasks_complete(phase):
        return ERROR("Task state changed during approval")

    # Safe to approve
    update_status("approved")
    update_project_phase(next_phase)
```

### 4. Display Deliverables and Validation Results

Show summary of phase deliverables and validation status:

```markdown
## Phase Review: {phase}

### Task Lifecycle Status
- Total tasks: {count}
- Completed: {completed_count}
- Blocked: {blocked_count}
- Stale: {stale_count} {if > 0: "⚠️ BLOCKER"}
- Minimum required: {min_tasks}
- Status: {✓ Met | ✗ Not met}

### Deliverables

{List of what was produced in this phase}

### Approval Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] All tasks in terminal state (completed/blocked)
- [ ] Minimum task count met ({actual}/{expected})
- [ ] No stale tasks in progress
- [ ] Sign-off recorded ({reviewer}: {result})

### Validation Results

{if all validations pass:}
✓ All validation checks passed

{if validation failures:}
✗ Validation failures detected:
- {List each failure}
- Override available: Set task_lifecycle.user_overrides.{specific_override}

**Approve and advance to {next_phase}?** (Y/n)
{if validation failures: "⚠️ Approval blocked. Fix issues or add overrides."}
```

### 5. Process Approval

**Only proceed if all validations pass OR user has set appropriate overrides.**

If user approves (Y or proceeds):

1. **Final Validation Check** (atomic):
   - Re-verify no stale tasks appeared
   - Re-verify task count
   - Re-verify task completion state

2. Update phase status.md:
   ```yaml
   status: approved
   approved: {date}
   task_stats:
     total: {count}
     completed: {count}
     blocked: {count}
     minimum_met: true
   validation:
     stale_check: passed
     min_count_check: passed
     completion_check: passed
     overrides_used: []
   ```

3. Update project state via phase_manager.py (which writes project.json):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_manager.py" {project} approve --phase {phase}
   ```
   This updates `current_phase` and marks the phase as approved in project.json.

4. Create next phase status.md:
   ```yaml
   phase: {next_phase}
   status: in_progress
   started: {date}
   ```

5. **Log Approval Activity:**
   Log the approval in the phase status file. Kanban activity is tracked automatically via PostToolUse hooks when tasks are updated.

### 6. Phase Progression

Phase progression follows the `phase_plan` stored in project.json (set during `/wicked-garden:crew:start`):

```
{phase_plan[0]} → {phase_plan[1]} → ... → done
```

The phase order is dynamic per project. After the last phase in the plan is approved, mark project as complete.

### 7. Report Next Steps

```markdown
## {Phase} Phase Approved

**Phase Progression**:
{previous phases} → **{current}** → {next phases}

### Task Lifecycle Summary
- Tasks completed: {count}
- Tasks blocked: {count}
- Validation status: ✓ All checks passed
- Overrides used: {list or "None"}

### What's Next: {next_phase}

{Description of what happens in next phase}

**To start**: `/wicked-garden:crew:execute`

### Task Lifecycle Configuration
Current settings:
- Staleness threshold: {threshold} minutes
- Recovery mode: {mode}
- Minimum tasks for {next_phase}: {min}

To customize, edit project.json:
```json
{
  "task_lifecycle": {
    "user_overrides": {
      "skip_phase": false,
      "min_tasks_per_phase": 5
    }
  }
}
```
```

## Task Lifecycle Reference for Approval

### Validation Checks (in order)

1. **Stale Task Check**
   - No tasks in `in_progress` > staleness_threshold
   - Override: `allow_stale_approval: true`

2. **Minimum Task Count**
   - Phase has minimum expected tasks
   - Case-insensitive subject prefix matching
   - Override: `skip_min_task_validation: true`

3. **Task Completion**
   - All tasks in terminal state (completed/blocked)
   - Override: `allow_partial_completion: true`

4. **Sign-Off Recorded**
   - Phase has sign-off in status.md (reviewer, result, findings)
   - Must be `approved` or `conditional` (not `rejected`)
   - Priority chain: third-party CLI > specialist > generic > human
   - Override: `skip_signoff: true`

5. **Race Condition Prevention**
   - Atomic status transitions
   - Re-validation before commit

### User Override Mechanism

Edit `~/.something-wicked/wicked-crew/projects/{project}/project.json`:

```json
{
  "task_lifecycle": {
    "staleness_threshold_minutes": 60,
    "recovery_mode": "manual",
    "user_overrides": {
      "allow_stale_approval": false,
      "skip_min_task_validation": false,
      "allow_partial_completion": false,
      "skip_signoff": false,
      "min_tasks_per_phase": 3,
      "skip_phase": false,
      "adaptive_task_creation": "enabled"
    }
  }
}
```

### should_skip_phase Priority Order

When determining if a phase should be skipped:

1. **User Override** (HIGHEST)
   - `task_lifecycle.user_overrides.skip_phase = true` → Skip
   - `task_lifecycle.user_overrides.skip_phase = false` → Don't skip
   - If not set, proceed to next check

2. **Signals** (MEDIUM)
   - If critical signals detected → Don't skip
   - If no relevant signals → Consider skipping
   - If specialists unavailable → May skip

3. **Complexity** (LOWEST)
   - Low (0-2) → May skip
   - Medium (3-5) → Recommended
   - High (6-7) → Required
