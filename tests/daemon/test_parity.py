"""tests/daemon/test_parity.py — Daemon projection parity harness.

Replays each fixture's event stream through daemon.projector.project_event and
asserts the resulting DB rows match expected_project.json + expected_phases.json.

Coverage:
  - 6 fixture scenarios exercising the full event-type surface
  - Idempotency: replaying the same fixture twice yields identical state (locked decision #6)
  - Timestamp wildcarding: expected values of 0 are ignored by the comparator

T1: deterministic — wall-clock isolated via in-memory DB + fixed-epoch fixture events.
T2: no sleep-based sync.
T3: isolated — each parametrize call gets a fresh mem_conn via function-scoped fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #589 parity harness, locked decisions #6 and #8 referenced inline.
"""

from __future__ import annotations

from typing import Any

import pytest

# sys.path setup is handled by tests/daemon/conftest.py — no mutation needed here.

# ---------------------------------------------------------------------------
# Fixtures parametrized over the 6 named scenarios
# ---------------------------------------------------------------------------

_FIXTURE_SCENARIOS = [
    "single_phase_approve",
    "reject_then_rework",
    "multi_phase_lifecycle",
    "auto_advance_low_complexity",
    "yolo_revoke_audit",
    "unknown_event_survives",
]


# ---------------------------------------------------------------------------
# Comparator helper
# ---------------------------------------------------------------------------


def _normalize_timestamps(obj: Any) -> Any:
    """Recursively replace sentinel 0 timestamps with a wildcard token ("__ANY__").

    The architecture contract says: when the expected JSON carries 0 for a
    timestamp field the comparator ignores it.  We normalise by replacing 0
    with "__ANY__" in both expected and actual before comparing, so
    _assert_projection_equals can skip those fields.

    Timestamp fields subject to wildcarding:
      updated_at, created_at, started_at, terminal_at, ingested_at, acked_at
    """
    _TIMESTAMP_KEYS = frozenset(
        {"updated_at", "created_at", "started_at", "terminal_at", "ingested_at", "acked_at"}
    )
    _WILDCARD = "__ANY__"

    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _TIMESTAMP_KEYS and v == 0:
                result[k] = _WILDCARD
            else:
                result[k] = _normalize_timestamps(v)
        return result
    if isinstance(obj, list):
        return [_normalize_timestamps(item) for item in obj]
    return obj


def _assert_projection_equals(
    actual: Any,
    expected: Any,
    path: str = "root",
) -> None:
    """Recursive deep-equality with timestamp wildcarding.

    When an expected value is '__ANY__' (a normalised sentinel-0 timestamp),
    the comparison passes regardless of the actual value — the field exists
    but its exact value is not constrained.
    """
    _WILDCARD = "__ANY__"

    if expected == _WILDCARD:
        # Any actual value is acceptable for this field.
        return

    if isinstance(expected, dict):
        assert isinstance(actual, dict), (
            f"[{path}] expected dict, got {type(actual).__name__}: {actual!r}"
        )
        for key, exp_val in expected.items():
            assert key in actual, (
                f"[{path}] key '{key}' missing from actual projection. "
                f"Actual keys: {list(actual.keys())}"
            )
            _assert_projection_equals(actual[key], exp_val, path=f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), (
            f"[{path}] expected list, got {type(actual).__name__}: {actual!r}"
        )
        assert len(actual) == len(expected), (
            f"[{path}] list length mismatch: expected {len(expected)}, got {len(actual)}. "
            f"Actual: {actual!r}"
        )
        for i, (act_item, exp_item) in enumerate(zip(actual, expected)):
            _assert_projection_equals(act_item, exp_item, path=f"{path}[{i}]")
        return

    # Scalar comparison.
    assert actual == expected, (
        f"[{path}] value mismatch: expected {expected!r}, got {actual!r}"
    )


def _replay_events(conn, events: list[dict]) -> None:
    """Project each event in order; log each result to event_log via db.append_event_log."""
    from daemon.db import append_event_log  # type: ignore[import]
    from daemon.projector import project_event  # type: ignore[import]

    for event in events:
        status = project_event(conn, event)
        append_event_log(
            conn,
            event_id=event["event_id"],
            event_type=event["event_type"],
            chain_id=event.get("chain_id"),
            payload=event.get("payload", {}),
            projection_status=status,
        )


