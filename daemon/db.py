"""SQLite schema, connection management, and per-table CRUD for the v8 projection daemon."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

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
    """Create all 4 tables and indexes idempotently; safe to call on every startup."""
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
            PRIMARY KEY (project_id, phase)
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
    """)
    conn.commit()


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
    """Insert or update a phase row; missing keys preserve existing column values."""
    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

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
