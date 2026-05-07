---
description: Run QE analysis on a target with configurable rigor
argument-hint: "[target] [--gate <category|specific-gate-name>] [--rigor quick|standard]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:crew:gate

Run quality engineering gate analysis on a target.

## Arguments

- `target` (optional): File or directory to analyze. Default: current directory
- `--gate` (optional): Which gate to run. Default: resolves from current phase.
- `--rigor` (optional): Analysis depth. Default: standard
  - `quick`: Fast triage (~30s)
  - `standard`: Full analysis (~2min)

### `--gate` accepts two vocabularies (Issue #852)

The runtime has **specific gate names** in `gate-policy.json` and a phase →
gate mapping in `scripts/crew/phase_manager.py::_PHASE_DEFAULT_GATE`. This
slash command also accepts three **categorical labels** that resolve to a
specific gate based on the current phase, for users who don't want to look
up the per-phase gate name.

**Specific gate names** (preferred — these are what `gate-policy.json`
defines and what the dispatcher routes on):

| Specific gate           | Default phase    | Question                                |
|-------------------------|------------------|-----------------------------------------|
| `requirements-quality`  | `clarify`        | Are the ACs testable and complete?      |
| `design-quality`        | `design`         | Is the design coherent and minimal?     |
| `testability`           | `test-strategy`  | Can we test what we built?              |
| `challenge-resolution`  | `challenge`      | Did we steelman the alternative?        |
| `code-quality`          | `build`          | Does the code meet R1-R6?               |
| `evidence-quality`      | `review`         | Does the evidence support the verdict?  |
| `final-audit`           | (review variant) | Final pre-merge audit                   |
| `convergence-verify`    | (build/test)     | Are tracked artifacts wired through?    |
| `semantic-alignment`    | (review)         | Do code and spec match?                 |
| `uncertainty-gate`      | (any)            | Is uncertainty bounded?                 |

**Categorical labels** (legacy 3-name vocab, resolved by current phase):

| Categorical | Resolves to (by phase) |
|-------------|------------------------|
| `value`     | `requirements-quality` (clarify) |
| `strategy`  | `design-quality` (design) or `testability` (test-strategy) |
| `execution` | `code-quality` (build) or `evidence-quality` (review) |

If the categorical is ambiguous for the current phase (e.g. `strategy` is
issued during `build`), surface an error listing the specific names and ask
the user to disambiguate — do not silently pick one.

The `gate` field written into `gate-result.json` MUST be one of the specific
names from `gate-policy.json` — that is what the runtime dispatcher and the
audit log key on. Categorical labels are input convenience, not storage shape.

## Instructions

### 1. Parse Arguments

Extract from the command arguments:
- `target`: The file or directory path (default: ".")
- `gate`: Either a specific gate name from the table above, or a categorical
  (`value | strategy | execution`). If categorical, resolve to the specific
  name via the current phase using `_PHASE_DEFAULT_GATE` semantics. If
  omitted, default to the gate for the current phase.
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

PreToolUse validates the task's `metadata` per scripts/_event_schema.py; the task persists natively under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/`.

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
  "verdict": "APPROVE|CONDITIONAL|REJECT",
  "gate": "value|strategy|execution",
  "phase": "{current phase}",
  "reviewer": "wicked-garden:crew:qe-orchestrator",
  "score": 0.0,
  "recorded_at": "2026-05-07T22:30:00Z",
  "findings": ["list of key findings"],
  "conditions": [{"id": "C-1", "description": "..."}]
}
```

- `verdict`: Extract from the orchestrator's decision (APPROVE, CONDITIONAL, or REJECT). The validator also accepts `result` as an alias.
- `gate`: One of the canonical short names (`value | strategy | execution`) — never a descriptive name.
- `score`: Map the orchestrator's confidence/quality assessment to a number in [0.0, 1.0]. Use 0.8 for clean APPROVE, 0.6 for CONDITIONAL, 0.3 for REJECT as defaults if no explicit score.
- `reviewer`: Always `"wicked-garden:crew:qe-orchestrator"` (never use auto-approve names).
- `recorded_at`: ISO-8601 timestamp. The validator also accepts `timestamp` as a deprecated alias (Issue #850) but emits a stderr warning — prefer `recorded_at`.
- `conditions`: Only include for CONDITIONAL results — list each condition with an `id` and `description`.
- `findings`: Brief list of key observations from the gate analysis.

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

**Task**: {task_id} (if created)

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
| Decision Memory | stored via wicked-brain:memory (if available) |

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
