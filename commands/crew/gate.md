---
description: Run QE analysis on a target with configurable rigor
argument-hint: "[target] [--gate value|strategy|execution] [--rigor quick|standard]"
---

# /wicked-garden:crew:gate

Run quality engineering gate analysis on a target.

## Arguments

- `target` (optional): File or directory to analyze. Default: current directory
- `--gate` (optional): Which gate to run. Default: strategy
  - `value`: Post-clarify - "Should we build this?"
  - `strategy`: Post-design - "Can we build it well?"
  - `execution`: Post-build - "Does it work?"
- `--rigor` (optional): Analysis depth. Default: standard
  - `quick`: Fast triage (~30s)
  - `standard`: Full analysis (~2min)

## Instructions

### 1. Parse Arguments

Extract from the command arguments:
- `target`: The file or directory path (default: ".")
- `gate`: value, strategy, or execution (default: strategy)
- `rigor`: quick or standard (default: standard)

### 2. Validate Target

Check the target exists:
```bash
ls -la {target}
```

If target doesn't exist, inform user and ask for correct path.

### 3. Track Gate Task

Create a task for this gate analysis using TaskCreate:
```
TaskCreate(
  subject="QE: {project-name} - {gate} Gate on {target}",
  description="Running {gate} gate analysis on {target}",
  activeForm="Running {gate} gate analysis"
)
```

This is automatically synced to kanban if installed.

### 4. Invoke Orchestrator

Use Task tool to run qe-orchestrator with gate type:

```
Task(
  subagent_type="wicked-garden:crew:qe-orchestrator",
  prompt="""
  Run {gate} Gate analysis.

  Target: {target}
  Gate: {gate}
  Rigor: {rigor}

  Route to the appropriate gate orchestrator and return decision.
  """
)
```

### 5. Persist Gate Result

After the orchestrator returns, write the gate result to the project phase directory so that `phase_manager.py` can validate it during approval.

**5a. Resolve the project directory:**

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project_name} current
```

This returns the current phase and project directory path.

**5b. Write `gate-result.json`:**

Write a JSON file to `{project_dir}/phases/{current_phase}/gate-result.json` with this schema:

```json
{
  "result": "APPROVE|CONDITIONAL|REJECT",
  "gate": "{gate type}",
  "phase": "{current phase}",
  "reviewer": "wicked-garden:crew:qe-orchestrator",
  "score": 0.0-1.0,
  "findings": ["list of key findings"],
  "conditions": [{"id": "C-1", "description": "..."}],
  "timestamp": "ISO 8601"
}
```

- `result`: Extract from the orchestrator's decision (APPROVE, CONDITIONAL, or REJECT)
- `score`: Map the orchestrator's confidence/quality assessment to 0.0-1.0. Use 0.8 for clean APPROVE, 0.6 for CONDITIONAL, 0.3 for REJECT as defaults if no explicit score
- `reviewer`: Always `"wicked-garden:crew:qe-orchestrator"` (never use auto-approve names)
- `conditions`: Only include for CONDITIONAL results — list each condition with an `id` and `description`
- `findings`: Brief list of key observations from the gate analysis

### 6. Complete Gate Task

After writing the gate result, mark the gate task as completed:
```
TaskUpdate(taskId={task_id from Step 3}, status="completed")
```

### 7. Format Output

Display the result from orchestrator:

```markdown
## QE Analysis Complete

**Target**: {target}
**Gate**: {gate}
**Rigor**: {rigor}

---

{orchestrator result}

---

**Kanban Task**: {task_id} (if created)

To view full evidence: `/wicked-garden:crew:evidence`
```

### 8. Handle Decisions

Based on the decision:

**APPROVE**:
```markdown
Gate: APPROVE

Ready to proceed. No blocking issues found.
```

**CONDITIONAL**:
```markdown
Gate: CONDITIONAL

Conditions to address:
1. {condition 1}
2. {condition 2}

You can proceed, but these should be addressed.
```

**REJECT**:
```markdown
Gate: REJECT

Blockers found:
1. {blocker 1}

Must fix before proceeding.
```

### 9. Show Evidence Summary

After displaying the gate result, show attached evidence:

```markdown
---

### Evidence Attached

| Type | Artifact |
|------|----------|
| Gate Result | `L3:qe:{gate}-gate` |
| Decision Memory | stored in wicked-garden:mem (if available) |

To view full evidence: `/wicked-garden:crew:evidence {task_id}`
```

## Examples

```bash
# Default: Strategy gate on current directory
/wicked-garden:crew:gate

# Value gate on outcome document
/wicked-garden:crew:gate outcome.md --gate value

# Strategy gate on specific directory
/wicked-garden:crew:gate src/auth --gate strategy

# Execution gate after implementation
/wicked-garden:crew:gate src/auth --gate execution

# Quick triage
/wicked-garden:crew:gate src/payments --rigor quick
```

## Gate Selection Guide

| Phase Just Completed | Gate to Run |
|---------------------|-------------|
| clarify | `--gate value` |
| design | `--gate strategy` |
| build | `--gate execution` |
