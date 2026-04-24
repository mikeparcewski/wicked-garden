"""tests/daemon/test_parity_tasks.py — Task state projection parity harness.

Stream 3 — #596 v8-PR-2.  Extends the existing parity suite with task-
lifecycle fixtures.  Tests cover the three required projection rules:

  wicked.task.created   → tasks row UPSERT
  wicked.task.updated   → tasks row delta update
  wicked.task.completed → tasks.status = 'completed'

Plus filtering by session_id, status, and chain_id via db.list_tasks.

T1: deterministic — wall-clock isolated via in-memory DB + fixed-epoch events.
T2: no sleep-based sync.
T3: isolated — each test gets its own mem_conn via function-scoped fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #596 v8-PR-2, Stream 3.
"""

from __future__ import annotations

from typing import Any

import pytest

# sys.path and daemon imports provided by tests/daemon/conftest.py.

# ---------------------------------------------------------------------------
# Helpers (re-use _normalize_timestamps / _assert_projection_equals pattern
# from test_parity.py via local reimport rather than import coupling)
# ---------------------------------------------------------------------------

_TIMESTAMP_KEYS = frozenset(
    {"updated_at", "created_at", "started_at", "terminal_at", "ingested_at"}
)
_WILDCARD = "__ANY__"


def _normalize_timestamps(obj: Any) -> Any:
    """Replace sentinel-0 timestamps with the wildcard token."""
    if isinstance(obj, dict):
        return {
            k: _WILDCARD if (k in _TIMESTAMP_KEYS and v == 0) else _normalize_timestamps(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize_timestamps(item) for item in obj]
    return obj


def _assert_task_equals(actual: dict, expected: dict, path: str = "task") -> None:
    """Deep-equal with timestamp wildcarding for task dicts."""
    for key, exp_val in expected.items():
        assert key in actual, (
            f"[{path}] key '{key}' missing. Actual keys: {list(actual.keys())}"
        )
        act_val = actual[key]
        if exp_val == _WILDCARD or act_val == _WILDCARD:
            continue
        assert act_val == exp_val, (
            f"[{path}.{key}] expected {exp_val!r}, got {act_val!r}"
        )


def _replay_task_events(conn, events: list[dict]) -> None:
    """Project each event in order via projector.project_event."""
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
# Fixture scenario: full task lifecycle (created → in_progress → completed)
# ---------------------------------------------------------------------------


def test_task_created_to_completed_lifecycle(
    mem_conn,
    load_task_fixture,
) -> None:
    """Project create → update (in_progress) → complete; assert final row state.

    Provenance: #596 v8-PR-2 Stream 3 — wicked.task.created / .updated / .completed.
    """
    from daemon.db import get_task  # type: ignore[import]

    events, expected_task = load_task_fixture("task_created_to_completed")
    assert expected_task is not None, "Fixture must include expected_task.json"

    _replay_task_events(mem_conn, events)

    task_id = expected_task["id"]
    actual = get_task(mem_conn, task_id)
    assert actual is not None, (
        f"Task '{task_id}' not found in DB after projection. "
        "Check wicked.task.created handler."
    )

    _assert_task_equals(
        _normalize_timestamps(actual),
        _normalize_timestamps(expected_task),
        path="task_created_to_completed",
    )


def test_task_lifecycle_idempotent(
    mem_conn,
    load_task_fixture,
) -> None:
    """Replaying the same task events twice produces identical row state.

    Locked decision #6 applies to task projections too — every UPSERT is
    deterministic; replay never corrupts the projected state.
    """
    from daemon.db import get_task  # type: ignore[import]

    events, expected_task = load_task_fixture("task_created_to_completed")
    assert expected_task is not None

    task_id = expected_task["id"]

    _replay_task_events(mem_conn, events)
    state_first = get_task(mem_conn, task_id)

    _replay_task_events(mem_conn, events)
    state_second = get_task(mem_conn, task_id)

    # Strip timestamps before comparing (updated_at may change on re-upsert).
    def _strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in _TIMESTAMP_KEYS}

    assert _strip(state_first) == _strip(state_second), (
        "Idempotency violated: second replay produced different task state.\n"
        f"First:  {_strip(state_first)!r}\n"
        f"Second: {_strip(state_second)!r}"
    )


# ---------------------------------------------------------------------------
# Fixture scenario: status filtering via list_tasks
# ---------------------------------------------------------------------------


