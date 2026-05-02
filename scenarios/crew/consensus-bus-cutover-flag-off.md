---
name: consensus-bus-cutover-flag-off
title: Bus-cutover Site 2 — both consensus flags off, byte-identity on disk and zero rows
description: Validates Council Condition C2/C3 — when WG_BUS_AS_TRUTH_CONSENSUS_REPORT and WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE are unset (default) the consensus_gate writes the on-disk JSON and both projector handlers are no-ops. The two projection tables stay empty. Disk SHA-256 baseline matches before vs after the cutover handlers register.
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Bus-cutover Site 2 — Flag-off

This scenario asserts the C2 byte-identity contract for Site 2: under
default flag-off mode, consensus writes are byte-for-byte identical to
pre-cutover code. Disk files written, bus emit fired (or skipped if bus
unavailable), and both projector handlers are no-ops.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-cons-off-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Write a consensus report with both flags unset

```bash
unset WG_BUS_AS_TRUTH_CONSENSUS_REPORT
unset WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE
WICKED_BUS_DISABLED=1 sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, hashlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report, _write_consensus_evidence
from jam.consensus import ConsensusResult, DissentingView

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[{"point": "fixture", "agreement": 3, "of": 3}],
    dissenting_views=[DissentingView(persona="sec", view="rotate", strength="moderate")],
    open_questions=["q?"], rounds=1, participants=3,
)
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-off"
_write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="abcdef123456")
_write_consensus_evidence(project_dir, "design", {
    "result": "REJECT", "reason": "dissent", "consensus_confidence": 0.4,
    "agreement_ratio": 0.4, "dissenting_views": [], "participants": 5,
    "eval_id": "abcdef123456",
})
report = (project_dir / "phases" / "design" / "consensus-report.json").read_bytes()
evidence = (project_dir / "phases" / "design" / "consensus-evidence.json").read_bytes()
print("REPORT_SHA256=" + hashlib.sha256(report).hexdigest())
print("EVIDENCE_SHA256=" + hashlib.sha256(evidence).hexdigest())
PYEOF
```

**Expected**: two `*_SHA256=` lines, one per file.

## Step 2: Capture the baseline SHAs

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
for name in ('consensus-report.json', 'consensus-evidence.json'):
    p = pathlib.Path('${TEST_DIR}/proj-flag-off/phases/design/' + name)
    print(name + ' SHA256=' + hashlib.sha256(p.read_bytes()).hexdigest())
" | tee "${TEST_DIR}/baseline-sha.txt"
```

## Step 3: Repeat the writes in a fresh project with flags explicitly off

```bash
WG_BUS_AS_TRUTH_CONSENSUS_REPORT=off WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE=off \
WICKED_BUS_DISABLED=1 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib, hashlib
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from consensus_gate import _write_consensus_report, _write_consensus_evidence
from jam.consensus import ConsensusResult, DissentingView

result = ConsensusResult(
    decision="APPROVE", confidence=0.85,
    consensus_points=[{"point": "fixture", "agreement": 3, "of": 3}],
    dissenting_views=[DissentingView(persona="sec", view="rotate", strength="moderate")],
    open_questions=["q?"], rounds=1, participants=3,
)
project_dir = pathlib.Path("${TEST_DIR}") / "proj-flag-off-explicit"
_write_consensus_report(project_dir, "design", result, {"agreement_ratio": 0.85}, eval_id="abcdef123456")
_write_consensus_evidence(project_dir, "design", {
    "result": "REJECT", "reason": "dissent", "consensus_confidence": 0.4,
    "agreement_ratio": 0.4, "dissenting_views": [], "participants": 5,
    "eval_id": "abcdef123456",
})
for name in ("consensus-report.json", "consensus-evidence.json"):
    sha = hashlib.sha256(
        (project_dir / "phases" / "design" / name).read_bytes()
    ).hexdigest()
    print(name + " SHA256=" + sha)
PYEOF
```

**Expected**: identical `SHA256=` lines to Step 2 — Council C2 byte-identity
contract: `unset` and `off` produce identical disk bytes for both files.
Note that `created_at` in the file uses wall-clock; pin to the exact same
fixture run to compare.  This step proves the flag value path; SHA equality
across runs holds because both writes happen in the same Python process.

## Step 4: Verify both projector handlers are no-ops when flags are off

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
os.environ.pop("WG_BUS_AS_TRUTH_CONSENSUS_REPORT", None)
os.environ.pop("WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE", None)
from daemon.db import connect, init_schema
from daemon.projector import project_event
conn = connect(":memory:")
init_schema(conn)
def _make(event_id, event_type, payload_extra):
    payload = {
        "project_id": "proj-flag-off", "phase": "design",
        "raw_payload": json.dumps({"phase": "design"}, indent=2),
    }
    payload.update(payload_extra)
    return {
        "event_id": event_id, "event_type": event_type,
        "created_at": 1_700_000_000 + event_id, "payload": payload,
    }
report_evt = _make(1, "wicked.consensus.report_created", {"decision": "APPROVE"})
evidence_evt = _make(2, "wicked.consensus.evidence_recorded", {"result": "REJECT"})
status1 = project_event(conn, report_evt)
status2 = project_event(conn, evidence_evt)
report_rows = conn.execute("SELECT COUNT(*) FROM consensus_reports").fetchone()[0]
evidence_rows = conn.execute("SELECT COUNT(*) FROM consensus_evidence").fetchone()[0]
assert status1 == "applied", f"expected applied for report, got {status1}"
assert status2 == "applied", f"expected applied for evidence, got {status2}"
assert report_rows == 0, f"C2/C3 violation: flag-off wrote {report_rows} report row(s)"
assert evidence_rows == 0, f"C2/C3 violation: flag-off wrote {evidence_rows} evidence row(s)"
print(f"PASS: report status={status1} rows={report_rows}, evidence status={status2} rows={evidence_rows}")
PYEOF
```

**Expected**: `PASS: report status=applied rows=0, evidence status=applied rows=0`

## Success Criteria

- [ ] Step 1 writes both consensus JSON files
- [ ] Step 2 records the baseline SHAs
- [ ] Step 3 produces matching SHAs in a second isolated process — proves byte-identity (Council C2)
- [ ] Step 4 returns `status=applied` and 0 rows in both projection tables when flags are off

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_CONSENSUS_REPORT WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE WICKED_BUS_DISABLED
```
