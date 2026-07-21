---
name: garden-self-test
description: |
  Bootstrap acceptance scenario for wicked-garden. Validates the core
  invariants that every release must preserve: test suite green, bus event
  registry valid, gate fails closed, sentinels registered.
  Dogfoods wicked-testing against wicked-garden itself.
version: "1.1"
category: cli
tags: [bootstrap, self-test, dogfood, garden]
tools:
  required: [node, npm, python3]
timeout: 180
assertions:
  - id: A1
    description: npm test passes — all unit and integration tests exit 0
  - id: A2
    description: BUS_EVENT_MAP contains exactly 52 events, all 4-segment wicked.<domain>.<noun>.<past-tense-verb>
  - id: A3
    description: gate_satisfied() fails closed when WICKED_LOOM_CUTOVER=off (loom disabled, returns gate unavailable, not green)
  - id: A4
    description: _SENTINEL_EVENTS frozenset contains claim_unverified, prepush_blocked, and unverified_task_done
---

# Garden Self-Test

Bootstrap acceptance dogfood — wicked-garden validates its own core invariants.

## Setup

```bash
echo "Working directory: $(pwd)"
echo "Node version: $(node --version)"
echo "Python version: $(sh scripts/_python.sh --version)"
```

## Steps

### Step 1: Run the test suite (npm test)

```bash
set -o pipefail
npm test 2>&1 | tail -5
echo "exit: $?"
```

**Expect**: Exit code 0 (captured from npm test via pipefail), test output contains no FAIL lines.

### Step 2: Verify BUS_EVENT_MAP event count and naming

```bash
sh scripts/_python.sh -c "
import sys; sys.path.insert(0, 'scripts')
from _bus import BUS_EVENT_MAP
count = len(BUS_EVENT_MAP)
print('event_count:', count)
bad = [k for k in BUS_EVENT_MAP if len(k.split('.')) != 4]
print('non_conforming:', bad)
bad_prefix = [k for k in BUS_EVENT_MAP if not k.startswith('wicked.')]
print('non_wicked_prefix:', bad_prefix)
assert count == 52, f'expected 52, got {count}'
assert not bad, f'non-4-segment events: {bad}'
assert not bad_prefix, f'events not starting with wicked.: {bad_prefix}'
print('PASS')
"
```

**Expect**: Exit code 0, `event_count: 52`, `non_conforming: []` (computed variable, not hardcoded), `non_wicked_prefix: []`, `PASS`.

### Step 3: Verify gate fails closed with WICKED_LOOM_CUTOVER=off

```bash
sh scripts/_python.sh -c "
import sys, os
for p in ('scripts', 'scripts/qe'):
    if p not in sys.path:
        sys.path.insert(0, p)
import vault_gate
os.environ['WICKED_LOOM_CUTOVER'] = 'off'
result = vault_gate.gate_satisfied('.', 'delivery', 'build')
print('gate_result:', result)
assert result.get('gate') == 'unavailable', f'expected unavailable, got {result}'
print('PASS: gate fails closed with WICKED_LOOM_CUTOVER=off')
"
```

**Expect**: Exit code 0, `gate_result` shows `gate: 'unavailable'`, `PASS: gate fails closed with WICKED_LOOM_CUTOVER=off`.

### Step 4: Verify _SENTINEL_EVENTS frozenset

```bash
sh scripts/_python.sh -c "
import sys; sys.path.insert(0, 'scripts')
from sentinel.invariants import _SENTINEL_EVENTS
print('sentinel_events:', sorted(_SENTINEL_EVENTS))
required = {'claim_unverified', 'prepush_blocked', 'unverified_task_done'}
missing = required - _SENTINEL_EVENTS
assert not missing, f'missing from _SENTINEL_EVENTS: {missing}'
print('PASS: all required sentinel events registered')
"
```

**Expect**: Exit code 0, all 3 required sentinel names present, `PASS: all required sentinel events registered`.

## Cleanup

```bash
echo "Garden self-test complete."
```
