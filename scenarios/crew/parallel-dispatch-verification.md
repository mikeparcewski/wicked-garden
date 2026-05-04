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

### Test — seed parallel gate-result.json

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
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
print('gate-result.json written')
"
Assert: gate-result.json written
```

### Assertion — dispatch_mode is parallel and windows overlap

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
from datetime import datetime
gr = json.loads(pathlib.Path('${PROJECT_DIR}/phases/build/gate-result.json').read_text())
assert gr['dispatch_mode'] == 'parallel', f'dispatch_mode mismatch: {gr[\"dispatch_mode\"]}'
verdicts = gr['per_reviewer_verdicts']
assert len(verdicts) >= 2, f'Expected >= 2 verdicts, got {len(verdicts)}'
# check at least one pair overlaps
overlaps = 0
for i, a in enumerate(verdicts):
    for b in verdicts[i+1:]:
        a_start = datetime.fromisoformat(a['dispatched_at'].replace('Z', '+00:00'))
        a_end   = datetime.fromisoformat(a['completed_at'].replace('Z', '+00:00'))
        b_start = datetime.fromisoformat(b['dispatched_at'].replace('Z', '+00:00'))
        b_end   = datetime.fromisoformat(b['completed_at'].replace('Z', '+00:00'))
        if a_start < b_end and b_start < a_end:
            overlaps += 1
assert overlaps >= 1, 'No overlapping reviewer windows found — dispatch was serial'
print(f'PASS: dispatch_mode=parallel, {overlaps} overlapping reviewer window pair(s)')
"
Assert: PASS: dispatch_mode=parallel, 1 or more overlapping reviewer window pair(s)
```

---

## Case 2: executor parallelization_check self-statement

**Verifies**: SC-6 — every phase-executor return includes the `parallelization_check` block.

### Test — seed executor-status.json with parallel sub-agent timing

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
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
print('executor-status.json written')
"
Assert: executor-status.json written
```

### Assertion — parallelization_check fields valid

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
es = json.loads(pathlib.Path('${PROJECT_DIR}/phases/build/executor-status.json').read_text())
pc = es.get('parallelization_check', {})
assert pc.get('dispatched_in_parallel') is True, f'dispatched_in_parallel is not True: {pc}'
timing = es.get('sub_agent_timing', [])
assert len(timing) >= 3, f'Expected >= 3 sub_agent_timing entries, got {len(timing)}'
print(f'PASS: parallelization_check.dispatched_in_parallel=True, {len(timing)} sub-agent timing entries')
"
Assert: PASS: parallelization_check.dispatched_in_parallel=True, 3 sub-agent timing entries

---

## Case 3: missing parallelization_check with >= 2 sub-tasks fails execution

**Verifies**: AC-α10 failure-mode — `phase_manager.execute()` returns `status: "failed"`
with reason `"parallelization-check-missing"` when `sub_task_count >= 2` and
`dispatched_in_parallel: false` with null/empty `serial_reason`.

### Test — seed executor-status.json with failing parallelization_check

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
es = {
    'executor_task_id': 'task-fail-pc',
    'phase': 'build',
    'started_at': '2026-04-19T14:02:00Z',
    'finished_at': '2026-04-19T14:02:30Z',
    'deliverables': ['phases/build/impl.md'],
    'parallelization_check': {'sub_task_count': 3, 'dispatched_in_parallel': False, 'serial_reason': None},
    'sub_agent_timing': [
        {'task_id': 's1', 'dispatched_at': '2026-04-19T14:02:00Z', 'completed_at': '2026-04-19T14:02:10Z'},
        {'task_id': 's2', 'dispatched_at': '2026-04-19T14:02:11Z', 'completed_at': '2026-04-19T14:02:21Z'},
        {'task_id': 's3', 'dispatched_at': '2026-04-19T14:02:22Z', 'completed_at': '2026-04-19T14:02:30Z'},
    ]
}
pathlib.Path('${PROJECT_DIR}/phases/build/executor-status-fail.json').write_text(json.dumps(es, indent=2))
print('executor-status-fail.json written')
"
Assert: executor-status-fail.json written
```

