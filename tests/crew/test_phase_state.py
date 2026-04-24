"""tests/crew/test_phase_state.py — Unit tests for scripts/crew/phase_state.py.

Tests the typed phase state machine introduced in v8-PR-3 (#590):
  - Every TRANSITIONS entry produces the documented target state.
  - The banned ``completed`` state raises InvalidTransition.
  - Unknown state strings raise InvalidTransition.
  - Unknown event names raise InvalidTransition.
  - Terminal states (approved, skipped) have no outgoing transitions
    except rework from rejected.
  - None current-state is treated as ``pending``.
  - The standalone migration script maps ``completed`` rows correctly.
  - The migration is idempotent (re-running is a no-op).

T1: deterministic — no wall-clock, no network.
T2: no sleep-based sync.
T3: isolated — each test is independent; in-memory SQLite for DB tests.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #590, #588 v8 thesis 3.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# sys.path: conftest.py handles scripts/ and scripts/crew/ — no duplication.
# daemon/ also needs to be importable for migration tests.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAEMON_DIR = _REPO_ROOT / "daemon"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_DAEMON_DIR) not in sys.path:
    sys.path.append(str(_DAEMON_DIR))

from phase_state import (  # type: ignore[import]
    BANNED_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    VALID_EVENTS,
    InvalidTransition,
    PhaseState,
    transition,
)


# ---------------------------------------------------------------------------
# Stream 1: state machine correctness
# ---------------------------------------------------------------------------


class TestAllTransitionsCovered:
    """Every entry in TRANSITIONS produces the documented target state."""

    def test_start_from_pending_produces_active(self) -> None:
        assert transition(PhaseState.PENDING, "start") == PhaseState.ACTIVE

    def test_approve_from_active_produces_approved(self) -> None:
        assert transition(PhaseState.ACTIVE, "approve") == PhaseState.APPROVED

    def test_reject_from_active_produces_rejected(self) -> None:
        assert transition(PhaseState.ACTIVE, "reject") == PhaseState.REJECTED

    def test_skip_from_pending_produces_skipped(self) -> None:
        assert transition(PhaseState.PENDING, "skip") == PhaseState.SKIPPED

    def test_skip_from_active_produces_skipped(self) -> None:
        assert transition(PhaseState.ACTIVE, "skip") == PhaseState.SKIPPED

    def test_rework_from_rejected_produces_active(self) -> None:
        """rework restarts a rejected phase — the only outgoing edge from REJECTED."""
        assert transition(PhaseState.REJECTED, "rework") == PhaseState.ACTIVE

    def test_transitions_table_fully_exercised(self) -> None:
        """Every entry in TRANSITIONS is reachable via the transition() function."""
        for (event, current), expected in TRANSITIONS.items():
            result = transition(current, event)
            assert result == expected, (
                f"transition({current!r}, {event!r}) returned {result!r}, "
                f"expected {expected!r}"
            )


class TestBannedStateRaises:
    """Any attempt to transition from 'completed' raises InvalidTransition."""

    def test_completed_with_approve_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="banned"):
            transition("completed", "approve")

    def test_completed_with_start_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="banned"):
            transition("completed", "start")

    def test_completed_with_skip_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="banned"):
            transition("completed", "skip")

    def test_completed_with_reject_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="banned"):
            transition("completed", "reject")

    def test_banned_states_frozenset_contains_completed(self) -> None:
        assert "completed" in BANNED_STATES


class TestUnknownStateRaises:
    """Unknown state strings raise InvalidTransition."""

    def test_gibberish_state_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="Unknown phase state"):
            transition("not-a-real-state", "start")

    def test_in_progress_internal_state_raises(self) -> None:
        """phase_manager.py uses 'in_progress' internally — that's NOT a canonical daemon state."""
        with pytest.raises(InvalidTransition):
            transition("in_progress", "approve")

    def test_complete_internal_state_raises(self) -> None:
        """phase_manager.py uses 'complete' internally — that's NOT a canonical daemon state."""
        with pytest.raises(InvalidTransition):
            transition("complete", "approve")


