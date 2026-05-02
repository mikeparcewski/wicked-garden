---
name: bus-cutover-dispatch-log-chain-id-uniqueness
title: Bus-cutover Site 1 — chain_id includes dispatch_id so retries do not dedupe
description: Validates Council Condition C5 — two dispatches to the same (project, phase, gate) with distinct dispatch_id values produce distinct chain_ids, so the bus dedupe ledger at _bus.py:569 does NOT collapse them. The projector lands both as separate rows in dispatch_log_entries.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 1 — chain_id Uniqueness

This scenario asserts the C5 latent-bug fix. Before this PR the chain_id
emitted by `dispatch_log.append` was `f"{project_id}.{phase}.{gate}"`,
which collapsed retries on the bus dedupe ledger
(`_bus.py:569 is_processed` keyed on `(event_type, chain_id)`). After the
fix the chain_id is `f"{project_id}.{phase}.{gate}.{dispatch_id}"` so
each retry produces a unique key.

This is a regression-detector: if a future maintainer reverts the chain_id
format, this scenario fails.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-disp-chain-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Append two dispatches to the same (phase, gate) with distinct dispatch_ids

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, pathlib
from unittest.mock import patch
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
import _bus
dispatch_log._reset_state_for_tests()
dispatch_log.set_hmac_secret("chain-id-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-chain-uniq"
(project_dir / "phases" / "design").mkdir(parents=True)
captured = []
def _fake_emit(event_type, payload, chain_id=None, metadata=None):
    captured.append({"event_type": event_type, "chain_id": chain_id, "payload": payload})
with patch.object(_bus, "emit_event", side_effect=_fake_emit):
    dispatch_log.append(project_dir, "design", reviewer="r", gate="design-quality",
                        dispatch_id="dispatch-A",
                        dispatched_at="2026-04-19T10:00:00+00:00")
    dispatch_log.append(project_dir, "design", reviewer="r", gate="design-quality",
                        dispatch_id="dispatch-B",
                        dispatched_at="2026-04-19T10:05:00+00:00")
assert len(captured) == 2, f"expected 2 emits, got {len(captured)}"
chain_ids = [c["chain_id"] for c in captured]
assert chain_ids[0] == "proj-chain-uniq.design.design-quality.dispatch-A"
assert chain_ids[1] == "proj-chain-uniq.design.design-quality.dispatch-B"
assert chain_ids[0] != chain_ids[1], (
    "C5 violation: chain_ids are identical for distinct dispatch_ids — "
    "the bus dedupe ledger would drop the second emit."
)
print(f"PASS: distinct chain_ids — {chain_ids[0]!r} vs {chain_ids[1]!r}")
PYEOF
```

**Expected**: `PASS: distinct chain_ids — 'proj-chain-uniq.design.design-quality.dispatch-A' vs 'proj-chain-uniq.design.design-quality.dispatch-B'`

## Step 2: Project both events and assert two distinct rows land

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
from daemon.db import connect, init_schema
from daemon.projector import project_event
conn = connect(":memory:")
init_schema(conn)
def _make_event(event_id, dispatch_id, dispatched_at):
    record = {"reviewer": "r", "phase": "design", "gate": "design-quality",
              "dispatched_at": dispatched_at,
              "dispatcher_agent": "wicked-garden:crew:phase-manager",
              "expected_result_path": "phases/design/gate-result.json",
              "dispatch_id": dispatch_id, "hmac": "deadbeef" * 8}
    return {
        "event_id": event_id,
        "event_type": "wicked.dispatch.log_entry_appended",
        "created_at": 1_700_000_000 + event_id,
        "payload": {
            "project_id": "proj-chain-uniq", "phase": "design",
            "gate": "design-quality", "reviewer": "r",
            "dispatch_id": dispatch_id,
            "dispatcher_agent": "wicked-garden:crew:phase-manager",
            "expected_result_path": "phases/design/gate-result.json",
            "dispatched_at": dispatched_at,
            "hmac": "deadbeef" * 8, "hmac_present": True,
            "raw_payload": json.dumps(record, separators=(",", ":")),
        },
    }
project_event(conn, _make_event(1, "dispatch-A", "2026-04-19T10:00:00+00:00"))
project_event(conn, _make_event(2, "dispatch-B", "2026-04-19T10:05:00+00:00"))
rows = conn.execute(
    "SELECT event_id, dispatch_id FROM dispatch_log_entries ORDER BY event_id"
).fetchall()
assert len(rows) == 2, f"expected 2 rows, got {len(rows)}: {[dict(r) for r in rows]}"
assert [(r['event_id'], r['dispatch_id']) for r in rows] == [
    (1, "dispatch-A"), (2, "dispatch-B"),
]
print(f"PASS: two distinct rows landed — {[dict(r) for r in rows]}")
PYEOF
```

**Expected**: `PASS: two distinct rows landed — [{'event_id': 1, 'dispatch_id': 'dispatch-A'}, {'event_id': 2, 'dispatch_id': 'dispatch-B'}]`

## Step 3: Bus dedupe ledger does not collapse the two emits

The bus's `is_processed` helper is keyed on `(event_type, chain_id)`. Two
distinct chain_ids must produce two distinct ledger keys.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import sys
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
import _bus
key_a = f"wicked.dispatch.log_entry_appended:proj-chain-uniq.design.design-quality.dispatch-A"
key_b = f"wicked.dispatch.log_entry_appended:proj-chain-uniq.design.design-quality.dispatch-B"
assert key_a != key_b, "Ledger keys collapse — C5 fix has been reverted"
print(f"PASS: distinct ledger keys — {key_a} vs {key_b}")
PYEOF
```

**Expected**: `PASS: distinct ledger keys — wicked.dispatch.log_entry_appended:proj-chain-uniq.design.design-quality.dispatch-A vs wicked.dispatch.log_entry_appended:proj-chain-uniq.design.design-quality.dispatch-B`

## Success Criteria

- [ ] Step 1 emits two distinct chain_ids for two distinct dispatch_ids
- [ ] Step 2 projects both events as separate rows in `dispatch_log_entries`
- [ ] Step 3 confirms the bus ledger keys do not collapse

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_DISPATCH_LOG
```
