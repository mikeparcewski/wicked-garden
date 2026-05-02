---
name: consensus-bus-cutover-daemon-down
title: Bus-cutover Site 2 — daemon-down with flag-on, disk writes still succeed
description: Validates Council Condition C4 — when the bus / daemon is unavailable AND the cutover flags are on, the consensus_gate disk writes MUST still succeed. The `.write_text()` calls at consensus_gate.py:429 and :490 are KEPT UNCHANGED. Bus emit is observability only this release.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 2 — Daemon-down

This scenario asserts Council Condition C4: even when the daemon is down
(or the bus is unavailable, or the bus emit raises), the consensus disk
writes MUST still complete.  The disk file is source of truth this
release; bus emit is observability only.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-cons-down-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Force the bus emit to raise, then write a consensus report

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, json
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report, _write_consensus_evidence
from jam.consensus import ConsensusResult, DissentingView
import _bus

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[{"point": "approved", "agreement": 3, "of": 3}],
    dissenting_views=[DissentingView(persona="sec", view="rotate", strength="moderate")],
    open_questions=["q?"], rounds=1, participants=3,
)
project_dir = pathlib.Path("${TEST_DIR}") / "proj-down"

def _bus_dead(event_type, payload, chain_id=None, metadata=None):
    raise RuntimeError("simulated bus / daemon down")

with patch.object(_bus, "emit_event", side_effect=_bus_dead):
    _write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="abcdef123456")
    _write_consensus_evidence(project_dir, "design", {
        "result": "REJECT", "reason": "dissent", "consensus_confidence": 0.4,
        "agreement_ratio": 0.4, "dissenting_views": [], "participants": 5,
        "eval_id": "abcdef123456",
    })

# Council Condition C4 — disk writes MUST still succeed.
report_path = project_dir / "phases" / "design" / "consensus-report.json"
evidence_path = project_dir / "phases" / "design" / "consensus-evidence.json"
assert report_path.exists(), "C4 violation: report disk write skipped under bus-down"
assert evidence_path.exists(), "C4 violation: evidence disk write skipped under bus-down"
report_doc = json.loads(report_path.read_text())
evidence_doc = json.loads(evidence_path.read_text())
assert report_doc["decision"] == "APPROVE"
assert evidence_doc["result"] == "REJECT"
print(f"PASS: both disk files written despite bus-down (report={len(report_path.read_bytes())}B, evidence={len(evidence_path.read_bytes())}B)")
PYEOF
```

**Expected**: `PASS: both disk files written despite bus-down (...)`

## Step 2: Same exercise with bus marked unavailable via WICKED_BUS_DISABLED

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=on WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=on \
WICKED_BUS_DISABLED=1 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report, _write_consensus_evidence
from jam.consensus import ConsensusResult, DissentingView

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[], dissenting_views=[], open_questions=[],
    rounds=1, participants=3,
)
project_dir = pathlib.Path("${TEST_DIR}") / "proj-down-disabled"
_write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="abcdef123456")
_write_consensus_evidence(project_dir, "design", {
    "result": "REJECT", "reason": "dissent", "consensus_confidence": 0.4,
    "agreement_ratio": 0.4, "dissenting_views": [], "participants": 5,
    "eval_id": "abcdef123456",
})
assert (project_dir / "phases" / "design" / "consensus-report.json").exists()
assert (project_dir / "phases" / "design" / "consensus-evidence.json").exists()
print("PASS: disk writes succeed when bus is disabled (degrades to today's behavior)")
PYEOF
```

**Expected**: `PASS: disk writes succeed when bus is disabled (degrades to today's behavior)`

## Success Criteria

- [ ] Step 1 writes both disk files even when bus emit raises (C4)
- [ ] Step 2 writes both disk files when WICKED_BUS_DISABLED=1
- [ ] Neither step propagates an exception (fail-open)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_CONSENSUS_REPORT WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE WICKED_BUS_DISABLED
```