class TestUnknownEventRaises:
    """Unknown event names raise InvalidTransition."""

    def test_gibberish_event_raises(self) -> None:
        with pytest.raises(InvalidTransition, match="No transition"):
            transition(PhaseState.PENDING, "not-an-event")

    def test_approve_from_pending_raises(self) -> None:
        """Cannot approve a phase that has not been started."""
        with pytest.raises(InvalidTransition):
            transition(PhaseState.PENDING, "approve")

    def test_reject_from_pending_raises(self) -> None:
        """Cannot reject a phase that has not been started."""
        with pytest.raises(InvalidTransition):
            transition(PhaseState.PENDING, "reject")

    def test_rework_from_active_raises(self) -> None:
        """rework only applies to rejected phases."""
        with pytest.raises(InvalidTransition):
            transition(PhaseState.ACTIVE, "rework")


class TestTerminalStatesHaveNoOutgoing:
    """Terminal states (approved, skipped) have no outgoing transitions.

    Rejected is not terminal — it has exactly one outgoing edge (rework).
    """

    def test_approved_has_no_outgoing_transitions(self) -> None:
        for event in VALID_EVENTS:
            with pytest.raises(InvalidTransition):
                transition(PhaseState.APPROVED, event)

    def test_skipped_has_no_outgoing_transitions(self) -> None:
        for event in VALID_EVENTS:
            with pytest.raises(InvalidTransition):
                transition(PhaseState.SKIPPED, event)

    def test_rejected_only_has_rework_outgoing(self) -> None:
        """From REJECTED only 'rework' is valid; all other events raise."""
        assert transition(PhaseState.REJECTED, "rework") == PhaseState.ACTIVE
        for event in VALID_EVENTS - {"rework"}:
            with pytest.raises(InvalidTransition):
                transition(PhaseState.REJECTED, event)

    def test_terminal_states_set_is_approved_and_skipped(self) -> None:
        assert TERMINAL_STATES == frozenset({PhaseState.APPROVED, PhaseState.SKIPPED})


class TestNoneCurrentState:
    """None current-state is treated as PhaseState.PENDING."""

    def test_none_start_produces_active(self) -> None:
        assert transition(None, "start") == PhaseState.ACTIVE

    def test_none_skip_produces_skipped(self) -> None:
        assert transition(None, "skip") == PhaseState.SKIPPED

    def test_none_approve_raises(self) -> None:
        """Cannot approve from implicit pending."""
        with pytest.raises(InvalidTransition):
            transition(None, "approve")


class TestStringCoercion:
    """Plain strings are coerced to PhaseState where valid."""

    def test_string_pending_coerced(self) -> None:
        assert transition("pending", "start") == PhaseState.ACTIVE

    def test_string_active_approve(self) -> None:
        assert transition("active", "approve") == PhaseState.APPROVED

    def test_return_value_is_phasstate_instance(self) -> None:
        result = transition("pending", "start")
        assert isinstance(result, PhaseState)
        assert result == "active"  # StrEnum equality with plain string


# ---------------------------------------------------------------------------
# Stream 3: migration tests (using in-memory SQLite)
# ---------------------------------------------------------------------------


def _make_mem_conn() -> sqlite3.Connection:
    """Open an in-memory SQLite connection with the daemon schema initialised."""
    from daemon.db import connect, init_schema  # type: ignore[import]
    conn = connect(":memory:")
    init_schema(conn)
    return conn


def _seed_completed_rows(conn: sqlite3.Connection) -> None:
    """Insert test project and phase rows — some with gate evidence, some without."""
    now = int(time.time())
    # Insert project first (FK constraint).
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("proj-a", "Project A", now, now),
    )
    # Phase with gate_score → should migrate to approved.
    conn.execute(
        "INSERT OR REPLACE INTO phases "
        "(project_id, phase, state, gate_score, gate_verdict, updated_at) "
        "VALUES (?, ?, 'completed', ?, ?, ?)",
        ("proj-a", "design", 0.85, "APPROVE", now),
    )
    # Phase with gate_verdict only → should migrate to approved.
    conn.execute(
        "INSERT OR REPLACE INTO phases "
        "(project_id, phase, state, gate_score, gate_verdict, updated_at) "
        "VALUES (?, ?, 'completed', NULL, ?, ?)",
        ("proj-a", "clarify", "APPROVE", now),
    )
    # Phase with no gate evidence → should migrate to skipped.
    conn.execute(
        "INSERT OR REPLACE INTO phases "
        "(project_id, phase, state, gate_score, gate_verdict, updated_at) "
        "VALUES (?, ?, 'completed', NULL, NULL, ?)",
        ("proj-a", "challenge", now),
    )
    conn.commit()


