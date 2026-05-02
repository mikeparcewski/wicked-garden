---
name: resume-projector-cross-session
title: Resume Projector — Snapshot Survives a Fresh Session and Identifies Active Phase
description: A session writes resume.json from the projector; a separate process reads it and correctly identifies the active phase without rebuilding from logs (#734)
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Resume Projector — Cross-Session Snapshot

The resume projector (#734) joins `daemon/projector.py` SQLite tables into
a per-project `crew/{project}/resume.json` snapshot. This scenario asserts
the **cross-session resume** contract:

1. Session A writes the snapshot (replay subcommand)
2. Session B (a fresh process — no shared state, no shared session_id)
   reads the snapshot file and correctly identifies the project's active
   phase, gate history, and active task count

The bus event log remains the source of truth. The snapshot is a derived
projection; reading it should never require the projector daemon to be
running, only the file to exist on disk.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-resume-cross-session-'))
")
echo "TEST_DIR=${TEST_DIR}"
export PROJECT_ID="resume-demo"
export PROJECT_DIR="${TEST_DIR}/${PROJECT_ID}"
export DB_PATH="${TEST_DIR}/projections.db"
```

**Expected**: `TEST_DIR=...` printed.

## Step 1: Stand up a minimal projector DB with a populated project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, sqlite3, json
db_path = os.environ['DB_PATH']
project_id = os.environ['PROJECT_ID']
conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, workspace TEXT, directory TEXT,
        archetype TEXT, complexity_score REAL, rigor_tier TEXT,
        current_phase TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active',
        chain_id TEXT, yolo_revoked_count INTEGER NOT NULL DEFAULT 0,
        last_revoke_reason TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
    CREATE TABLE phases (
        project_id TEXT NOT NULL, phase TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending', gate_score REAL,
        gate_verdict TEXT, gate_reviewer TEXT,
        started_at INTEGER, terminal_at INTEGER,
        rework_iterations INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL,
        PRIMARY KEY (project_id, phase));
    CREATE TABLE event_log (
        event_id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, chain_id TEXT,
        payload_json TEXT NOT NULL, projection_status TEXT NOT NULL,
        error_message TEXT, ingested_at INTEGER NOT NULL);
    CREATE TABLE tasks (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending', chain_id TEXT, event_type TEXT,
        metadata TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
""")
conn.execute("INSERT INTO projects (id,name,archetype,complexity_score,rigor_tier,current_phase,status,chain_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
    (project_id, "Resume Demo", "code-repo", 7, "full", "build", "active", f"{project_id}.root", 1700000000, 1700001000))
conn.execute("INSERT INTO phases (project_id,phase,state,gate_score,gate_verdict,gate_reviewer,started_at,terminal_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
    (project_id, "clarify", "approved", 0.85, "APPROVE", "rev-1", 1700000100, 1700000200, 1700000200))
conn.execute("INSERT INTO phases (project_id,phase,state,gate_score,gate_verdict,gate_reviewer,started_at,terminal_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
    (project_id, "design", "approved", 0.78, "APPROVE", "rev-2", 1700000300, 1700000400, 1700000400))
conn.execute("INSERT INTO phases (project_id,phase,state,updated_at) VALUES (?,?,?,?)",
    (project_id, "build", "in_progress", 1700001000))
conn.execute("INSERT INTO event_log (event_id,event_type,chain_id,payload_json,projection_status,ingested_at) VALUES (?,?,?,?,?,?)",
    (1, "wicked.gate.decided", f"{project_id}.clarify",
     json.dumps({"phase":"clarify","result":"APPROVE","score":0.85,"reviewer":"rev-1"}),
     "applied", 1700000200))
conn.execute("INSERT INTO tasks (id,session_id,status,chain_id,created_at,updated_at) VALUES (?,?,?,?,?,?)",
    ("t1", "session-A", "in_progress", f"{project_id}.build", 1700001000, 1700001100))
conn.commit()
conn.close()
print("seeded projector DB")
PYEOF
```

**Expected**: `seeded projector DB`

## Step 2: Session A — write the snapshot via the replay CLI

```bash
WG_PROJECTOR_DB_PATH="${DB_PATH}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resume_projector.py" \
  replay "${PROJECT_ID}" "${PROJECT_DIR}"
```

**Expected**: `WROTE: ${PROJECT_DIR}/resume.json`

```bash
test -f "${PROJECT_DIR}/resume.json" && echo "PASS: snapshot file exists"
```

## Step 3: Session B — fresh subshell, read the snapshot WITHOUT the projector DB env

This proves the snapshot is self-contained. Session B does not see the
projector DB; it only sees the on-disk `resume.json`.

```bash
(
  unset WG_PROJECTOR_DB_PATH
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resume_projector.py" \
    read "${PROJECT_DIR}"
) | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
snap = json.loads(sys.stdin.read())
assert snap['project_id'] == 'resume-demo', f'wrong project_id: {snap[\"project_id\"]!r}'
assert snap['project']['current_phase'] == 'build', f'wrong current_phase: {snap[\"project\"][\"current_phase\"]!r}'
assert snap['project']['archetype'] == 'code-repo'
assert snap['project']['complexity_score'] == 7
assert snap['active_tasks_count'] == 1
phases_by_name = {p['phase']: p for p in snap['phases']}
assert 'clarify' in phases_by_name and phases_by_name['clarify']['gate_verdict'] == 'APPROVE'
assert 'design' in phases_by_name and phases_by_name['design']['gate_verdict'] == 'APPROVE'
assert 'build' in phases_by_name and phases_by_name['build']['state'] == 'in_progress'
assert snap['pointers']['dispatch_log'] == 'phases/build/dispatch-log.jsonl'
print('PASS: session B read the snapshot and identified active phase=build')
"
```

**Expected**: `PASS: session B read the snapshot and identified active phase=build`

## Step 4: Verify subcommand reports OK against unchanged projector

```bash
WG_PROJECTOR_DB_PATH="${DB_PATH}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resume_projector.py" \
  verify "${PROJECT_ID}" "${PROJECT_DIR}"
```

**Expected**: `OK`

## Step 5: Mutate the projector — verify must surface divergence WITHOUT rewriting

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, sqlite3, json
conn = sqlite3.connect(os.environ['DB_PATH'])
conn.execute("INSERT INTO event_log (event_id,event_type,chain_id,payload_json,projection_status,ingested_at) VALUES (?,?,?,?,?,?)",
    (99, "wicked.gate.decided", f"{os.environ['PROJECT_ID']}.build",
     json.dumps({"phase":"build","result":"REJECT","score":0.2}),
     "applied", 1700002000))
conn.commit()
conn.close()
print("mutated projector with new REJECT event")
PYEOF

# Capture the on-disk snapshot bytes BEFORE verify.
before=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('${PROJECT_DIR}/resume.json').read_bytes()).hexdigest())
")

