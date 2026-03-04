#!/usr/bin/env python3
"""
_sqlite_store.py — SqliteStore: direct SQLite backend for local-only storage mode.

Replaces CP HTTP calls with direct SQLite reads/writes. Uses FTS5 + BM25 ranking.

Usage:
    from _sqlite_store import SqliteStore
    store = SqliteStore("/path/to/wicked-garden.db")
    store.create("wicked-mem", "memories", "abc123", {"title": "...", "content": "..."})
    record = store.get("wicked-mem", "memories", "abc123")
    results = store.search("deployment", domain="wicked-mem", limit=10)
    store.close()
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _sanitize_fts_query(query: str) -> str:
    """Sanitize a query string for FTS5 MATCH expressions.

    FTS5's default tokenizer splits on hyphens, so a query like
    ``wicked-garden`` is interpreted as ``wicked NOT garden``.
    This function wraps any hyphenated token in double-quotes so
    FTS5 treats it as a phrase query (adjacent tokens) instead.

    Already-quoted terms are left untouched.

    Note: This is NOT a general-purpose input sanitization layer.
    Callers are internal plugin agents (memory recall, search commands),
    not raw end-user input. FTS5 operators (OR, NOT, NEAR, column
    filters) are intentionally preserved for advanced queries.
    Malformed FTS5 expressions raise OperationalError, caught by
    ``SqliteStore.search()`` which returns ``[]`` gracefully.

    Examples:
        "wicked-garden"          -> '"wicked-garden"'
        "code-review deployment" -> '"code-review" deployment'
        '"already quoted"'       -> '"already quoted"'
        "plain search"           -> 'plain search'
    """
    if not query:
        return query

    tokens: list[str] = []
    i = 0
    chars = query

    while i < len(chars):
        # Pass through already-quoted phrases untouched
        if chars[i] == '"':
            end = chars.find('"', i + 1)
            if end == -1:
                # Unmatched quote — take rest of string as-is
                tokens.append(chars[i:])
                break
            tokens.append(chars[i:end + 1])
            i = end + 1
        elif chars[i] in (' ', '\t', '\n'):
            tokens.append(chars[i])
            i += 1
        else:
            # Collect a non-whitespace, non-quoted token
            j = i
            while j < len(chars) and chars[j] not in (' ', '\t', '\n', '"'):
                j += 1
            token = chars[i:j]
            # Wrap tokens with internal hyphens in double-quotes.
            # Preserve leading-hyphen tokens (FTS5 NOT operator, e.g. "-bar")
            # and FTS5 column filters (e.g. "title:foo-bar").
            if '-' in token and not token.startswith('"') and not token.startswith('-') and ':' not in token:
                token = f'"{token}"'
            tokens.append(token)
            i = j

    return ''.join(tokens)

_connections: dict[str, sqlite3.Connection] = {}

# Per-path locks protect concurrent execute/commit sequences on the shared connection.
# _locks_lock serializes lock creation so two threads racing on the same new db_path
# don't each create a separate Lock object.
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()

_PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
]

# FTS column named 'data' (not 'content') — 'content' collides with FTS5 internals.
_DDL = [
    """CREATE TABLE IF NOT EXISTS records (
        domain TEXT NOT NULL, source TEXT NOT NULL, id TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (domain, source, id)
    )""",
    """CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
        id UNINDEXED, domain UNINDEXED, data,
        content='records', content_rowid='rowid'
    )""",
    """CREATE TRIGGER IF NOT EXISTS records_fts_insert AFTER INSERT ON records BEGIN
        INSERT INTO records_fts(rowid, id, domain, data)
        VALUES (new.rowid, new.id, new.domain, new.data);
    END""",
    """CREATE TRIGGER IF NOT EXISTS records_fts_update AFTER UPDATE ON records BEGIN
        INSERT INTO records_fts(records_fts, rowid, id, domain, data)
        VALUES ('delete', old.rowid, old.id, old.domain, old.data);
        INSERT INTO records_fts(rowid, id, domain, data)
        VALUES (new.rowid, new.id, new.domain, new.data);
    END""",
    """CREATE TRIGGER IF NOT EXISTS records_fts_delete AFTER DELETE ON records BEGIN
        INSERT INTO records_fts(records_fts, rowid, id, domain, data)
        VALUES ('delete', old.rowid, old.id, old.domain, old.data);
    END""",
]


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Return a cached per-process connection, creating schema on first open."""
    if db_path not in _connections:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for sql in _PRAGMAS + _DDL:
            conn.execute(sql)
        conn.commit()
        _connections[db_path] = conn
    return _connections[db_path]


