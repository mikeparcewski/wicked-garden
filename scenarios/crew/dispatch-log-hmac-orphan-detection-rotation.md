---
name: dispatch-log-hmac-orphan-detection-rotation
title: Dispatch Log HMAC Authentication, Orphan Detection, and Log Rotation (AC-7, PR #513)
description: Verify dispatch-log append writes HMAC-signed entries, orphan detection flags gate-results without matching entries, and log rotation fires at 10MB
type: testing
difficulty: advanced
estimated_minutes: 15
covers:
  - "#516 — dispatch-log HMAC + orphan detection + rotation"
  - AC-7 (orphan detection — gate-result without dispatch entry → CONDITIONAL)
  - "#500 (HMAC authentication for dispatch log)"
  - "#471 (dispatch log)"
ac_ref: "v6.2 PR #513, PR #500, PR #471 | scripts/crew/dispatch_log.py"
---

# Dispatch Log HMAC Authentication, Orphan Detection, and Log Rotation

This scenario tests `scripts/crew/dispatch_log.py`:

1. **Append** writes a JSON line with an HMAC-SHA256 `hmac` field.
2. **Orphan detection** (`check_orphan`) — a gate-result.json with no matching dispatch
   entry → CONDITIONAL gate finding.
3. **Log rotation** — when the dispatch log file exceeds 10 MB it is compressed to
   `dispatch-log.jsonl.gz` and a fresh log begins.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="dispatch-log-test"
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/build"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 3,
    'rigor_tier': 'standard',
    'current_phase': 'build',
    'phase_plan': ['clarify', 'build', 'review']
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written')
"
```

```bash
Run: test -f "${PROJECT_DIR}/project.json" && echo "PASS: project ready"
Assert: PASS: project ready
```

---

## Case 1: Append writes HMAC-signed dispatch entry

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, hmac as hmaclib, hashlib, json, pathlib, secrets
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from dispatch_log import append_dispatch, load_dispatch_log

secret = secrets.token_hex(32)
project_dir = pathlib.Path('${PROJECT_DIR}')
log_path = project_dir / 'dispatch-log.jsonl'

entry = append_dispatch(
    project_dir=project_dir,
    phase='build',
    reviewer='senior-engineer',
    session_id='test-session-001',
    hmac_secret=secret
)

assert log_path.exists(), f'dispatch-log.jsonl not created at {log_path}'

lines = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
assert len(lines) >= 1, 'Expected at least 1 entry'
record = lines[-1]

assert 'hmac' in record, f'HMAC field missing from dispatch entry: {record}'
assert record['phase'] == 'build', f'phase mismatch: {record[\"phase\"]}'
assert record['reviewer'] == 'senior-engineer', f'reviewer mismatch'

# Verify HMAC integrity
record_copy = {k: v for k, v in record.items() if k != 'hmac'}
expected_hmac = hmaclib.new(
    secret.encode(), json.dumps(record_copy, sort_keys=True).encode(), hashlib.sha256
).hexdigest()
assert record['hmac'] == expected_hmac, 'HMAC mismatch — entry may have been tampered'

print(f'PASS: dispatch entry appended with valid HMAC ({record[\"hmac\"][:16]}...)')
" 2>&1
Assert: PASS: dispatch entry appended with valid HMAC
```

---

## Case 2: Orphan detection — gate-result without dispatch entry → CONDITIONAL

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from dispatch_log import check_orphan

project_dir = pathlib.Path('${PROJECT_DIR}')

# Write a gate-result.json for a reviewer that has NO dispatch entry
orphan_gr = {
    'result': 'APPROVE',
    'score': 0.85,
    'reviewer': 'orphan-reviewer',
    'phase': 'build',
    'session_id': 'test-session-orphan'
}
gr_path = project_dir / 'phases' / 'build' / 'orphan-gate-result.json'
gr_path.write_text(json.dumps(orphan_gr))

result = check_orphan(
    project_dir=project_dir,
    phase='build',
    reviewer='orphan-reviewer',
    session_id='test-session-orphan'
)

# Should detect orphan (no matching dispatch entry) and return CONDITIONAL
assert result.get('verdict') in ('CONDITIONAL', 'REJECT'), (
    f'Expected CONDITIONAL or REJECT for orphan gate-result, got: {result}'
)
print(f'PASS: orphan detected — verdict={result[\"verdict\"]}')
print(f'  reason: {result.get(\"reason\", \"(none)\")}')
" 2>&1
Assert: PASS: orphan detected — verdict=CONDITIONAL (or REJECT)
```

---

## Case 3: Matched entry — orphan check passes

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib, secrets
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from dispatch_log import append_dispatch, check_orphan

project_dir = pathlib.Path('${PROJECT_DIR}')
secret = secrets.token_hex(32)

# First append a proper dispatch entry for 'senior-engineer'
append_dispatch(
    project_dir=project_dir,
    phase='build',
    reviewer='senior-engineer',
    session_id='test-session-matched',
    hmac_secret=secret
)

# Now orphan check for the matched reviewer should pass (no orphan)
result = check_orphan(
    project_dir=project_dir,
    phase='build',
    reviewer='senior-engineer',
    session_id='test-session-matched',
    hmac_secret=secret
)

assert result.get('verdict') == 'ok', (
    f'Expected verdict=ok for matched entry, got: {result}'
)
print(f'PASS: matched dispatch entry — orphan check passed (verdict=ok)')
" 2>&1
Assert: PASS: matched dispatch entry — orphan check passed (verdict=ok)
```

---

## Case 4: Log rotation at 10 MB

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, pathlib, json, secrets, gzip
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from dispatch_log import append_dispatch, ROTATION_THRESHOLD_BYTES

project_dir = pathlib.Path('${PROJECT_DIR}')
log_path = project_dir / 'dispatch-log.jsonl'
rotated_path = project_dir / 'dispatch-log.jsonl.gz'

# Pre-fill the log to just over the rotation threshold
filler = ('x' * 1023 + '\n') * 1  # 1KB block
chunks_needed = (ROTATION_THRESHOLD_BYTES // 1024) + 2
log_path.write_text(filler * chunks_needed)
print(f'  Pre-filled dispatch-log to {log_path.stat().st_size} bytes (threshold={ROTATION_THRESHOLD_BYTES})')

# Append a new entry — this should trigger rotation
append_dispatch(
    project_dir=project_dir,
    phase='build',
    reviewer='rotation-test-reviewer',
    session_id='rotation-test-session',
    hmac_secret=secrets.token_hex(32)
)

assert rotated_path.exists(), f'Expected rotated .gz file at {rotated_path}'
assert log_path.exists(), f'Fresh log not created after rotation at {log_path}'

# Verify the fresh log only has the new entry (post-rotation)
new_lines = [l for l in log_path.read_text().splitlines() if l.strip()]
assert len(new_lines) >= 1, 'Fresh log after rotation should have at least 1 entry'

print(f'PASS: log rotated to {rotated_path.name}, fresh log has {len(new_lines)} entry/entries')

# Verify .gz is readable
with gzip.open(rotated_path, 'rt') as gz:
    content = gz.read()
assert len(content) > 0, 'Rotated .gz file is empty'
print(f'PASS: rotated .gz is non-empty and readable')
" 2>&1
Assert: PASS: log rotated to dispatch-log.jsonl.gz, fresh log has 1 entry
Assert: PASS: rotated .gz is non-empty and readable
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

## Success Criteria

- [ ] `append_dispatch` writes HMAC-signed JSON lines to `dispatch-log.jsonl`
- [ ] HMAC field matches `hmac-sha256(secret, record_json)` independently recomputed
- [ ] `check_orphan` returns `CONDITIONAL` (or `REJECT`) for gate-results with no matching entry
- [ ] `check_orphan` returns `verdict=ok` when a matching, valid dispatch entry exists
- [ ] Log rotation fires when file size exceeds `ROTATION_THRESHOLD_BYTES` (10 MB)
- [ ] Rotated log compressed to `dispatch-log.jsonl.gz`; fresh log created with the triggering entry
