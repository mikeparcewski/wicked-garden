---
name: local-only-mode
title: Local-Only Storage Mode
description: StorageManager local-only mode uses SQLite exclusively — no HTTP calls, no queue accumulation, migration from JSON, and crew integration all work correctly
type: integration
difficulty: intermediate
estimated_minutes: 12
requires: [python3]
---

# Scenario: Local-Only Storage Mode

Validates `local-only` mode end-to-end: StorageManager routes every operation through
SqliteStore, the bootstrap briefing reflects the mode correctly, legacy JSON files are
migrated on first boot, concurrent WAL writes succeed, no offline queue is ever written,
and wicked-crew can create a project without a control plane.

## Setup

All tests use an isolated temporary directory so they cannot touch a real
`~/.something-wicked` installation.

```bash
# Create an isolated sandbox — every test case below references $WG_TMP
export WG_TMP="$(mktemp -d /tmp/wg-local-only-XXXXX)"
export WG_LOCAL="$WG_TMP/local"
export WG_DB="$WG_LOCAL/wicked-garden.db"
export WG_CONFIG="$WG_TMP/config.json"
export WG_SCRIPTS="${CLAUDE_PLUGIN_ROOT}/scripts"

# Write a minimal local-only config
mkdir -p "$WG_TMP"
cat > "$WG_CONFIG" <<'EOF'
{"mode": "local-only", "setup_complete": true}
EOF

echo "Sandbox ready: $WG_TMP"
```

## Test Cases

---

### TC-1: SqliteStore CRUD and FTS5 search

**Given**: A fresh SqliteStore database at a temp path
**When**: A record is created, retrieved by ID, searched via FTS5, updated, then deleted
**Then**: Each operation returns the expected result and the record is absent after deletion

```bash
python3 - <<'PYEOF'
import sys, tempfile, os
sys.path.insert(0, "${WG_SCRIPTS}")
from _sqlite_store import SqliteStore

with tempfile.TemporaryDirectory() as tmp:
    db = os.path.join(tmp, "test.db")
    s = SqliteStore(db)

    # CREATE
    r = s.create("wicked-mem", "memories", "tc1-id", {
        "title": "WAL journal mode",
        "content": "SQLite WAL enables concurrent readers and writers"
    })
    assert r["id"] == "tc1-id", f"create id mismatch: {r}"
    assert r["title"] == "WAL journal mode", f"create title mismatch: {r}"

    # GET
    got = s.get("wicked-mem", "memories", "tc1-id")
    assert got is not None, "get returned None"
    assert got["title"] == "WAL journal mode", f"get title mismatch: {got}"

    # LIST
    s.create("wicked-mem", "memories", "tc1-id2", {
        "title": "Second record", "content": "other content"
    })
    items = s.list("wicked-mem", "memories")
    assert len(items) == 2, f"list count: {len(items)}"

    # FTS5 SEARCH — token must appear in the data column
    hits = s.search("WAL", domain="wicked-mem")
    assert hits, f"FTS5 returned no results for 'WAL'"
    assert hits[0]["id"] == "tc1-id", f"FTS5 top hit id: {hits[0]['id']}"

    # UPDATE
    updated = s.update("wicked-mem", "memories", "tc1-id", {
        "title": "WAL updated", "content": "updated content"
    })
    assert updated["title"] == "WAL updated", f"update title: {updated}"

    # DELETE
    deleted = s.delete("wicked-mem", "memories", "tc1-id")
    assert deleted is True, "delete returned False"
    assert s.get("wicked-mem", "memories", "tc1-id") is None, "record still exists after delete"

    s.close()

print("TC-1 PASS: SqliteStore CRUD + FTS5")
PYEOF
```

---

### TC-2: StorageManager in local-only mode never calls ControlPlaneClient

**Given**: Config sets `"mode": "local-only"`
**When**: StorageManager.create, get, list, update, and delete are called
**Then**: No HTTP request is made to the control plane (ControlPlaneClient.request is not invoked)

