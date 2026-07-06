"""
projector.py — State projector for the wicked-garden daemon.

Maintains a projection of the garden's current state — installed skills, active
sessions, daemon health — by applying incoming events to a key-value store
backed by the ``projector_state`` SQLite table. Values are serialised as JSON.

Event handlers are registered by event-type prefix. The projector is designed
to be called from the EventConsumer callback on the consumer thread; all methods
acquire a threading.Lock so they are safe to call from multiple threads.

Usage::

    from daemon.projector import Projector

    projector = Projector(conn)
    projector.update("wicked.garden.skill.installed", {"skill": "my-skill"})
    state = projector.snapshot()
    val   = projector.get("daemon.health", default="unknown")
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any, Optional

from daemon._internal import now_iso

logger = logging.getLogger("wicked-garden.daemon.projector")

# ---------------------------------------------------------------------------
# Built-in projector key names
# ---------------------------------------------------------------------------

_KEY_HEALTH = "daemon.health"
_KEY_INSTALLED_SKILLS = "garden.installed_skills"
_KEY_ACTIVE_SESSIONS = "garden.active_sessions"
_KEY_EVENT_COUNT = "daemon.event_count"
_KEY_LAST_EVENT = "daemon.last_event"
_KEY_LAST_EVENT_AT = "daemon.last_event_at"


class Projector:
    """Applies events to a persistent key-value state.

    All state is stored in the ``projector_state`` SQLite table so it survives
    daemon restarts.

    Args:
        db_conn: Open sqlite3 connection (check_same_thread=False).
    """

    def __init__(self, db_conn: sqlite3.Connection) -> None:
        self._conn = db_conn
        self._lock = threading.Lock()
        self._init_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, event_type: str, payload: dict[str, Any]) -> None:
        """Apply an event to the projected state.

        Dispatches to a type-specific handler if one is registered, then
        always updates the generic ``daemon.event_count`` and ``daemon.last_event``
        keys.

        Args:
            event_type: The event type string.
            payload: The event payload dict.
        """
        with self._lock:
            self._dispatch(event_type, payload)
            self._increment_event_count()
            self._set(_KEY_LAST_EVENT, event_type)
            self._set(_KEY_LAST_EVENT_AT, now_iso())

    def snapshot(self) -> dict[str, Any]:
        """Return the current projected state as a plain dict.

        Deserialises JSON values. Returns an empty dict if the table is empty.
        """
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT key, value FROM projector_state"
                ).fetchall()
            except Exception as exc:  # noqa: BLE001
                logger.error("projector snapshot failed: %s", exc)
                return {}

            result: dict[str, Any] = {}
            for row in rows:
                try:
                    result[row["key"]] = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    result[row["key"]] = row["value"]
            return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific state value.

        Args:
            key: The projector state key.
            default: Returned when the key does not exist.

        Returns:
            Deserialised JSON value, or ``default`` if not found.
        """
        with self._lock:
            return self._get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Explicitly set a state value (for external callers).

        Args:
            key: The state key.
            value: Any JSON-serialisable value.
        """
        with self._lock:
            self._set(key, value)

    # ------------------------------------------------------------------
    # Internal state helpers (caller must hold self._lock)
    # ------------------------------------------------------------------

    def _get(self, key: str, default: Any = None) -> Any:
        try:
            row = self._conn.execute(
                "SELECT value FROM projector_state WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return default
            return json.loads(row["value"])
        except Exception:  # noqa: BLE001
            return default

    def _set(self, key: str, value: Any) -> None:
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO projector_state (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(value, default=str), now_iso()),
            )
            self._conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("projector _set(%r) failed: %s", key, exc)

    def _increment_event_count(self) -> None:
        current = self._get(_KEY_EVENT_COUNT, 0)
        try:
            current = int(current)
        except (ValueError, TypeError):
            current = 0
        self._set(_KEY_EVENT_COUNT, current + 1)

    def _init_defaults(self) -> None:
        """Set initial state keys if they are not already present."""
        with self._lock:
            if self._get(_KEY_HEALTH) is None:
                self._set(_KEY_HEALTH, "starting")
            if self._get(_KEY_INSTALLED_SKILLS) is None:
                self._set(_KEY_INSTALLED_SKILLS, [])
            if self._get(_KEY_ACTIVE_SESSIONS) is None:
                self._set(_KEY_ACTIVE_SESSIONS, [])
            if self._get(_KEY_EVENT_COUNT) is None:
                self._set(_KEY_EVENT_COUNT, 0)
            # Mark daemon as healthy once defaults are written
            self._set(_KEY_HEALTH, "ok")

    # ------------------------------------------------------------------
    # Event-type handlers (called inside self._lock)
    # ------------------------------------------------------------------

    def _dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        """Dispatch to a typed handler if one matches."""
        handlers = {
            "wicked.garden.skill.installed": self._on_skill_installed,
            "wicked.garden.skill.removed": self._on_skill_removed,
            "wicked.session.started": self._on_session_started,
            "wicked.session.synthesized": self._on_session_completed,
            "wicked.council.voted": self._on_session_completed,
        }
        handler = handlers.get(event_type)
        if handler:
            try:
                handler(payload)
            except Exception as exc:  # noqa: BLE001
                logger.error("Projector handler for %s raised: %s", event_type, exc, exc_info=True)

    def _on_skill_installed(self, payload: dict[str, Any]) -> None:
        skill_name = payload.get("skill") or payload.get("name")
        if not skill_name:
            return
        skills = list(self._get(_KEY_INSTALLED_SKILLS, []))
        if skill_name not in skills:
            skills.append(skill_name)
            self._set(_KEY_INSTALLED_SKILLS, skills)

    def _on_skill_removed(self, payload: dict[str, Any]) -> None:
        skill_name = payload.get("skill") or payload.get("name")
        if not skill_name:
            return
        skills = list(self._get(_KEY_INSTALLED_SKILLS, []))
        if skill_name in skills:
            skills.remove(skill_name)
            self._set(_KEY_INSTALLED_SKILLS, skills)

    def _on_session_started(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id")
        if not session_id:
            return
        sessions = list(self._get(_KEY_ACTIVE_SESSIONS, []))
        if session_id not in sessions:
            sessions.append(session_id)
            self._set(_KEY_ACTIVE_SESSIONS, sessions)

    def _on_session_completed(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id")
        if not session_id:
            return
        sessions = list(self._get(_KEY_ACTIVE_SESSIONS, []))
        if session_id in sessions:
            sessions.remove(session_id)
            self._set(_KEY_ACTIVE_SESSIONS, sessions)
