---
name: local-mode
title: Local Storage Mode
description: Plugin operates standalone without external dependencies — DomainStore writes local JSON files, data persists across instances, and bootstrap briefing reflects local mode correctly
type: integration
difficulty: intermediate
estimated_minutes: 8
requires: [python3]
---

# Scenario: Local Storage Mode

Validates that wicked-garden is fully self-contained when no external integrations are
configured. The plugin must work with nothing but Python and a local filesystem.

Core storage layer: `DomainStore` (`scripts/_domain_store.py`) writes JSON files under
`~/.something-wicked/wicked-garden/projects/{project-slug}/{domain}/{source}/{id}.json`.
No external services, no SQLite migrations, no brain server required.

## Setup

All tests use an isolated temporary directory so they cannot touch a real
`~/.something-wicked` installation.

```bash
# Create an isolated sandbox — every test case below references $WG_TMP
export WG_TMP="$(mktemp -d /tmp/wg-local-mode-XXXXX)"
export WG_SCRIPTS="${CLAUDE_PLUGIN_ROOT}/scripts"

echo "Sandbox ready: $WG_TMP"
```

## Test Cases

---

### TC-1: DomainStore creates local JSON files without any external dependencies

**Given**: No external MCP tools configured, no brain server, no external services
**When**: `DomainStore.create` is called for the `wicked-mem` domain
**Then**:
  - The JSON file is written under the project-scoped local storage path for the sandbox
  - The file contains the correct payload fields

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PYEOF'
import sys, os, json
from pathlib import Path

# Point DomainStore at isolated sandbox
os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

# Override _LOCAL_ROOT before importing DomainStore
import _paths
_paths._LOCAL_ROOT = Path("${WG_TMP}") / ".something-wicked" / "wicked-garden" / "local"

import _domain_store
_domain_store._LOCAL_ROOT = _paths._LOCAL_ROOT

from _domain_store import DomainStore

ds = DomainStore("wicked-mem", hook_mode=True)  # hook_mode skips discovery
record = ds.create("memories", {
    "id": "tc1-test",
    "title": "Local mode test",
    "content": "DomainStore writes local JSON without external deps",
})

assert record is not None, "create() returned None"
assert record.get("id") == "tc1-test", f"id mismatch: {record.get('id')}"
assert record.get("title") == "Local mode test", f"title mismatch: {record.get('title')}"

# Verify the JSON file was written to disk
expected_path = _domain_store._LOCAL_ROOT / "wicked-mem" / "memories" / "tc1-test.json"
assert expected_path.exists(), f"JSON file not created at {expected_path}"

on_disk = json.loads(expected_path.read_text())
assert on_disk["id"] == "tc1-test", f"on-disk id mismatch: {on_disk}"
assert on_disk["content"] == "DomainStore writes local JSON without external deps"

print(f"TC-1 PASS: DomainStore created JSON at {expected_path}")
PYEOF
```

---

### TC-2: Data persists across DomainStore instances

**Given**: A record was written by one DomainStore instance
**When**: A fresh DomainStore instance for the same domain calls `get` and `list`
**Then**: The record is returned correctly — local JSON is the durable store

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PYEOF'
import sys, os, json
from pathlib import Path

os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

import _paths
_paths._LOCAL_ROOT = Path("${WG_TMP}") / ".something-wicked" / "wicked-garden" / "local"

import _domain_store
_domain_store._LOCAL_ROOT = _paths._LOCAL_ROOT

from _domain_store import DomainStore

# Instance 1: write
ds1 = DomainStore("wicked-crew", hook_mode=True)
ds1.create("projects", {
    "id": "tc2-project",
    "name": "tc2-project",
    "current_phase": "clarify",
})

# Instance 2: read (fresh object, same domain)
ds2 = DomainStore("wicked-crew", hook_mode=True)

got = ds2.get("projects", "tc2-project")
assert got is not None, "get() returned None on second instance"
assert got["name"] == "tc2-project", f"name mismatch: {got}"
assert got["current_phase"] == "clarify", f"phase mismatch: {got}"

all_projects = ds2.list("projects")
assert any(p.get("id") == "tc2-project" for p in all_projects), (
    f"project not in list: {[p.get('id') for p in all_projects]}"
)

print(f"TC-2 PASS: Data persisted across DomainStore instances ({len(all_projects)} projects in list)")
PYEOF
```

---

### TC-3: DomainStore update and delete work in local mode

**Given**: A record exists in local JSON storage
**When**: `update` patches a field, then `delete` soft-deletes the record
**Then**:
  - `update` returns the merged record with the new field value
  - `get` after `delete` returns `None` (soft-delete hides the record)
  - `list` after `delete` excludes the record

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PYEOF'
import sys, os
from pathlib import Path

os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

import _paths
_paths._LOCAL_ROOT = Path("${WG_TMP}") / ".something-wicked" / "wicked-garden" / "local"

import _domain_store
_domain_store._LOCAL_ROOT = _paths._LOCAL_ROOT

from _domain_store import DomainStore

ds = DomainStore("wicked-garden:mem", hook_mode=True)

ds.create("tasks", {"id": "tc3-task", "title": "Original title", "status": "pending"})

