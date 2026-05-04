---
name: dispatch-liveness-stuck-state
title: Dispatch Liveness Audit — Stuck Dispatch + External-Trigger Conditions
description: Verify scripts/crew/dispatch_liveness.py surfaces stale dispatch-log entries and CONDITIONAL gate-results that defer to external triggers without naming a producer event
type: testing
difficulty: standard
estimated_minutes: 5
covers:
  - "Theme 4 — terminal-state deferred paths need bounded retry, not 'next event' reliance"
  - "Stale dispatch-log entries detection (default 5min threshold)"
  - "CONDITIONAL gate-result conditions referencing external triggers must declare producer_event/trigger_event/resolves_on"
  - "Configuration override via gate-policy.json::dispatch_liveness block (additive)"
ac_ref: "Theme 4 (cross-project memory synthesis cluster B)"
---

# Dispatch Liveness — Stuck-State Audit

This scenario exercises the new liveness audit added by cluster B. The audit
catches two classes of "deferred to next responder, but the state is terminal"
bugs:

1. **Stale dispatch-log entries.** A reviewer was dispatched (entry written to
   `phases/{phase}/dispatch-log.jsonl` via the bus-as-truth projector), but the
   reviewer never delivered. After 5 minutes (configurable), the entry is
   reported as stuck — there is no next event coming.
2. **CONDITIONAL gate-results with external-trigger conditions.** The verdict
   text says "wait for", "external", "deferred", "awaiting", etc. — but the
   condition does NOT carry a `producer_event` / `trigger_event` / `resolves_on`
   field naming the event that will resolve it. Operators have no way to
   advance the gate.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT_DIR="${TMPDIR:-/tmp}/dispatch-liveness-scenario-$$"
rm -rf "${TEST_PROJECT_DIR}"
mkdir -p "${TEST_PROJECT_DIR}/phases/review"
```

## Step 1 — Stale dispatch-log entry surfaced as `stale-dispatch`

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

# Write a dispatch-log entry that's 10 minutes old with no matching gate-result.
old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
entry = {
    'reviewer': 'security-engineer',
    'phase': 'review',
    'gate': 'evidence-quality',
    'dispatch_id': 'liveness-test-001',
    'dispatched_at': old,
    'dispatcher_agent': 'wicked-garden:crew:phase-manager',
    'expected_result_path': 'gate-result.json',
}
log_path = Path('${TEST_PROJECT_DIR}') / 'phases' / 'review' / 'dispatch-log.jsonl'
log_path.write_text(json.dumps(entry) + '\n')

import dispatch_liveness as dl
findings = dl.audit_phase(Path('${TEST_PROJECT_DIR}'), 'review')
assert len(findings) == 1, f'Expected 1 finding, got {len(findings)}: {findings}'
assert findings[0]['kind'] == 'stale-dispatch'
assert findings[0]['evidence']['age_secs'] >= 600
print('PASS step 1: stale-dispatch detected')
"
```

## Step 2 — CONDITIONAL with external-trigger condition lacking producer surfaces as `external-trigger-no-producer`

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path

sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

gate_result = {
    'verdict': 'CONDITIONAL',
    'gate': 'evidence-quality',
    'reviewer': 'senior-engineer',
    'conditions': [
        {'description': 'Wait for external auditor sign-off'},  # MATCH — no producer
        {'description': 'Awaiting next responder',                # OK — has producer
         'producer_event': 'security.review.complete'},
        {'description': 'Increase test coverage to 80%'},         # OK — not external
    ],
}
gp = Path('${TEST_PROJECT_DIR}') / 'phases' / 'review' / 'gate-result.json'
gp.write_text(json.dumps(gate_result))

import dispatch_liveness as dl
# Re-audit (now BOTH stale-dispatch and external-trigger findings should appear,
# because the gate-result.json arrived for evidence-quality but doesn't resolve
# the dispatch entry whose orphan-detection lives elsewhere — and the CONDITIONAL
# external-trigger condition is a separate finding class).
findings = dl.audit_conditional_externals(Path('${TEST_PROJECT_DIR}'), 'review')
assert len(findings) == 1, f'Expected 1 external-trigger finding, got {len(findings)}: {findings}'
assert findings[0]['kind'] == 'external-trigger-no-producer'
assert findings[0]['evidence']['condition_index'] == 0
print('PASS step 2: external-trigger-no-producer detected')
"
```

## Step 3 — `--strict` exit code surfaces blocking findings to CI

```bash
WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED=strict sh "${PLUGIN_ROOT}/scripts/_python.sh" \
    "${PLUGIN_ROOT}/scripts/crew/dispatch_liveness.py" \
    "${TEST_PROJECT_DIR}" --json --strict > /tmp/liveness-out.json
strict_exit=$?
test "${strict_exit}" -eq 1 || { echo "FAIL: --strict should exit 1, got ${strict_exit}"; exit 1; }
grep -q '"kind": "external-trigger-no-producer"' /tmp/liveness-out.json
echo 'PASS step 3: --strict exit code = 1 with blocking findings'
```

## Step 4 — Operator can disable the audit via `WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED=off`

```bash
WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED=off sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
from pathlib import Path
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
import dispatch_liveness as dl
findings = dl.audit_conditional_externals(Path('${TEST_PROJECT_DIR}'), 'review')
assert findings == [], f'Expected no findings with mode=off, got: {findings}'
print('PASS step 4: producer-required=off disables the check')
"
```

## Step 5 — Configuration via gate-policy.json (additive contract)

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json
gp = json.loads(open('${PLUGIN_ROOT}/.claude-plugin/gate-policy.json').read())
block = gp.get('dispatch_liveness') or {}
assert isinstance(block.get('stale_dispatch_secs'), int) and block['stale_dispatch_secs'] > 0
assert block.get('producer_event_required') in ('warn', 'strict', 'off')
print('PASS step 5: gate-policy.json::dispatch_liveness block present and well-formed')
"
```

## Cleanup

```bash
rm -rf "${TEST_PROJECT_DIR}"
```

## Expected Results

- Step 1: `stale-dispatch` finding emitted; evidence carries `age_secs >= 600`.
- Step 2: `external-trigger-no-producer` finding for the bare condition; the
  one with `producer_event` is silent.
- Step 3: `--strict` exits non-zero so CI / cron scripts can pipeline-fail.
- Step 4: `WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED=off` disables the check
  cleanly (no stuck-state findings; rollback lever for false positives).
- Step 5: gate-policy.json carries the operator-tunable defaults; env-vars
  override them but the canonical source is the JSON config (Theme 2 — no
  hidden hardcoded constants).

## Notes — bus-as-truth invariant

The audit reads dispatch-log entries via `dispatch_log.read_entries`, which
honors the `WG_BUS_AS_TRUTH_DISPATCH_LOG` flag and pulls from the event_log
when bus-as-truth is on. It does NOT bypass the bus or write to disk —
liveness is a read-only audit, fail-open, and never mutates gate-results.