# verify must report DIVERGED and exit non-zero — but must NOT rewrite the file.
WG_PROJECTOR_DB_PATH="${DB_PATH}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resume_projector.py" \
  verify "${PROJECT_ID}" "${PROJECT_DIR}"
verify_exit=$?

after=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('${PROJECT_DIR}/resume.json').read_bytes()).hexdigest())
")

if [ "$verify_exit" = "0" ]; then
  echo "FAIL: verify exit code was 0; expected non-zero on divergence"
  exit 1
fi

if [ "$before" != "$after" ]; then
  echo "FAIL: verify silently rewrote the snapshot — contract violation"
  exit 1
fi

echo "PASS: verify reported divergence and did not rewrite on-disk snapshot"
```

**Expected**: a `DIVERGED:` line printed by the CLI, then `PASS: verify reported divergence and did not rewrite on-disk snapshot`.

## Success Criteria

- [ ] Step 2: `replay` writes `resume.json` to the project_dir
- [ ] Step 3: a separate process can read the snapshot WITHOUT access to the projector DB and correctly identify the active phase, gate history, and active task count
- [ ] Step 4: `verify` returns exit 0 when projector and snapshot agree
- [ ] Step 5: `verify` returns non-zero on divergence AND does not rewrite the on-disk snapshot

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR PROJECT_ID PROJECT_DIR DB_PATH
```
