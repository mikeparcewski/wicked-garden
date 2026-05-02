---
name: consensus-chain-id-uniqueness
title: Bus-cutover Site 2 — chain_id includes eval_id so retried consensus evals do not dedupe
description: Validates Council Condition C9 — two consensus evals on the same (project, phase) with distinct eval_ids produce distinct chain_ids, so the bus dedupe ledger does NOT collapse them. The projector lands both as separate rows in `consensus_reports`. The OLD chain_id format `f"{project_id}.{phase}"` would have collided.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 2 — chain_id Uniqueness

This scenario asserts the C9 latent-bug fix.  Before this PR the chain_id
emitted by `_write_consensus_report` and `_write_consensus_evidence` was
`f"{project_id}.{phase}"`, which collapsed retries on the bus dedupe
ledger (`_bus.is_processed` keyed on `(event_type, chain_id)`).  After the
fix the chain_ids are:

  * report   → `f"{project_id}.{phase}.consensus.{eval_id}"`
  * evidence → `f"{project_id}.{phase}.consensus.{eval_id}.evidence"`

Each retry mints a fresh `eval_id` so distinct evals land as distinct
ledger keys AND distinct projection rows.  The `.evidence` discriminator
on the second chain_id keeps report and evidence within the SAME eval
distinct from each other.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-cons-chain-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Two consensus reports on the same phase, distinct eval_ids → distinct chain_ids

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report
from jam.consensus import ConsensusResult, DissentingView
import _bus

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[], dissenting_views=[], open_questions=[],
    rounds=1, participants=3,
)

captured = []
def _fake_emit(event_type, payload, chain_id=None, metadata=None):
    captured.append({"chain_id": chain_id, "event_type": event_type})

with patch.object(_bus, "emit_event", side_effect=_fake_emit):
    project_dir = pathlib.Path("${TEST_DIR}") / "proj-chain"
    _write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="eval-1-id")
    # Second eval — same (project, phase) but different eval_id.
    _write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="eval-2-id")

assert len(captured) == 2
chain_ids = [c["chain_id"] for c in captured]
assert chain_ids[0] == "proj-chain.design.consensus.eval-1-id"
assert chain_ids[1] == "proj-chain.design.consensus.eval-2-id"
assert chain_ids[0] != chain_ids[1], (
    "C9 violation: chain_ids collide for distinct eval_ids — "
    "the bus dedupe ledger would drop the second emit."
)

# Pin the OLD format would have collided.
old_format = ["proj-chain.design", "proj-chain.design"]
assert old_format[0] == old_format[1], (
    "Setup invariant: OLD format MUST collapse — that's the bug C9 fixes."
)
print(f"PASS: distinct chain_ids — {chain_ids[0]!r} vs {chain_ids[1]!r}")
PYEOF
```

**Expected**: `PASS: distinct chain_ids — 'proj-chain.design.consensus.eval-1-id' vs 'proj-chain.design.consensus.eval-2-id'`

## Step 2: Report and evidence within the SAME eval are distinguished by `.evidence`

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report, _write_consensus_evidence
from jam.consensus import ConsensusResult, DissentingView
import _bus

result = ConsensusResult(
    decision="REJECT", confidence=0.45,
    consensus_points=[], dissenting_views=[], open_questions=[],
    rounds=1, participants=3,
)

captured = []
def _fake_emit(event_type, payload, chain_id=None, metadata=None):
    captured.append({"chain_id": chain_id, "event_type": event_type})

with patch.object(_bus, "emit_event", side_effect=_fake_emit):
    project_dir = pathlib.Path("${TEST_DIR}") / "proj-chain-report-vs-evidence"
    _write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.45}, eval_id="shared-eval-id")
    _write_consensus_evidence(project_dir, "design", {
        "result": "REJECT", "reason": "dissent", "consensus_confidence": 0.45,
        "agreement_ratio": 0.45, "dissenting_views": [], "participants": 5,
        "eval_id": "shared-eval-id",
    })

assert len(captured) == 2
report_chain = captured[0]["chain_id"]
evidence_chain = captured[1]["chain_id"]
assert report_chain == "proj-chain-report-vs-evidence.design.consensus.shared-eval-id"
assert evidence_chain == "proj-chain-report-vs-evidence.design.consensus.shared-eval-id.evidence"
assert report_chain != evidence_chain, (
    "C9 violation: report and evidence within the same eval landed on the "
    "same chain_id — they would dedupe against each other on the bus ledger."
)
print(f"PASS: report and evidence chain_ids differ within same eval — {report_chain!r} vs {evidence_chain!r}")
PYEOF
```

**Expected**: `PASS: report and evidence chain_ids differ within same eval — 'proj-chain-report-vs-evidence.design.consensus.shared-eval-id' vs 'proj-chain-report-vs-evidence.design.consensus.shared-eval-id.evidence'`

## Step 3: Project both events and verify two distinct rows land

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event

def _make(event_id, eval_id):
    payload = {
        "project_id": "proj-chain-uniq", "phase": "design",
        "decision": "APPROVE", "confidence": 0.85,
        "agreement_ratio": 0.85, "participants": 3, "rounds": 1,
        "eval_id": eval_id,
        "raw_payload": json.dumps({"phase": "design", "eval_id": eval_id}, indent=2),
    }
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.report_created",
        "chain_id": f"proj-chain-uniq.design.consensus.{eval_id}",
        "created_at": 1_700_000_000 + event_id,
        "payload": payload,
    }

conn = connect(":memory:")
init_schema(conn)
for ev in (_make(1, "eval-A"), _make(2, "eval-B")):
    conn.execute(
        "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ev["event_id"], ev["event_type"], ev["chain_id"], json.dumps(ev["payload"]), "pending", ev["created_at"]),
    )
    project_event(conn, ev)

rows = conn.execute(
    "SELECT event_id FROM consensus_reports WHERE project_id='proj-chain-uniq' AND phase='design' ORDER BY event_id"
).fetchall()
assert [r["event_id"] for r in rows] == [1, 2], f"expected [1, 2], got {[r['event_id'] for r in rows]}"
print(f"PASS: two distinct rows landed for two evals — event_ids={[r['event_id'] for r in rows]}")
PYEOF
```

**Expected**: `PASS: two distinct rows landed for two evals — event_ids=[1, 2]`

## Success Criteria

- [ ] Step 1 emits two distinct chain_ids for two distinct eval_ids on the same phase
- [ ] Step 2 confirms report and evidence within the same eval have different chain_ids
- [ ] Step 3 projects both events as separate rows in `consensus_reports`

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_CONSENSUS_REPORT
```
