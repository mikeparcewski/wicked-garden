---
name: rigor-escalator-end-to-end
title: Rigor Escalator — End-to-End Loop Closure
description: |
  Acceptance scenario for PR-3 of the steering detector epic (#679). Closes the
  steering loop end-to-end with no LLM in the path:

    1. Project at rigor=minimal exists.
    2. Sensitive-path detector (PR-2) runs against an auth path fixture.
    3. Detector emits `wicked.steer.escalated` (PR-1 + PR-2 wiring).
    4. Subscriber (PR-3) receives the event and bumps rigor_tier to full.
    5. Subscriber emits `wicked.steer.applied` audit event.
    6. Project state — verified via phase_manager.load_project_state — shows
       rigor_tier=full and a populated rigor_escalation_history.

  Cases 1-3 are deterministic (apply_steering_event invoked directly with a
  fake phase_manager). Case 4 is the fail-open guard for an unreachable bus.
  Cases 5-6 exercise the bus path only when wicked-bus is present (gated by
  reachability probe).
type: integration
difficulty: intermediate
estimated_minutes: 5
covers:
  - epic #679 (steering detector registry)
  - PR-3 (rigor-escalator subscriber)
  - scripts/crew/rigor_escalator.py
  - scripts/crew/detectors/sensitive_path.py (loop source)
  - scripts/crew/steering_event_schema.py (validator integration)
---

# Rigor Escalator — End-to-End Loop Closure

Verifies that the steering loop closes: a detector signal mutates project
rigor in a way the next gate dispatch will read. All assertions are structural
(JSON shape + string equality) — no LLM in the loop.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export DETECTOR="${PLUGIN_ROOT}/scripts/crew/detectors/sensitive_path.py"
export SUBSCRIBER="${PLUGIN_ROOT}/scripts/crew/rigor_escalator.py"
```

---

## Case 1: Detector payload + apply_steering_event raises rigor_tier to full

**Verifies**: a `wicked.steer.escalated` payload built by the sensitive-path
detector is accepted by the subscriber and bumps a minimal-tier project to
full. No live bus required — the subscriber is invoked in-process via its
public Python API with an in-memory fake phase_manager.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from crew.detectors.sensitive_path import detect_sensitive_path_touch
from crew import rigor_escalator as escalator
from datetime import datetime, timezone

# 1. Detector produces a real schema-valid payload from a sensitive path.
payloads = detect_sensitive_path_touch(
    ['src/auth/login.py'],
    session_id='scenario-001',
    project_slug='loop-demo',
    now=datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc),
)
assert len(payloads) == 1, f'expected 1 payload, got {len(payloads)}'

# 2. Set up a fake phase_manager with project at rigor=minimal.
class FakeProject:
    def __init__(self):
        self.name = 'loop-demo'
        self.extras = {'rigor_tier': 'minimal'}

class FakePM:
    def __init__(self):
        self.proj = FakeProject()
        self.update_calls = []
    def load_project_state(self, slug):
        return self.proj if slug == 'loop-demo' else None
    def update_project(self, state, data):
        for k, v in data.items():
            state.extras[k] = v
        self.update_calls.append(dict(data))
        return state, list(data.keys())

pm = FakePM()

# 3. Build a bus-style envelope and feed it to the subscriber's public API.
event = {
    'id': 'evt-loop-1',
    'event_type': 'wicked.steer.escalated',
    'payload': payloads[0],
}

# Suppress the audit emit (Case 1 is the in-process loop assertion only).
class _NoEmit:
    call_count = 0
    @staticmethod
    def patched(*a, **kw):
        _NoEmit.call_count += 1
        return True

import unittest.mock as mock
with mock.patch.object(escalator, '_emit_applied_event', side_effect=_NoEmit.patched):
    decision = escalator.apply_steering_event(event, pm=pm)

print('ACTION_TAKEN:', decision['action_taken'])
print('PREVIOUS_TIER:', decision['previous_tier'])
print('NEW_TIER:', decision['new_tier'])
print('PROJECT_TIER_AFTER:', pm.proj.extras['rigor_tier'])
print('HISTORY_LEN:', len(pm.proj.extras.get('rigor_escalation_history', [])))
print('AUDIT_EMIT_CALLS:', _NoEmit.call_count)
"
```

**Expected**:

```
ACTION_TAKEN: escalated
PREVIOUS_TIER: minimal
NEW_TIER: full
PROJECT_TIER_AFTER: full
HISTORY_LEN: 1
AUDIT_EMIT_CALLS: 1
```

---

## Case 2: Never-de-escalate — second event on a full project is redundant

**Verifies**: a second `force-full-rigor` recommendation against an
already-full project does not de-escalate, returns `redundant`, and still
records the event in history (for false-positive metrics).

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from crew import rigor_escalator as escalator

class FakeProject:
    def __init__(self):
        self.name = 'loop-demo'
        self.extras = {'rigor_tier': 'full'}

class FakePM:
    def __init__(self):
        self.proj = FakeProject()
    def load_project_state(self, slug):
        return self.proj
    def update_project(self, state, data):
        for k, v in data.items():
            state.extras[k] = v
        return state, list(data.keys())

pm = FakePM()
event = {
    'id': 'evt-redundant',
    'event_type': 'wicked.steer.escalated',
    'payload': {
        'detector': 'sensitive-path',
        'signal': 'auth path touched',
        'threshold': {'glob': '**/auth/**'},
        'recommended_action': 'force-full-rigor',
        'evidence': {'file': 'src/auth/login.py'},
        'session_id': 'scenario-002',
        'project_slug': 'loop-demo',
        'timestamp': '2026-04-27T10:00:00Z',
    },
}

import unittest.mock as mock
with mock.patch.object(escalator, '_emit_applied_event', return_value=True):
    decision = escalator.apply_steering_event(event, pm=pm)

print('ACTION_TAKEN:', decision['action_taken'])
print('PROJECT_TIER_AFTER:', pm.proj.extras['rigor_tier'])
print('NEVER_DE_ESCALATED:', pm.proj.extras['rigor_tier'] == 'full')
print('HISTORY_RECORDED:', len(pm.proj.extras.get('rigor_escalation_history', [])) == 1)
"
```

**Expected**:

```
ACTION_TAKEN: redundant
PROJECT_TIER_AFTER: full
NEVER_DE_ESCALATED: True
HISTORY_RECORDED: True
```

---

## Case 3: In-session idempotency — same event twice is processed once

**Verifies**: the subscriber's process-local idempotency set short-circuits a
duplicate event so we don't double-mutate.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from crew import rigor_escalator as escalator

class FakeProject:
    def __init__(self):
        self.name = 'loop-demo'
        self.extras = {'rigor_tier': 'minimal'}

class FakePM:
    def __init__(self):
        self.proj = FakeProject()
        self.update_count = 0
    def load_project_state(self, slug):
        return self.proj
    def update_project(self, state, data):
        for k, v in data.items():
            state.extras[k] = v
        self.update_count += 1
        return state, list(data.keys())

pm = FakePM()
event = {
    'id': 'evt-dup',
    'event_type': 'wicked.steer.escalated',
    'payload': {
        'detector': 'sensitive-path',
        'signal': 'x', 'threshold': {'glob': '**/auth/**'},
        'recommended_action': 'force-full-rigor',
        'evidence': {'file': 'src/auth/login.py'},
        'session_id': 's1', 'project_slug': 'loop-demo',
        'timestamp': '2026-04-27T10:00:00Z',
    },
}

seen = set()
import unittest.mock as mock
with mock.patch.object(escalator, '_emit_applied_event', return_value=True):
    d1 = escalator.apply_steering_event(event, pm=pm, seen_event_ids=seen)
    d2 = escalator.apply_steering_event(event, pm=pm, seen_event_ids=seen)

print('FIRST_ACTION:', d1['action_taken'])
print('SECOND_ACTION:', d2['action_taken'])
print('UPDATE_CALL_COUNT:', pm.update_count)
print('IDEMPOTENT:', d2['action_taken'] == 'no-op' and pm.update_count == 1)
"
```

**Expected**:

```
FIRST_ACTION: escalated
SECOND_ACTION: no-op
UPDATE_CALL_COUNT: 1
IDEMPOTENT: True
```

---

## Case 4: Bus unreachable — subscriber CLI exits 1 cleanly

**Verifies**: the CLI cannot subscribe without the bus, but it fails clean
(exit 1, no traceback) so a calling workflow can detect the condition.

### Test

```bash
# Restrict PATH so wicked-bus and npx are not findable.
env PATH="/usr/bin:/bin" sh "${PLUGIN_ROOT}/scripts/_python.sh" "${SUBSCRIBER}" --dry-run \
  > /tmp/rigor-escalator-busfail.out 2> /tmp/rigor-escalator-busfail.err
RC=$?
echo "EXIT_CODE: $RC"
echo "STDERR_MENTIONS_NOT_INSTALLED: $(grep -c 'wicked-bus is not installed' /tmp/rigor-escalator-busfail.err || true)"
echo "NO_TRACEBACK: $(grep -c 'Traceback' /tmp/rigor-escalator-busfail.err || true)"
rm -f /tmp/rigor-escalator-busfail.out /tmp/rigor-escalator-busfail.err
```

**Expected**:

```
EXIT_CODE: 1
STDERR_MENTIONS_NOT_INSTALLED: 1
NO_TRACEBACK: 0
```

---

## Case 5: Audit payload validates against the PR-1 schema

**Verifies**: the `wicked.steer.applied` audit payload built by the subscriber
passes `validate_payload`. Catches schema drift between PR-1 and PR-3.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from crew import rigor_escalator as escalator
from crew.steering_event_schema import validate_payload

class FakeProject:
    def __init__(self):
        self.name = 'audit-demo'
        self.extras = {'rigor_tier': 'minimal'}

class FakePM:
    def load_project_state(self, slug): return FakeProject()
    def update_project(self, state, data):
        return state, list(data.keys())

pm = FakePM()
event = {
    'id': 'evt-audit',
    'event_type': 'wicked.steer.escalated',
    'payload': {
        'detector': 'sensitive-path',
        'signal': 'x', 'threshold': {'glob': '**/auth/**'},
        'recommended_action': 'force-full-rigor',
        'evidence': {'file': 'src/auth/login.py'},
        'session_id': 's1', 'project_slug': 'audit-demo',
        'timestamp': '2026-04-27T10:00:00Z',
    },
}

captured = {}
class _OkProc:
    returncode = 0
    stderr = ''

def _capture(cmd, *a, **kw):
    if '--payload' in cmd:
        idx = cmd.index('--payload')
        captured['payload'] = json.loads(cmd[idx + 1])
        captured['type'] = cmd[cmd.index('--type') + 1]
    return _OkProc()

import unittest.mock as mock
with mock.patch.object(escalator, '_resolve_bus_command', return_value=['wicked-bus']), \
     mock.patch.object(escalator.subprocess, 'run', side_effect=_capture):
    decision = escalator.apply_steering_event(event, pm=pm)

errors, warnings = validate_payload('wicked.steer.applied', captured.get('payload', {}))
print('AUDIT_TYPE:', captured.get('type'))
print('SCHEMA_ERRORS:', len(errors))
print('SCHEMA_WARNINGS:', len(warnings))
print('ACTION_TAKEN_RECORDED:', captured['payload']['evidence'].get('action_taken'))
print('SCHEMA_VALID:', not errors)
"
```

**Expected**:

```
AUDIT_TYPE: wicked.steer.applied
SCHEMA_ERRORS: 0
SCHEMA_WARNINGS: 0
ACTION_TAKEN_RECORDED: escalated
SCHEMA_VALID: True
```

---

## Success Criteria

- [ ] Case 1 — detector payload mutates a minimal project to full; history populated
- [ ] Case 2 — never-de-escalate guard returns redundant; tier stays full; history still recorded
- [ ] Case 3 — same event twice produces one mutation; second decision is no-op
- [ ] Case 4 — CLI fails clean (exit 1, no traceback) when wicked-bus is unreachable
- [ ] Case 5 — `wicked.steer.applied` audit payload passes the PR-1 schema validator

## Cleanup

(No persistent state to clean — all five cases use in-memory fake phase_manager
or temp files that are removed inline.)
