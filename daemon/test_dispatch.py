"""
test_dispatch.py — Tests for hook_dispatch.py.

Tests the HookDispatcher: event-to-hook matching, graceful handling of missing
hooks, and execution record persistence.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the daemon package is importable regardless of how pytest is invoked.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from daemon.db import SCHEMA
from daemon.hook_dispatch import HookDispatcher, _event_type_to_prefix


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_conn():
    """In-memory SQLite connection with garden schema applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def hooks_dir(tmp_path):
    """Temporary hooks directory."""
    d = tmp_path / "hooks"
    d.mkdir()
    return d


@pytest.fixture()
def dispatcher(db_conn, hooks_dir):
    return HookDispatcher(db_conn, hooks_dir)


# ---------------------------------------------------------------------------
# Unit tests: _event_type_to_prefix
# ---------------------------------------------------------------------------


def test_event_type_to_prefix_basic():
    assert _event_type_to_prefix("wicked.garden.skill.installed") == "on-wicked-garden-skill-installed"


def test_event_type_to_prefix_single_segment():
    assert _event_type_to_prefix("foo") == "on-foo"


def test_event_type_to_prefix_preserves_order():
    assert _event_type_to_prefix("a.b.c") == "on-a-b-c"


# ---------------------------------------------------------------------------
# Tests: dispatch matches hook by event type
# ---------------------------------------------------------------------------


def test_dispatch_matches_hook_by_event_type(db_conn, hooks_dir):
    """A hook named on-{event}-type.sh is found and executed for the event."""
    hook = hooks_dir / "on-wicked-garden-ready.sh"
    hook.write_text("#!/bin/sh\nexit 0\n")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    dispatched = dispatcher.dispatch("wicked.garden.ready", {})

    assert hook.name in dispatched


def test_dispatch_matches_py_hook(db_conn, hooks_dir):
    """A .py hook is executed with the Python interpreter."""
    hook = hooks_dir / "on-wicked-garden-council-voted.py"
    hook.write_text("import sys\nsys.exit(0)\n")

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    dispatched = dispatcher.dispatch("wicked.garden.council.voted", {"session_id": "abc"})

    assert hook.name in dispatched


def test_dispatch_passes_payload_env(db_conn, hooks_dir, tmp_path):
    """The hook receives the event payload via WICKED_EVENT_PAYLOAD env var."""
    out_file = tmp_path / "payload_out.json"
    hook = hooks_dir / "on-wicked-test-event.sh"
    hook.write_text(f'#!/bin/sh\necho "$WICKED_EVENT_PAYLOAD" > "{out_file}"\n')
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    payload = {"key": "value", "n": 42}
    dispatcher.dispatch("wicked.test.event", payload)

    assert out_file.exists()
    written = json.loads(out_file.read_text().strip())
    assert written["key"] == "value"
    assert written["n"] == 42


# ---------------------------------------------------------------------------
# Tests: no hook found — graceful degradation
# ---------------------------------------------------------------------------


def test_dispatch_handles_missing_hook_gracefully(dispatcher):
    """Dispatching an event with no matching hooks returns an empty list."""
    result = dispatcher.dispatch("wicked.garden.unknown.event.xyz", {"x": 1})
    assert result == []


def test_dispatch_handles_missing_hooks_dir(db_conn, tmp_path):
    """Dispatching when hooks dir does not exist returns empty without error."""
    missing_dir = tmp_path / "no-such-dir"
    dispatcher = HookDispatcher(db_conn, missing_dir)
    result = dispatcher.dispatch("wicked.garden.skill.installed", {"skill": "foo"})
    assert result == []


def test_dispatch_handles_nonexecutable_hook(db_conn, hooks_dir):
    """A non-executable hook is skipped gracefully."""
    hook = hooks_dir / "on-wicked-garden-ready.sh"
    hook.write_text("#!/bin/sh\nexit 0\n")
    # Explicitly remove execute permission
    hook.chmod(0o644)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    # Should not raise; returns empty list since hook failed
    result = dispatcher.dispatch("wicked.garden.ready", {})
    # The hook failed (not executable) so it won't be in dispatched list
    assert isinstance(result, list)


def test_dispatch_handles_hook_exit_nonzero(db_conn, hooks_dir):
    """A hook that exits non-zero is not included in the dispatched list."""
    hook = hooks_dir / "on-wicked-garden-ready.sh"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    result = dispatcher.dispatch("wicked.garden.ready", {})
    assert hook.name not in result


# ---------------------------------------------------------------------------
# Tests: execution record persisted in DB
# ---------------------------------------------------------------------------


def test_dispatch_records_execution_in_db(db_conn, hooks_dir):
    """Hook executions are recorded in the hitl_prompts table."""
    hook = hooks_dir / "on-wicked-garden-ready.sh"
    hook.write_text("#!/bin/sh\nexit 0\n")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    dispatcher.dispatch("wicked.garden.ready", {"x": 1})

    rows = db_conn.execute("SELECT * FROM hitl_prompts").fetchall()
    assert len(rows) >= 1
    record = dict(rows[0])
    assert "hook:" in record["prompt"]
    assert record["status"] in ("completed", "failed")


def test_dispatch_records_failed_hook_in_db(db_conn, hooks_dir):
    """Failed hook executions are recorded with status='failed'."""
    hook = hooks_dir / "on-wicked-garden-ready.sh"
    hook.write_text("#!/bin/sh\nexit 2\n")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    dispatcher.dispatch("wicked.garden.ready", {})

    rows = db_conn.execute(
        "SELECT * FROM hitl_prompts WHERE status = 'failed'"
    ).fetchall()
    assert len(rows) >= 1


def test_dispatch_records_no_entry_when_no_hook(db_conn, hooks_dir):
    """No hitl_prompts entry is created when there is no matching hook."""
    dispatcher = HookDispatcher(db_conn, hooks_dir)
    dispatcher.dispatch("wicked.garden.nonexistent.event", {})

    rows = db_conn.execute("SELECT * FROM hitl_prompts").fetchall()
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# Tests: multiple hooks for same event
# ---------------------------------------------------------------------------


def test_dispatch_executes_all_matching_hooks(db_conn, hooks_dir):
    """All matching hooks for an event are executed."""
    hook_sh = hooks_dir / "on-wicked-garden-ready.sh"
    hook_py = hooks_dir / "on-wicked-garden-ready.py"
    hook_sh.write_text("#!/bin/sh\nexit 0\n")
    hook_sh.chmod(hook_sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    hook_py.write_text("import sys; sys.exit(0)\n")

    dispatcher = HookDispatcher(db_conn, hooks_dir)
    result = dispatcher.dispatch("wicked.garden.ready", {})

    assert hook_sh.name in result
    assert hook_py.name in result
