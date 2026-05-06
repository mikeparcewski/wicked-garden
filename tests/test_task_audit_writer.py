"""tests/test_task_audit_writer.py — Phase 3 cross-session task audit writer.

Provenance: jam session 03 designed a thin cross-session chain index
(NOT a parallel task-state mirror, NOT an HMAC-signed dispatch log).
This file owns the JSONL schema and is the SOLE writer; tests pin both.

T1: deterministic — pure I/O against tmp_path
T3: isolated — every test gets its own tmp directory
T4: single focus per test
T5: descriptive names
T6: docstrings cite session 03 / decision memory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/crew on sys.path so the module imports as `_task_audit_writer`
# without needing the `crew` package prefix; conftest.py keeps scripts/
# at index 0 so we append (not insert).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CREW_DIR = _REPO_ROOT / "scripts" / "crew"
if str(_CREW_DIR) not in sys.path:
    sys.path.append(str(_CREW_DIR))

import _task_audit_writer as audit  # noqa: E402


@pytest.fixture
def isolated_audit_dir(tmp_path, monkeypatch):
    """Redirect CLAUDE_CONFIG_DIR so the writer's audit_dir() points at
    a per-test directory. Avoids cross-test contamination."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    return tmp_path / "wicked-garden" / "task-audit"


# ---------------------------------------------------------------------------
# append_task_audit — write side
# ---------------------------------------------------------------------------

def test_taskcreate_writes_one_jsonl_line(isolated_audit_dir):
    """Phase 3 / session 03: a single TaskCreate produces one JSONL
    entry under the per-session file."""
    ok = audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={
            "subject": "Implement OAuth flow",
            "metadata": {
                "chain_id": "feat-oauth.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
            },
        },
        tool_response={"taskId": "task-001"},
        session_id="abc-123",
    )
    assert ok is True
    f = isolated_audit_dir / "abc-123.jsonl"
    assert f.exists()
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "TaskCreate"
    assert entry["task_id"] == "task-001"
    assert entry["chain_id"] == "feat-oauth.root"
    assert entry["status"] == "pending"
    assert entry["schema_version"] == audit.AUDIT_SCHEMA_VERSION


def test_taskupdate_appends_second_line(isolated_audit_dir):
    """Phase 3: TaskUpdate after TaskCreate appends; the writer is
    append-only (no rewrites)."""
    audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "Step", "metadata": {"chain_id": "c.root"}},
        tool_response={"taskId": "t1"},
        session_id="s1",
    )
    audit.append_task_audit(
        tool_name="TaskUpdate",
        tool_input={"taskId": "t1", "status": "completed"},
        tool_response=None,
        session_id="s1",
    )
    f = isolated_audit_dir / "s1.jsonl"
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    e2 = json.loads(lines[1])
    assert e2["tool"] == "TaskUpdate"
    assert e2["task_id"] == "t1"
    assert e2["status"] == "completed"


def test_unsupported_tool_returns_false_and_writes_nothing(isolated_audit_dir):
    """Phase 3: only TaskCreate / TaskUpdate are accepted. Anything
    else short-circuits before any file I/O."""
    ok = audit.append_task_audit(
        tool_name="Bash",
        tool_input={"command": "ls"},
        tool_response={"output": "x"},
        session_id="s1",
    )
    assert ok is False
    assert not isolated_audit_dir.exists()


def test_session_id_sanitised_against_path_traversal(isolated_audit_dir):
    """Phase 3 / security: session_id is interpolated into a filename;
    a malicious value with `..` or `/` must NOT escape the audit dir."""
    ok = audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "x", "metadata": {"chain_id": "c"}},
        tool_response={"taskId": "t1"},
        session_id="../../etc/passwd",
    )
    assert ok is True
    # The file must live inside the audit dir, with a sanitised name.
    files = list(isolated_audit_dir.iterdir())
    assert len(files) == 1
    assert all(c.isalnum() or c in "_.-" for c in files[0].stem)


def test_writer_fails_open_on_io_error(monkeypatch, tmp_path):
    """Phase 3: any I/O failure swallowed; never raises into the hook.

    Force the failure by monkey-patching json.dumps inside the writer
    module to raise. The fail-open contract is the only thing keeping
    PostToolUse latency safe — a broken writer must NEVER take down a
    TaskCreate hook invocation.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))

    def boom(*args, **kwargs):
        raise RuntimeError("simulated json failure")

    monkeypatch.setattr(audit.json, "dumps", boom)

    ok = audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "x", "metadata": {"chain_id": "c"}},
        tool_response={"taskId": "t1"},
        session_id="s1",
    )
    assert ok is False


# ---------------------------------------------------------------------------
# scan_chain + latest_per_task — read side
# ---------------------------------------------------------------------------

def test_scan_chain_returns_empty_when_audit_dir_missing(monkeypatch, tmp_path):
    """Phase 3: missing audit dir → empty list, no exception (the
    cross-session fallback degrades cleanly when nothing has been written)."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "nonexistent"))
    assert audit.scan_chain("c.root") == []


def test_scan_chain_finds_entries_across_session_files(isolated_audit_dir):
    """Phase 3: the cross-session rescue. Entries written under
    different session-id files for the same chain_id must all surface
    in scan_chain."""
    audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "A", "metadata": {"chain_id": "shared.root"}},
        tool_response={"taskId": "t1"},
        session_id="alpha",
    )
    audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "B", "metadata": {"chain_id": "shared.root"}},
        tool_response={"taskId": "t2"},
        session_id="beta",
    )
    audit.append_task_audit(
        tool_name="TaskCreate",
        tool_input={"subject": "C", "metadata": {"chain_id": "other.root"}},
        tool_response={"taskId": "t3"},
        session_id="gamma",
    )
    rows = audit.scan_chain("shared.root")
    ids = {r.get("task_id") for r in rows}
    assert ids == {"t1", "t2"}


def test_scan_chain_skips_malformed_lines(isolated_audit_dir):
    """Phase 3 robustness: a corrupt JSONL line in one session file
    must not break the whole scan — skip the bad line, keep going."""
    isolated_audit_dir.mkdir(parents=True, exist_ok=True)
    target = isolated_audit_dir / "s1.jsonl"
    target.write_text(
        '{"chain_id": "c.root", "task_id": "t1"}\n'
        'this is not json\n'
        '{"chain_id": "c.root", "task_id": "t2"}\n',
        encoding="utf-8",
    )
    rows = audit.scan_chain("c.root")
    ids = sorted(r["task_id"] for r in rows)
    assert ids == ["t1", "t2"]


def test_latest_per_task_keeps_most_recent_entry():
    """Phase 3: TaskCreate then TaskUpdate for the same id should
    collapse to the most recent (the update). Verifier wants one row
    per task at the latest known status."""
    entries = [
        {"task_id": "t1", "ts": "2026-01-01T00:00:00Z", "status": "pending"},
        {"task_id": "t1", "ts": "2026-01-02T00:00:00Z", "status": "completed"},
        {"task_id": "t2", "ts": "2026-01-01T00:00:00Z", "status": "pending"},
    ]
    out = audit.latest_per_task(entries)
    by_id = {e["task_id"]: e for e in out}
    assert len(out) == 2
    assert by_id["t1"]["status"] == "completed"
    assert by_id["t2"]["status"] == "pending"
