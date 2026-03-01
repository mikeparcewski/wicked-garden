---
description: Run QE analysis on a target with configurable rigor
argument-hint: [target] [--gate value|strategy|execution] [--rigor quick|standard]
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

### 5. Format Output

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

### 6. Handle Decisions

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

### 7. Show Evidence Summary

After displaying the gate result, show attached evidence:

```markdown
---

### Evidence Attached

| Type | Artifact |
|------|----------|
| Gate Result | `L3:qe:{gate}-gate` |
| Decision Memory | stored in wicked-mem (if available) |

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
