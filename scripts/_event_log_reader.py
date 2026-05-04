"""Event-log reader helpers for bus-as-truth reads (Scope B, #746).

Post-cutover, the bus event_log is the canonical source of truth for
artifact data.  These helpers replace on-disk reads for sites where
the projector has a handler that materialises the file from bus events.

Design constraints
------------------
- **Fail-open**: sqlite errors return None / [] — never raise.  Callers
  always fall back to on-disk reads for pre-cutover projects.
- **No daemon import**: the helpers accept an open ``sqlite3.Connection``
  so the caller controls the DB lifetime (mirrors the pattern in
  ``scripts/crew/reconcile_v2.py::_get_projector_last_applied_seq``).
- **Lightweight**: stdlib only — no third-party deps.

Usage
-----
Typical call in a reader that previously read from disk::

    from _event_log_reader import read_latest_event_data
    # fast path — bus is source of truth
    data = read_latest_event_data(conn, project_id=..., phase=...,
                                  event_type="wicked.gate.decided")
    if data is None:
        # disk fallback for legacy projects pre-cutover
        data = _load_from_disk(...)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _escape_like(value: str) -> str:
    """Escape LIKE special chars for SQLite (mirrors reconcile_v2 pattern)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_latest_event_data(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    phase: str,
    event_type: str,
) -> Optional[Dict[str, Any]]:
    """Return ``payload['data']`` from the most recent matching event.

    Filters ``event_log`` by::

        chain_id LIKE '{project_id}.{phase}%'  AND  event_type = ?

    Returns the highest-``event_id`` match's ``payload['data']``.  Returns
    ``None`` when:
      - no matching rows exist
      - ``payload['data']`` is absent
      - ``payload['data']`` is not a ``dict``
      - ``payload_json`` is malformed JSON
      - any sqlite error occurs (fail-open)

    Used by readers that previously loaded from disk — bus is the source
    of truth post-cutover so reads come from event_log.
    """
    escaped = _escape_like(project_id)
    prefix = f"{escaped}.{_escape_like(phase)}"
    try:
        row = conn.execute(
            """
            SELECT payload_json
            FROM   event_log
            WHERE  chain_id LIKE ? ESCAPE '\\'
              AND  event_type = ?
            ORDER  BY event_id DESC
            LIMIT  1
            """,
            (f"{prefix}%", event_type),
        ).fetchone()
    except sqlite3.Error:
        return None

    if row is None:
        return None

    payload_json = row[0]
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    return data


def read_event_appends(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    phase: str,
    event_type: str,
) -> List[str]:
    """Return ``raw_payload`` lines from ALL matching events in event_id order.

    For JSONL append-stream artifacts (dispatch-log etc.).  Each element is
    the original ``raw_payload`` string from the event payload (newline-
    stripped).  An empty list is returned when:
      - no matching rows exist
      - any sqlite error occurs (fail-open)

    Rows whose ``payload_json`` does not contain a string ``raw_payload``
    field are silently skipped — the caller sees only well-formed entries.
    """
    escaped = _escape_like(project_id)
    prefix = f"{escaped}.{_escape_like(phase)}"
    try:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM   event_log
            WHERE  chain_id LIKE ? ESCAPE '\\'
              AND  event_type = ?
            ORDER  BY event_id ASC
            """,
            (f"{prefix}%", event_type),
        ).fetchall()
    except sqlite3.Error:
        return []

    out: List[str] = []
    for row in rows:
        payload_json = row[0]
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get("raw_payload")
        if isinstance(raw, str):
            out.append(raw.rstrip("\n"))
    return out
