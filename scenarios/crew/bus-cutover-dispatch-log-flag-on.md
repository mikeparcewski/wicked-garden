---
name: bus-cutover-dispatch-log-flag-on
title: Bus-cutover Site 1 — flag-on writes disk file AND projection row with HMAC
description: Validates Council Conditions C3, C6, C7 — under WG_BUS_AS_TRUTH_DISPATCH_LOG=on the dispatch_log.append() path writes the on-disk JSONL AND the projector handler writes a row to dispatch_log_entries with the HMAC stored verbatim. Orphan check still passes against the disk file.
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Bus-cutover Site 1 — Flag-on

This scenario asserts the C3 dual-write contract under flag-on: disk
file is still written (one full release of dual-write before deletion),
projector handler writes a row to `dispatch_log_entries` with HMAC
stored verbatim (C7), and the existing orphan check
(`dispatch_log.check_orphan` at `:476-547`) still validates against the
on-disk JSONL — read-side stays disk-based per C7.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-disp-on-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Append under flag-on, capture the in-memory record

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on WICKED_BUS_DISABLED=1 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
dispatch_log._reset_state_for_tests()
dispatch_log.set_hmac_secret("scenario-flag-on-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-on"
(project_dir / "phases" / "design").mkdir(parents=True)
dispatch_log.append(
    project_dir, "design",
    reviewer="security-engineer",
    gate="design-quality",
    dispatch_id="d-flag-on-1",
    dispatched_at="2026-04-19T10:00:00+00:00",
)
log_path = project_dir / "phases" / "design" / "dispatch-log.jsonl"
record = json.loads(log_path.read_text(encoding="utf-8").strip())
print("HMAC=" + record["hmac"])
print("DISPATCH_ID=" + record["dispatch_id"])
print("DISK_FILE_EXISTS=" + str(log_path.is_file()))
PYEOF
```

**Expected**: `HMAC=<64-hex-chars>`, `DISPATCH_ID=d-flag-on-1`,
`DISK_FILE_EXISTS=True` — flag-on still writes the disk file (C3 step 3).

## Step 2: Project the synthesized event under flag-on

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event

# Re-read the on-disk record so the emit payload matches reality.
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-on"
log_path = project_dir / "phases" / "design" / "dispatch-log.jsonl"
record = json.loads(log_path.read_text(encoding="utf-8").strip())

conn = connect(":memory:")
init_schema(conn)
event = {
    "event_id": 7,
    "event_type": "wicked.dispatch.log_entry_appended",
    "created_at": 1_700_000_000,
    "payload": {
        "project_id": "proj-flag-on",
        "phase": "design",
        "gate": "design-quality",
        "reviewer": record["reviewer"],
        "dispatch_id": record["dispatch_id"],
        "dispatcher_agent": record["dispatcher_agent"],
        "expected_result_path": record["expected_result_path"],
        "dispatched_at": record["dispatched_at"],
        "hmac": record["hmac"],
        "hmac_present": True,
        "raw_payload": json.dumps(record, separators=(",", ":")),
    },
}
status = project_event(conn, event)
row = conn.execute(
    "SELECT event_id, hmac, hmac_present, dispatch_id, raw_payload "
    "FROM dispatch_log_entries WHERE event_id = 7"
).fetchone()
assert status == "applied", f"expected applied, got {status}"
assert row is not None, "C3+C6 violation: no row written under flag-on"
assert row["hmac"] == record["hmac"], (
    f"C7 violation: HMAC mismatch — emit signed {record['hmac']}, projector stored {row['hmac']}"
)
assert row["hmac_present"] == 1, "C7: hmac_present must be stored verbatim"
assert row["dispatch_id"] == record["dispatch_id"]
roundtripped = json.loads(row["raw_payload"])
assert roundtripped["reviewer"] == record["reviewer"]
print(f"PASS: row inserted, hmac={row['hmac'][:16]}..., dispatch_id={row['dispatch_id']}")
PYEOF
```

**Expected**: `PASS: row inserted, hmac=<16-hex>..., dispatch_id=d-flag-on-1`

## Step 3: Orphan check still passes against the disk file (C7 read-side)

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on WG_GATE_RESULT_STRICT_AFTER=2099-01-01 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
dispatch_log.set_hmac_secret("scenario-flag-on-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-on"
parsed = {
    "reviewer": "security-engineer",
    "recorded_at": "2026-04-19T11:00:00+00:00",
    "gate": "design-quality",
}
# Should NOT raise — disk-based orphan check unchanged under flag-on per C7.
dispatch_log.check_orphan(parsed, project_dir, "design")
print("PASS: disk-based orphan check still validates under flag-on")
PYEOF
```

**Expected**: `PASS: disk-based orphan check still validates under flag-on`

## Success Criteria

- [ ] Step 1 produces a disk JSONL file with HMAC + dispatch_id
- [ ] Step 2 projector inserts a row with HMAC stored verbatim (C7)
- [ ] Step 3 orphan check still passes against the disk file (C7 read-side)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_DISPATCH_LOG WICKED_BUS_DISABLED WG_GATE_RESULT_STRICT_AFTER
```
