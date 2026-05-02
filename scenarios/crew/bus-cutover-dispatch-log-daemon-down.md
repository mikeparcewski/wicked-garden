---
name: bus-cutover-dispatch-log-daemon-down
title: Bus-cutover Site 1 — daemon-down with flag-on does not break dispatch flow
description: Validates fail-open behaviour — under WG_BUS_AS_TRUTH_DISPATCH_LOG=on with the projector daemon stopped, the disk write succeeds, the bus emit fires-and-forgets, and the dispatch flow returns without surfacing an error to the caller.
type: testing
difficulty: intermediate
estimated_minutes: 4
---

# Bus-cutover Site 1 — Daemon-down

This scenario asserts that the dispatch flow stays fail-open even when
the projector daemon is unreachable. Disk write is the source of truth
during dual-write; the emit is fire-and-forget per `_bus.py:371-381`.
Caller sees a successful return regardless of daemon state.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-bc-disp-down-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Append under flag-on with the bus binary unavailable

We disable the bus shim entirely via `WICKED_BUS_DISABLED=1` to simulate
the daemon-down case at the dispatch-flow level. The `_bus.emit_event`
call short-circuits at `_check_available()` and returns immediately —
the same path the dispatch flow sees if the bus binary is missing or
the daemon is dead.

```bash
WG_BUS_AS_TRUTH_DISPATCH_LOG=on WICKED_BUS_DISABLED=1 \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<PYEOF
import os, sys, json, pathlib, time
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts/crew")
import dispatch_log
dispatch_log._reset_state_for_tests()
dispatch_log.set_hmac_secret("daemon-down-secret")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-daemon-down"
(project_dir / "phases" / "design").mkdir(parents=True)
start = time.monotonic()
try:
    dispatch_log.append(
        project_dir, "design",
        reviewer="security-engineer",
        gate="design-quality",
        dispatch_id="d-daemon-down-1",
        dispatched_at="2026-04-19T10:00:00+00:00",
    )
    elapsed = time.monotonic() - start
    print(f"RETURNED_OK elapsed_ms={int(elapsed*1000)}")
except Exception as exc:
    print(f"FAIL: append raised {type(exc).__name__}: {exc}")
    raise
log_path = project_dir / "phases" / "design" / "dispatch-log.jsonl"
print(f"DISK_FILE_EXISTS={log_path.is_file()}")
print(f"LINES={len(log_path.read_text(encoding='utf-8').splitlines())}")
PYEOF
```

**Expected**:
```
RETURNED_OK elapsed_ms=<small number, well under 5000>
DISK_FILE_EXISTS=True
LINES=1
```

## Step 2: Verify the bus emit fail-open swallows runtime errors too

Even if the bus binary IS present but throws unexpectedly, the dispatch
flow must not surface the error.

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
dispatch_log.set_hmac_secret("daemon-down-secret-2")
project_dir = pathlib.Path("${TEST_DIR}") / "proj-daemon-emit-error"
(project_dir / "phases" / "design").mkdir(parents=True)
with patch.object(_bus, "emit_event", side_effect=RuntimeError("daemon unreachable")):
    try:
        dispatch_log.append(
            project_dir, "design",
            reviewer="r", gate="g", dispatch_id="d-emit-err",
            dispatched_at="2026-04-19T10:00:00+00:00",
        )
        print("PASS: append returned OK despite emit_event raising RuntimeError")
    except Exception as exc:
        print(f"FAIL: append surfaced exception {type(exc).__name__}: {exc}")
        raise
log_path = project_dir / "phases" / "design" / "dispatch-log.jsonl"
assert log_path.is_file(), "Disk write must still succeed even when emit raises"
print(f"DISK_FILE_EXISTS={log_path.is_file()}")
PYEOF
```

**Expected**:
```
PASS: append returned OK despite emit_event raising RuntimeError
DISK_FILE_EXISTS=True
```

## Success Criteria

- [ ] Step 1 returns OK under flag-on with the bus disabled; disk file exists
- [ ] Step 2 returns OK even when emit_event raises mid-call; disk file still exists

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR WG_BUS_AS_TRUTH_DISPATCH_LOG WICKED_BUS_DISABLED
```