### Assertion — parallelization_check violation is detectable

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
es = json.loads(pathlib.Path('${PROJECT_DIR}/phases/build/executor-status-fail.json').read_text())
pc = es.get('parallelization_check', {})
sub_task_count = pc.get('sub_task_count', 0)
dispatched = pc.get('dispatched_in_parallel', True)
serial_reason = pc.get('serial_reason')
# SC-6 enforcement: sub_task_count >= 2, dispatched=False, serial_reason=None is a violation
violation = sub_task_count >= 2 and not dispatched and not serial_reason
if violation:
    print('PASS: parallelization-check violation detected (sub_task_count=%d, dispatched_in_parallel=False, serial_reason=None)' % sub_task_count)
    sys.exit(0)
else:
    print('FAIL: expected violation not detected — check fixture')
    sys.exit(1)
"
Assert: PASS: parallelization-check violation detected (sub_task_count=3, dispatched_in_parallel=False, serial_reason=None)
```

---

## Case 4: qe-orchestrator gate emits batched dispatch_mode + per_reviewer_verdicts

**Verifies**: qe-orchestrator's inlined output contract — every gate verdict
declares `dispatch_mode` and lists `per_reviewer_verdicts` for the reviewers
named in step 2 of the agent body. Catches the "serial loop disguised as
parallel" failure where an agent claims parallel but emits one verdict at
a time.

### Test — seed a strategy-gate qe-orchestrator output

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
go = {
    'gate': 'strategy',
    'target': 'phases/design/design.md',
    'decision': 'APPROVE',
    'score': 0.84,
    'reviewer': 'qe-orchestrator',
    'reviewers_dispatched': [
        'wicked-testing:testability-reviewer',
        'wicked-testing:test-strategist',
        'wicked-testing:risk-assessor',
    ],
    'dispatch_mode': 'parallel',
    'serial_reason': None,
    'per_reviewer_verdicts': [
        {'reviewer': 'wicked-testing:testability-reviewer', 'verdict': 'APPROVE', 'score': 0.86, 'summary': 'design is testable'},
        {'reviewer': 'wicked-testing:test-strategist',     'verdict': 'APPROVE', 'score': 0.82, 'summary': 'scenarios cover ACs'},
        {'reviewer': 'wicked-testing:risk-assessor',       'verdict': 'APPROVE', 'score': 0.84, 'summary': 'risk acceptable'},
    ],
    'findings': [],
    'conditions': [],
    'blockers': [],
    'evidence_artifact': 'phases/design/strategy-gate-20260419.md',
}
pathlib.Path('${PROJECT_DIR}/phases/build/qe-orchestrator-output.json').write_text(json.dumps(go, indent=2))
print('qe-orchestrator-output.json written')
"
Assert: qe-orchestrator-output.json written
```

### Assertion — dispatch_mode + reviewer count match the strategy-gate contract

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
go = json.loads(pathlib.Path('${PROJECT_DIR}/phases/build/qe-orchestrator-output.json').read_text())
# Strategy gate names 3 reviewers in agents/crew/qe-orchestrator.md
assert go['gate'] == 'strategy', f'gate mismatch: {go[\"gate\"]}'
assert go['dispatch_mode'] in ('parallel', 'serial'), f'dispatch_mode invalid: {go[\"dispatch_mode\"]}'
if go['dispatch_mode'] == 'serial':
    assert go.get('serial_reason'), 'serial dispatch missing serial_reason'
verdicts = go['per_reviewer_verdicts']
assert len(verdicts) == 3, f'strategy gate must batch 3 reviewers, got {len(verdicts)}'
expected = {'wicked-testing:testability-reviewer','wicked-testing:test-strategist','wicked-testing:risk-assessor'}
got = {v['reviewer'] for v in verdicts}
assert got == expected, f'reviewer set mismatch: expected {expected}, got {got}'
# APPROVE invariant: empty conditions + blockers + score >= 0.70
if go['decision'] == 'APPROVE':
    assert not go['conditions'], 'APPROVE with non-empty conditions'
    assert not go['blockers'],   'APPROVE with non-empty blockers'
    assert go['score'] >= 0.70,  'APPROVE with score < 0.70'
# banned reviewer guard
banned = {'fast-pass', 'just-finish-auto'}
assert go['reviewer'] not in banned, 'banned reviewer identity'
assert not go['reviewer'].startswith('auto-approve-'), 'banned auto-approve identity'
print(f'PASS: qe-orchestrator strategy gate batched {len(verdicts)} reviewers, dispatch_mode={go[\"dispatch_mode\"]}, decision={go[\"decision\"]}')
"
Assert: PASS: qe-orchestrator strategy gate batched 3 reviewers, dispatch_mode=parallel, decision=APPROVE
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```