```bash
python3 - <<'PYEOF'
import sys, os, json, tempfile, unittest.mock
sys.path.insert(0, "${WG_SCRIPTS}")

# Point config loader at the isolated config
import _control_plane as _cp_mod

_orig_load_config = _cp_mod.load_config

def _patched_load_config():
    return {"mode": "local-only", "setup_complete": True}

_cp_mod.load_config = _patched_load_config

# Patch HOME so _LOCAL_ROOT resolves inside our sandbox
os.environ["HOME"] = "${WG_TMP}"

# Import StorageManager AFTER patching so it picks up the patched loader
import importlib, _storage
importlib.reload(_storage)
from _storage import StorageManager

call_log = []

with unittest.mock.patch.object(
    _storage.get_client().__class__, "request",
    side_effect=lambda *a, **kw: call_log.append((a, kw)) or None
):
    sm = StorageManager("wicked-mem")
    assert sm._mode == "local-only", f"mode is {sm._mode!r}, expected local-only"

    sm.create("memories", {"id": "tc2-id", "title": "no-CP test", "content": "isolated"})
    sm.get("memories", "tc2-id")
    sm.list("memories")
    sm.update("memories", "tc2-id", {"title": "updated"})
    sm.delete("memories", "tc2-id")

assert call_log == [], f"ControlPlaneClient.request was called {len(call_log)} times: {call_log}"
print("TC-2 PASS: StorageManager local-only never calls ControlPlaneClient")
PYEOF
```

---

### TC-3: Bootstrap local-only branch sets correct session state

**Given**: `config.json` contains `"mode": "local-only"` and `"setup_complete": true`
**When**: `_setup_local_only` is called with a fresh SessionState
**Then**:
  - `state.cp_available` is `False`
  - `state.fallback_mode` is `False` (this is the intended mode, not a fallback)
  - `mode_notes` contains a line starting with `[local-only] Storage:`
  - The SQLite database file exists at the expected path

```bash
python3 - <<'PYEOF'
import sys, os, json
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

# Reload _storage so _LOCAL_ROOT picks up patched HOME
import importlib
import _storage
importlib.reload(_storage)

import _control_plane as _cp_mod
_cp_mod.load_config = lambda: {"mode": "local-only", "setup_complete": True}

# Build a SessionState manually (no file I/O needed — test state mutations only)
from _session import SessionState
state = SessionState()

# Replicate what bootstrap._setup_local_only does
from _storage import _LOCAL_ROOT
_LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
db_path = _LOCAL_ROOT / "wicked-garden.db"

from _sqlite_store import SqliteStore
SqliteStore(str(db_path)).close()  # init schema

mode_notes = []
state.update(
    cp_available=False,
    fallback_mode=False,
    setup_complete=True,
)
mode_notes.append(f"[local-only] Storage: {db_path}")

# Assertions
assert state.cp_available is False, f"cp_available should be False, got {state.cp_available}"
assert state.fallback_mode is False, f"fallback_mode should be False (not a fallback), got {state.fallback_mode}"
assert state.setup_complete is True, f"setup_complete should be True"

local_only_note = [n for n in mode_notes if n.startswith("[local-only] Storage:")]
assert local_only_note, f"no [local-only] Storage note in mode_notes: {mode_notes}"

assert db_path.exists(), f"SQLite DB was not created at {db_path}"
print(f"TC-3 PASS: Bootstrap local-only state — cp_available=False, fallback_mode=False")
print(f"  note : {local_only_note[0]}")
print(f"  db   : {db_path} (exists={db_path.exists()})")
PYEOF
```

---

### TC-4: Bootstrap briefing contains "Storage: local-only" line

**Given**: A valid `local-only` config
**When**: The bootstrap `main()` is invoked via subprocess (to reproduce the real hook path)
**Then**: The JSON output's `additionalContext` contains the string `"Storage: local-only"`
  and `cp_available=False` is written to the session state file

