---
name: gate-enforcement-adversarial
title: Adversarial Gate Enforcement — Bypass Attempts Blocked
description: Verify that all Tier 1 gate enforcement checks in pre_tool.py block adversarial bypass attempts under strict-mode enforcement
type: testing
difficulty: advanced
estimated_minutes: 20
---

# Adversarial Gate Enforcement — Bypass Attempts Blocked

This scenario deliberately tries to bypass gate enforcement and verifies each attempt is
blocked with a specific error message. All checks are Tier 1 (hook layer, `pre_tool.py`)
and run at <100ms via file stat + small reads before `phase_manager.py` ever executes.

The scenario tests six adversarial paths:

1. Missing phase directory — phase has no output at all
2. Missing required deliverables — phase directory exists but deliverables absent
3. Skipped phase bypass — attempt to approve a later phase while an earlier phase is missing
4. Test coverage below threshold — test-results.md has 25% coverage when 80% is required
5. Missing specialist engagement — complexity 7 project missing required specialists
6. Unresolved conditions — prior CONDITIONAL gate conditions not verified

(v6.0 removed the env-var bypass; strict enforcement is always active. Rollback is a
`git revert` on the PR, not a runtime toggle.)

The hook functions are tested directly via Python import. This avoids requiring a running
Claude session and makes the tests deterministic and infrastructure-free.

## Setup

```bash
export TEST_PROJECT="test-gate-enforcement"
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"

# Resolve the project directory using the same path logic as the hook.
# get_local_path is project-scoped so it must be resolved at runtime.
export PROJECT_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")
echo "PROJECT_DIR=${PROJECT_DIR}"

# Clean start
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"

# project.json — complexity 7, full 6-phase plan
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_local_path
project_dir = get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}'
project_dir.mkdir(parents=True, exist_ok=True)
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 7,
    'current_phase': 'clarify',
    'phase_plan': ['clarify', 'design', 'test-strategy', 'build', 'test', 'review'],
    'specialists_recommended': ['engineering', 'qe', 'product'],
    'phases': {
        'clarify': {'status': 'in_progress'},
        'design': {'status': 'pending'},
        'test-strategy': {'status': 'pending'},
        'build': {'status': 'pending'},
        'test': {'status': 'pending'},
        'review': {'status': 'pending'}
    }
}
(project_dir / 'project.json').write_text(json.dumps(d, indent=2))
print('project.json written to', project_dir)
"
```

**Expected**: `project.json written to <path>`

## Helper: run preflight check

All steps use this helper to call `_crew_gate_preflight` directly in-process,
bypassing the hook dispatch machinery while exercising the exact same logic.

```bash
preflight() {
  local phase="$1"
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from pre_tool import _crew_gate_preflight
cmd = '${PLUGIN_ROOT}/scripts/crew/phase_manager.py ${TEST_PROJECT} approve --phase $phase'
result = _crew_gate_preflight(cmd)
import json
print(json.dumps(result, indent=2))
"
}
```

## Steps

### Step 1: Missing phase directory → BLOCKED

The phase has no directory at all — it has produced zero output.

```bash
# No phases/ directory yet — every phase directory is absent
result=$(preflight clarify)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
assert 'directory does not exist' in d['reason'] or 'silently skipped' in d['reason'], \
    f'Expected directory/skipped message, got: {d[\"reason\"]}'
print('PASS: missing phase directory blocked')
print('reason:', d['reason'])
"
```

**Expected**: `PASS: missing phase directory blocked`

The reason must contain "directory does not exist" or "silently skipped" — a specific
message, not a generic "gate failed".

### Step 2: Empty phase directory (no deliverables) → BLOCKED

The phase directory exists but all required deliverables are absent.

```bash
# Create phase directory with no files inside
mkdir -p "${PROJECT_DIR}/phases/clarify"
# No deliverables inside — only the directory exists

result=$(preflight clarify)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
reason = d['reason']
# Must call out a specific missing file — not a generic message
assert 'objective.md' in reason or 'required deliverable' in reason, \
    f'Expected specific deliverable name, got: {reason}'
print('PASS: missing deliverables blocked with specific file name')
print('reason:', reason)
"
```

**Expected**: `PASS: missing deliverables blocked with specific file name`

### Step 3: Skipped phase bypass → BLOCKED

