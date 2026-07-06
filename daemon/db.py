"""
db.py — SQLite connection manager for the wicked-garden daemon.

Auto-creates `.wicked-garden/garden.db` in the current working directory.
Thread-safe via check_same_thread=False + a module-level threading.Lock.

Usage::

    from daemon.db import get_connection

    conn = get_connection()           # uses default path
    conn = get_connection("/path/to/garden.db")  # explicit path
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("wicked-garden.daemon.db")

_lock = threading.Lock()
_write_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS garden_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS council_sessions (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    verdict TEXT,
    votes TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS hitl_prompts (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    prompt TEXT NOT NULL,
    response TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    responded_at TEXT
);

CREATE TABLE IF NOT EXISTS projector_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hooks (
    id TEXT PRIMARY KEY,
    event_pattern TEXT NOT NULL,
    command TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);
"""


def _default_db_path() -> Path:
    """Return the default database path: .wicked-garden/garden.db in cwd."""
    db_dir = Path.cwd() / ".wicked-garden"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "garden.db"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return (and cache) the module-level SQLite connection.

    Thread-safe: uses a module-level lock so multiple threads can call this
    safely. The connection itself is created with check_same_thread=False so it
    can be shared across threads.

    Args:
        db_path: Path to the SQLite database file. Defaults to
                 ``.wicked-garden/garden.db`` in the current working directory.
                 Ignored on subsequent calls — the first path wins.

    Returns:
        sqlite3.Connection with WAL journal mode and row_factory set to
        sqlite3.Row for named-column access.
    """
    global _conn, _db_path

    with _lock:
        if _conn is not None:
            return _conn

        resolved = Path(db_path) if db_path else _default_db_path()
        resolved.parent.mkdir(parents=True, exist_ok=True)

        logger.debug("Opening garden DB at %s", resolved)
        conn = sqlite3.connect(
            str(resolved),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_schema(conn)

        _conn = conn
        _db_path = str(resolved)

    return _conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not already exist.

    Called only from within ``get_connection()``'s ``_lock`` scope; no
    additional locking is needed here.
    """
    conn.executescript(SCHEMA)
    conn.commit()
    logger.debug("Schema applied")


def get_write_lock() -> threading.Lock:
    """Return the module-level write lock.

    All callers that write to the shared connection must acquire this lock
    around their ``execute`` / ``commit`` pair to prevent concurrent
    interleaving under Flask's threaded request handling.

    Usage::

        from daemon.db import get_write_lock

        with get_write_lock():
            conn.execute(...)
            conn.commit()
    """
    return _write_lock


def close_connection() -> None:
    """Close the cached connection. Primarily for tests / graceful shutdown."""
    global _conn, _db_path

    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
            _db_path = None