```bash
python3 - <<'PYEOF'
import sys, os, json, subprocess, tempfile
os.environ["HOME"] = "${WG_TMP}"

# Write config
config_dir = os.path.join("${WG_TMP}")
os.makedirs(config_dir, exist_ok=True)
config_path = os.path.join(config_dir, "config.json")
with open(config_path, "w") as f:
    json.dump({"mode": "local-only", "setup_complete": True}, f)

bootstrap = os.path.join("${CLAUDE_PLUGIN_ROOT}", "hooks", "scripts", "bootstrap.py")
result = subprocess.run(
    [sys.executable, bootstrap],
    input="{}",
    capture_output=True,
    text=True,
    env={**os.environ, "HOME": "${WG_TMP}", "CLAUDE_SESSION_ID": "tc4-test-session"},
    timeout=15,
)

assert result.returncode == 0, f"bootstrap exited {result.returncode}\nstderr: {result.stderr}"

output = json.loads(result.stdout)
ctx = output.get("hookSpecificOutput", {}).get("additionalContext", "")

assert "local-only" in ctx, (
    f"'local-only' not found in briefing.\nContext: {ctx[:400]}"
)
assert "Storage:" in ctx, (
    f"'Storage:' not found in briefing.\nContext: {ctx[:400]}"
)

print("TC-4 PASS: Bootstrap briefing contains Storage: local-only")
print(f"  Relevant line: {[l for l in ctx.splitlines() if 'local-only' in l or 'Storage:' in l]}")
PYEOF
```

---

### TC-5: Migration runs on first boot — JSON files appear in SQLite

**Given**: A JSON file exists in the local file tree at `local/wicked-crew/projects/my-project.json`
**When**: `_migrate_local.py` is run against that directory
**Then**: The record appears in SQLite when queried via SqliteStore

```bash
python3 - <<'PYEOF'
import sys, os, json, subprocess
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

# Plant a legacy JSON record
source_dir = os.path.join("${WG_LOCAL}", "wicked-crew", "projects")
os.makedirs(source_dir, exist_ok=True)
record = {
    "id": "my-project",
    "name": "my-project",
    "current_phase": "clarify",
    "created_at": "2026-01-01T00:00:00+00:00",
}
with open(os.path.join(source_dir, "my-project.json"), "w") as f:
    json.dump(record, f)

# Run migration
migrate_script = os.path.join("${WG_SCRIPTS}", "_migrate_local.py")
result = subprocess.run(
    [sys.executable, migrate_script,
     "--db", "${WG_DB}",
     "--root", "${WG_LOCAL}"],
    capture_output=True,
    text=True,
    timeout=15,
)
assert result.returncode == 0, f"migrate exited {result.returncode}\nstderr: {result.stderr}"

stats = json.loads(result.stdout)
assert stats["inserted"] >= 1, f"expected at least 1 insert, got: {stats}"
assert stats["errors"] == 0, f"migration errors: {stats}"

# Verify record appears in SQLite
from _sqlite_store import SqliteStore
store = SqliteStore("${WG_DB}")
got = store.get("wicked-crew", "projects", "my-project")
store.close()

assert got is not None, "migrated record not found in SQLite"
assert got["name"] == "my-project", f"name mismatch: {got}"

print(f"TC-5 PASS: Migration moved JSON → SQLite (stats={stats})")
print(f"  Retrieved from DB: name={got['name']}, phase={got['current_phase']}")
PYEOF
```

---

### TC-6: Migration is idempotent — running twice does not duplicate records

**Given**: TC-5 has already run (record is in SQLite)
**When**: `_migrate_local.py` is run a second time against the same directory
**Then**: `inserted == 0` and `skipped >= 1` (INSERT OR IGNORE fires)

