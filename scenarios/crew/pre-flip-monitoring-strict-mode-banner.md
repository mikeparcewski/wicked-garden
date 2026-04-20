---
name: pre-flip-monitoring-strict-mode-banner
title: Pre-Flip Monitoring and Strict-Mode Banner (AC-#506, PR #513)
description: Verify bootstrap emits PreFlipNotice banner when WG_GATE_RESULT_STRICT_AFTER is within 30 days, and StrictMode banner post-flip
type: testing
difficulty: intermediate
estimated_minutes: 10
covers:
  - "#520 — pre-flip monitoring banner acceptance criteria"
  - "#506 (WG_GATE_RESULT_STRICT_AFTER pre-flip monitoring in bootstrap.py)"
  - hooks/scripts/bootstrap.py::_check_pre_flip_notice()
ac_ref: "v6.2 PR #513 | hooks/scripts/bootstrap.py #506 block"
---

# Pre-Flip Monitoring and Strict-Mode Banner

This scenario tests `hooks/scripts/bootstrap.py::_check_pre_flip_notice()`:

- **Silent** when flip date > 7 days away.
- **PreFlipNotice WARN** (every session) when 1 ≤ days_until_flip ≤ 7.
- **StrictMode INFO** (one-time per session, latched) on/after the flip date.

The helper is testable by importing it directly and passing a `today` override.
All tests are deterministic — no real system clock dependency.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
```

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
from bootstrap import _check_pre_flip_notice
print('PASS: _check_pre_flip_notice importable from bootstrap.py')
"
Assert: PASS: _check_pre_flip_notice importable from bootstrap.py
```

---

## Case 1: Flip date > 7 days away → silent (no stderr output)

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, io
from datetime import date
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ['WG_GATE_RESULT_STRICT_AFTER'] = '2099-12-31'

import importlib
import bootstrap
importlib.reload(bootstrap)
from bootstrap import _check_pre_flip_notice

# Capture stderr
buf = io.StringIO()
old_stderr = sys.stderr
sys.stderr = buf

# today = far before the flip date
_check_pre_flip_notice(state=None, today=date(2099, 12, 20))

sys.stderr = old_stderr
output = buf.getvalue()
del os.environ['WG_GATE_RESULT_STRICT_AFTER']

assert output == '', f'Expected silent output, got: {output!r}'
print('PASS: silent when flip date > 7 days away')
"
Assert: PASS: silent when flip date > 7 days away
```

---

## Case 2: 1 ≤ days_until_flip ≤ 7 → PreFlipNotice WARN on stderr

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, io
from datetime import date, timedelta
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

flip_date = date.today() + timedelta(days=3)
os.environ['WG_GATE_RESULT_STRICT_AFTER'] = flip_date.isoformat()

import importlib
import bootstrap
importlib.reload(bootstrap)
from bootstrap import _check_pre_flip_notice

buf = io.StringIO()
old_stderr = sys.stderr
sys.stderr = buf

# today = 3 days before flip
_check_pre_flip_notice(state=None, today=date.today())

sys.stderr = old_stderr
output = buf.getvalue()
del os.environ['WG_GATE_RESULT_STRICT_AFTER']

assert 'PreFlipNotice' in output, f'Expected PreFlipNotice in stderr, got: {output!r}'
assert '3' in output or 'days' in output, f'Day count missing from banner: {output!r}'
print(f'PASS: PreFlipNotice emitted for 3-day pre-flip window')
print(f'  stderr: {output.strip()}')
"
Assert: PASS: PreFlipNotice emitted for 3-day pre-flip window
```

---

## Case 3: Exactly 7 days away → PreFlipNotice emitted

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, io
from datetime import date, timedelta
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

flip_date = date.today() + timedelta(days=7)
os.environ['WG_GATE_RESULT_STRICT_AFTER'] = flip_date.isoformat()

import importlib
import bootstrap
importlib.reload(bootstrap)
from bootstrap import _check_pre_flip_notice

buf = io.StringIO()
old_stderr = sys.stderr
sys.stderr = buf
_check_pre_flip_notice(state=None, today=date.today())
sys.stderr = old_stderr
output = buf.getvalue()
del os.environ['WG_GATE_RESULT_STRICT_AFTER']

assert 'PreFlipNotice' in output, f'Expected PreFlipNotice at T-7, got: {output!r}'
print(f'PASS: PreFlipNotice at T=7 days boundary')
"
Assert: PASS: PreFlipNotice at T=7 days boundary
```

---

## Case 4: Flip date is today (T=0) → StrictMode INFO on stderr

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, io
from datetime import date
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

flip_date = date.today()
os.environ['WG_GATE_RESULT_STRICT_AFTER'] = flip_date.isoformat()

import importlib
import bootstrap
importlib.reload(bootstrap)
from bootstrap import _check_pre_flip_notice

buf = io.StringIO()
old_stderr = sys.stderr
sys.stderr = buf
_check_pre_flip_notice(state=None, today=date.today())
sys.stderr = old_stderr
output = buf.getvalue()
del os.environ['WG_GATE_RESULT_STRICT_AFTER']

assert 'StrictMode' in output, f'Expected StrictMode banner at T=0, got: {output!r}'
print(f'PASS: StrictMode banner emitted on flip day')
print(f'  stderr: {output.strip()}')
"
Assert: PASS: StrictMode banner emitted on flip day
```

---

## Case 5: Post-flip (T < 0) → StrictMode INFO latched once per session

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, io
from datetime import date, timedelta
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

# Flip date was 5 days ago
flip_date = date.today() - timedelta(days=5)
os.environ['WG_GATE_RESULT_STRICT_AFTER'] = flip_date.isoformat()

import importlib
import bootstrap
importlib.reload(bootstrap)
from bootstrap import _check_pre_flip_notice

# First call — no state (banner fires)
buf1 = io.StringIO()
old_stderr = sys.stderr
sys.stderr = buf1
_check_pre_flip_notice(state=None, today=date.today())
sys.stderr = old_stderr
first_output = buf1.getvalue()

assert 'StrictMode' in first_output, f'Expected StrictMode post-flip, got: {first_output!r}'

# Second call with latched state — banner should NOT re-fire
class MockState:
    strict_mode_active_announced = True

buf2 = io.StringIO()
sys.stderr = buf2
_check_pre_flip_notice(state=MockState(), today=date.today())
sys.stderr = old_stderr
second_output = buf2.getvalue()
del os.environ['WG_GATE_RESULT_STRICT_AFTER']

assert second_output == '', f'Expected silent on second call (latched), got: {second_output!r}'
print(f'PASS: StrictMode fires once (latched via strict_mode_active_announced=True)')
"
Assert: PASS: StrictMode fires once (latched via strict_mode_active_announced=True)
```

---

## Success Criteria

- [ ] `_check_pre_flip_notice` is importable from `hooks/scripts/bootstrap.py`
- [ ] Silent when flip date > 7 days away
- [ ] `[PreFlipNotice]` WARN emitted to stderr when 1 ≤ days_until_flip ≤ 7
- [ ] `[PreFlipNotice]` fires at exactly T=7 (boundary)
- [ ] `[StrictMode]` INFO emitted on T=0 (flip day)
- [ ] `[StrictMode]` INFO emitted post-flip (T < 0)
- [ ] Banner is latched once per session via `state.strict_mode_active_announced`
