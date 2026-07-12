"""
consumer.py — Bus event consumer for the wicked-garden daemon.

Polls wicked-bus for new events matching ``wicked.garden.*`` (and related
garden-relevant event prefixes) on a configurable interval, stores them in the
``garden_events`` table, and dispatches them to a caller-supplied callback.

Graceful degradation: if the bus is unavailable or a poll fails, the error is
logged and the consumer continues — it never crashes the daemon.

Usage::

    from daemon.consumer import EventConsumer

    def on_event(event_type: str, payload: dict) -> None:
        print(event_type, payload)

    consumer = EventConsumer(db_conn, on_event=on_event)
    consumer.start()
    # ... later ...
    consumer.stop()
"""
from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import threading
import time
from typing import Any, Callable, Optional

from daemon._internal import generate_id, now_iso
from daemon.db import get_write_lock

logger = logging.getLogger("wicked-garden.daemon.consumer")

# Event type prefixes the daemon cares about.
# Post 4-seg migration every garden-owned event (including the former
# wicked.hitl.* and wicked.session.* families, and council) is namespaced
# under "wicked.garden.*", so a single prefix covers them all. Self-emitted
# "wicked.garden.council.voted" is filtered out in _store_event to avoid a
# council feedback loop.
_WATCH_PREFIXES = (
    "wicked.garden.",
)

# Maximum events to fetch per poll call.
_PAGE_SIZE = 100

# Timeout for each bus query subprocess call (seconds).
_QUERY_TIMEOUT_S = 10


class EventConsumer:
    """Polls wicked-bus for garden-relevant events and dispatches them.

    Thread-safety: ``start()`` spawns a single daemon thread. ``stop()`` sets a
    threading.Event that the thread checks between polls, so it terminates
    cleanly on the next cycle.

    Args:
        db_conn: Open sqlite3 connection (check_same_thread=False).
        poll_interval_ms: Milliseconds between bus polls. Default 5000.
        on_event: Optional callback invoked for each new event after it is
                  stored. Signature: ``(event_type: str, payload: dict) -> None``.
                  Exceptions raised by the callback are caught and logged.
    """

    def __init__(
        self,
        db_conn: sqlite3.Connection,
        poll_interval_ms: int = 5000,
        on_event: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        self._conn = db_conn
        self._interval_s = poll_interval_ms / 1000.0
        self._on_event = on_event
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cursor: Optional[str] = self._load_cursor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start polling in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("EventConsumer.start() called while already running; ignoring")
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="garden-consumer",
            daemon=True,
        )
        self._thread.start()
        logger.info("EventConsumer started (interval=%.1fs)", self._interval_s)

    def stop(self) -> None:
        """Signal the consumer thread to stop after the current poll cycle."""
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=self._interval_s + _QUERY_TIMEOUT_S + 2)
        logger.info("EventConsumer stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Main polling loop — runs in the background thread."""
        while not self._stop_flag.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                logger.error("EventConsumer poll error (continuing): %s", exc, exc_info=True)
            self._stop_flag.wait(timeout=self._interval_s)

    def _poll_once(self) -> None:
        """Poll wicked-bus for new events since the last cursor.

        Calls::

            npx wicked-bus query --type "wicked.garden.*" --since <cursor> --json

        On error, logs and returns — never raises so the caller loop continues.
        """
        cmd = [
            "npx",
            "wicked-bus",
            "query",
            "--json",
            "--limit", str(_PAGE_SIZE),
        ]
        if self._cursor:
            cmd.extend(["--since", self._cursor])

        # Query for each watched prefix
        for prefix in _WATCH_PREFIXES:
            self._query_prefix(prefix, cmd)

    def _query_prefix(self, prefix: str, base_cmd: list[str]) -> None:
        """Run a single bus query for one event prefix and store results."""
        cmd = base_cmd + ["--type", prefix]
        try:
            result = subprocess.run(
                cmd,
                timeout=_QUERY_TIMEOUT_S,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            logger.debug("npx not found — wicked-bus unavailable; skipping poll")
            return
        except subprocess.TimeoutExpired:
            logger.warning("wicked-bus query timed out for prefix %s", prefix)
            return

        if result.returncode != 0:
            logger.debug("wicked-bus query returned %d for prefix %s", result.returncode, prefix)
            return

        stdout = result.stdout.strip()
        if not stdout:
            return

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse wicked-bus query output: %s", exc)
            return

        events = data if isinstance(data, list) else data.get("events", [])
        for raw_event in events:
            self._store_event(raw_event)

    def _store_event(self, raw_event: dict[str, Any]) -> None:
        """Persist a raw bus event and dispatch it to the callback."""
        event_type = raw_event.get("type", "")

        # Self-consumption prevention: skip events emitted by this daemon to
        # avoid feedback loops (e.g. wicked.garden.council.voted re-triggering
        # council sessions).
        if event_type == "wicked.garden.council.voted":
            logger.debug("Skipping self-emitted event: %s", event_type)
            return

        payload_raw = raw_event.get("payload", {})
        payload = payload_raw if isinstance(payload_raw, dict) else {}
        event_id = raw_event.get("id") or generate_id()
        received_at = now_iso()

        try:
            with get_write_lock():
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO garden_events
                        (id, event_type, payload, received_at, processed)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (event_id, event_type, json.dumps(payload), received_at),
                )
                self._conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to store event %s: %s", event_id, exc)
            return

        # Advance cursor to this event's ID so we don't re-fetch it.
        self._cursor = event_id
        self._save_cursor(event_id)

        if self._on_event:
            try:
                self._on_event(event_type, payload)
            except Exception as exc:  # noqa: BLE001
                logger.error("on_event callback raised for %s: %s", event_type, exc, exc_info=True)

    # ------------------------------------------------------------------
    # Cursor persistence (stored in projector_state table)
    # ------------------------------------------------------------------

    def _load_cursor(self) -> Optional[str]:
        """Load the last-seen event cursor from projector_state."""
        try:
            row = self._conn.execute(
                "SELECT value FROM projector_state WHERE key = 'consumer.cursor'"
            ).fetchone()
            if row:
                return json.loads(row["value"])
        except Exception:  # noqa: BLE001
            pass
        return None

    def _save_cursor(self, cursor: str) -> None:
        """Persist the cursor to projector_state."""
        try:
            with get_write_lock():
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO projector_state (key, value, updated_at)
                    VALUES ('consumer.cursor', ?, ?)
                    """,
                    (json.dumps(cursor), now_iso()),
                )
                self._conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to save consumer cursor: %s", exc)
