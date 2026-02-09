---
description: Show evidence summary for a task or project
argument-hint: [task-id] [--project project-id]
---

# /wicked-crew:evidence

Query and display evidence collected for a task.

## Arguments

- `task-id` (optional): Task ID to query. Default: active task
- `--project` (optional): Project ID. Default: active project

## Instructions

### 1. Determine Context

Get project and task from args or active context:
- If task-id provided, use it directly
- If no task specified, call `TaskList` and find the most recently active task
- If no project specified, use the current crew project from `project.md`

### 2. Get Task with Artifacts

Call `TaskGet` with the task ID to retrieve the task details including subject, description, and status.

For evidence artifacts, check the crew project's phase directories for deliverables.

### 3. Get Activity from Task History

Review the task's status history and any associated deliverables in the crew project structure:
- `phases/*/status.md` — Phase completion records
- `outcome.md` — Success criteria and scope
- Design/build artifacts in phase directories

### 4. Categorize Evidence by Tier

Parse artifact names using `{tier}:{type}:{detail}` convention:

**L1 (Commits + Comments)**:
- Count commits from task
- Count comments from activity log

**L2 (Docs + Scenarios)**:
- Artifacts matching `L2:*`
- Types: `doc:requirements`, `doc:design`, `qe:scenarios`

**L3 (Gates + Tests)**:
- Artifacts matching `L3:*`
- Types: `qe:value-gate`, `qe:execution-gate`, `test:*`

**L4 (Audit)**:
- Artifacts matching `L4:*`
- Types: `audit:control-*`

### 5. Check wicked-mem for Decisions

If wicked-mem available:
```
/wicked-mem:recall "gate decision {task}" --limit 5
```

### 6. Display Evidence Summary

```markdown
## Evidence Summary: {task_name}

**Task ID**: {task_id}
**Project**: {project_name}

### L1: Commits + Comments
- **Commits**: {count} linked
  {list commit hashes if any}
- **Activity Entries**: {count}

### L2: Design Documentation
{For each L2 artifact:}
- `{artifact_name}` → {path or url}

{If none: "No L2 evidence attached"}

### L3: Gates + Tests
{For each L3 artifact:}
- `{artifact_name}` → {path or url}
  {If gate result, show decision: APPROVE/CONDITIONAL/REJECT}

{If none: "No L3 evidence attached"}

### L4: Audit Evidence
{For each L4 artifact:}
- `{artifact_name}` → {path or url}

{If none: "N/A (no compliance requirements)"}

### Coverage Summary

| Tier | Status |
|------|--------|
| L1 (commits/comments) | {✓ if commits > 0 or comments > 0} |
| L2 (docs/scenarios) | {✓/partial/—} |
| L3 (gates/tests) | {✓/partial/—} |
| L4 (audit) | {✓/n/a} |

### Related Decisions (from wicked-mem)
{List any recalled gate decisions}
```

## Examples

```bash
# Evidence for specific task
/wicked-crew:evidence abc12345

# Evidence for task in specific project
/wicked-crew:evidence abc12345 --project my-project

# Evidence for active task (if context set)
/wicked-crew:evidence
```

## No Evidence Found

If task has no evidence:

```markdown
## Evidence Summary: {task_name}

No evidence has been attached to this task yet.

### How to Add Evidence

**L1** (automatic):
- Commits are linked via TodoWrite hook
- Comments added via orchestrators

**L2** (manual):
Store design docs in the crew project's `phases/design/` directory. They are automatically associated with the project.

**L3** (automatic from gates):
- Run `/wicked-crew:gate --gate value` to generate gate evidence

See: [EVIDENCE.md](../docs/EVIDENCE.md) for full schema
```