# Update
updated = ds.update("tasks", "tc3-task", {"status": "in_progress"})
assert updated is not None, "update() returned None"
assert updated["status"] == "in_progress", f"status not updated: {updated}"
assert updated["title"] == "Original title", f"title clobbered: {updated}"

# Delete
deleted = ds.delete("tasks", "tc3-task")
assert deleted is True, "delete() returned False"

# get() after delete must return None
gone = ds.get("tasks", "tc3-task")
assert gone is None, f"get() after delete should return None, got: {gone}"

# list() after delete must exclude the record
tasks = ds.list("tasks")
assert not any(t.get("id") == "tc3-task" for t in tasks), (
    f"deleted task still in list: {tasks}"
)

print("TC-3 PASS: update and soft-delete work correctly in local mode")
PYEOF
```

---

### TC-4: Bootstrap briefing contains "Storage: local" in additionalContext

**Given**: Config file under HOME contains `"mode": "local-only"` and `"setup_complete": true`
**When**: `bootstrap.py` is invoked as a subprocess (reproduces the real hook path)
**Then**: The JSON output's `additionalContext` contains the string `"Storage:"` and `"local"`

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PYEOF'
import sys, os, json, subprocess
from pathlib import Path

home = Path("${WG_TMP}")
os.makedirs(home, exist_ok=True)

# Write a minimal local-only config
config_path = home / "config.json"
config_path.write_text(json.dumps({"mode": "local-only", "setup_complete": True}))

bootstrap = os.path.join("${CLAUDE_PLUGIN_ROOT}", "hooks", "scripts", "bootstrap.py")
result = subprocess.run(
    [sys.executable, bootstrap],
    input="{}",
    capture_output=True,
    text=True,
    env={**os.environ, "HOME": str(home), "CLAUDE_SESSION_ID": "tc4-test-session"},
    timeout=15,
)

assert result.returncode == 0, (
    f"bootstrap exited {result.returncode}\nstderr: {result.stderr}"
)

output = json.loads(result.stdout)
ctx = output.get("hookSpecificOutput", {}).get("additionalContext", "")

assert "Storage:" in ctx and "local" in ctx, (
    f"'Storage:.*local' not found in briefing.\nContext snippet: {ctx[:400]}"
)

matching = [l for l in ctx.splitlines() if "Storage:" in l]
print("TC-4 PASS: Bootstrap briefing contains Storage: local")
print(f"  Relevant line: {matching}")
PYEOF
```

---

### TC-5: DomainStore search filters by query token

**Given**: Two records in local JSON storage with distinct content
**When**: `search("memories", "authentication")` is called
**Then**: Only the record containing "authentication" is returned

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PYEOF'
import sys, os
from pathlib import Path

os.environ["HOME"] = "${WG_TMP}"
sys.path.insert(0, "${WG_SCRIPTS}")

import _paths
_paths._LOCAL_ROOT = Path("${WG_TMP}") / ".something-wicked" / "wicked-garden" / "local"

import _domain_store
_domain_store._LOCAL_ROOT = _paths._LOCAL_ROOT

from _domain_store import DomainStore

ds = DomainStore("wicked-mem", hook_mode=True)

ds.create("memories", {
    "id": "tc5-auth",
    "title": "Authentication flow",
    "content": "Describes JWT authentication and token refresh logic",
})
ds.create("memories", {
    "id": "tc5-deploy",
    "title": "Deployment checklist",
    "content": "Steps for deploying to production environment",
})

results = ds.search("memories", "authentication")
ids = [r.get("id") for r in results]

assert "tc5-auth" in ids, f"auth record not in results: {ids}"
assert "tc5-deploy" not in ids, f"deploy record incorrectly matched: {ids}"

print(f"TC-5 PASS: search() filters by query token (matched {len(results)} record(s))")
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

All five test cases pass with `PASS` in their output and exit code 0.

| TC | Description | Key Assertion |
|----|-------------|---------------|
| TC-1 | DomainStore creates local JSON | File written to expected path with correct content |
| TC-2 | Data persists across instances | Fresh DomainStore instance reads what the first wrote |
| TC-3 | Update and delete | Patched fields merge; soft-delete hides record from get/list |
| TC-4 | Bootstrap reflects local mode | `Storage: local` present in `additionalContext` |
| TC-5 | Search filters by token | Only matching record returned, non-matching excluded |

## Success Criteria

- [ ] TC-1: `DomainStore.create` writes a JSON file to the local storage path
- [ ] TC-2: A second `DomainStore` instance reads records written by the first
- [ ] TC-3: `update` merges diff and `delete` soft-deletes (hidden from get/list)
- [ ] TC-4: Bootstrap subprocess outputs `Storage: local` in `additionalContext`
- [ ] TC-5: `search()` returns only records whose content matches the query token

## Value Demonstrated

`DomainStore` makes wicked-garden fully self-contained for individuals and air-gapped
environments. No network server to install, no Docker, no Node — just JSON files under
`~/.something-wicked/wicked-garden/projects/{project-slug}/`. All wicked-garden features
(crew, mem, search) use the same `DomainStore` API. External integrations (Linear,
Jira, Notion) are optional; the plugin works identically without them.
