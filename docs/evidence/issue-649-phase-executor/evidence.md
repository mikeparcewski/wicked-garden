# Evidence — Issue #649: Phase Executor Deliverable Contract

**Date**: 2026-04-25
**Branch**: fix/649-phase-executor-contract
**Scenario**: scenarios/crew/phase-executor-deliverable-contract.md

## Root Cause

`agents/crew/phase-executor.md` Step 1 described running the phase-start re-eval
bookend but did not explicitly instruct the agent to continue to deliverable
production after it returned. The agent could interpret a successful bookend return
(even a no-op `mutations: []`) as completion and exit. No deliverables were written.
No error was emitted. The caller received `status: "ok"` with `files_written: []`,
which `phase_manager.execute()` catches as `executor-empty-deliverables` — but that
recovery path was too late for the user session that triggered #649.

This is an R4 (swallowed error) violation: the real failure (no deliverables written)
was never surfaced until an upstream script happened to check `files_written`.

## Design Decision: Path (a)

The agent's description and Step 3 both state "Produce the phase's required
deliverables." Architecture clearly intends the phase-executor to produce deliverables.
Path (b) (bookend-only with specialist dispatch) was rejected because:
- The existing delegation contract (`phase_executor_may_delegate=false` for
  clarify/design) means the agent produces deliverables directly — not via specialists.
- The scenario `mode3-execution.md` asserts `executor-status.json` plus named
  deliverables per phase, confirming deliverable production is the expected output.

## Changes Made

### agents/crew/phase-executor.md

1. **Step 1 continuation directive** — Added a CRITICAL block immediately after the
   phase-start re-eval instructions:
   > "The phase-start re-eval is infrastructure, not the deliverable. After the
   > bookend returns, you MUST proceed immediately to Steps 2–4."
   This eliminates the ambiguous "bookend returned = done" exit path.

2. **Deliverable Verification section** (new, pre-return) — A mandatory loop that
   checks each expected deliverable before the agent may emit `status:"ok"`. If any
   deliverable is absent or < 100 bytes, the agent MUST halt and return:
   `status:"failed"`, `reason:"executor-missing-deliverable"`, `missing:[...]`
   with an explicit error message naming the unwritten file.

3. **Failure Modes update** — Added `executor-missing-deliverable` as a named
   failure reason. This is distinct from `executor-empty-deliverables` (which
   `phase_manager.execute()` detects from outside) — this one is emitted by the
   agent itself at the pre-return verification step.

### scenarios/crew/phase-executor-deliverable-contract.md

New structural scenario with 8 assertions covering:
- Continuation directive present (case 1)
- Deliverable Verification section present (case 2)
- `executor-missing-deliverable` halt reason present (case 2–3)
- Both failure reasons present without regression (case 3)
- Ordering: Deliverable Verification precedes Return Contract (case 4)
- Existing orchestrator-no-inline-work assertions still pass (case 5)

## Scenario Run Results

```
PASS case-1: continuation directive present
PASS case-2a: Deliverable Verification section present
PASS case-2b: executor-missing-deliverable halt reason present
PASS case-3: executor-empty-deliverables still present (no regression)
PASS case-4: Deliverable Verification precedes Return Contract
PASS case-5: Task() dispatch present
PASS case-5: executor-status.json instruction present
PASS case-5: parallelization_check present

All 8 checks passed
```

## Files Changed

- `agents/crew/phase-executor.md` — tightened contract (continuation + verification)
- `scenarios/crew/phase-executor-deliverable-contract.md` — new regression scenario
- `docs/evidence/issue-649-phase-executor/evidence.md` — this file
