---
name: phase-executor-deliverable-contract
title: Phase Executor Deliverable Contract — Halt vs Silent Exit
description: |
  Regression scenario for issue #649: phase-executor silently exited after the
  phase-start re-eval bookend without producing deliverables, forcing the user to
  write them inline (orchestrator violation). The fix tightens the contract so the
  agent either produces named deliverables or halts with a structured error.
type: workflow
difficulty: intermediate
estimated_minutes: 6
fixes: "#649"
covers:
  - executor must proceed past phase-start bookend to deliverable production
  - executor must halt with executor-missing-deliverable, not silent empty manifest
  - executor-status.json must record named deliverables in files_written
---

# Phase Executor Deliverable Contract

Regression for #649. Validates two invariants in `agents/crew/phase-executor.md`:

1. The "CRITICAL: phase-start re-eval is infrastructure, not the deliverable" clause
   exists — ensuring the agent cannot treat a bookend return as a completion signal.
2. The pre-return deliverable verification block exists — ensuring a missing
   deliverable halts with `executor-missing-deliverable`, not `status:"ok"`.

All assertions are structural (grep against the agent file). No LLM-in-the-loop.

---

## Setup

```bash
Run: test -f "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "agent found"
Assert: agent found
```

---

## Case 1: agent contains the mandatory continuation directive

**Verifies**: The phase-start re-eval bookend is labelled "infrastructure" and the
agent is instructed to proceed to deliverable production immediately after.

```bash
Run: grep -q "phase-start re-eval is infrastructure" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: continuation directive present"
Assert: PASS: continuation directive present
```

---

## Case 2: agent contains the pre-return deliverable verification block

**Verifies**: The Deliverable Verification section exists and names the
`executor-missing-deliverable` halt path.

```bash
Run: grep -q "Deliverable Verification" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: verification section present"
Assert: PASS: verification section present
```

```bash
Run: grep -q "executor-missing-deliverable" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: halt reason present"
Assert: PASS: halt reason present
```

---

## Case 3: Failure Modes section documents the halt path

**Verifies**: The Failure Modes section explicitly names `executor-missing-deliverable`
as a distinct reason from `executor-empty-deliverables`.

```bash
Run: python3 -c "
import pathlib, sys
text = pathlib.Path('${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md').read_text()
assert 'executor-missing-deliverable' in text, 'executor-missing-deliverable reason not found'
assert 'executor-empty-deliverables' in text, 'executor-empty-deliverables reason not found (must remain)'
print('PASS: both failure-mode reasons present')
"
Assert: PASS: both failure-mode reasons present
```

---

## Case 4: agent does NOT emit status:ok with empty files_written as a valid path

**Verifies**: The Return Contract and Deliverable Verification sections together
make a silent empty-manifest exit impossible — the verification must run before
any ok return.

```bash
Run: python3 -c "
import pathlib, sys, re
text = pathlib.Path('${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md').read_text()

# Deliverable Verification must appear BEFORE Return Contract in the file
dv_pos = text.find('Deliverable Verification')
rc_pos = text.find('Return Contract')
assert dv_pos != -1, 'Deliverable Verification section not found'
assert rc_pos != -1, 'Return Contract section not found'
assert dv_pos < rc_pos, (
    f'Deliverable Verification (pos {dv_pos}) must precede Return Contract (pos {rc_pos})'
)
print('PASS: Deliverable Verification precedes Return Contract')
"
Assert: PASS: Deliverable Verification precedes Return Contract
```

---

## Case 5: orchestrator-no-inline-work still passes (no regression)

**Verifies**: The existing structural checks from the orchestrator-no-inline-work
scenario remain valid after this change.

```bash
Run: grep -q "Task(" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: Task() dispatch present"
Assert: PASS: Task() dispatch present
```

```bash
Run: grep -q "executor-status.json" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: executor-status.json instruction present"
Assert: PASS: executor-status.json instruction present
```

```bash
Run: grep -q "parallelization_check" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: parallelization_check defined"
Assert: PASS: parallelization_check defined
```

---

## Expected Outcome

- `agents/crew/phase-executor.md` explicitly labels the phase-start re-eval as
  infrastructure and mandates continuation to deliverable production.
- The pre-return Deliverable Verification loop halts with a structured error when
  any named deliverable is absent.
- `executor-missing-deliverable` is a named failure mode, distinct from the existing
  `executor-empty-deliverables` (which `phase_manager.execute()` catches on its side).
- All prior structural assertions from orchestrator-no-inline-work still pass.

## Success Criteria

- [ ] `PASS: continuation directive present`
- [ ] `PASS: verification section present`
- [ ] `PASS: halt reason present`
- [ ] `PASS: both failure-mode reasons present`
- [ ] `PASS: Deliverable Verification precedes Return Contract`
- [ ] `PASS: Task() dispatch present`
- [ ] `PASS: executor-status.json instruction present`
- [ ] `PASS: parallelization_check defined`