# ---------------------------------------------------------------------------
# Parametrized parity tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_projection_matches_expected(
    scenario: str,
    mem_conn,
    load_fixture,
) -> None:
    """Project fixture events and assert DB state matches expected_project + expected_phases.

    Provenance: #589 acceptance criterion 5 — parity harness must cover 5+ fixture scenarios.
    """
    from daemon.db import get_project, list_phases  # type: ignore[import]

    events, expected_project, expected_phases = load_fixture(scenario)
    project_id = expected_project["id"]

    _replay_events(mem_conn, events)

    actual_project = get_project(mem_conn, project_id)
    assert actual_project is not None, (
        f"[{scenario}] project '{project_id}' not found in DB after projection. "
        "Check that wicked.project.created handler upserts the row."
    )

    actual_phases = list_phases(mem_conn, project_id)

    _assert_projection_equals(
        _normalize_timestamps(actual_project),
        _normalize_timestamps(expected_project),
        path=f"{scenario}/project",
    )

    # Sort both lists by phase name for stable comparison
    # (list_phases is ordered by started_at NULLS LAST, but fixtures may differ).
    actual_phases_sorted = sorted(actual_phases, key=lambda p: p.get("phase", ""))
    expected_phases_sorted = sorted(expected_phases, key=lambda p: p.get("phase", ""))

    _assert_projection_equals(
        _normalize_timestamps(actual_phases_sorted),
        _normalize_timestamps(expected_phases_sorted),
        path=f"{scenario}/phases",
    )


@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_projection_is_idempotent(
    scenario: str,
    mem_conn,
    load_fixture,
) -> None:
    """Replaying the same event stream twice produces identical DB state.

    Locked decision #6: every projection is a deterministic UPSERT — replaying
    the same event yields identical state.  Tests all 6 fixture scenarios.
    """
    from daemon.db import get_project, list_phases  # type: ignore[import]

    events, expected_project, _ = load_fixture(scenario)
    project_id = expected_project["id"]

    # First replay.
    _replay_events(mem_conn, events)
    state_after_first = {
        "project": get_project(mem_conn, project_id),
        "phases": sorted(
            list_phases(mem_conn, project_id),
            key=lambda p: p.get("phase", ""),
        ),
    }

    # Second replay — same events, same connection.
    _replay_events(mem_conn, events)
    state_after_second = {
        "project": get_project(mem_conn, project_id),
        "phases": sorted(
            list_phases(mem_conn, project_id),
            key=lambda p: p.get("phase", ""),
        ),
    }

    # updated_at may legitimately differ if the second upsert touches it, so we
    # wildcard it in both snapshots before comparing.
    _TIMESTAMP_KEYS = frozenset(
        {"updated_at", "created_at", "started_at", "terminal_at", "ingested_at"}
    )

    def _strip_timestamps(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _strip_timestamps(v) for k, v in obj.items() if k not in _TIMESTAMP_KEYS}
        if isinstance(obj, list):
            return [_strip_timestamps(i) for i in obj]
        return obj

    stripped_first = _strip_timestamps(state_after_first)
    stripped_second = _strip_timestamps(state_after_second)

    assert stripped_first == stripped_second, (
        f"[{scenario}] idempotency violated: second replay produced different state.\n"
        f"After first replay:  {stripped_first!r}\n"
        f"After second replay: {stripped_second!r}"
    )


# ---------------------------------------------------------------------------
# Event log audit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_all_events_appear_in_event_log(
    scenario: str,
    mem_conn,
    load_fixture,
) -> None:
    """Every replayed event must produce a row in event_log with a valid projection_status.

    Valid statuses: 'applied', 'ignored', 'error'.
    This exercises the db.append_event_log + event_log retention contract.
    """
    from daemon.db import connect  # type: ignore[import]  # noqa: F401

    events, _, _ = load_fixture(scenario)
    _replay_events(mem_conn, events)

    cursor = mem_conn.execute(
        "SELECT event_id, event_type, projection_status FROM event_log ORDER BY event_id ASC"
    )
    log_rows = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    valid_statuses = {"applied", "ignored", "error"}
    for event in events:
        eid = event["event_id"]
        assert eid in log_rows, (
            f"[{scenario}] event_id={eid} ({event['event_type']!r}) "
            "not found in event_log after projection."
        )
        _, status = log_rows[eid]
        assert status in valid_statuses, (
            f"[{scenario}] event_id={eid} has invalid projection_status={status!r}. "
            f"Must be one of {valid_statuses}."
        )


# ---------------------------------------------------------------------------
# unknown_event_survives: specific invariant for the known events in that fixture
# ---------------------------------------------------------------------------