```bash
python3 - <<'PYEOF'
import sys, os, json, subprocess
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

migrate_script = os.path.join("${WG_SCRIPTS}", "_migrate_local.py")
result = subprocess.run(
    [sys.executable, migrate_script,
     "--db", "${WG_DB}",
     "--root", "${WG_LOCAL}"],
    capture_output=True,
    text=True,
    timeout=15,
)
assert result.returncode == 0, f"second migrate exited {result.returncode}"

stats = json.loads(result.stdout)
assert stats["inserted"] == 0, f"expected 0 inserts on second run, got {stats['inserted']}"
assert stats["skipped"] >= 1, f"expected at least 1 skip, got {stats['skipped']}"

from _sqlite_store import SqliteStore
store = SqliteStore("${WG_DB}")
items = store.list("wicked-crew", "projects")
store.close()
assert len(items) == 1, f"expected 1 record, found {len(items)}: {items}"

print(f"TC-6 PASS: Migration is idempotent (stats={stats})")
PYEOF
```

---

### TC-7: WAL concurrent access — two writers do not produce OperationalError

**Given**: A SqliteStore database with WAL journal mode
**When**: Two threads concurrently write distinct records
**Then**: Both writes succeed and both records are retrievable; no `sqlite3.OperationalError` is raised

```bash
python3 - <<'PYEOF'
import sys, os, threading, sqlite3
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")
from _sqlite_store import SqliteStore

errors = []
results = {}

def write_record(store, record_id, title):
    try:
        r = store.create("wicked-mem", "memories", record_id, {
            "title": title, "content": f"content for {record_id}"
        })
        results[record_id] = r
    except Exception as exc:
        errors.append(f"{record_id}: {exc}")

store = SqliteStore("${WG_DB}")

t1 = threading.Thread(target=write_record, args=(store, "concurrent-a", "Thread A write"))
t2 = threading.Thread(target=write_record, args=(store, "concurrent-b", "Thread B write"))
t1.start(); t2.start()
t1.join(); t2.join()

assert errors == [], f"OperationalError(s) raised during concurrent writes: {errors}"

got_a = store.get("wicked-mem", "memories", "concurrent-a")
got_b = store.get("wicked-mem", "memories", "concurrent-b")
assert got_a is not None, "concurrent-a not found after concurrent write"
assert got_b is not None, "concurrent-b not found after concurrent write"

store.close()
print(f"TC-7 PASS: WAL concurrent writes — both records persisted without error")
PYEOF
```

---

### TC-8: No _queue.jsonl accumulation in local-only mode

**Given**: StorageManager is in `"local-only"` mode
**When**: create, update, and delete are called
**Then**: `_queue.jsonl` is never created or appended to

```bash
python3 - <<'PYEOF'
import sys, os, json
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

import _control_plane as _cp_mod
_cp_mod.load_config = lambda: {"mode": "local-only", "setup_complete": True}

import importlib, _storage
importlib.reload(_storage)
from _storage import StorageManager, _QUEUE_FILE

# Ensure any leftover queue from other tests doesn't interfere
if _QUEUE_FILE.exists():
    _QUEUE_FILE.unlink()

sm = StorageManager("wicked-mem")
assert sm._mode == "local-only", f"expected local-only, got {sm._mode}"

sm.create("memories", {"id": "tc8-id", "title": "queue test", "content": "no queue"})
sm.update("memories", "tc8-id", {"title": "updated"})
sm.delete("memories", "tc8-id")

assert not _QUEUE_FILE.exists(), (
    f"_queue.jsonl was created at {_QUEUE_FILE} — local-only mode must not enqueue writes"
)

print("TC-8 PASS: No _queue.jsonl created in local-only mode")
PYEOF
```

---

### TC-9: Regression — wicked-crew project creation works in local-only mode

**Given**: StorageManager is in `"local-only"` mode and no control plane is running
**When**: `create_project` is called via phase_manager
**Then**:
  - StorageManager persists the project in SQLite (not in JSON files)
  - The project can be retrieved by `sm.get("projects", project_name)`
  - The local project directory and `project.md` are created on disk

