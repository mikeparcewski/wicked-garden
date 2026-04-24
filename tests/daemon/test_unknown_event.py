"""tests/daemon/test_unknown_event.py — Focused invariant tests for unknown event handling.

Locks locked decision #8 from daemon/ARCHITECTURE.md:
  "All others [non-listed event types] are appended to event_log with
   projection_status='ignored' and never raise."

Kept in a separate file for visibility: a CI failure here is immediately
identifiable as the unknown-event invariant rather than a general parity failure.

T1: deterministic — fixed-epoch timestamps, no wall-clock.
T2: no sleep-based sync.
T3: isolated — each test uses its own mem_conn via function-scoped fixture.
T4: single assertion focus per test.
T5: descriptive names.
T6: provenance: locked decision #8, #589.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL_TS = 1_700_100_000

_KNOWN_PROJECT_CREATED = {
    "event_id": 10,
    "event_type": "wicked.project.created",
    "created_at": _SENTINEL_TS + 10,
    "chain_id": "test-proj.root",
    "payload": {"project_id": "test-proj", "complexity_score": 2.5},
}

_UNKNOWN_EVENT = {
    "event_id": 20,
    "event_type": "wicked.totally.fake_event",
    "created_at": _SENTINEL_TS + 20,
    "chain_id": None,
    "payload": {"project_id": "test-proj", "arbitrary_field": "should be ignored"},
}

_KNOWN_GATE_DECIDED = {
    "event_id": 30,
    "event_type": "wicked.gate.decided",
    "created_at": _SENTINEL_TS + 30,
    "chain_id": "test-proj.clarify",
    "payload": {
        "project_id": "test-proj",
        "phase": "clarify",
        "result": "APPROVE",
        "score": 0.78,
        "reviewer": "wicked-garden:crew:gate-adjudicator",
    },
}

_ANOTHER_UNKNOWN = {
    "event_id": 40,
    "event_type": "wicked.future.feature_not_yet_built",
    "created_at": _SENTINEL_TS + 40,
    "chain_id": "test-proj.root",
    "payload": {"project_id": "test-proj", "new_field": 42},
}


def _project_event_and_log(conn, event: dict) -> str:
    """Call project_event and write result to event_log. Returns status string."""
    from daemon.db import append_event_log  # type: ignore[import]
    from daemon.projector import project_event  # type: ignore[import]

    status = project_event(conn, event)
    append_event_log(
        conn,
        event_id=event["event_id"],
        event_type=event["event_type"],
        chain_id=event.get("chain_id"),
        payload=event.get("payload", {}),
        projection_status=status,
    )
    return status


# ---------------------------------------------------------------------------
# Locked decision #8: unknown event does not raise
# ---------------------------------------------------------------------------


def test_unknown_event_does_not_raise(mem_conn) -> None:
    """project_event must not raise for an unknown event_type.

    If the projector raises, the consumer crashes and the cursor stalls —
    violating the 'never blocks crew flow' principle.
    """
    from daemon.projector import project_event  # type: ignore[import]

    # Should not raise — any exception here is a hard contract violation.
    try:
        result = project_event(mem_conn, _UNKNOWN_EVENT)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"project_event raised {type(exc).__name__} for unknown event type "
            f"{_UNKNOWN_EVENT['event_type']!r}: {exc}"
        )

    assert result in {"applied", "ignored", "error"}, (
        f"project_event returned unexpected status {result!r} for unknown event. "
        "Must be one of: 'applied', 'ignored', 'error'."
    )


def test_unknown_event_returns_ignored_status(mem_conn) -> None:
    """project_event must return 'ignored' for an unknown event_type.

    'error' would be wrong — an unknown type is expected, not erroneous.
    'applied' would be wrong — nothing was written to the projection tables.
    """
    from daemon.projector import project_event  # type: ignore[import]

    status = project_event(mem_conn, _UNKNOWN_EVENT)
    assert status == "ignored", (
        f"project_event returned {status!r} for unknown event_type="
        f"{_UNKNOWN_EVENT['event_type']!r}. Expected 'ignored'."
    )


def test_unknown_event_is_logged_with_ignored_status(mem_conn) -> None:
    """event_log must contain a row for the unknown event with projection_status='ignored'.

    The event_log is the audit trail — every event that passes through the
    projector must be recorded, including unknowns.
    """
    _project_event_and_log(mem_conn, _UNKNOWN_EVENT)

    row = mem_conn.execute(
        "SELECT event_type, projection_status FROM event_log WHERE event_id = ?",
        (_UNKNOWN_EVENT["event_id"],),
    ).fetchone()

    assert row is not None, (
        f"event_id={_UNKNOWN_EVENT['event_id']} not found in event_log. "
        "append_event_log must be called for every event, including unknowns."
    )
    event_type_logged, status_logged = row
    assert event_type_logged == "wicked.totally.fake_event", (
        f"event_type in event_log is {event_type_logged!r}, "
        "expected 'wicked.totally.fake_event'."
    )
    assert status_logged == "ignored", (
        f"projection_status in event_log is {status_logged!r}, expected 'ignored'."
    )


def test_unknown_event_does_not_mutate_projects_table(mem_conn) -> None:
    """An unknown event must not insert or modify any row in the projects table.

    An unknown event may carry a project_id in its payload, but the projector
    must not act on it — only registered handlers touch projection tables.
    """
    _project_event_and_log(mem_conn, _UNKNOWN_EVENT)

    row = mem_conn.execute(
        "SELECT id FROM projects WHERE id = ?",
        (_UNKNOWN_EVENT["payload"].get("project_id", "__nonexistent__"),),
    ).fetchone()

    assert row is None, (
        "unknown event caused a row to appear in the projects table. "
        "Only registered handlers (e.g. wicked.project.created) may write project rows."
    )


# ---------------------------------------------------------------------------
# Locked decision #8: next known event still projects correctly
# ---------------------------------------------------------------------------


def test_known_event_after_unknown_projects_correctly(mem_conn) -> None:
    """A known event that follows an unknown event must project normally.

    If the unknown event corrupts state or raises mid-stream, this test will
    fail — catching both a state corruption and a stall scenario.
    """
    from daemon.db import get_project  # type: ignore[import]

    # Setup: create the project first.
    _project_event_and_log(mem_conn, _KNOWN_PROJECT_CREATED)

    # Inject the unknown event.
    _project_event_and_log(mem_conn, _UNKNOWN_EVENT)

    # Now project the known gate.decided event.
    _project_event_and_log(mem_conn, _KNOWN_GATE_DECIDED)

    # The gate.decided event should have updated the phase row.
    phase_row = mem_conn.execute(
        "SELECT state, gate_verdict, gate_score FROM phases WHERE project_id = ? AND phase = ?",
        ("test-proj", "clarify"),
    ).fetchone()

    assert phase_row is not None, (
        "Phase row for 'clarify' not found after wicked.gate.decided. "
        "Known event after unknown event was not projected."
    )
    _state, verdict, score = phase_row
    assert verdict == "APPROVE", (
        f"gate_verdict is {verdict!r}, expected 'APPROVE'. "
        "Known event projection was corrupted by preceding unknown event."
    )
    assert abs(score - 0.78) < 1e-6, (
        f"gate_score is {score!r}, expected 0.78."
    )

    # Project row must still be intact.
    project = get_project(mem_conn, "test-proj")
    assert project is not None, "Project row disappeared after unknown + known event sequence."
    assert project["status"] == "active", (
        f"project.status is {project['status']!r}, expected 'active'."
    )


def test_cursor_advances_past_unknown_event(mem_conn) -> None:
    """The cursor must be advanceable past an unknown event_id.

    The consumer advances the cursor after processing a batch. If the projector
    returns 'ignored' correctly, the cursor will include the unknown event_id in
    its advance. This test simulates that by manually setting the cursor and
    verifying it accepts an event_id that came from an ignored event.
    """
    from daemon.db import get_cursor, set_cursor  # type: ignore[import]

    # Simulate consumer having processed events up to and including the unknown.
    _project_event_and_log(mem_conn, _KNOWN_PROJECT_CREATED)
    _project_event_and_log(mem_conn, _UNKNOWN_EVENT)

    # Consumer sets cursor after the batch (event_id=20 is the unknown event).
    set_cursor(mem_conn, bus_source="wicked-bus", cursor_id="cid-test", last_event_id=20)

    row = get_cursor(mem_conn)
    assert row is not None, "Cursor row not found after set_cursor."
    assert row["last_event_id"] == 20, (
        f"Cursor last_event_id={row['last_event_id']}, expected 20. "
        "Consumer must advance cursor past unknown events, not stall."
    )


# ---------------------------------------------------------------------------
# Multiple unknown events in sequence
# ---------------------------------------------------------------------------


def test_multiple_consecutive_unknown_events_all_ignored(mem_conn) -> None:
    """Multiple consecutive unknown events must all be logged as 'ignored'.

    Edge case: a burst of future event types interspersed with known ones.
    """
    events = [
        _KNOWN_PROJECT_CREATED,
        _UNKNOWN_EVENT,
        _ANOTHER_UNKNOWN,
        _KNOWN_GATE_DECIDED,
    ]

    for event in events:
        _project_event_and_log(mem_conn, event)

    rows = mem_conn.execute(
        "SELECT event_id, event_type, projection_status FROM event_log ORDER BY event_id ASC"
    ).fetchall()

    by_id = {row[0]: (row[1], row[2]) for row in rows}

    # Known events should be 'applied'.
    assert by_id[10][1] == "applied", (
        f"wicked.project.created (event_id=10) should be 'applied', got {by_id[10][1]!r}."
    )
    assert by_id[30][1] == "applied", (
        f"wicked.gate.decided (event_id=30) should be 'applied', got {by_id[30][1]!r}."
    )

    # Unknown events should be 'ignored'.
    assert by_id[20][1] == "ignored", (
        f"wicked.totally.fake_event (event_id=20) should be 'ignored', got {by_id[20][1]!r}."
    )
    assert by_id[40][1] == "ignored", (
        f"wicked.future.feature_not_yet_built (event_id=40) should be 'ignored', "
        f"got {by_id[40][1]!r}."
    )