def _get_lock(db_path: str) -> threading.Lock:
    """Return the per-path lock, creating it if needed (thread-safe via _locks_lock)."""
    if db_path not in _locks:
        with _locks_lock:
            # Double-checked locking: re-test after acquiring the meta-lock
            if db_path not in _locks:
                _locks[db_path] = threading.Lock()
    return _locks[db_path]


def _row(record_id: str, data_json: str, created_at: str, updated_at: str) -> dict:
    try:
        rec = json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        rec = {}
    rec.setdefault("id", record_id)
    rec.setdefault("created_at", created_at)
    rec.setdefault("updated_at", updated_at)
    return rec


class SqliteStore:
    """Direct SQLite CRUD + FTS5 search for wicked-garden local-only mode."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = _get_lock(db_path)
        self._conn = _get_connection(db_path)

    def create(self, domain: str, source: str, record_id: str, data: dict) -> dict:
        """INSERT OR IGNORE — idempotent, returns existing record if already present."""
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO records (domain, source, id, data) VALUES (?, ?, ?, ?)",
                    (domain, source, record_id, json.dumps(data)),
                )
                self._conn.commit()
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] create %s/%s/%s: %s", domain, source, record_id, exc)
            try:
                r = self._conn.execute(
                    "SELECT data, created_at, updated_at FROM records "
                    "WHERE domain=? AND source=? AND id=?",
                    (domain, source, record_id),
                ).fetchone()
            except sqlite3.OperationalError:
                r = None
        return (_row(record_id, r["data"], r["created_at"], r["updated_at"]) if r else None) or data

    def update(self, domain: str, source: str, record_id: str, data: dict) -> dict | None:
        """Replace record data. Returns None if record not found."""
        with self._lock:
            try:
                cur = self._conn.execute(
                    "UPDATE records SET data=?, updated_at=datetime('now') "
                    "WHERE domain=? AND source=? AND id=?",
                    (json.dumps(data), domain, source, record_id),
                )
                self._conn.commit()
                if cur.rowcount == 0:
                    return None
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] update %s/%s/%s: %s", domain, source, record_id, exc)
                return None
            try:
                r = self._conn.execute(
                    "SELECT data, created_at, updated_at FROM records "
                    "WHERE domain=? AND source=? AND id=?",
                    (domain, source, record_id),
                ).fetchone()
            except sqlite3.OperationalError:
                r = None
        return _row(record_id, r["data"], r["created_at"], r["updated_at"]) if r else None

    def delete(self, domain: str, source: str, record_id: str) -> bool:
        """Hard-delete a record. Returns True if a row was removed."""
        with self._lock:
            try:
                cur = self._conn.execute(
                    "DELETE FROM records WHERE domain=? AND source=? AND id=?",
                    (domain, source, record_id),
                )
                self._conn.commit()
                return cur.rowcount > 0
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] delete %s/%s/%s: %s", domain, source, record_id, exc)
                return False

    def get(self, domain: str, source: str, record_id: str) -> dict | None:
        """Fetch by primary key. Returns None if not found."""
        with self._lock:
            try:
                r = self._conn.execute(
                    "SELECT data, created_at, updated_at FROM records "
                    "WHERE domain=? AND source=? AND id=?",
                    (domain, source, record_id),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] get %s/%s/%s: %s", domain, source, record_id, exc)
                return None
            return _row(record_id, r["data"], r["created_at"], r["updated_at"]) if r else None

    def list(self, domain: str, source: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """List records, newest first."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT id, data, created_at, updated_at FROM records "
                    "WHERE domain=? AND source=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (domain, source, limit, offset),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] list %s/%s: %s", domain, source, exc)
                return []
            return [_row(r["id"], r["data"], r["created_at"], r["updated_at"]) for r in rows]

    def search(self, query: str, domain: str | None = None, limit: int = 20) -> list[dict]:
        """FTS5 BM25-ranked full-text search, optionally scoped to a domain."""
        safe_query = _sanitize_fts_query(query)
        with self._lock:
            try:
                if domain:
                    rows = self._conn.execute(
                        "SELECT r.id, r.data, r.created_at, r.updated_at "
                        "FROM records_fts JOIN records r ON r.rowid = records_fts.rowid "
                        "WHERE records_fts MATCH ? AND records_fts.domain=? "
                        "ORDER BY bm25(records_fts) LIMIT ?",
                        (safe_query, domain, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT r.id, r.data, r.created_at, r.updated_at "
                        "FROM records_fts JOIN records r ON r.rowid = records_fts.rowid "
                        "WHERE records_fts MATCH ? ORDER BY bm25(records_fts) LIMIT ?",
                        (safe_query, limit),
                    ).fetchall()
            except sqlite3.OperationalError as exc:
                logger.error("[SqliteStore] search %r: %s", query, exc)
                return []
            return [_row(r["id"], r["data"], r["created_at"], r["updated_at"]) for r in rows]

    def close(self) -> None:
        """Close connection and remove from process cache."""
        with self._lock:
            conn = _connections.pop(self._db_path, None)
            if conn:
                try:
                    conn.close()
                except sqlite3.OperationalError as exc:
                    logger.error("[SqliteStore] close: %s", exc)
        # Remove the lock entry after the connection is gone so _locks doesn't grow unboundedly.
        with _locks_lock:
            _locks.pop(self._db_path, None)


if __name__ == "__main__":
    import os, tempfile

    with tempfile.TemporaryDirectory() as tmp:
        s = SqliteStore(os.path.join(tmp, "test.db"))
        r = s.create("wicked-mem", "memories", "id-001", {"title": "Deploy", "content": "Use WAL"})
        assert r["id"] == "id-001" and r["title"] == "Deploy", f"create: {r}"
        assert s.create("wicked-mem", "memories", "id-001", {"title": "X"})["title"] == "Deploy"
        assert s.get("wicked-mem", "memories", "id-001")["title"] == "Deploy"
        s.create("wicked-mem", "memories", "id-002", {"title": "Second", "content": "other"})
        assert len(s.list("wicked-mem", "memories")) == 2
        hits = s.search("WAL", domain="wicked-mem")
        assert hits and hits[0]["id"] == "id-001", f"search miss: {hits}"
        u = s.update("wicked-mem", "memories", "id-001", {"title": "v2", "content": "updated"})
        assert u and u["title"] == "v2"
        assert s.delete("wicked-mem", "memories", "id-001") is True
        assert s.get("wicked-mem", "memories", "id-001") is None

        # Issue #178: hyphenated tags must not cause FTS5 tokenization errors
        s.create("wicked-mem", "memories", "id-hyp", {
            "title": "Hyphen test",
            "content": "tags: wicked-garden code-review",
            "tags": ["wicked-garden", "code-review"],
        })
        hits = s.search("wicked-garden", domain="wicked-mem")
        assert hits and hits[0]["id"] == "id-hyp", f"hyphenated search miss: {hits}"
        hits = s.search("code-review", domain="wicked-mem")
        assert hits and hits[0]["id"] == "id-hyp", f"hyphenated search miss: {hits}"
        # Also test mixed: hyphenated + normal term
        hits = s.search("wicked-garden test", domain="wicked-mem")
        assert any(h["id"] == "id-hyp" for h in hits), f"mixed search miss: {hits}"

        # Verify _sanitize_fts_query edge cases
        assert _sanitize_fts_query("wicked-garden") == '"wicked-garden"'
        assert _sanitize_fts_query("plain search") == "plain search"
        assert _sanitize_fts_query('"already-quoted"') == '"already-quoted"'
        assert _sanitize_fts_query("code-review deployment") == '"code-review" deployment'
        assert _sanitize_fts_query("") == ""

        s.close()
    print("All smoke tests passed.")