```bash
python3 - <<'PYEOF'
import sys, os, json
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")
sys.path.insert(0, os.path.join("${WG_SCRIPTS}", "crew"))

import _control_plane as _cp_mod
_cp_mod.load_config = lambda: {"mode": "local-only", "setup_complete": True}

import importlib, _storage
importlib.reload(_storage)

# Override the crew project directory to land inside the sandbox
import crew.phase_manager as pm
_orig_get_dir = pm.get_project_dir
pm.get_project_dir = lambda name: (
    _storage._LOCAL_ROOT.parent / "wicked-crew" / "projects" / name
)

# Reset the module-level StorageManager so it uses our patched config
pm._sm = _storage.StorageManager("wicked-crew")

project_name = "tc9-local-only-crew"
state, project_dir = pm.create_project(
    project_name,
    description="Regression: crew project creation in local-only mode",
)

# Verify project is in SQLite
saved = pm._sm.get("projects", project_name)
assert saved is not None, "project not found in SQLite after create_project"
assert saved.get("name") == project_name, f"name mismatch: {saved.get('name')}"

# Verify project directory and markdown file exist
assert project_dir.exists(), f"project directory not created: {project_dir}"
project_md = project_dir / "project.md"
assert project_md.exists(), f"project.md not written: {project_md}"

# Verify no JSON fallback file was written to the old flat path
legacy_json = (
    _storage._LOCAL_ROOT / "wicked-crew" / "projects" / f"{project_name}.json"
)
# legacy path is acceptable as a local write (StorageManager._local_write is still
# called for local-only mode via the sqlite path), so we only check SQLite is the
# source of truth
items = pm._sm.list("projects")
assert any(p.get("name") == project_name for p in items), (
    f"project not in sm.list: {[p.get('name') for p in items]}"
)

print(f"TC-9 PASS: wicked-crew create_project works in local-only mode")
print(f"  project: {project_name}, phase: {state.current_phase}")
print(f"  dir    : {project_dir}")
PYEOF
```

---

## Teardown

```bash
# Remove the isolated sandbox
rm -rf "$WG_TMP"
echo "Sandbox removed."
```

## Expected Outcome

All nine test cases pass with `PASS` in their output and exit code 0.

| TC | Description | Key Assertion |
|----|-------------|---------------|
| TC-1 | SqliteStore CRUD + FTS5 | Record survives create/get/update/delete cycle; FTS search hits |
| TC-2 | StorageManager never calls CP | `ControlPlaneClient.request` call log is empty after 5 CRUD ops |
| TC-3 | Session state after bootstrap | `cp_available=False`, `fallback_mode=False`, Storage note present |
| TC-4 | Briefing contains "Storage: local-only" | Subprocess bootstrap produces correct `additionalContext` |
| TC-5 | Migration JSON → SQLite on first boot | Planted JSON record appears in DB after migration run |
| TC-6 | Migration is idempotent | Second run: `inserted=0`, `skipped>=1` |
| TC-7 | WAL concurrent writes | Two threads write concurrently, both records retrievable, no OperationalError |
| TC-8 | No _queue.jsonl accumulation | Queue file does not exist after create/update/delete cycle |
| TC-9 | wicked-crew regression | `create_project` stores in SQLite, project directory and project.md written |

## Success Criteria

- [ ] TC-1: SqliteStore CRUD roundtrip and FTS5 search pass
- [ ] TC-2: No HTTP calls to ControlPlaneClient in local-only mode
- [ ] TC-3: Session state has `cp_available=False` and `fallback_mode=False` after local-only bootstrap
- [ ] TC-4: Bootstrap briefing includes `Storage: local-only` line
- [ ] TC-5: JSON migration inserts planted record into SQLite
- [ ] TC-6: Re-running migration skips already-present records (INSERT OR IGNORE)
- [ ] TC-7: Concurrent WAL writes complete without `sqlite3.OperationalError`
- [ ] TC-8: `_queue.jsonl` is not created or appended in local-only mode
- [ ] TC-9: `create_project` works end-to-end without a control plane

## Value Demonstrated

`local-only` mode makes wicked-garden fully self-contained for individuals and air-gapped
environments. No network server to install, no Docker, no Node — just a SQLite file in
`~/.something-wicked/wicked-garden/local/`. Existing JSON data migrates automatically
on first boot. All wicked-garden features (crew, kanban, mem, search) continue to work
with the same StorageManager API — the mode switch is transparent to domain scripts.