class TestMigrationCompletedWithAcsMapsToApproved:
    """completed phase rows with gate evidence map to approved."""

    def test_gate_score_present_maps_to_approved(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        # The migration runs inside init_schema, but the seed inserts happen
        # AFTER init_schema, so we need to run the migration function directly.
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        # Reset the migration guard so we can re-run.
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        result = run_migration(conn)
        row = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a' AND phase = 'design'"
        ).fetchone()
        assert row[0] == "approved", f"Expected 'approved', got {row[0]!r}"
        conn.close()

    def test_gate_verdict_only_maps_to_approved(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        run_migration(conn)
        row = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a' AND phase = 'clarify'"
        ).fetchone()
        assert row[0] == "approved", f"Expected 'approved', got {row[0]!r}"
        conn.close()


class TestMigrationCompletedWithoutAcsMapsToSkipped:
    """completed phase rows without gate evidence map to skipped."""

    def test_no_gate_evidence_maps_to_skipped(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        result = run_migration(conn)
        row = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a' AND phase = 'challenge'"
        ).fetchone()
        assert row[0] == "skipped", f"Expected 'skipped', got {row[0]!r}"
        conn.close()

    def test_migration_result_counts_correct(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        result = run_migration(conn)
        # 2 with evidence → approved, 1 without → skipped
        assert result["rows_approved"] == 2
        assert result["rows_skipped"] == 1
        assert result["applied"] is True
        conn.close()


class TestMigrationIdempotent:
    """Re-running the migration is a no-op; DB state is unchanged on second run."""

    def test_second_run_returns_already_applied(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        # First run: applies the migration.
        result1 = run_migration(conn)
        assert result1["applied"] is True
        # Second run: no-op.
        result2 = run_migration(conn)
        assert result2["already_applied"] is True
        assert result2["applied"] is False
        conn.close()

    def test_second_run_does_not_change_states(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        run_migration(conn)
        # Capture states after first run.
        states_after_first = {
            r[0]: r[1] for r in conn.execute(
                "SELECT phase, state FROM phases WHERE project_id = 'proj-a'"
            ).fetchall()
        }
        run_migration(conn)
        states_after_second = {
            r[0]: r[1] for r in conn.execute(
                "SELECT phase, state FROM phases WHERE project_id = 'proj-a'"
            ).fetchall()
        }
        assert states_after_first == states_after_second, (
            "States changed on second migration run — migration is not idempotent"
        )
        conn.close()


class TestDryRun:
    """--dry-run shows what would be migrated without writing anything."""

    def test_dry_run_does_not_change_states(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        result = run_migration(conn, dry_run=True)
        assert result["dry_run"] is True
        # States should still be 'completed'.
        rows = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a'"
        ).fetchall()
        for row in rows:
            assert row[0] == "completed", f"Expected 'completed' after dry-run, got {row[0]!r}"
        conn.close()

    def test_dry_run_returns_correct_counts(self) -> None:
        conn = _make_mem_conn()
        _seed_completed_rows(conn)
        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()
        result = run_migration(conn, dry_run=True)
        assert result["rows_approved"] == 2
        assert result["rows_skipped"] == 1
        conn.close()


# ---------------------------------------------------------------------------
# Migration transaction atomicity (council C1 fix-up — #590 #613)
# ---------------------------------------------------------------------------


class _FailingOnFirstUpdateConnection(sqlite3.Connection):
    """sqlite3.Connection subclass that raises on the first UPDATE phases SET state call.

    Used by TestMigrationRollbackOnRowError to simulate a mid-loop UPDATE failure
    without patching the C-level read-only ``execute`` attribute.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._update_call_count = 0

    def execute(self, sql, parameters=()):  # type: ignore[override]
        if "UPDATE phases SET state" in sql:
            self._update_call_count += 1
            if self._update_call_count == 1:
                raise sqlite3.OperationalError("simulated UPDATE failure")
        return super().execute(sql, parameters)


class TestMigrationRollbackOnRowError:
    """If any row UPDATE fails during migration the entire transaction rolls back.

    Asserts:
      (a) No rows were updated — all phases remain 'completed'.
      (b) _migrations table has no row for this migration.
      (c) Re-running without the fault succeeds and updates all rows.

    Provenance: #590 #613 council C1 — run_migration UPDATE loop must be wrapped
    in a single transaction so partial-migration is impossible on error.
    """

    def _make_failing_conn(self) -> sqlite3.Connection:
        """Open an in-memory DB using _FailingOnFirstUpdateConnection + daemon schema."""
        from daemon.db import init_schema  # type: ignore[import]
        conn = sqlite3.connect(":memory:", factory=_FailingOnFirstUpdateConnection)
        init_schema(conn)
        return conn

    def test_migration_rollback_on_row_error(self) -> None:
        conn = self._make_failing_conn()
        _seed_completed_rows(conn)

        from scripts.crew.phase_state_migration import run_migration  # type: ignore[import]
        conn.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn.commit()

        # Run migration — must raise because the first UPDATE is intercepted.
        with pytest.raises(sqlite3.OperationalError, match="simulated UPDATE failure"):
            run_migration(conn)

        # (a) No rows updated — all phases still 'completed'.
        rows = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a'"
        ).fetchall()
        assert rows, "Expected phase rows to still exist after rollback."
        for row in rows:
            assert row[0] == "completed", (
                f"Expected state='completed' after rollback, got {row[0]!r}. "
                "Migration transaction did not roll back atomically."
            )

        # (b) _migrations has no entry — migration was not recorded as applied.
        marker = conn.execute(
            "SELECT name FROM _migrations "
            "WHERE name = 'phase_state_completed_to_canonical'"
        ).fetchone()
        assert marker is None, (
            "_migrations should have no entry after a rolled-back migration. "
            "Re-running the migration must be possible."
        )

        # (c) Re-running via a normal connection succeeds.
        from daemon.db import connect, init_schema  # type: ignore[import]
        # Dump DB state from failing conn into a new normal conn for re-run check.
        # Simpler: seed a fresh normal conn and verify run_migration succeeds.
        conn2 = _make_mem_conn()
        _seed_completed_rows(conn2)
        conn2.execute("DELETE FROM _migrations WHERE name = 'phase_state_completed_to_canonical'")
        conn2.commit()
        result = run_migration(conn2)
        assert result["applied"] is True, (
            "Re-run after rollback should apply the migration successfully."
        )
        rows_after = conn2.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-a'"
        ).fetchall()
        states = {r[0] for r in rows_after}
        assert "completed" not in states, (
            "After successful re-run no phases should remain in 'completed' state."
        )
        conn.close()
        conn2.close()


# ---------------------------------------------------------------------------
# Stream 2: upsert_phase ban enforcement via db layer
# ---------------------------------------------------------------------------


class TestUpsertPhaseBanEnforcement:
    """upsert_phase rejects banned state values via the validation guard."""

    def test_upsert_phase_with_completed_state_raises(self) -> None:
        conn = _make_mem_conn()
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("proj-x", "X", now, now),
        )
        conn.commit()
        from daemon.db import upsert_phase  # type: ignore[import]
        from phase_state import InvalidTransition  # type: ignore[import]
        with pytest.raises(InvalidTransition, match="banned"):
            upsert_phase(conn, "proj-x", "design", {"state": "completed"})
        conn.close()

    def test_upsert_phase_with_unknown_state_raises(self) -> None:
        conn = _make_mem_conn()
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("proj-y", "Y", now, now),
        )
        conn.commit()
        from daemon.db import upsert_phase  # type: ignore[import]
        from phase_state import InvalidTransition  # type: ignore[import]
        with pytest.raises(InvalidTransition, match="unknown state"):
            upsert_phase(conn, "proj-y", "design", {"state": "in_progress"})
        conn.close()

    def test_upsert_phase_with_valid_state_succeeds(self) -> None:
        conn = _make_mem_conn()
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("proj-z", "Z", now, now),
        )
        conn.commit()
        from daemon.db import upsert_phase  # type: ignore[import]
        upsert_phase(conn, "proj-z", "design", {"state": "active"})
        row = conn.execute(
            "SELECT state FROM phases WHERE project_id = 'proj-z' AND phase = 'design'"
        ).fetchone()
        assert row[0] == "active"
        conn.close()