def test_task_status_filter(
    mem_conn,
    load_task_fixture,
) -> None:
    """Replay 3-task fixture and verify list_tasks(status_filter=...) returns the right rows.

    Verifies that pending / in_progress / completed tasks are projected with the
    correct status and that the status-filter parameter is honoured.
    """
    from daemon.db import list_tasks  # type: ignore[import]

    events, _ = load_task_fixture("task_status_filter")
    _replay_task_events(mem_conn, events)

    # After replay:
    #   task-A → pending
    #   task-B → in_progress
    #   task-C → completed
    pending_tasks = list_tasks(mem_conn, session_id="sess-def", status_filter="pending")
    in_progress_tasks = list_tasks(mem_conn, session_id="sess-def", status_filter="in_progress")
    completed_tasks = list_tasks(mem_conn, session_id="sess-def", status_filter="completed")
    all_tasks = list_tasks(mem_conn, session_id="sess-def")

    assert len(pending_tasks) == 1, (
        f"Expected 1 pending task; got {len(pending_tasks)}: {[t['id'] for t in pending_tasks]}"
    )
    assert pending_tasks[0]["id"] == "task-A", (
        f"Expected task-A pending; got {pending_tasks[0]['id']!r}"
    )

    assert len(in_progress_tasks) == 1, (
        f"Expected 1 in_progress task; got {len(in_progress_tasks)}"
    )
    assert in_progress_tasks[0]["id"] == "task-B", (
        f"Expected task-B in_progress; got {in_progress_tasks[0]['id']!r}"
    )

    assert len(completed_tasks) == 1, (
        f"Expected 1 completed task; got {len(completed_tasks)}"
    )
    assert completed_tasks[0]["id"] == "task-C", (
        f"Expected task-C completed; got {completed_tasks[0]['id']!r}"
    )

    assert len(all_tasks) == 3, (
        f"Expected 3 total tasks; got {len(all_tasks)}"
    )


# ---------------------------------------------------------------------------
# Fixture scenario: chain_id filtering via list_tasks
# ---------------------------------------------------------------------------


def test_task_chain_id_filter(
    mem_conn,
    load_task_fixture,
) -> None:
    """Replay multi-chain fixture; verify list_tasks(chain_id_filter=...) returns correct rows.

    Ensures chain_id is correctly projected and that the chain_id filter on
    list_tasks narrows results to the requested chain only.
    """
    from daemon.db import list_tasks  # type: ignore[import]

    events, _ = load_task_fixture("task_chain_filter")
    _replay_task_events(mem_conn, events)

    alpha_tasks = list_tasks(mem_conn, chain_id_filter="proj-alpha.root")
    beta_tasks = list_tasks(mem_conn, chain_id_filter="proj-beta.root")
    all_tasks = list_tasks(mem_conn, session_id="sess-ghi")

    assert len(alpha_tasks) == 2, (
        f"Expected 2 alpha tasks; got {len(alpha_tasks)}: {[t['id'] for t in alpha_tasks]}"
    )
    assert len(beta_tasks) == 1, (
        f"Expected 1 beta task; got {len(beta_tasks)}: {[t['id'] for t in beta_tasks]}"
    )
    assert len(all_tasks) == 3, (
        f"Expected 3 total tasks for sess-ghi; got {len(all_tasks)}"
    )
    assert all(t["chain_id"] == "proj-alpha.root" for t in alpha_tasks), (
        "All alpha tasks must have chain_id='proj-alpha.root'"
    )
    assert beta_tasks[0]["chain_id"] == "proj-beta.root", (
        f"Beta task chain_id mismatch: {beta_tasks[0]['chain_id']!r}"
    )


# ---------------------------------------------------------------------------
# Inline stream: metadata preservation
# ---------------------------------------------------------------------------


def test_task_metadata_preserved(
    mem_conn,
    task_event_stream,
) -> None:
    """Metadata dict is stored + retrieved correctly after task.created.

    Verifies that the metadata column round-trips JSON serialisation and that
    the projector preserves all fields from the enriched metadata envelope.
    """
    from daemon.db import get_task  # type: ignore[import]

    meta = {
        "chain_id": "my-proj.build",
        "event_type": "coding-task",
        "source_agent": "senior-engineer",
        "phase": "build",
        "requirement_id": "REQ-ENG-042",
    }
    events = task_event_stream(
        {
            "event_type": "wicked.task.created",
            "payload": {
                "task_id": "task-meta-001",
                "session_id": "sess-meta",
                "subject": "Write the router module",
                "status": "pending",
                "chain_id": "my-proj.build",
                "event_type": "coding-task",
                "metadata": meta,
            },
        }
    )

    _replay_task_events(mem_conn, events)

    actual = get_task(mem_conn, "task-meta-001")
    assert actual is not None, "task-meta-001 not found after projection"
    assert isinstance(actual.get("metadata"), dict), (
        "metadata should be deserialised to a dict; "
        f"got {type(actual.get('metadata')).__name__}: {actual.get('metadata')!r}"
    )
    stored_meta = actual["metadata"]
    assert stored_meta.get("event_type") == "coding-task", (
        f"metadata.event_type mismatch: {stored_meta.get('event_type')!r}"
    )
    assert stored_meta.get("source_agent") == "senior-engineer", (
        f"metadata.source_agent mismatch: {stored_meta.get('source_agent')!r}"
    )
    assert stored_meta.get("phase") == "build", (
        f"metadata.phase mismatch: {stored_meta.get('phase')!r}"
    )


