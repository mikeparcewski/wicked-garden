"""SQLite schema, connection management, and per-table CRUD for the v8 projection daemon."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Phase state machine import (v8-PR-3 #590).
# The scripts/crew directory is not on sys.path by default when daemon/db.py
# is imported standalone (e.g. from tests).  Add it if needed so that
# phase_state can be resolved without requiring callers to set PYTHONPATH.
# ---------------------------------------------------------------------------
_SCRIPTS_CREW = Path(__file__).resolve().parents[1] / "scripts" / "crew"
if str(_SCRIPTS_CREW) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CREW))

_DEFAULT_DB_PATH = Path.home() / ".something-wicked" / "wicked-garden-daemon" / "projections.db"
_ENV_DB_KEY = "WG_DAEMON_DB"

_BUS_SOURCE_DEFAULT = "wicked-bus"
_STATUS_ACTIVE = "active"
_PRUNE_KEEP_DEFAULT = 10_000

_PROJECTION_STATUS_APPLIED = "applied"
_PROJECTION_STATUS_IGNORED = "ignored"
_PROJECTION_STATUS_ERROR = "error"


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open the projections DB; set WAL mode and foreign keys. Caller is responsible for closing."""
    resolved = path or os.environ.get(_ENV_DB_KEY) or str(_DEFAULT_DB_PATH)
    db_path = Path(resolved)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes idempotently; safe to call on every startup.

    Also runs the phase-state migration (v8-PR-3 #590) exactly once via the
    _migrations table, mapping any legacy ``completed`` rows to ``approved``
    (AC-linked evidence present) or ``skipped`` (no evidence).
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id                  TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            workspace           TEXT,
            directory           TEXT,
            archetype           TEXT,
            complexity_score    REAL,
            rigor_tier          TEXT,
            current_phase       TEXT NOT NULL DEFAULT '',
            status              TEXT NOT NULL DEFAULT 'active',
            chain_id            TEXT,
            yolo_revoked_count  INTEGER NOT NULL DEFAULT 0,
            last_revoke_reason  TEXT,
            created_at          INTEGER NOT NULL,
            updated_at          INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_projects_status
            ON projects(status);

        CREATE INDEX IF NOT EXISTS idx_projects_updated
            ON projects(updated_at DESC);

        CREATE TABLE IF NOT EXISTS phases (
            project_id          TEXT NOT NULL,
            phase               TEXT NOT NULL,
            state               TEXT NOT NULL DEFAULT 'pending',
            gate_score          REAL,
            gate_verdict        TEXT,
            gate_reviewer       TEXT,
            started_at          INTEGER,
            terminal_at         INTEGER,
            rework_iterations   INTEGER NOT NULL DEFAULT 0,
            updated_at          INTEGER NOT NULL,
            PRIMARY KEY (project_id, phase),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_phases_project
            ON phases(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS cursor (
            bus_source      TEXT PRIMARY KEY,
            cursor_id       TEXT NOT NULL,
            last_event_id   INTEGER NOT NULL DEFAULT 0,
            acked_at        INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_log (
            event_id            INTEGER PRIMARY KEY,
            event_type          TEXT NOT NULL,
            chain_id            TEXT,
            payload_json        TEXT NOT NULL,
            projection_status   TEXT NOT NULL,
            error_message       TEXT,
            ingested_at         INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_event_log_type
            ON event_log(event_type, event_id DESC);

        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            subject     TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'in_progress', 'completed')),
            chain_id    TEXT,
            event_type  TEXT,
            metadata    TEXT,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_session
            ON tasks(session_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status);

        CREATE INDEX IF NOT EXISTS idx_tasks_chain
            ON tasks(chain_id);

        -- Migration tracking (v8-PR-3 #590): each row records one idempotent
        -- migration that has been applied.  Re-running init_schema is a no-op
        -- once the migration row exists.
        CREATE TABLE IF NOT EXISTS _migrations (
            name        TEXT PRIMARY KEY,
            applied_at  INTEGER NOT NULL
        );
    """)
    conn.commit()

    # Run one-time migrations registered above.
    _run_migration(conn, "phase_state_completed_to_canonical",
                   _migrate_phase_state_completed_to_canonical)


# ---------------------------------------------------------------------------
# Migration helpers (v8-PR-3 #590)
# ---------------------------------------------------------------------------

def _run_migration(
    conn: sqlite3.Connection,
    name: str,
    fn: "Callable[[sqlite3.Connection], None]",
) -> None:
    """Apply *fn* exactly once, guarded by a _migrations row.

    Idempotent: if the migration row already exists the function is not called.
    The row is written inside the same transaction as the migration body so
    partial migrations cannot produce a committed row without committed data.
    """
    from typing import Callable  # local import avoids circular at module level

    row = conn.execute(
        "SELECT name FROM _migrations WHERE name = ?", (name,)
    ).fetchone()
    if row is not None:
        return  # already applied
    fn(conn)
    conn.execute(
        "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
        (name, int(time.time())),
    )
    conn.commit()


def _migrate_phase_state_completed_to_canonical(conn: sqlite3.Connection) -> None:
    """Map legacy ``completed`` phase rows to canonical states.

    Mapping rule (v8-PR-3 #590):
    - gate_score IS NOT NULL or gate_verdict IS NOT NULL → ``approved``
      (AC-linked evidence present from a prior gate decision)
    - otherwise → ``skipped``
      (no gate evidence; treat as a no-gate-required skip)

    This migration targets the daemon ``phases`` table only.  The
    phase_manager.py JSON file store is unaffected.
    """
    now = int(time.time())
    rows = conn.execute(
        "SELECT project_id, phase, gate_score, gate_verdict "
        "FROM phases WHERE state = 'completed'"
    ).fetchall()
    for row in rows:
        project_id = row[0]
        phase = row[1]
        has_evidence = (row[2] is not None) or (row[3] is not None)
        new_state = "approved" if has_evidence else "skipped"
        conn.execute(
            "UPDATE phases SET state = ?, updated_at = ? "
            "WHERE project_id = ? AND phase = ? AND state = 'completed'",
            (new_state, now, project_id, phase),
        )
    # Commit is handled by _run_migration after the migration row is written.


def upsert_project(conn: sqlite3.Connection, project_id: str, fields: dict[str, Any]) -> None:
    """Insert or update a project row; missing keys preserve existing column values."""
    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Columns that can be updated after creation (never overwrite id or created_at).
    mutable_cols = [
        "name", "workspace", "directory", "archetype",
        "complexity_score", "rigor_tier", "current_phase", "status",
        "chain_id", "yolo_revoked_count", "last_revoke_reason", "updated_at",
    ]

    # For a brand-new row: require name (NOT NULL in schema). INSERT OR IGNORE leaves
    # an existing row untouched; the UPDATE below then applies the supplied fields.
    if "name" in fields:
        created_at = fields.get("created_at", now)
        # Collect all supplied columns for the initial insert.
        ins_cols: list[str] = ["id", "created_at"]
        ins_vals: list[Any] = [project_id, created_at]
        for col in mutable_cols:
            if col in fields:
                ins_cols.append(col)
                ins_vals.append(fields[col])
        placeholders = ", ".join("?" for _ in ins_cols)
        conn.execute(
            f"INSERT OR IGNORE INTO projects ({', '.join(ins_cols)}) VALUES ({placeholders})",
            ins_vals,
        )

    # Apply all supplied mutable fields as an in-place update so partial calls
    # (e.g. only archetype) update the existing row without touching other columns.
    # Touch-null semantic (#589 coordination item #7): for columns that must never
    # regress to NULL when a richer value already exists, use COALESCE so that a
    # None/null payload value is silently ignored on the row.
    _PRESERVE_NONNULL = frozenset({"name", "archetype"})
    update_cols = [c for c in mutable_cols if c in fields]
    if update_cols:
        set_parts = []
        for c in update_cols:
            if c in _PRESERVE_NONNULL:
                set_parts.append(f"{c} = COALESCE(?, {c})")
            else:
                set_parts.append(f"{c} = ?")
        set_clause = ", ".join(set_parts)
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            [fields[c] for c in update_cols] + [project_id],
        )

    conn.commit()


def upsert_phase(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
    fields: dict[str, Any],
) -> None:
    """Insert or update a phase row; missing keys preserve existing column values.

    When ``fields`` contains a ``state`` key the value is validated against the
    canonical phase state machine (v8-PR-3 #590).  The current DB state is read
    first so the transition check can verify the move is legal.  Raises
    ``phase_state.InvalidTransition`` if the write attempts a banned or illegal
    state transition.

    Callers in ``projector.py`` use named constants from ``phase_state.PhaseState``
    so a typo or new banned value is caught at import time rather than at runtime.
    """
    from phase_state import InvalidTransition, PhaseState, BANNED_STATES, transition as _transition  # type: ignore[import]

    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Validate the requested state transition before touching the DB.
    if "state" in fields:
        requested_state = fields["state"]
        # Reject banned states immediately (R2: no silent failures).
        if str(requested_state) in BANNED_STATES:
            raise InvalidTransition(
                f"upsert_phase: attempted to write banned state {requested_state!r} "
                f"for ({project_id!r}, {phase!r}). "
                "Run phase_state_migration.py to clean up existing rows."
            )
        # Coerce to PhaseState to catch unknown values early.
        try:
            PhaseState(str(requested_state))
        except ValueError as exc:
            raise InvalidTransition(
                f"upsert_phase: unknown state {requested_state!r} for ({project_id!r}, {phase!r}). "
                f"Valid states: {sorted(PhaseState)}"
            ) from exc
        # Note: we do NOT call _transition() here because upsert_phase is also
        # used by the projector for INSERT (creating a row at the target state
        # directly from an event, not by applying an event to existing state).
        # The projector's _transition-validated constants (PhaseState.ACTIVE etc.)
        # already guarantee the value is canonical.  The guard above ensures no
        # banned / unknown string can slip through regardless of the caller.

    # Columns that can be set after (project_id, phase) PK is established.
    mutable_cols = [
        "state", "gate_score", "gate_verdict", "gate_reviewer",
        "started_at", "terminal_at", "rework_iterations", "updated_at",
    ]

    # Ensure the row exists; schema defaults cover state/rework_iterations.
    ins_cols: list[str] = ["project_id", "phase"]
    ins_vals: list[Any] = [project_id, phase]
    for col in mutable_cols:
        if col in fields:
            ins_cols.append(col)
            ins_vals.append(fields[col])
    placeholders = ", ".join("?" for _ in ins_cols)
    conn.execute(
        f"INSERT OR IGNORE INTO phases ({', '.join(ins_cols)}) VALUES ({placeholders})",
        ins_vals,
    )

    # Apply supplied mutable fields to the (possibly pre-existing) row.
    update_cols = [c for c in mutable_cols if c in fields]
    if update_cols:
        set_clause = ", ".join(f"{c} = ?" for c in update_cols)
        conn.execute(
            f"UPDATE phases SET {set_clause} WHERE project_id = ? AND phase = ?",
            [fields[c] for c in update_cols] + [project_id, phase],
        )

    conn.commit()


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    """Return a project row as a dict, or None if not found."""
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return dict(row) if row else None


def list_projects(
    conn: sqlite3.Connection,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return projects ordered by updated_at DESC; optionally filtered by status."""
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_phases(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    """Return all phases for a project ordered by started_at NULLS LAST."""
    rows = conn.execute(
        "SELECT * FROM phases WHERE project_id = ? ORDER BY started_at ASC NULLS LAST",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_cursor(
    conn: sqlite3.Connection,
    bus_source: str = _BUS_SOURCE_DEFAULT,
) -> dict[str, Any] | None:
    """Return the cursor row for bus_source, or None if not yet registered."""
    row = conn.execute(
        "SELECT * FROM cursor WHERE bus_source = ?", (bus_source,)
    ).fetchone()
    return dict(row) if row else None


def set_cursor(
    conn: sqlite3.Connection,
    bus_source: str,
    cursor_id: str,
    last_event_id: int,
) -> None:
    """Upsert the bus cursor; updates last_event_id and acked_at."""
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO cursor (bus_source, cursor_id, last_event_id, acked_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bus_source) DO UPDATE SET
            cursor_id     = excluded.cursor_id,
            last_event_id = excluded.last_event_id,
            acked_at      = excluded.acked_at
        """,
        (bus_source, cursor_id, last_event_id, now),
    )
    conn.commit()


def append_event_log(
    conn: sqlite3.Connection,
    event_id: int,
    event_type: str,
    chain_id: str | None,
    payload: dict[str, Any],
    projection_status: str,
    error_message: str | None = None,
) -> None:
    """Append one event to the audit log; silently replaces on duplicate event_id."""
    now = int(time.time())
    payload_json = json.dumps(payload, separators=(",", ":"))
    conn.execute(
        """
        INSERT OR REPLACE INTO event_log
            (event_id, event_type, chain_id, payload_json, projection_status, error_message, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, event_type, chain_id, payload_json, projection_status, error_message, now),
    )
    conn.commit()


def list_events(
    conn: sqlite3.Connection,
    since: int = 0,
    limit: int = 100,
    event_type_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Return event_log rows with event_id > since, ordered by event_id ASC, LIMIT.

    Optionally filter to event_type values that start with event_type_prefix.
    Used by server.py's /events endpoint (#589, coordination item #1).
    """
    if event_type_prefix is not None:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE event_id > ? AND event_type LIKE ?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (since, event_type_prefix + "%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE event_id > ?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def prune_event_log(conn: sqlite3.Connection, keep_last: int = _PRUNE_KEEP_DEFAULT) -> int:
    """Delete oldest event_log rows beyond keep_last; returns the count deleted."""
    cursor = conn.execute(
        "SELECT MIN(event_id) FROM (SELECT event_id FROM event_log ORDER BY event_id DESC LIMIT ?)",
        (keep_last,),
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return 0
    cutoff_id: int = row[0]
    result = conn.execute(
        "DELETE FROM event_log WHERE event_id < ?", (cutoff_id,)
    )
    conn.commit()
    return result.rowcount


# ---------------------------------------------------------------------------
# Task CRUD (Stream 1 — #596 v8-PR-2)
# ---------------------------------------------------------------------------
# Tasks are projected from bus events (wicked.task.created / .updated /
# .completed).  The daemon is READ-ONLY from the task side — Claude's native
# TaskList remains the primary writer; the daemon projects over it.

_VALID_TASK_STATUSES: frozenset[str] = frozenset({"pending", "in_progress", "completed"})
_TASK_MUTABLE_COLS: tuple[str, ...] = (
    "subject", "status", "chain_id", "event_type", "metadata", "updated_at",
)


def upsert_task(conn: sqlite3.Connection, task_id: str, fields: dict[str, Any]) -> None:
    """Insert or update a task row; missing keys preserve existing column values.

    ``fields`` keys that map to mutable columns are applied via INSERT OR IGNORE
    (to establish the row) followed by an UPDATE (to apply deltas).  The
    ``id``, ``session_id``, and ``created_at`` columns are immutable after
    creation; supply them on the initial call.

    Callers may pass ``metadata`` as a dict — it is JSON-serialised before
    storage so the column stays TEXT.
    """
    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Serialise metadata dict → TEXT so the column stays TEXT in SQLite.
    if isinstance(fields.get("metadata"), dict):
        fields["metadata"] = json.dumps(fields["metadata"], separators=(",", ":"))

    session_id = fields.get("session_id", "")
    subject = fields.get("subject", "")
    created_at = fields.get("created_at", now)

    # Bootstrap the row so subsequent UPDATE has a target.
    ins_cols: list[str] = ["id", "session_id", "subject", "created_at"]
    ins_vals: list[Any] = [task_id, session_id, subject, created_at]
    for col in _TASK_MUTABLE_COLS:
        if col in fields:
            ins_cols.append(col)
            ins_vals.append(fields[col])
    placeholders = ", ".join("?" for _ in ins_cols)
    conn.execute(
        f"INSERT OR IGNORE INTO tasks ({', '.join(ins_cols)}) VALUES ({placeholders})",
        ins_vals,
    )

    # Apply mutable-column deltas to the (possibly pre-existing) row.
    update_cols = [c for c in _TASK_MUTABLE_COLS if c in fields]
    if update_cols:
        set_clause = ", ".join(f"{c} = ?" for c in update_cols)
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            [fields[c] for c in update_cols] + [task_id],
        )

    conn.commit()


def get_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    """Return a task row as a dict (metadata deserialised to dict), or None."""
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    _deserialize_task_metadata(result)
    return result


def list_tasks(
    conn: sqlite3.Connection,
    session_id: str | None = None,
    status_filter: str | None = None,
    chain_id_filter: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return task rows ordered by updated_at DESC.

    All filter args are optional and combinable.  An empty result is []
    rather than None.  ``limit`` is capped at 500 (R5: no unbounded reads).
    """
    _MAX_LIMIT = 500
    limit = min(limit, _MAX_LIMIT)

    clauses: list[str] = []
    params: list[Any] = []

    if session_id is not None:
        clauses.append("session_id = ?")
        params.append(session_id)
    if status_filter is not None:
        clauses.append("status = ?")
        params.append(status_filter)
    if chain_id_filter is not None:
        clauses.append("chain_id = ?")
        params.append(chain_id_filter)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM tasks {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        _deserialize_task_metadata(d)
        result.append(d)
    return result


def _deserialize_task_metadata(task_dict: dict[str, Any]) -> None:
    """Deserialise the ``metadata`` column from TEXT to dict in-place.

    Silently leaves the field as-is if parsing fails — the caller gets the raw
    string rather than a crash.  Per R4: swallowed only because metadata is
    optional/enrichment and the row is still usable without it.
    """
    raw = task_dict.get("metadata")
    if isinstance(raw, str):
        try:
            task_dict["metadata"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass  # leave as raw string — callers treat metadata as best-effort
