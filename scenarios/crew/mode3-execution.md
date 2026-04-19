---
name: mode3-execution
title: Mode-3 Crew Execution — Full Pipeline Traversal
description: |
  Acceptance scenario for AC-α8: exercises the full mode-3 pipeline on a synthetic
  crew project from clarify through review. Assertions are structural — script exit
  codes, file presence, JSONL record counts, and gate-result contents. No
  LLM-in-the-loop assertions.
type: testing
difficulty: advanced
estimated_minutes: 10
covers:
  - AC-α1 (phase-executor agent exists and is discoverable)
  - AC-α2 (phase_manager.execute records deliverables + executor-status.json)
  - AC-α3 (phase_manager.approve dispatches gate + persists gate-result.json)
  - AC-α4 (re-eval wiring; addendum JSONL written per phase)
  - AC-α8 (full pipeline traversal)
---

# Mode-3 Crew Execution — Full Pipeline Traversal

This scenario verifies that a mode-3 crew project traverses **clarify → design →
challenge → build → test → review** with:

- A `phase-executor` dispatch per phase.
- A gate dispatch per phase producing `gate-result.json` with `result: APPROVE`.
- Re-eval addendum records accumulating in `process-plan.addendum.jsonl`.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="mode3-exec-test"

export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 3,
    'current_phase': 'clarify',
    'phase_plan': ['clarify', 'design', 'build', 'review'],
    'phase_plan_mode': 'facilitator',
    'rigor_tier': 'standard',
    'dispatch_mode': 'mode-3',
    'phases': {k: {'status': 'pending'} for k in ['clarify', 'design', 'build', 'review']}
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written')
"
```

**Expected stdout**: `project.json written`

---

## Case 1: executor + approve per phase

**Verifies**: AC-α2 (execute records deliverables) + AC-α3 (approve persists gate-result.json).

### Test

For each phase in the plan:

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${TEST_PROJECT}" execute --phase "${PHASE}"

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${TEST_PROJECT}" approve --phase "${PHASE}"
```

### Assertions

- Every `phases/{phase}/executor-status.json` exists and parses as JSON.
- Every `phases/{phase}/gate-result.json` contains `"result": "APPROVE"`.
- `process-plan.addendum.jsonl` contains at least one record per phase.

### Pass criteria

```
count_executor_status == len(phase_plan)
count_gate_result == len(phase_plan)
all(gate_result["result"] == "APPROVE" for each phase)
```

---

## Case 2: CONDITIONAL blocks next-phase execute

**Verifies**: AC-α7(b) — a CONDITIONAL verdict blocks the next phase until conditions clear.

### Test

Seed a CONDITIONAL gate result at `phases/design/gate-result.json`:

```json
{"result": "CONDITIONAL", "score": 0.65, "min_score": 0.70,
 "conditions": [{"description": "Clarify FR-1 ambiguity", "source": "reviewer"}]}
```

Attempt `phase_manager.py execute --phase build` → **expected non-zero exit** with
`unresolved-conditions` in stderr.

Resolve the manifest (write `resolved: true` on each condition) and retry →
**expected exit 0**.

---

## Case 3: addendum integrity

**Verifies**: AC-α4 — every phase emits a phase-end JSONL record.

### Assertions

- `process-plan.addendum.jsonl` line count >= `len(phase_plan)`.
- Every record passes `scripts/crew/validate_reeval_addendum.py`.
- Every record's `chain_id` starts with `${TEST_PROJECT}.`.

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

The scenario is idempotent — re-running it from Setup produces the same evidence.