Clarify directory is absent while we attempt to approve `design`. The hook must detect
that `clarify` was silently skipped (no directory, no recorded skip reason).

```bash
# clarify has no directory; attempt to approve design
rm -rf "${PROJECT_DIR}/phases/clarify"

result=$(preflight design)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
reason = d['reason']
assert 'clarify' in reason, f'Expected clarify mentioned in reason, got: {reason}'
# Must say skipped or directory-related — not just generic block
assert 'skipped' in reason or 'directory' in reason or 'execution directory' in reason, \
    f'Expected skipped/directory message, got: {reason}'
print('PASS: skipped-phase bypass blocked')
print('reason:', reason)
"
```

**Expected**: `PASS: skipped-phase bypass blocked`

The reason must reference `clarify` specifically.

### Step 4: Test coverage below threshold → BLOCKED

All phases up to `test` have valid directories. `test-strategy/test-strategy.md` declares
20 planned test cases. `test/test-results.md` shows only 5 executed (25%). The 80%
minimum coverage gate must block approval.

```bash
# Build out all preceding phases with minimal valid deliverables
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
base = get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}' / 'phases'

# clarify deliverables
(base / 'clarify').mkdir(exist_ok=True)
(base / 'clarify' / 'objective.md').write_text('# Objective\n\nBuild a payment processing service.\n' + 'x' * 80)
(base / 'clarify' / 'complexity.md').write_text('# Complexity\n\nThis is a complex project.\n')
(base / 'clarify' / 'acceptance-criteria.md').write_text(
    '---\ncase_count: 20\n---\n\n# Acceptance Criteria\n\nThe system must process payments.\n' + 'x' * 80
)

# design deliverables
(base / 'design').mkdir(exist_ok=True)
(base / 'design' / 'architecture.md').write_text(
    '# Architecture\n\nMicroservices with event sourcing.\n' + 'x' * 180
)

# test-strategy deliverables — 20 planned cases
(base / 'test-strategy').mkdir(exist_ok=True)
(base / 'test-strategy' / 'test-strategy.md').write_text(
    '---\ncase_count: 20\n---\n\n# Test Strategy\n\n20 test cases planned across unit, integration, e2e.\n' + 'x' * 160
)

# build directory (no required deliverables)
(base / 'build').mkdir(exist_ok=True)

# test — only 5 of 20 tests executed (25% coverage)
(base / 'test').mkdir(exist_ok=True)
(base / 'test' / 'evidence').mkdir(exist_ok=True)
test_results = '---\npass_count: 5\nfail_count: 0\n---\n\n# Test Results\n\n'
test_results += '- [x] TC-001 payment succeeds\n'
test_results += '- [x] TC-002 payment fails invalid card\n'
test_results += '- [x] TC-003 refund processes\n'
test_results += '- [x] TC-004 duplicate payment rejected\n'
test_results += '- [x] TC-005 timeout handled\n'
test_results += 'x' * 160
(base / 'test' / 'test-results.md').write_text(test_results)
(base / 'test' / 'evidence' / 'report.md').write_text(
    '# Evidence Report\n\nTest run completed in CI pipeline.\n' + 'x' * 80
)
print('phase directories written')
"

result=$(preflight test)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
reason = d['reason']
# Must contain coverage numbers: 5/20 and 25% and minimum 80%
assert '5' in reason and '20' in reason, f'Expected 5/20 in reason, got: {reason}'
assert '25' in reason or '25%' in reason, f'Expected 25% in reason, got: {reason}'
assert '80' in reason or '80%' in reason, f'Expected 80% minimum in reason, got: {reason}'
print('PASS: test coverage blocked with specific numbers (5/20, 25%, minimum 80%)')
print('reason:', reason)
"
```

**Expected**: `PASS: test coverage blocked with specific numbers (5/20, 25%, minimum 80%)`

### Step 5: Missing specialist engagement → BLOCKED

Fix coverage to 20/20 (100%). No `specialist-engagement.json` exists. Complexity is 7
(>= 5), so specialist engagement is mandatory for the `test` phase which requires `qe`.

