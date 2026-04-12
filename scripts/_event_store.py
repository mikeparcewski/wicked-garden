#!/usr/bin/env python3
"""
_event_store.py — Unified event log for cross-domain queries.

Append-only SQLite event store with FTS5 full-text search.
Every DomainStore write auto-emits an event. Domains can also
emit events directly for richer tracking.

Events.db is a SEPARATE file from domain JSON storage.
Corruption of events.db never breaks core domain operations.

DB location:
    ~/.something-wicked/wicked-garden/local/wicked-garden/events.db

Usage:
    from _event_store import EventStore

    # Append an event
    EventStore.append(
        domain="crew",
        action="phases.transitioned",
        source="phases",
        record_id="abc123",
        payload={"from": "clarify", "to": "build"},
        project_id="my-project",
        tags=["phase-change"],
    )

    # Query events
    results = EventStore.query(domain="crew", since="7d", limit=50)
    results = EventStore.query(project_id="my-project", fts="auth migration")

    # Purge old events
    EventStore.purge_before(days=90)

Stdlib-only. No external dependencies.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------

_MAX_PAYLOAD_BYTES = 8192  # 8KB — larger payloads get truncated + payload_ref


def _db_path() -> Path:
    """Resolve events.db path using the same root as DomainStore."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from _paths import get_local_path
        p = get_local_path("wicked-garden", "events")
    except ImportError:
        p = Path.home() / ".something-wicked" / "wicked-garden" / "local" / "wicked-garden" / "events"
    p.mkdir(parents=True, exist_ok=True)
    return p / "events.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    event_id       TEXT PRIMARY KEY,
    ts             TEXT NOT NULL,
    domain         TEXT NOT NULL,
    action         TEXT NOT NULL,
    source         TEXT,
    record_id      TEXT,
    project_id     TEXT,
    session_id     TEXT,
    sprint_ref     TEXT,
    actor          TEXT DEFAULT 'claude',
    payload        TEXT,
    payload_ref    TEXT,
    tags           TEXT,
    schema_version INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_domain_ts ON events(domain, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_project_ts ON events(project_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    domain, action, payload, tags,
    content='events',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, domain, action, payload, tags)
    VALUES (new.rowid, new.domain, new.action, new.payload, new.tags);
END;
"""


# ---------------------------------------------------------------------------
# EventStore
# ---------------------------------------------------------------------------

class EventStore:
    """Append-only event store with FTS5 search.

    Note: singleton connection assumes single-threaded access.
    Hook scripts run sequentially — this is safe in the current architecture.
    """

    _conn: sqlite3.Connection | None = None
    _schema_ready: bool = False

    @classmethod
    def _get_conn(cls) -> sqlite3.Connection:
        if cls._conn is None:
            db = _db_path()
            cls._conn = sqlite3.connect(str(db), timeout=5.0)
            cls._conn.row_factory = sqlite3.Row
            cls._conn.execute("PRAGMA journal_mode=WAL")
            cls._conn.execute("PRAGMA synchronous=NORMAL")
        return cls._conn

    @classmethod
    def ensure_schema(cls) -> None:
        """Create tables and indexes if they don't exist. Cached after first call."""
        if cls._schema_ready:
            return
        conn = cls._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.commit()
        cls._schema_ready = True

    @classmethod
    def append(
        cls,
        domain: str,
        action: str,
        source: str | None = None,
        record_id: str | None = None,
        payload: dict | str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        sprint_ref: str | None = None,
        actor: str = "claude",
        tags: list[str] | None = None,
        file_refs: list[str] | None = None,
    ) -> str | None:
        """Append an event. Returns event_id or None on failure."""
        try:
            conn = cls._get_conn()

            event_id = str(uuid.uuid4())
            ts = datetime.now(timezone.utc).isoformat()

            # Auto-resolve session_id
            if session_id is None:
                session_id = os.environ.get("CLAUDE_SESSION_ID", "")

            # Serialize payload
            payload_str = None
            payload_ref = None
            if payload is not None:
                if isinstance(payload, dict):
                    payload_str = json.dumps(payload, default=str)
                else:
                    payload_str = str(payload)

                # Truncate large payloads
                if len(payload_str) > _MAX_PAYLOAD_BYTES:
                    payload_ref = f"{domain}/{source}/{record_id}" if source and record_id else None
                    payload_str = payload_str[:_MAX_PAYLOAD_BYTES]
                    tags = (tags or []) + ["truncated"]

            # Add file_refs to tags
            if file_refs:
                tags = (tags or []) + [f"file:{f}" for f in file_refs]

            tags_str = json.dumps(tags) if tags else None

            conn.execute(
                """INSERT INTO events (
                    event_id, ts, domain, action, source, record_id,
                    project_id, session_id, sprint_ref, actor,
                    payload, payload_ref, tags, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    event_id, ts, domain, action, source, record_id,
                    project_id, session_id, sprint_ref, actor,
                    payload_str, payload_ref, tags_str,
                ),
            )
            conn.commit()
            return event_id

        except Exception:
            return None

    @classmethod
    def query(
        cls,
        domain: str | None = None,
        action: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        since: str | None = None,
        fts: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query events with filters.

        Args:
            domain: filter by domain name
            action: filter by action (supports prefix match with *)
            project_id: filter by project
            session_id: filter by session
            since: time window — "7d", "24h", "2026-03-01"
            fts: full-text search query
            limit: max results (default 50)
        """
        try:
            conn = cls._get_conn()
            conditions = []
            params: list[Any] = []

            if fts:
                # FTS query joins events_fts
                conditions.append("e.rowid IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)")
                params.append(fts)

            if domain:
                conditions.append("e.domain = ?")
                params.append(domain)

            if action:
                if action.endswith("*"):
                    conditions.append("e.action LIKE ?")
                    params.append(action.rstrip("*") + "%")
                else:
                    conditions.append("e.action = ?")
                    params.append(action)

            if project_id:
                conditions.append("e.project_id = ?")
                params.append(project_id)

            if session_id:
                conditions.append("e.session_id = ?")
                params.append(session_id)

            if since:
                ts_cutoff = _parse_since(since)
                if ts_cutoff:
                    conditions.append("e.ts >= ?")
                    params.append(ts_cutoff)

            where = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)

            rows = conn.execute(
                f"SELECT * FROM events e WHERE {where} ORDER BY e.ts DESC LIMIT ?",
                params,
            ).fetchall()

            return [dict(r) for r in rows]

        except Exception:
            return []

    @classmethod
    def purge_before(cls, days: int = 90) -> int:
        """Delete events older than N days. Returns count deleted."""
        try:
            conn = cls._get_conn()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            # Delete from FTS first
            conn.execute(
                "DELETE FROM events_fts WHERE rowid IN (SELECT rowid FROM events WHERE ts < ?)",
                (cutoff,),
            )
            cursor = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
        except Exception:
            return 0

    @classmethod
    def count(cls) -> int:
        """Return total event count."""
        try:
            conn = cls._get_conn()
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    @classmethod
    def close(cls) -> None:
        """Close the database connection."""
        if cls._conn is not None:
            cls._conn.close()
            cls._conn = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_since(since: str) -> str | None:
    """Parse a 'since' string into an ISO timestamp."""
    now = datetime.now(timezone.utc)
    s = since.strip().lower()

    if s.endswith("d"):
        try:
            days = int(s[:-1])
            return (now - timedelta(days=days)).isoformat()
        except ValueError:
            pass  # fail open
    elif s.endswith("h"):
        try:
            hours = int(s[:-1])
            return (now - timedelta(hours=hours)).isoformat()
        except ValueError:
            pass  # fail open
    else:
        # Assume ISO date
        try:
            datetime.fromisoformat(since)
            return since
        except ValueError:
            pass  # fail open
    return None


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Event store CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Initialize schema")
    sub.add_parser("count", help="Count events")

    q = sub.add_parser("query", help="Query events")
    q.add_argument("--domain", help="Filter by domain")
    q.add_argument("--action", help="Filter by action")
    q.add_argument("--project", help="Filter by project")
    q.add_argument("--since", help="Time window (7d, 24h, ISO date)")
    q.add_argument("--fts", help="Full-text search")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--json", action="store_true")

    p = sub.add_parser("purge", help="Purge old events")
    p.add_argument("--days", type=int, default=90)

    args = parser.parse_args()

    EventStore.ensure_schema()

    if args.cmd == "init":
        print("Schema initialized.")
    elif args.cmd == "count":
        print(json.dumps({"count": EventStore.count()}))
    elif args.cmd == "query":
        results = EventStore.query(
            domain=args.domain, action=args.action,
            project_id=args.project, since=args.since,
            fts=args.fts, limit=args.limit,
        )
        if getattr(args, "json", False):
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"[{r['ts'][:19]}] {r['domain']}.{r['action']}: {r.get('record_id', '')}")
    elif args.cmd == "purge":
        deleted = EventStore.purge_before(days=args.days)
        print(json.dumps({"deleted": deleted}))
    else:
        parser.print_help()
