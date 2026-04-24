"""tests/daemon/test_council_schema.py — Stream 5 schema tests for v8 PR-4.

Verifies:
- council_sessions and council_votes tables exist after init_schema
- Required indexes are present
- Unique/PK constraints on council_votes(session_id, model)
- Foreign-key cascade from council_sessions to council_votes
- CRUD functions (insert_council_session, upsert_council_vote,
  complete_council_session, get_council_session,
  list_council_sessions, list_council_votes) round-trip correctly

T1: deterministic — no wall-clock, in-memory DB.
T3: isolated — each test uses function-scoped mem_conn.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #594 v8-PR-4 council schema.
"""

from __future__ import annotations

import pytest

# sys.path setup is handled by tests/daemon/conftest.py


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _indexes(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCouncilTablesExist:
    """Verify schema presence after init_schema."""

    def test_council_sessions_table_created(self, mem_conn):
        assert "council_sessions" in _tables(mem_conn)

    def test_council_votes_table_created(self, mem_conn):
        assert "council_votes" in _tables(mem_conn)

    def test_expected_indexes_present(self, mem_conn):
        idx = _indexes(mem_conn)
        assert "idx_council_sessions_started" in idx, "missing idx_council_sessions_started"
        assert "idx_council_sessions_verdict" in idx, "missing idx_council_sessions_verdict"
        assert "idx_council_sessions_hitl_rule" in idx, "missing idx_council_sessions_hitl_rule"
        assert "idx_council_votes_session" in idx, "missing idx_council_votes_session"


class TestCouncilSessionInsert:
    """insert_council_session round-trips correctly."""

    def test_insert_and_get_session(self, mem_conn):
        from daemon.db import insert_council_session, get_council_session
        insert_council_session(
            mem_conn,
            session_id="sess-001",
            topic="Should we use event sourcing?",
            question="Evaluate event sourcing vs CRUD for the orders domain.",
            started_at=1_700_000_000,
        )
        row = get_council_session(mem_conn, "sess-001")
        assert row is not None
        assert row["id"] == "sess-001"
        assert row["topic"] == "Should we use event sourcing?"
        assert row["started_at"] == 1_700_000_000
        assert row["completed_at"] is None

    def test_insert_or_ignore_does_not_overwrite(self, mem_conn):
        from daemon.db import insert_council_session, get_council_session
        insert_council_session(mem_conn, "sess-002", "topic-a", "q-a", started_at=100)
        insert_council_session(mem_conn, "sess-002", "topic-b", "q-b", started_at=999)
        row = get_council_session(mem_conn, "sess-002")
        # Original row must survive the second insert (idempotent)
        assert row["topic"] == "topic-a"
        assert row["started_at"] == 100

    def test_get_nonexistent_session_returns_none(self, mem_conn):
        from daemon.db import get_council_session
        assert get_council_session(mem_conn, "no-such-session") is None


class TestCouncilVoteUpsert:
    """upsert_council_vote persists and can overwrite a vote row."""

    def _setup_session(self, conn):
        from daemon.db import insert_council_session
        insert_council_session(conn, "sess-v", "topic", "question", started_at=1_000)

    def test_upsert_single_vote(self, mem_conn):
        from daemon.db import upsert_council_vote, list_council_votes
        self._setup_session(mem_conn)
        upsert_council_vote(
            mem_conn,
            session_id="sess-v",
            model="gemini",
            verdict="APPROVE",
            confidence=0.85,
            rationale="Looks good",
            raw_response="Full response text",
            latency_ms=1200,
            emitted_at=1_001,
        )
        votes = list_council_votes(mem_conn, "sess-v")
        assert len(votes) == 1
        v = votes[0]
        assert v["model"] == "gemini"
        assert v["verdict"] == "APPROVE"
        assert v["confidence"] == pytest.approx(0.85)
        assert v["latency_ms"] == 1200

    def test_upsert_replaces_existing_vote(self, mem_conn):
        """A second upsert for the same (session_id, model) overwrites the first."""
        from daemon.db import upsert_council_vote, list_council_votes
        self._setup_session(mem_conn)
        upsert_council_vote(mem_conn, "sess-v", "codex", "timeout", None,
                            "timed out", "", 30_001, 1_001)
        upsert_council_vote(mem_conn, "sess-v", "codex", "APPROVE", 0.9,
                            "retry succeeded", "Approve text", 1_500, 1_002)
        votes = list_council_votes(mem_conn, "sess-v")
        assert len(votes) == 1  # only one row per (session, model)
        assert votes[0]["verdict"] == "APPROVE"

    def test_pk_constraint_holds_for_same_session_different_models(self, mem_conn):
        from daemon.db import upsert_council_vote, list_council_votes
        self._setup_session(mem_conn)
        upsert_council_vote(mem_conn, "sess-v", "gemini", "APPROVE", 0.8, "", "", 100, 1_001)
        upsert_council_vote(mem_conn, "sess-v", "codex", "REJECT", 0.7, "", "", 200, 1_002)
        votes = list_council_votes(mem_conn, "sess-v")
        assert len(votes) == 2
        models = {v["model"] for v in votes}
        assert models == {"gemini", "codex"}

    def test_unavailable_and_timeout_votes_persist(self, mem_conn):
        from daemon.db import upsert_council_vote, list_council_votes
        self._setup_session(mem_conn)
        upsert_council_vote(mem_conn, "sess-v", "goose", "unavailable", None,
                            "goose not found in PATH", "", 0, 1_001)
        upsert_council_vote(mem_conn, "sess-v", "aider", "timeout", None,
                            "aider exceeded timeout of 120s", "", 120_001, 1_002)
        votes = list_council_votes(mem_conn, "sess-v")
        verdicts = {v["verdict"] for v in votes}
        assert "unavailable" in verdicts
        assert "timeout" in verdicts


class TestCompleteCouncilSession:
    """complete_council_session writes synthesis results back to the session row."""

    def test_complete_sets_all_fields(self, mem_conn):
        from daemon.db import insert_council_session, complete_council_session, get_council_session
        insert_council_session(mem_conn, "sess-c", "topic", "question", 1_000)
        complete_council_session(
            mem_conn,
            session_id="sess-c",
            synthesized_verdict="APPROVE",
            agreement_ratio=0.75,
            hitl_paused=True,
            hitl_rule_id="council.split-verdict",
            completed_at=2_000,
        )
        row = get_council_session(mem_conn, "sess-c")
        assert row["completed_at"] == 2_000
        assert row["synthesized_verdict"] == "APPROVE"
        assert row["agreement_ratio"] == pytest.approx(0.75)
        assert row["hitl_paused"] == 1
        assert row["hitl_rule_id"] == "council.split-verdict"

    def test_complete_with_no_hitl_pause(self, mem_conn):
        from daemon.db import insert_council_session, complete_council_session, get_council_session
        insert_council_session(mem_conn, "sess-d", "topic", "question", 1_000)
        complete_council_session(
            mem_conn,
            session_id="sess-d",
            synthesized_verdict="APPROVE",
            agreement_ratio=1.0,
            hitl_paused=False,
            hitl_rule_id="council.auto-proceed",
            completed_at=2_000,
        )
        row = get_council_session(mem_conn, "sess-d")
        assert row["hitl_paused"] == 0


class TestListCouncilSessions:
    """list_council_sessions filtering and ordering."""

    def _insert(self, conn, session_id, topic, started_at):
        from daemon.db import insert_council_session
        insert_council_session(conn, session_id, topic, "q", started_at)

    def test_returns_sessions_ordered_by_started_at_desc(self, mem_conn):
        from daemon.db import list_council_sessions
        self._insert(mem_conn, "s1", "topic-arch", 1_000)
        self._insert(mem_conn, "s2", "topic-arch", 3_000)
        self._insert(mem_conn, "s3", "topic-arch", 2_000)
        rows = list_council_sessions(mem_conn)
        assert rows[0]["started_at"] == 3_000
        assert rows[1]["started_at"] == 2_000
        assert rows[2]["started_at"] == 1_000

    def test_topic_prefix_filter(self, mem_conn):
        from daemon.db import list_council_sessions
        self._insert(mem_conn, "t1", "arch: event sourcing", 1_000)
        self._insert(mem_conn, "t2", "db: postgres vs mysql", 2_000)
        self._insert(mem_conn, "t3", "arch: microservices", 3_000)
        rows = list_council_sessions(mem_conn, topic_prefix="arch:")
        assert len(rows) == 2
        topics = {r["topic"] for r in rows}
        assert all(t.startswith("arch:") for t in topics)

    def test_since_filter(self, mem_conn):
        from daemon.db import list_council_sessions
        self._insert(mem_conn, "u1", "topic", 500)
        self._insert(mem_conn, "u2", "topic", 1_500)
        self._insert(mem_conn, "u3", "topic", 2_500)
        rows = list_council_sessions(mem_conn, since=1_000)
        started_ats = {r["started_at"] for r in rows}
        assert 500 not in started_ats  # below since
        assert 1_500 in started_ats
        assert 2_500 in started_ats

    def test_limit_respected(self, mem_conn):
        from daemon.db import list_council_sessions
        for i in range(10):
            self._insert(mem_conn, f"lim-{i}", "topic", 1_000 + i)
        rows = list_council_sessions(mem_conn, limit=3)
        assert len(rows) == 3

    def test_empty_db_returns_empty_list(self, mem_conn):
        from daemon.db import list_council_sessions
        assert list_council_sessions(mem_conn) == []


class TestForeignKeyCascade:
    """Deleting a session cascades to its votes."""

    def test_votes_cascade_deleted_with_session(self, mem_conn):
        from daemon.db import insert_council_session, upsert_council_vote, list_council_votes
        insert_council_session(mem_conn, "sess-fk", "topic", "q", 1_000)
        upsert_council_vote(mem_conn, "sess-fk", "gemini", "APPROVE", 0.9, "", "", 100, 1_001)
        upsert_council_vote(mem_conn, "sess-fk", "codex", "APPROVE", 0.8, "", "", 200, 1_002)

        # Delete the session — FK cascade should remove votes
        mem_conn.execute("DELETE FROM council_sessions WHERE id = 'sess-fk'")
        mem_conn.commit()

        votes = list_council_votes(mem_conn, "sess-fk")
        assert votes == []