```bash
# Fix test-results.md to 20/20 executed
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
base = get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}' / 'phases' / 'test'
test_results = '---\npass_count: 20\nfail_count: 0\n---\n\n# Test Results\n\n'
for i in range(1, 21):
    test_results += f'- [x] TC-{i:03d} test case {i} passed\n'
test_results += 'x' * 160
(base / 'test-results.md').write_text(test_results)
print('test-results.md updated to 20/20')
"

# Confirm no specialist-engagement.json exists
ls "${PROJECT_DIR}/phases/test/" 2>&1 | grep specialist || echo "(no specialist-engagement.json present)"

result=$(preflight test)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
reason = d['reason']
assert 'specialist' in reason.lower(), f'Expected specialist mention, got: {reason}'
assert 'qe' in reason or 'required' in reason.lower(), f'Expected qe or required in reason, got: {reason}'
print('PASS: missing specialist engagement blocked')
print('reason:', reason)
"
```

**Expected**: `PASS: missing specialist engagement blocked`

### Step 6: Successful approval (all checks satisfied)

Create `specialist-engagement.json` with the required `qe` specialist. All other
checks already pass. The preflight must return `ok: true`.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
phase_dir = get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}' / 'phases' / 'test'
engagement = [{'domain': 'testing', 'agent': 'wicked-testing:review', 'engaged_at': '2026-04-05T00:00:00Z'}]
(phase_dir / 'specialist-engagement.json').write_text(json.dumps(engagement, indent=2))
print('specialist-engagement.json written')
"

result=$(preflight test)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert d['ok'], f'Expected ok=True but got: {d}'
print('PASS: all checks satisfied — preflight passes')
"
```

**Expected**: `PASS: all checks satisfied — preflight passes`

### Step 7: Conditions manifest enforcement → BLOCKED

A prior phase (`design`) has a `conditions-manifest.json` with an unresolved condition
and `conditions_manifest_required: true` in phases.json. Attempting to approve the next
phase (`test-strategy`) must be blocked with a specific unresolved-conditions message.

```bash
# Write an unresolved conditions manifest for the design phase
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
design_dir = get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}' / 'phases' / 'design'
design_dir.mkdir(parents=True, exist_ok=True)
manifest = {
    'source_gate': 'design',
    'created_at': '2026-04-05T00:00:00Z',
    'conditions': [
        {
            'id': 'CONDITION-1',
            'description': 'API rate limits must be documented before build phase',
            'verified': False,
            'resolution': None,
            'verified_at': None
        }
    ]
}
(design_dir / 'conditions-manifest.json').write_text(json.dumps(manifest, indent=2))
print('conditions-manifest.json written with 1 unresolved condition')
"

result=$(preflight test-strategy)
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.load(sys.stdin)
assert not d['ok'], 'Expected block but got ok=True'
reason = d['reason']
assert 'condition' in reason.lower() or 'unresolved' in reason.lower(), \
    f'Expected unresolved condition message, got: {reason}'
assert 'design' in reason, f'Expected design phase mentioned, got: {reason}'
print('PASS: unresolved conditions manifest blocked')
print('reason:', reason)
"
```

**Expected**: `PASS: unresolved conditions manifest blocked`

The reason must reference `design` and unresolved conditions.

## Expected Outcome

Every adversarial bypass attempt produces a specific, actionable error message — not a
generic "gate failed". The messages identify the exact file, phase, or condition that
failed so engineers can fix the root cause rather than guess.

(v6.0 removed the env-var bypass; strict enforcement is always active. Rollback is a
`git revert` on the PR, not a runtime toggle.)

## Success Criteria

- [ ] Missing phase directory blocked with "directory does not exist" or "silently skipped" message
- [ ] Missing deliverables blocked with the specific filename (e.g. `objective.md`)
- [ ] Skipped-phase bypass blocked with the missing phase name referenced (e.g. `clarify`)
- [ ] Test coverage blocked with exact numbers: `5/20`, `25%`, `minimum 80%`
- [ ] Missing specialist engagement blocked with specialist domain name referenced
- [ ] Successful path passes when all checks are satisfied
- [ ] Unresolved conditions manifest blocked with prior phase name and "condition" referenced

## Value Demonstrated

Without adversarial testing, gate enforcement may pass compliance tests under cooperative
conditions but fail under the real attack surface: a distracted engineer who approves too
early, an agent that hallucinates a phase as complete, or a script that jumps directly to
`build` without running `design`. This scenario exercises the full Tier 1 check matrix
against deliberately invalid state and confirms each check produces a diagnostic message
specific enough to unblock the engineer without manual investigation.

## Cleanup

```bash
rm -rf "${PROJECT_DIR}"
```
