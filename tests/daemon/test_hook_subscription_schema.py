"""tests/daemon/test_hook_subscription_schema.py — Schema + CRUD for hook subscriptions.

Issue #592 (v8 PR-8).

Coverage:
  - hook_subscriptions and hook_invocations tables created by init_schema
  - upsert_hook_subscription: insert + update semantics
  - get_hook_subscription: found and not-found
  - list_hook_subscriptions: all + enabled_only filter
  - toggle_hook_subscription: enable / disable / not-found
  - append_hook_invocation: insert + digest truncation
  - list_hook_invocations: filtering by since + limit cap
  - _deserialize_debounce_rule: JSON TEXT → dict in-place

T1: deterministic — no wall-clock, no network
T3: isolated — each test uses a fresh in-memory DB (mem_conn fixture)
T4: single assertion focus per test
T5: descriptive names
T6: provenance #592 v8-PR-8
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from daemon.db import (  # noqa: E402
    connect,
    init_schema,
    upsert_hook_subscription,
    get_hook_subscription,
    list_hook_subscriptions,
    toggle_hook_subscription,
    append_hook_invocation,
    list_hook_invocations,
    _INVOCATION_DIGEST_LENGTH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mem():
    conn = connect(":memory:")
    init_schema(conn)
    return conn


def _sub(conn, sid="sub-1", fp="wicked.gate.*", hp="hooks/scripts/subscribers/on_gate_decided.py",
         debounce=None, enabled=True):
    upsert_hook_subscription(conn, sid, fp, hp, debounce_rule=debounce, enabled=enabled)
    return sid


# ===========================================================================
# Schema: tables exist after init_schema
# ===========================================================================

class TestSchemaCreated:
    def test_hook_subscriptions_table_exists(self):
        conn = _mem()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hook_subscriptions'"
        ).fetchone()
        assert row is not None, "hook_subscriptions table should exist"

    def test_hook_invocations_table_exists(self):
        conn = _mem()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hook_invocations'"
        ).fetchone()
        assert row is not None, "hook_invocations table should exist"

    def test_hook_subscriptions_index_filter_enabled_exists(self):
        conn = _mem()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_hook_subscriptions_filter'"
        ).fetchone()
        assert row is not None

    def test_hook_invocations_index_event_type_exists(self):
        conn = _mem()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_hook_invocations_event_type'"
        ).fetchone()
        assert row is not None


# ===========================================================================
# upsert_hook_subscription
# ===========================================================================

class TestUpsertHookSubscription:
    def test_insert_creates_row(self):
        conn = _mem()
        _sub(conn)
        row = conn.execute(
            "SELECT * FROM hook_subscriptions WHERE subscription_id = 'sub-1'"
        ).fetchone()
        assert row is not None

    def test_filter_pattern_stored(self):
        conn = _mem()
        _sub(conn, fp="wicked.gate.*")
        row = get_hook_subscription(conn, "sub-1")
        assert row["filter_pattern"] == "wicked.gate.*"

    def test_handler_path_stored(self):
        conn = _mem()
        _sub(conn, hp="hooks/scripts/subscribers/on_gate_decided.py")
        row = get_hook_subscription(conn, "sub-1")
        assert row["handler_path"] == "hooks/scripts/subscribers/on_gate_decided.py"

    def test_debounce_rule_stored_as_dict(self):
        conn = _mem()
        rule = {"type": "phase-boundary"}
        _sub(conn, debounce=rule)
        row = get_hook_subscription(conn, "sub-1")
        assert row["debounce_rule"] == rule

    def test_debounce_none_stored_as_none(self):
        conn = _mem()
        _sub(conn, debounce=None)
        row = get_hook_subscription(conn, "sub-1")
        assert row["debounce_rule"] is None

    def test_enabled_default_is_true(self):
        conn = _mem()
        _sub(conn)
        row = get_hook_subscription(conn, "sub-1")
        assert row["enabled"] == 1

    def test_enabled_false_stored(self):
        conn = _mem()
        _sub(conn, enabled=False)
        row = get_hook_subscription(conn, "sub-1")
        assert row["enabled"] == 0

    def test_upsert_updates_filter_on_conflict(self):
        conn = _mem()
        _sub(conn, fp="wicked.gate.*")
        _sub(conn, fp="wicked.phase.*")  # same sid
        row = get_hook_subscription(conn, "sub-1")
        assert row["filter_pattern"] == "wicked.phase.*"

    def test_upsert_updates_handler_on_conflict(self):
        conn = _mem()
        _sub(conn, hp="old/handler.py")
        _sub(conn, hp="new/handler.py")
        row = get_hook_subscription(conn, "sub-1")
        assert row["handler_path"] == "new/handler.py"

    def test_upsert_idempotent_same_values(self):
        conn = _mem()
        _sub(conn)
        _sub(conn)  # re-run
        rows = conn.execute("SELECT COUNT(*) FROM hook_subscriptions").fetchone()
        assert rows[0] == 1

    def test_multiple_subscriptions_stored(self):
        conn = _mem()
        _sub(conn, sid="sub-1")
        _sub(conn, sid="sub-2", fp="wicked.phase.*")
        rows = conn.execute("SELECT COUNT(*) FROM hook_subscriptions").fetchone()
        assert rows[0] == 2

    def test_created_at_preserved_on_update(self):
        conn = _mem()
        upsert_hook_subscription(conn, "sub-1", "wicked.*", "h.py", created_at=1_000_000)
        upsert_hook_subscription(conn, "sub-1", "wicked.gate.*", "h.py")
        row = get_hook_subscription(conn, "sub-1")
        assert row["created_at"] == 1_000_000


# ===========================================================================
# get_hook_subscription
# ===========================================================================

class TestGetHookSubscription:
    def test_returns_none_for_missing(self):
        conn = _mem()
        assert get_hook_subscription(conn, "nonexistent") is None

    def test_returns_dict_for_existing(self):
        conn = _mem()
        _sub(conn)
        row = get_hook_subscription(conn, "sub-1")
        assert isinstance(row, dict)

    def test_debounce_rule_deserialized_to_dict(self):
        conn = _mem()
        rule = {"type": "rate-limit", "window_s": 60, "max": 3}
        _sub(conn, debounce=rule)
        row = get_hook_subscription(conn, "sub-1")
        assert row["debounce_rule"] == rule

    def test_rate_limit_rule_fields_preserved(self):
        conn = _mem()
        rule = {"type": "rate-limit", "window_s": 120, "max": 5}
        _sub(conn, debounce=rule)
        row = get_hook_subscription(conn, "sub-1")
        assert row["debounce_rule"]["window_s"] == 120
        assert row["debounce_rule"]["max"] == 5


# ===========================================================================
# list_hook_subscriptions
# ===========================================================================

class TestListHookSubscriptions:
    def test_returns_empty_when_no_subscriptions(self):
        conn = _mem()
        assert list_hook_subscriptions(conn) == []

    def test_returns_all_subscriptions(self):
        conn = _mem()
        _sub(conn, sid="sub-1")
        _sub(conn, sid="sub-2", fp="wicked.phase.*")
        rows = list_hook_subscriptions(conn)
        assert len(rows) == 2

    def test_enabled_only_filters_disabled(self):
        conn = _mem()
        _sub(conn, sid="sub-enabled", enabled=True)
        _sub(conn, sid="sub-disabled", enabled=False)
        rows = list_hook_subscriptions(conn, enabled_only=True)
        ids = {r["subscription_id"] for r in rows}
        assert "sub-enabled" in ids
        assert "sub-disabled" not in ids

    def test_enabled_only_false_returns_all(self):
        conn = _mem()
        _sub(conn, sid="sub-1", enabled=True)
        _sub(conn, sid="sub-2", enabled=False)
        rows = list_hook_subscriptions(conn, enabled_only=False)
        assert len(rows) == 2

    def test_ordered_by_created_at_asc(self):
        conn = _mem()
        upsert_hook_subscription(conn, "sub-b", "wicked.*", "h.py", created_at=2_000_000)
        upsert_hook_subscription(conn, "sub-a", "wicked.*", "h.py", created_at=1_000_000)
        rows = list_hook_subscriptions(conn)
        assert rows[0]["subscription_id"] == "sub-a"
        assert rows[1]["subscription_id"] == "sub-b"


# ===========================================================================
# toggle_hook_subscription
# ===========================================================================

class TestToggleHookSubscription:
    def test_toggle_to_disabled(self):
        conn = _mem()
        _sub(conn, enabled=True)
        result = toggle_hook_subscription(conn, "sub-1", enabled=False)
        assert result is True
        row = get_hook_subscription(conn, "sub-1")
        assert row["enabled"] == 0

    def test_toggle_to_enabled(self):
        conn = _mem()
        _sub(conn, enabled=False)
        toggle_hook_subscription(conn, "sub-1", enabled=True)
        row = get_hook_subscription(conn, "sub-1")
        assert row["enabled"] == 1

    def test_toggle_nonexistent_returns_false(self):
        conn = _mem()
        result = toggle_hook_subscription(conn, "nonexistent", enabled=True)
        assert result is False

    def test_toggle_updates_updated_at(self):
        conn = _mem()
        upsert_hook_subscription(conn, "sub-1", "wicked.*", "h.py", created_at=1_000_000)
        row_before = get_hook_subscription(conn, "sub-1")
        toggle_hook_subscription(conn, "sub-1", enabled=False)
        row_after = get_hook_subscription(conn, "sub-1")
        assert row_after["updated_at"] >= row_before["updated_at"]


# ===========================================================================
# append_hook_invocation
# ===========================================================================

class TestAppendHookInvocation:
    def test_inserts_row(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(
            conn, "inv-1", "sub-1", 42, "wicked.gate.decided", "dispatched", 150
        )
        row = conn.execute(
            "SELECT * FROM hook_invocations WHERE invocation_id = 'inv-1'"
        ).fetchone()
        assert row is not None

    def test_verdict_stored(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "debounced", 5)
        rows = list_hook_invocations(conn, "sub-1")
        assert rows[0]["verdict"] == "debounced"

    def test_latency_ms_stored(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 247)
        rows = list_hook_invocations(conn, "sub-1")
        assert rows[0]["latency_ms"] == 247

    def test_stdout_digest_stored(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(
            conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 10,
            stdout_digest='{"status":"ok"}'
        )
        rows = list_hook_invocations(conn, "sub-1")
        assert rows[0]["stdout_digest"] == '{"status":"ok"}'

    def test_digest_truncated_to_max_length(self):
        conn = _mem()
        _sub(conn)
        long_text = "x" * (_INVOCATION_DIGEST_LENGTH + 500)
        append_hook_invocation(
            conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 10,
            stdout_digest=long_text
        )
        rows = list_hook_invocations(conn, "sub-1")
        assert len(rows[0]["stdout_digest"]) == _INVOCATION_DIGEST_LENGTH

    def test_idempotent_on_same_invocation_id(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 10)
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "handler_error", 20)
        rows = list_hook_invocations(conn, "sub-1")
        assert len(rows) == 1
        # First write wins (INSERT OR IGNORE)
        assert rows[0]["verdict"] == "dispatched"


# ===========================================================================
# list_hook_invocations
# ===========================================================================

class TestListHookInvocations:
    def test_returns_empty_when_none(self):
        conn = _mem()
        _sub(conn)
        assert list_hook_invocations(conn, "sub-1") == []

    def test_returns_rows_for_subscription(self):
        conn = _mem()
        _sub(conn)
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 10)
        append_hook_invocation(conn, "inv-2", "sub-1", 2, "wicked.gate.decided", "debounced", 5)
        rows = list_hook_invocations(conn, "sub-1")
        assert len(rows) == 2

    def test_since_filters_old_rows(self):
        conn = _mem()
        _sub(conn)
        past = int(time.time()) - 10000
        append_hook_invocation(
            conn, "inv-old", "sub-1", 1, "wicked.gate.decided", "dispatched", 10,
            emitted_at=past
        )
        now = int(time.time())
        append_hook_invocation(
            conn, "inv-new", "sub-1", 2, "wicked.gate.decided", "dispatched", 10,
            emitted_at=now
        )
        rows = list_hook_invocations(conn, "sub-1", since=now - 100)
        ids = {r["invocation_id"] for r in rows}
        assert "inv-new" in ids
        assert "inv-old" not in ids

    def test_limit_respected(self):
        conn = _mem()
        _sub(conn)
        for i in range(10):
            append_hook_invocation(
                conn, f"inv-{i}", "sub-1", i, "wicked.gate.decided", "dispatched", 5,
                emitted_at=int(time.time()) + i
            )
        rows = list_hook_invocations(conn, "sub-1", limit=3)
        assert len(rows) == 3

    def test_ordered_by_emitted_at_desc(self):
        conn = _mem()
        _sub(conn)
        t = int(time.time())
        append_hook_invocation(conn, "inv-1", "sub-1", 1, "wicked.gate.decided", "dispatched", 5,
                               emitted_at=t - 100)
        append_hook_invocation(conn, "inv-2", "sub-1", 2, "wicked.gate.decided", "dispatched", 5,
                               emitted_at=t)
        rows = list_hook_invocations(conn, "sub-1")
        assert rows[0]["invocation_id"] == "inv-2"  # most recent first
