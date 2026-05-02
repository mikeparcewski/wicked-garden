---
name: consensus-bus-cutover-flag-on-evidence
title: Bus-cutover Site 2 — evidence flag on (REJECT path), projector populates consensus_evidence
description: Validates Council Conditions C5/C6/C10 on the evidence side — under WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on the projector handler INSERT OR IGNOREs one row per event_id and stores raw_payload verbatim. Evidence emits only fire on REJECT outcomes.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 2 — Evidence Flag-on

This scenario asserts the evidence-side cutover contract.  Evidence emits
ONLY fire on consensus REJECT, so the test path threads a REJECT outcome
through `_write_consensus_evidence`.  The flags are independent of the
report flag (Council Condition C5).

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-cons-on-evd-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Write a consensus REJECT and capture the evidence emit

```bash
WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, json
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_evidence
import _bus

project_dir = pathlib.Path("${TEST_DIR}") / "proj-evd-on"
captured = []
def _fake_emit(event_type, payload, chain_id=None, metadata=None):
    captured.append({"event_type": event_type, "payload": payload, "chain_id": chain_id})

consensus_result = {
    "result": "REJECT",
    "reason": "Strong dissent on credential rotation cadence",
    "consensus_confidence": 0.45,
    "agreement_ratio": 0.45,
    "dissenting_views": [
        {"persona": "security-engineer", "view": "JWT rotation cadence undefined", "strength": "strong"},
    ],
    "participants": 5,
    "eval_id": "abcdef123456",
}
with patch.object(_bus, "emit_event", side_effect=_fake_emit):
    _write_consensus_evidence(project_dir, "design", consensus_result)

assert len(captured) == 1, f"expected 1 emit, got {len(captured)}"
emit = captured[0]
assert emit["event_type"] == "wicked.consensus.evidence_recorded"
# Council C9: evidence chain_id includes ".evidence" discriminator on top of eval_id.
assert emit["chain_id"] == "proj-evd-on.design.consensus.abcdef123456.evidence"
assert "raw_payload" in emit["payload"]
disk = (project_dir / "phases" / "design" / "consensus-evidence.json").read_text()
assert emit["payload"]["raw_payload"] == disk, "raw_payload diverges from on-disk file"
emit_path = pathlib.Path("${TEST_DIR}") / "captured-emit.json"
emit_path.write_text(json.dumps(emit, default=str))
print(f"PASS: evidence emit captured, chain_id={emit['chain_id']}")
PYEOF
```

**Expected**: `PASS: evidence emit captured, chain_id=proj-evd-on.design.consensus.abcdef123456.evidence`

## Step 2: Project the captured emit and verify the row

```bash
WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event

emit = json.loads(pathlib.Path("${TEST_DIR}/captured-emit.json").read_text())
event = {
    "event_id": 7,
    "event_type": "wicked.consensus.evidence_recorded",
    "chain_id": emit["chain_id"],
    "created_at": 1_700_000_007,
    "payload": emit["payload"],
}

conn = connect(":memory:")
init_schema(conn)
conn.execute(
    "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (7, event["event_type"], event["chain_id"], json.dumps(event["payload"]), "pending", 1_700_000_007),
)
status = project_event(conn, event)

rows = conn.execute(
    "SELECT event_id, project_id, phase, result, reason, consensus_confidence, "
    "agreement_ratio, participants, raw_payload FROM consensus_evidence"
).fetchall()
assert status == "applied", f"expected applied, got {status}"
assert len(rows) == 1
row = rows[0]
assert row["result"] == "REJECT"
assert row["reason"] == "Strong dissent on credential rotation cadence"
assert row["participants"] == 5
disk = (pathlib.Path("${TEST_DIR}") / "proj-evd-on" / "phases" / "design" / "consensus-evidence.json").read_text()
assert row["raw_payload"] == disk
print(f"PASS: evidence row landed, raw_payload matches disk ({len(row['raw_payload'])} bytes)")
PYEOF
```

**Expected**: `PASS: evidence row landed, raw_payload matches disk (...)`

## Step 3: Verify report flag stays independent (Council C5)

```bash
WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
os.environ.pop("WG_BUS_AS_TRUTH_CONSENSUS_REPORT", None)
from daemon.db import connect, init_schema
from daemon.projector import project_event

# Synthesize a report event under the evidence flag — the report handler
# MUST stay no-op because its own flag is off.
report_event = {
    "event_id": 8, "event_type": "wicked.consensus.report_created",
    "chain_id": "p.design.consensus.x", "created_at": 1_700_000_008,
    "payload": {
        "project_id": "p", "phase": "design", "decision": "APPROVE",
        "confidence": 0.9, "agreement_ratio": 0.9, "participants": 3, "rounds": 1,
        "raw_payload": json.dumps({"phase": "design"}, indent=2),
    },
}
conn = connect(":memory:")
init_schema(conn)
conn.execute(
    "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (8, report_event["event_type"], report_event["chain_id"], json.dumps(report_event["payload"]), "pending", 1_700_000_008),
)
project_event(conn, report_event)
rows = conn.execute("SELECT COUNT(*) FROM consensus_reports WHERE event_id = 8").fetchone()[0]
assert rows == 0, "C5 violation: evidence flag enabled the report handler"
print("PASS: report flag stays independent — 0 report rows under evidence flag-on")
PYEOF
```

**Expected**: `PASS: report flag stays independent — 0 report rows under evidence flag-on`

## Success Criteria

- [ ] Step 1 captures the evidence emit with the `.evidence` chain_id discriminator
- [ ] Step 2 projects one row in `consensus_evidence`, raw_payload byte-for-byte matches disk
- [ ] Step 3 confirms the two flags are independent (Council C5)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE
```