# ---------------------------------------------------------------------------
# Inline stream: unknown task event type is ignored (decision #8)
# ---------------------------------------------------------------------------


def test_unknown_task_event_ignored(
    mem_conn,
    task_event_stream,
) -> None:
    """An unknown wicked.task.* subtype is logged as 'ignored', not 'error'.

    Decision #8: projector never raises on unknown event_type; cursor advances.
    """
    events = task_event_stream(
        {
            "event_type": "wicked.task.created",
            "payload": {
                "task_id": "task-unk-pre",
                "session_id": "sess-unk",
                "subject": "Before unknown",
                "status": "pending",
            },
        },
        {
            "event_type": "wicked.task.future_extension",
            "payload": {"task_id": "task-unk-pre", "session_id": "sess-unk"},
        },
        {
            "event_type": "wicked.task.completed",
            "payload": {"task_id": "task-unk-pre", "session_id": "sess-unk"},
        },
    )

    _replay_task_events(mem_conn, events)

    # The unknown event (event_id=2) must be logged as 'ignored'.
    cursor = mem_conn.execute(
        "SELECT projection_status FROM event_log WHERE event_id = 2"
    )
    row = cursor.fetchone()
    assert row is not None, (
        "event_id=2 (wicked.task.future_extension) not found in event_log"
    )
    assert row[0] == "ignored", (
        f"Unknown task event expected 'ignored'; got {row[0]!r}"
    )

    # The downstream completed event (event_id=3) must still project correctly.
    from daemon.db import get_task  # type: ignore[import]
    actual = get_task(mem_conn, "task-unk-pre")
    assert actual is not None, "task-unk-pre not found after unknown event in stream"
    assert actual["status"] == "completed", (
        f"Status after completed event expected 'completed'; got {actual['status']!r}"
    )


# ---------------------------------------------------------------------------
# Status-rank guard: out-of-order bus events must not regress task status
# ---------------------------------------------------------------------------


def test_status_regression_refused_by_rank_guard(
    mem_conn,
    task_event_stream,
) -> None:
    """Out-of-order wicked.task.updated must not overwrite a higher-rank status.

    Event sequence:
      1. wicked.task.created  → status='pending'
      2. wicked.task.updated  → status='completed'   (advances to terminal state)
      3. wicked.task.updated  → status='in_progress' (stale/out-of-order bus event)

    Expected end state: status='completed' (regression refused by _STATUS_RANK guard).

    Provenance: #596 v8-PR-2, council condition #611 — status_rank guard.
    """
    from daemon.db import get_task  # type: ignore[import]

    events = task_event_stream(
        {
            "event_type": "wicked.task.created",
            "payload": {
                "task_id": "task-rank-001",
                "session_id": "sess-rank",
                "subject": "Rank guard test task",
                "status": "pending",
            },
        },
        {
            "event_type": "wicked.task.updated",
            "payload": {
                "task_id": "task-rank-001",
                "session_id": "sess-rank",
                "status": "completed",
            },
        },
        {
            # Out-of-order event: attempts to regress completed → in_progress.
            "event_type": "wicked.task.updated",
            "payload": {
                "task_id": "task-rank-001",
                "session_id": "sess-rank",
                "status": "in_progress",
            },
        },
    )

    _replay_task_events(mem_conn, events)

    actual = get_task(mem_conn, "task-rank-001")
    assert actual is not None, "task-rank-001 not found after projection"
    assert actual["status"] == "completed", (
        f"Status regression guard failed: expected 'completed' after out-of-order "
        f"'in_progress' event; got {actual['status']!r}"
    )


def test_status_progression_forward_allowed(
    mem_conn,
    task_event_stream,
) -> None:
    """Forward status transitions must always be applied by the rank guard.

    Event sequence:
      1. wicked.task.created  → status='pending'
      2. wicked.task.updated  → status='in_progress'   (forward)
      3. wicked.task.updated  → status='completed'     (forward)

    Expected end state: status='completed'.

    Provenance: #596 v8-PR-2, council condition #611 — status_rank guard.
    """
    from daemon.db import get_task  # type: ignore[import]

    events = task_event_stream(
        {
            "event_type": "wicked.task.created",
            "payload": {
                "task_id": "task-rank-002",
                "session_id": "sess-rank-fwd",
                "subject": "Forward progression task",
                "status": "pending",
            },
        },
        {
            "event_type": "wicked.task.updated",
            "payload": {
                "task_id": "task-rank-002",
                "session_id": "sess-rank-fwd",
                "status": "in_progress",
            },
        },
        {
            "event_type": "wicked.task.updated",
            "payload": {
                "task_id": "task-rank-002",
                "session_id": "sess-rank-fwd",
                "status": "completed",
            },
        },
    )

    _replay_task_events(mem_conn, events)

    actual = get_task(mem_conn, "task-rank-002")
    assert actual is not None, "task-rank-002 not found after projection"
    assert actual["status"] == "completed", (
        f"Forward progression expected 'completed'; got {actual['status']!r}"
    )
