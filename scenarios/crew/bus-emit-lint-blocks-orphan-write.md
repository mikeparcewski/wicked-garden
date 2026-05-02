---
name: bus-emit-lint-blocks-orphan-write
title: Bus-Emit Lint — Strict Mode Blocks Orphan Writes to Load-Bearing Artifacts
description: Verifies WG_BUS_EMIT_LINT detects writes to gate-result.json / dispatch-log.jsonl / conditions-manifest.json / reviewer-report.md without a recent bus emit; warn mode emits systemMessage, strict mode denies, off bypasses (#734 part B)
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Bus-Emit Lint — Orphan Write Detection

The bus-emit lint (#734 Part B) catches writes to load-bearing crew state
artifacts that are NOT accompanied by a recent `wicked-bus` emit on the
project's chain. This scenario asserts the three-mode contract:

- `WG_BUS_EMIT_LINT=off` — disabled
- `WG_BUS_EMIT_LINT=warn` (default) — `systemMessage` finding, write proceeds
- `WG_BUS_EMIT_LINT=strict` — write denied

Detection runs against the daemon's `event_log` table (read-only). A write
is considered "paired" if there is any event whose `chain_id` starts with
`{active_project_id}.` and whose `ingested_at >= now - WG_BUS_EMIT_LINT_WINDOW_SEC`
(default 60).

## Setup

```bash
export TEST_PROJECT="bus-emit-lint-demo"
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export CLAUDE_PROJECT_NAME="wg-scenario-bus-emit-lint"
export TEST_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bus-emit-lint-'))
")
export WG_DAEMON_DB="${TEST_DIR}/projections.db"
echo "TEST_DIR=${TEST_DIR}"

# Provision an active crew project for _find_active_crew_project to return.
sh "${PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
project_dir = projects_root / project
project_dir.mkdir(parents=True, exist_ok=True)
data = {
    "id": project, "name": project,
    "workspace": os.environ['CLAUDE_PROJECT_NAME'],
    "complexity_score": 7, "current_phase": "build",
}
(projects_root / f"{project}.json").write_text(json.dumps(data, indent=2))
(project_dir / "project.json").write_text(json.dumps(data, indent=2))
print(f"PROJECT_DIR={project_dir}")
PYEOF

# Seed an empty event_log — no emits exist for this project.
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sqlite3
conn = sqlite3.connect('${WG_DAEMON_DB}')
conn.executescript('''CREATE TABLE event_log (event_id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, chain_id TEXT, payload_json TEXT NOT NULL, projection_status TEXT NOT NULL, error_message TEXT, ingested_at INTEGER NOT NULL);''')
conn.commit(); conn.close()
print('seeded empty event_log')
"
```

**Expected**: `TEST_DIR=...` and `seeded empty event_log` printed.

## Helper

```bash
write_guard() {
  sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
os.environ['CLAUDE_PLUGIN_ROOT'] = '${PLUGIN_ROOT}'
from pre_tool import _handle_write_guard
print(_handle_write_guard({'file_path': '$1', 'content': 'x'}))
"
}
```

## Step 1: Default mode (warn) on a target file → systemMessage, write proceeds

```bash
unset WG_BUS_EMIT_LINT  # default = warn
result=$(write_guard "${TEST_DIR}/${TEST_PROJECT}/phases/build/gate-result.json")
echo "${result}" | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision', 'allow') != 'deny', f'expected allow in warn mode: {d}'
sm = d.get('systemMessage', '')
assert 'bus-emit lint' in sm.lower(), f'expected lint warning in systemMessage: {sm!r}'
assert 'WG_BUS_EMIT_LINT=off' in sm, 'expected bypass instruction in message'
print('PASS warn: systemMessage attached, write allowed')
"
```

**Expected**: `PASS warn: systemMessage attached, write allowed`

## Step 2: Strict mode → write denied

```bash
export WG_BUS_EMIT_LINT=strict
result=$(write_guard "${TEST_DIR}/${TEST_PROJECT}/phases/build/dispatch-log.jsonl")
echo "${result}" | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision') == 'deny', f'expected deny in strict mode: {d}'
reason = out.get('permissionDecisionReason', '')
assert 'bus-emit lint' in reason.lower(), f'expected lint reason: {reason!r}'
print('PASS strict: write denied with bus-emit lint reason')
"
unset WG_BUS_EMIT_LINT
```

**Expected**: `PASS strict: write denied with bus-emit lint reason`

## Step 3: Off mode → no lint at all

```bash
export WG_BUS_EMIT_LINT=off
result=$(write_guard "${TEST_DIR}/${TEST_PROJECT}/phases/build/gate-result.json")
echo "${result}" | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision', 'allow') != 'deny', f'expected allow: {d}'
sm = d.get('systemMessage', '')
assert 'bus-emit lint' not in sm.lower(), f'lint should be off, got: {sm!r}'
print('PASS off: lint disabled, no message attached')
"
unset WG_BUS_EMIT_LINT
```

**Expected**: `PASS off: lint disabled, no message attached`

## Step 4: Recent emit on the project's chain → strict allows the write

A real emit on `{project_id}.build` within the window must satisfy the lint
even in strict mode. This proves the lint distinguishes orphan writes from
properly-paired ones.

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sqlite3, time
conn = sqlite3.connect('${WG_DAEMON_DB}')
conn.execute('INSERT INTO event_log (event_id,event_type,chain_id,payload_json,projection_status,ingested_at) VALUES (?,?,?,?,?,?)',
    (1, 'wicked.gate.decided', '${TEST_PROJECT}.build',
     '{}', 'applied', int(time.time())))
conn.commit(); conn.close()
print('seeded recent emit')
"

export WG_BUS_EMIT_LINT=strict
result=$(write_guard "${TEST_DIR}/${TEST_PROJECT}/phases/build/gate-result.json")
echo "${result}" | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision', 'allow') != 'deny', f'recent emit should satisfy lint: {d}'
sm = d.get('systemMessage', '')
assert 'bus-emit lint' not in sm.lower(), f'should be no warning: {sm!r}'
print('PASS strict + recent emit: write allowed')
"
unset WG_BUS_EMIT_LINT
```

**Expected**: `PASS strict + recent emit: write allowed`

## Step 5: Non-target path (e.g. status.md) is NEVER linted

```bash
export WG_BUS_EMIT_LINT=strict
result=$(write_guard "${TEST_DIR}/${TEST_PROJECT}/phases/build/status.md")
echo "${result}" | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision', 'allow') != 'deny', f'non-target should never deny: {d}'
sm = d.get('systemMessage', '')
assert 'bus-emit lint' not in sm.lower(), f'non-target should not lint: {sm!r}'
print('PASS non-target: lint did not fire')
"
unset WG_BUS_EMIT_LINT
```

**Expected**: `PASS non-target: lint did not fire`

## Success Criteria

- [ ] Step 1: warn mode emits `systemMessage` containing `bus-emit lint` and bypass instruction; write proceeds
- [ ] Step 2: strict mode denies the write with a `bus-emit lint` reason
- [ ] Step 3: `WG_BUS_EMIT_LINT=off` disables the lint entirely
- [ ] Step 4: a recent emit on `{project}.{phase}` within `WG_BUS_EMIT_LINT_WINDOW_SEC` satisfies even strict mode
- [ ] Step 5: only the four target suffixes (`gate-result.json`, `dispatch-log.jsonl`, `conditions-manifest.json`, `reviewer-report.md`) are linted

## Cleanup

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys, shutil
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
(projects_root / f'{project}.json').unlink(missing_ok=True)
shutil.rmtree(projects_root / project, ignore_errors=True)
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset CLAUDE_PROJECT_NAME WG_BUS_EMIT_LINT WG_BUS_EMIT_LINT_WINDOW_SEC
unset WG_DAEMON_DB TEST_PROJECT TEST_DIR PLUGIN_ROOT
```