def test_unknown_event_survives_known_event_still_projects(
    mem_conn,
    load_fixture,
) -> None:
    """After an unknown event, subsequent known events project correctly.

    Specialised assertion for the 'unknown_event_survives' fixture: ensures that
    the unknown event (event_id=2) is logged as 'ignored' and the downstream
    gate.decided + phase.transitioned (event_ids 3-4) project normally.

    Locked decision #8: unknown event_type → projector returns without raising,
    event_log records status='ignored'.
    """
    from daemon.db import get_project, list_phases  # type: ignore[import]

    events, expected_project, expected_phases = load_fixture("unknown_event_survives")
    _replay_events(mem_conn, events)

    # Check the unknown event (event_id=2) is logged as ignored.
    cursor = mem_conn.execute(
        "SELECT projection_status FROM event_log WHERE event_id = 2"
    )
    row = cursor.fetchone()
    assert row is not None, (
        "event_id=2 (wicked.totally.fake_event) not found in event_log. "
        "Projector must append every event regardless of type."
    )
    assert row[0] == "ignored", (
        f"event_id=2 expected projection_status='ignored', got {row[0]!r}. "
        "Unknown events must be logged as ignored, not applied or error."
    )

    # Confirm the known events after the unknown one still produced correct state.
    project_id = expected_project["id"]
    actual_project = get_project(mem_conn, project_id)
    assert actual_project is not None, "Project row missing after unknown event in stream."

    actual_phases = sorted(list_phases(mem_conn, project_id), key=lambda p: p["phase"])
    expected_phases_sorted = sorted(expected_phases, key=lambda p: p["phase"])

    _assert_projection_equals(
        _normalize_timestamps(actual_project),
        _normalize_timestamps(expected_project),
        path="unknown_event_survives/project",
    )
    _assert_projection_equals(
        _normalize_timestamps(actual_phases),
        _normalize_timestamps(expected_phases_sorted),
        path="unknown_event_survives/phases",
    )


# ---------------------------------------------------------------------------
# Cursor advancement test
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rework state-transition test (council C1 fix-up — #590 #613)
# ---------------------------------------------------------------------------


def test_rework_transitions_rejected_to_active(
    mem_conn,
    load_fixture,
) -> None:
    """wicked.rework.triggered must flip a REJECTED phase back to ACTIVE.

    Event sequence: project.created → phase.transitioned(active) →
    gate.decided(REJECT) → rework.triggered.

    Expected end state: phase row state='active', rework_iterations=1.

    Pre-fix this test FAILS because _rework_triggered only sets rework_iterations
    and leaves state='rejected'.  Post-fix it passes.

    Provenance: #590 #613 council C1 — projector._rework_triggered missing
    upsert_phase(state=PhaseState.ACTIVE) call.
    """
    from daemon.db import get_project, list_phases  # type: ignore[import]

    events, expected_project, expected_phases = load_fixture(
        "rework_transitions_to_active"
    )
    project_id = expected_project["id"]

    _replay_events(mem_conn, events)

    actual_phases = list_phases(mem_conn, project_id)
    actual_build = next(
        (p for p in actual_phases if p["phase"] == "build"), None
    )

    assert actual_build is not None, (
        "Phase 'build' not found after replay. "
        "Check that gate.decided handler creates the phase row."
    )
    assert actual_build["state"] == "active", (
        f"After rework.triggered the phase must be state='active' "
        f"(REJECTED → ACTIVE transition). Got state={actual_build['state']!r}. "
        "Bug: _rework_triggered in projector.py does not call "
        "upsert_phase(state=PhaseState.ACTIVE)."
    )
    assert actual_build["rework_iterations"] == 1, (
        f"rework_iterations expected 1, got {actual_build['rework_iterations']!r}"
    )

    # Full parity assertion via fixture comparator.
    actual_phases_sorted = sorted(actual_phases, key=lambda p: p.get("phase", ""))
    expected_phases_sorted = sorted(expected_phases, key=lambda p: p.get("phase", ""))
    _assert_projection_equals(
        _normalize_timestamps(actual_phases_sorted),
        _normalize_timestamps(expected_phases_sorted),
        path="rework_transitions_to_active/phases",
    )


def test_cursor_can_be_set_and_retrieved(mem_conn) -> None:
    """db.set_cursor + db.get_cursor roundtrip works with the in-memory schema.

    Not a parity test per se, but validates the cursor table used by consumer.py.
    """
    from daemon.db import get_cursor, set_cursor  # type: ignore[import]

    # Initially no cursor row.
    initial = get_cursor(mem_conn)
    assert initial is None, (
        "get_cursor should return None on fresh schema before any cursor is set."
    )

    set_cursor(mem_conn, bus_source="wicked-bus", cursor_id="cid-abc123", last_event_id=42)
    row = get_cursor(mem_conn)
    assert row is not None, "get_cursor returned None after set_cursor call."
    assert row["cursor_id"] == "cid-abc123", (
        f"cursor_id mismatch: expected 'cid-abc123', got {row['cursor_id']!r}"
    )
    assert row["last_event_id"] == 42, (
        f"last_event_id mismatch: expected 42, got {row['last_event_id']!r}"
    )

    # Overwrite — last-write-wins.
    set_cursor(mem_conn, bus_source="wicked-bus", cursor_id="cid-abc123", last_event_id=99)
    row2 = get_cursor(mem_conn)
    assert row2["last_event_id"] == 99, (
        "set_cursor should overwrite last_event_id on conflict."
    )
