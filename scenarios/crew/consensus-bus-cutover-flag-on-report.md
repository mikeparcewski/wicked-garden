---
name: consensus-bus-cutover-flag-on-report
title: Bus-cutover Site 2 — report flag on, projector populates consensus_reports byte-for-byte
description: Validates Council Conditions C5/C6/C10 — under WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on the projector handler INSERT OR IGNOREs one row per event_id and stores raw_payload verbatim. The raw_payload reproduces the on-disk consensus-report.json byte-for-byte.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 2 — Report Flag-on

This scenario asserts the C5+C6+C10 contract: when the report flag flips,
the projector populates `consensus_reports` and the `raw_payload` field
reproduces the on-disk file byte-for-byte.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-cons-on-rpt-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Write a consensus report and capture the emit payload

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, json
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report
from jam.consensus import ConsensusResult, DissentingView
import _bus

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[{"point": "approved", "agreement": 3, "of": 3}],
    dissenting_views=[DissentingView(persona="sec", view="rotate", strength="moderate")],
    open_questions=["q?"], rounds=1, participants=3,
)
project_dir = pathlib.Path("${TEST_DIR}") / "proj-rpt-on"
captured = []
def _fake_emit(event_type, payload, chain_id=None, metadata=None):
    captured.append({"event_type": event_type, "payload": payload, "chain_id": chain_id})
with patch.object(_bus, "emit_event", side_effect=_fake_emit):
    _write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="abcdef123456")

assert len(captured) == 1, f"expected 1 emit, got {len(captured)}"
emit = captured[0]
assert emit["event_type"] == "wicked.consensus.report_created"
assert emit["chain_id"] == "proj-rpt-on.design.consensus.abcdef123456"
assert "raw_payload" in emit["payload"], "C10 violation: raw_payload missing"
disk = (project_dir / "phases" / "design" / "consensus-report.json").read_text()
assert emit["payload"]["raw_payload"] == disk, "raw_payload diverges from on-disk file"
# Persist the emit payload so Step 2 can replay it through the projector.
emit_path = pathlib.Path("${TEST_DIR}") / "captured-emit.json"
emit_path.write_text(json.dumps(emit, default=str))
print(f"PASS: emit captured, raw_payload={len(emit['payload']['raw_payload'])} bytes, chain_id={emit['chain_id']}")
PYEOF
```

**Expected**: `PASS: emit captured, raw_payload=...`

## Step 2: Project the captured emit and verify the row + raw_payload round-trip

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event

emit = json.loads(pathlib.Path("${TEST_DIR}/captured-emit.json").read_text())
event = {
    "event_id": 1,
    "event_type": "wicked.consensus.report_created",
    "chain_id": emit["chain_id"],
    "created_at": 1_700_000_001,
    "payload": emit["payload"],
}

conn = connect(":memory:")
init_schema(conn)
# Insert event_log parent row (FK requires it).
conn.execute(
    "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (1, event["event_type"], event["chain_id"], json.dumps(event["payload"]), "pending", 1_700_000_001),
)
status = project_event(conn, event)

rows = conn.execute(
    "SELECT event_id, project_id, phase, decision, confidence, agreement_ratio, "
    "participants, rounds, raw_payload FROM consensus_reports"
).fetchall()
assert status == "applied", f"expected applied, got {status}"
assert len(rows) == 1
row = rows[0]
assert row["event_id"] == 1
assert row["project_id"] == "proj-rpt-on"
assert row["phase"] == "design"
assert row["decision"] == "APPROVE"

disk = (pathlib.Path("${TEST_DIR}") / "proj-rpt-on" / "phases" / "design" / "consensus-report.json").read_text()
assert row["raw_payload"] == disk, "C10 violation: raw_payload in DB diverges from on-disk file"
print(f"PASS: 1 row, raw_payload byte-identity holds ({len(row['raw_payload'])} bytes)")
PYEOF
```

**Expected**: `PASS: 1 row, raw_payload byte-identity holds (...)`

## Step 3: Replay the same event — idempotent (Decision #6)

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event

emit = json.loads(pathlib.Path("${TEST_DIR}/captured-emit.json").read_text())
event = {
    "event_id": 99, "event_type": "wicked.consensus.report_created",
    "chain_id": emit["chain_id"], "created_at": 1_700_000_099, "payload": emit["payload"],
}
conn = connect(":memory:")
init_schema(conn)
for i in range(3):
    conn.execute(
        "INSERT OR IGNORE INTO event_log (event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (99, event["event_type"], event["chain_id"], json.dumps(event["payload"]), "pending", 1_700_000_099),
    )
    project_event(conn, event)
rows = conn.execute("SELECT COUNT(*) FROM consensus_reports WHERE event_id = 99").fetchone()[0]
assert rows == 1, f"Decision #6 violation: replay produced {rows} rows"
print("PASS: idempotent on replay (1 row)")
PYEOF
```

**Expected**: `PASS: idempotent on replay (1 row)`

## Success Criteria

- [ ] Step 1 captures one emit with raw_payload matching on-disk file
- [ ] Step 2 projects the emit, lands one row, raw_payload round-trips byte-for-byte
- [ ] Step 3 replays produce a single row (Decision #6)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_CONSENSUS_REPORT
```
