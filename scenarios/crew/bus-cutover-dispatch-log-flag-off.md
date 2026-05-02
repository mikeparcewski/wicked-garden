---
name: bus-cutover-dispatch-log-flag-off
title: Bus-cutover Site 1 — flag-off produces byte-identical disk file and zero rows
description: Validates Council Condition C2 — when WG_BUS_AS_TRUTH_DISPATCH_LOG is unset (default) the dispatch_log.append() path writes the on-disk JSONL and the projector handler is a no-op. The dispatch_log_entries table stays empty.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 1 — Flag-off

This scenario asserts the C2 byte-identity contract: under the default
flag-off mode, dispatch-log behaviour is byte-for-byte identical to
pre-cutover code. Disk file written, bus emit fired (or skipped if bus
unavailable), projector handler runs as a no-op.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-disp-off-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Append a dispatch entry with flag unset

```bash
unset WG_BUS_AS_TRUTH_DISPATCH_LOG
WICKED_BUS_DISABLED=1 sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
dispatch_log._reset_state_for_tests()
dispatch_log.set_hmac_secret("scenario-flag-off-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-off"
(project_dir / "phases" / "design").mkdir(parents=True)
dispatch_log.append(
    project_dir, "design",
    reviewer="security-engineer",
    gate="design-quality",
    dispatch_id="d-flag-off-1",
    dispatched_at="2026-04-19T10:00:00+00:00",
)
log = (project_dir / "phases" / "design" / "dispatch-log.jsonl").read_text(encoding="utf-8")
print("LINES=" + str(len(log.splitlines())))
print(log.strip())
PYEOF
```

**Expected**: `LINES=1` followed by one JSONL line containing
`"reviewer":"security-engineer"` and `"hmac":...`.

## Step 2: Compute the disk-file SHA-256 baseline

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
p = pathlib.Path('${TEST_DIR}/proj-flag-off/phases/design/dispatch-log.jsonl')
sha = hashlib.sha256(p.read_bytes()).hexdigest()
print('SHA256=' + sha)
" | tee "${TEST_DIR}/baseline-sha.txt"
```

## Step 3: Repeat the append in a fresh project with flag explicitly off

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=off WICKED_BUS_DISABLED=1 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, hashlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
dispatch_log._reset_state_for_tests()
dispatch_log.set_hmac_secret("scenario-flag-off-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-off-explicit"
(project_dir / "phases" / "design").mkdir(parents=True)
dispatch_log.append(
    project_dir, "design",
    reviewer="security-engineer",
    gate="design-quality",
    dispatch_id="d-flag-off-1",
    dispatched_at="2026-04-19T10:00:00+00:00",
)
sha = hashlib.sha256(
    (project_dir / "phases" / "design" / "dispatch-log.jsonl").read_bytes()
).hexdigest()
print("SHA256=" + sha)
PYEOF
```

**Expected**: same `SHA256=` line as Step 2 — Council C2 byte-identity
contract: `unset` and `off` produce identical disk bytes.

## Step 4: Verify projector handler is a no-op when flag is off

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
from daemon.db import connect, init_schema
from daemon.projector import project_event
conn = connect(":memory:")
init_schema(conn)
event = {
    "event_id": 1,
    "event_type": "wicked.dispatch.log_entry_appended",
    "created_at": 1_700_000_000,
    "payload": {
        "project_id": "proj-flag-off",
        "phase": "design",
        "gate": "design-quality",
        "reviewer": "security-engineer",
        "dispatch_id": "d-flag-off-1",
        "dispatcher_agent": "wicked-garden:crew:phase-manager",
        "expected_result_path": "phases/design/gate-result.json",
        "dispatched_at": "2026-04-19T10:00:00+00:00",
        "hmac": "deadbeef" * 8,
        "hmac_present": True,
        "raw_payload": json.dumps({"reviewer": "security-engineer"}),
    },
}
status = project_event(conn, event)
count = conn.execute("SELECT COUNT(*) FROM dispatch_log_entries").fetchone()[0]
assert status == "applied", f"expected applied, got {status}"
assert count == 0, f"C2 violation: flag-off wrote {count} row(s) to dispatch_log_entries"
print(f"PASS: status={status}, dispatch_log_entries rows={count}")
PYEOF
```

**Expected**: `PASS: status=applied, dispatch_log_entries rows=0`

## Success Criteria

- [ ] Step 1 writes one JSONL line with reviewer + hmac
- [ ] Step 2 records the baseline SHA-256
- [ ] Step 3 produces the same SHA-256 — proves byte-identity (Council C2)
- [ ] Step 4 returns `status=applied` and 0 rows in `dispatch_log_entries`

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_DISPATCH_LOG WICKED_BUS_DISABLED
```
