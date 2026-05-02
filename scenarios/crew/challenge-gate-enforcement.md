---
name: challenge-gate-enforcement
title: Challenge Gate Enforcement — Write Blocked Without Valid v2 Contrarian Artifact
description: Verify the challenge-artifacts gate (#442 + #721 v2 schema) blocks build-phase Write/Edit when the artifact is missing or has under-3 dissent vectors covered, and clears with a v2-conformant artifact
type: testing
difficulty: advanced
estimated_minutes: 15
---

# Challenge Gate Enforcement (v2 schema, Issue #721)

Drives the `_check_challenge_gate` hook end-to-end against the v2
schema: Write intent → active crew project discovery → complexity check
→ artifact validation → deny reason. Three cases plus the documented
bypass.

## Setup

```bash
export TEST_PROJECT="test-challenge-gate-v2"
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export CLAUDE_PROJECT_NAME="wg-scenario-challenge-gate-v2"

export PROJECT_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, shutil, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
(projects_root / f"{project}.json").unlink(missing_ok=True)
shutil.rmtree(projects_root / project, ignore_errors=True)
project_dir = projects_root / project
project_dir.mkdir(parents=True)
data = {
    "id": project, "name": project,
    "workspace": os.environ['CLAUDE_PROJECT_NAME'],
    "complexity_score": 7, "current_phase": "build",
    "phase_plan": ["clarify", "design", "build", "test", "review"],
    "phases": {p: {"status": "completed" if p in ("clarify","design") else ("in_progress" if p=="build" else "pending")} for p in ["clarify","design","build","test","review"]},
}
(projects_root / f"{project}.json").write_text(json.dumps(data, indent=2))
(project_dir / "project.json").write_text(json.dumps(data, indent=2))
print(project_dir)
PYEOF
)
echo "PROJECT_DIR=${PROJECT_DIR}"
```

**Expected**: `PROJECT_DIR=...` printed.

## Helper

```bash
write_guard() {
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
os.environ['CLAUDE_PLUGIN_ROOT'] = '${PLUGIN_ROOT}'
from pre_tool import _handle_write_guard
print(_handle_write_guard({'file_path': '$1', 'content': 'x'}))
"
}
```

## Step 1: Well-formed v2 artifact → Write ALLOWED

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import pathlib, textwrap
p = pathlib.Path("${PROJECT_DIR}") / "phases" / "design"
p.mkdir(parents=True, exist_ok=True)
(p / "challenge-artifacts.md").write_text(textwrap.dedent("""\\
    # Challenge Artifacts
    ## Incongruent Representation
    The dominant story claims the new pipeline ships value this quarter.
    The actual shape of the work is a refactor disguised as a feature.
    No customer in recent interviews asked for it.
    ## Unasked Question
    What measurable user outcome would tell us this migration was worth?
    ## Steelman of Alternative Path
    I argue we should not ship the pipeline this quarter. The current
    system serves traffic with a known operational profile. Replacing
    it diverts engineers from a backlog of customer-facing fixes. A
    staged rewrite carries less rollback risk and preserves optionality.
    Most importantly, no customer has asked for the work.
    ## Dissent Vectors Covered
    - [x] security
    - [x] cost
    - [x] operability
    - [ ] ethics
    - [ ] ux
    - [ ] maintenance
    """), encoding="utf-8")
PYEOF
result=$(write_guard "src/payments/processor.py")
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
decision = d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
assert decision != 'deny', f'Expected allow, got: {d}'
print('PASS: v2 well-formed artifact cleared the gate')
"
```

**Expected**: `PASS: v2 well-formed artifact cleared the gate`

## Step 2: Missing artifact → Write BLOCKED

```bash
rm -f "${PROJECT_DIR}/phases/design/challenge-artifacts.md"
result=$(write_guard "src/payments/processor.py")
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision') == 'deny', f'Expected deny, got: {d}'
reason = out.get('permissionDecisionReason', '')
assert 'challenge-artifacts.md' in reason and 'contrarian' in reason.lower() and 'WG_CHALLENGE_GATE' in reason, \
    f'Expected reason to mention filename + contrarian + bypass, got: {reason}'
print('PASS: missing artifact blocked with specific reason')
"
```

**Expected**: `PASS: missing artifact blocked with specific reason`

## Step 3: Single vector covered → Write BLOCKED, then bypass clears

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import pathlib, textwrap
p = pathlib.Path("${PROJECT_DIR}") / "phases" / "design"
p.mkdir(parents=True, exist_ok=True)
(p / "challenge-artifacts.md").write_text(textwrap.dedent("""\\
    # Challenge Artifacts
    ## Incongruent Representation
    Story: auth improves security. Reality: surface narrows in one place
    and expands in two others. Net change unmodelled.
    ## Unasked Question
    What is the net change in attack surface across all three planes?
    ## Steelman of Alternative Path
    Keep the existing flow. It has stood up to three years of audit. The
    proposed flow uses a custom token no auditor has reviewed. Migration
    forces all tenants onto the new flow at once. Rollback requires
    coordinated downtime across all tenants.
    ## Dissent Vectors Covered
    - [x] security
    - [ ] cost
    - [ ] operability
    - [ ] ethics
    - [ ] ux
    - [ ] maintenance
    """), encoding="utf-8")
PYEOF

unset WG_CHALLENGE_GATE
result=$(write_guard "src/payments/processor.py")
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision') == 'deny', f'Expected deny, got: {d}'
r = out.get('permissionDecisionReason', '').lower()
assert 'dissent vectors covered' in r or 'convergence collapse' in r, f'Got: {r}'
print('PASS: under-3 vectors blocked')
"

export WG_CHALLENGE_GATE=off
result=$(write_guard "src/payments/processor.py")
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow') != 'deny', f'Got: {d}'
print('PASS: WG_CHALLENGE_GATE=off bypasses the gate')
"
unset WG_CHALLENGE_GATE
```

**Expected**: two `PASS:` lines.

## Success Criteria

- [ ] Step 1: well-formed v2 → allowed
- [ ] Step 2: missing → deny names `challenge-artifacts.md`, `contrarian`, `WG_CHALLENGE_GATE`
- [ ] Step 3: 1-vector → deny mentions vectors/collapse; bypass allows it

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys, shutil
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
(projects_root / f'{project}.json').unlink(missing_ok=True)
shutil.rmtree(projects_root / project, ignore_errors=True)
"
unset CLAUDE_PROJECT_NAME WG_CHALLENGE_GATE TEST_PROJECT PROJECT_DIR PLUGIN_ROOT
```
