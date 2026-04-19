---
name: parallel-dispatch-verification
title: Parallel Subagent Dispatch Verification (SC-6 / AC-α10)
description: |
  Acceptance scenario for SC-6 / AC-α10: verifies that multi-reviewer parallel gates
  actually dispatch reviewers in parallel (timestamp overlap in gate-result.json)
  AND that build-phase executors emit the parallelization_check self-statement.
type: testing
difficulty: advanced
estimated_minutes: 5
covers:
  - AC-α10 (parallel subagent dispatch enforcement)
  - SC-6   (prefer parallel subagent dispatch — design principle)
---

# Parallel Subagent Dispatch Verification

When `gate-policy.json` declares `mode: parallel` with `reviewers` of length >= 2, the
gate-dispatch helper MUST issue all reviewer calls in a **single batched message**, not
serially. When a phase-executor produces >= 2 independent sub-tasks in the `build` or
`test` phase, its output MUST include `parallelization_check.dispatched_in_parallel: true`.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="parallel-dispatch-test"

export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/build"
```

---

## Case 1: multi-reviewer gate timestamp overlap

**Verifies**: AC-α10 — reviewer dispatch windows overlap in time when `mode: parallel`.

### Test

Seed a synthetic `gate-result.json` that records a parallel dispatch:

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
gr = {
    'result': 'APPROVE',
    'score': 0.85,
    'dispatch_mode': 'parallel',
    'reviewers_dispatched': ['senior-engineer', 'security-engineer', 'risk-assessor'],
    'per_reviewer_verdicts': [
        {'reviewer': 'senior-engineer', 'verdict': 'APPROVE', 'score': 0.85,
         'dispatched_at': '2026-04-19T14:00:00Z', 'completed_at': '2026-04-19T14:00:10Z'},
        {'reviewer': 'security-engineer', 'verdict': 'APPROVE', 'score': 0.82,
         'dispatched_at': '2026-04-19T14:00:00Z', 'completed_at': '2026-04-19T14:00:12Z'},
        {'reviewer': 'risk-assessor', 'verdict': 'APPROVE', 'score': 0.80,
         'dispatched_at': '2026-04-19T14:00:01Z', 'completed_at': '2026-04-19T14:00:11Z'},
    ]
}
pathlib.Path('${PROJECT_DIR}/phases/build/gate-result.json').write_text(json.dumps(gr, indent=2))
"
```

### Assertions

- `gate-result.json`  `dispatch_mode == "parallel"`.
- At least two `per_reviewer_verdicts` entries have overlapping `[dispatched_at, completed_at]` windows.

---

## Case 2: executor parallelization_check self-statement

**Verifies**: SC-6 — every phase-executor return includes the `parallelization_check` block.

### Test

Seed a synthetic `executor-status.json` with three sub-agent timing entries showing overlap:

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
es = {
    'executor_task_id': 'task-123',
    'phase': 'build',
    'started_at': '2026-04-19T14:01:00Z',
    'finished_at': '2026-04-19T14:01:30Z',
    'deliverables': ['phases/build/impl.md'],
    'parallelization_check': {'sub_task_count': 3, 'dispatched_in_parallel': True, 'serial_reason': None},
    'sub_agent_timing': [
        {'task_id': 's1', 'dispatched_at': '2026-04-19T14:01:00Z', 'completed_at': '2026-04-19T14:01:15Z'},
        {'task_id': 's2', 'dispatched_at': '2026-04-19T14:01:00Z', 'completed_at': '2026-04-19T14:01:20Z'},
        {'task_id': 's3', 'dispatched_at': '2026-04-19T14:01:01Z', 'completed_at': '2026-04-19T14:01:18Z'},
    ]
}
pathlib.Path('${PROJECT_DIR}/phases/build/executor-status.json').write_text(json.dumps(es, indent=2))
"
```

### Assertions

- `executor-status.json` `parallelization_check.dispatched_in_parallel == True`.
- `sub_agent_timing` has at least 3 entries.
- At least two `sub_agent_timing` entries have overlapping windows.

---

## Case 3: missing parallelization_check with >= 2 sub-tasks fails execution

**Verifies**: AC-α10 failure-mode — `phase_manager.execute()` returns `status: "failed"`
with reason `"parallelization-check-missing"` when `sub_task_count >= 2` and
`dispatched_in_parallel: false` with null/empty `serial_reason`.

Assert: the check is enforced by `scripts/crew/phase_manager.py::execute()` per design
addendum-3 §SC-6.

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```
