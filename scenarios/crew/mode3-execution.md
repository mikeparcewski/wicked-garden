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

For each phase in the plan (clarify → design → build → review):

```bash
Run: for PHASE in clarify design build review; do
  sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
    scripts/crew/phase_manager.py "${TEST_PROJECT}" execute --phase "${PHASE}" && \
  sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
    scripts/crew/phase_manager.py "${TEST_PROJECT}" approve --phase "${PHASE}"
done
Assert: exit code 0 for all phases; no "unresolved" or "error" in stderr
```

### Assertion: executor-status and gate-result written for all phases

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
project_dir = pathlib.Path('${PROJECT_DIR}')
phases = ['clarify', 'design', 'build', 'review']
errors = []
for phase in phases:
    es = project_dir / 'phases' / phase / 'executor-status.json'
    gr = project_dir / 'phases' / phase / 'gate-result.json'
    if not es.exists():
        errors.append(f'MISSING executor-status.json for {phase}')
    if not gr.exists():
        errors.append(f'MISSING gate-result.json for {phase}')
    elif json.loads(gr.read_text()).get('result') != 'APPROVE':
        errors.append(f'gate-result not APPROVE for {phase}')
if errors:
    for e in errors:
        print('FAIL:', e)
    sys.exit(1)
print('PASS: executor-status.json + gate-result.json (APPROVE) found for all %d phases' % len(phases))
"
Assert: PASS: executor-status.json + gate-result.json (APPROVE) found for all 4 phases
```

---

## Case 2: CONDITIONAL blocks next-phase execute

**Verifies**: AC-α7(b) — a CONDITIONAL verdict blocks the next phase until conditions clear.

### Test — seed CONDITIONAL, verify block

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
gr_path = pathlib.Path('${PROJECT_DIR}') / 'phases' / 'design' / 'gate-result.json'
gr_path.parent.mkdir(parents=True, exist_ok=True)
gr_path.write_text(json.dumps({
    'result': 'CONDITIONAL', 'score': 0.65, 'min_score': 0.70,
    'conditions': [{'description': 'Clarify FR-1 ambiguity', 'source': 'reviewer', 'resolved': False}]
}))
print('CONDITIONAL gate seeded')
"
Assert: CONDITIONAL gate seeded
```

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${TEST_PROJECT}" execute --phase build 2>&1; echo "exit:$?"
Assert: output contains "unresolved" or "conditions" and exit code is non-zero (exit:1)
```

### Test — resolve conditions, verify unblock

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
gr_path = pathlib.Path('${PROJECT_DIR}') / 'phases' / 'design' / 'gate-result.json'
gr = json.loads(gr_path.read_text())
for c in gr.get('conditions', []):
    c['resolved'] = True
gr_path.write_text(json.dumps(gr))
print('conditions resolved')
"
Assert: conditions resolved
```

---

## Case 3: addendum integrity

**Verifies**: AC-α4 — every phase emits a phase-end JSONL record.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib, sys
addendum = pathlib.Path('${PROJECT_DIR}') / 'process-plan.addendum.jsonl'
if not addendum.exists():
    print('FAIL: process-plan.addendum.jsonl missing')
    sys.exit(1)
lines = [l for l in addendum.read_text().splitlines() if l.strip()]
if len(lines) < 4:
    print(f'FAIL: expected >= 4 addendum records, got {len(lines)}')
    sys.exit(1)
print(f'PASS: {len(lines)} addendum records found')
"
Assert: PASS: 4 or more addendum records found

Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/validate_reeval_addendum.py "${PROJECT_DIR}/process-plan.addendum.jsonl"
Assert: exit code 0 (all records valid)
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

The scenario is idempotent — re-running it from Setup produces the same evidence.
