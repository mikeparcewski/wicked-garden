"""daemon/consumer.py — Bus event consumer (cursor-poll, restart-safe)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
from typing import Callable, Optional

import daemon.db as db
import daemon.projector as projector

# ---------------------------------------------------------------------------
# Constants — R3: no magic values
# ---------------------------------------------------------------------------
_BUS_SOURCE: str = "wicked-bus"
_DEFAULT_POLL_INTERVAL_MS: int = 1_000
_BACKOFF_INITIAL_S: float = 1.0
_BACKOFF_MAX_S: float = 30.0
_BACKOFF_FACTOR: float = 2.0
_REGISTER_TIMEOUT_S: int = 10
_REPLAY_TIMEOUT_S: int = 15
_ACK_TIMEOUT_S: int = 10
_BUS_CMD: str = "npx"
_BUS_FILTER: str = "wicked.*"
_STATUS_APPLIED: str = "applied"
_STATUS_IGNORED: str = "ignored"
_STATUS_ERROR: str = "error"

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _env_poll_interval_ms() -> int:
    raw = os.environ.get("WG_DAEMON_POLL_INTERVAL_MS", "").strip()
    return int(raw) if raw.isdigit() else _DEFAULT_POLL_INTERVAL_MS


def _register_cursor() -> Optional[str]:
    """Register a new wicked-bus cursor. Returns cursor_id or None on failure."""
    cmd = [_BUS_CMD, "wicked-bus", "register", "--filter", _BUS_FILTER, "--json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_REGISTER_TIMEOUT_S
        )
        if result.returncode != 0:
            _log.warning("wicked-bus register failed (rc=%d): %s",
                         result.returncode, result.stderr.strip())
            return None
        data = json.loads(result.stdout.strip())
        cursor_id: Optional[str] = data.get("cursor_id") or data.get("id")
        if not cursor_id:
            _log.warning("wicked-bus register returned no cursor_id: %s", data)
        return cursor_id
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        _log.warning("wicked-bus register error: %s", exc)
        return None


def _replay_events(cursor_id: str, from_event_id: int) -> Optional[list[dict]]:
    """Replay events since from_event_id. Returns list or None on bus failure."""
    cmd = [
        _BUS_CMD, "wicked-bus", "replay",
        "--cursor-id", cursor_id,
        "--from-event-id", str(from_event_id),
        "--json",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_REPLAY_TIMEOUT_S
        )
        if result.returncode != 0:
            _log.warning("wicked-bus replay failed (rc=%d): %s",
                         result.returncode, result.stderr.strip())
            return None
        raw = result.stdout.strip()
        if not raw:
            return []
        if raw.startswith("["):
            return json.loads(raw)
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return events
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        _log.warning("wicked-bus replay error: %s", exc)
        return None


def _ack_cursor(cursor_id: str, last_event_id: int) -> bool:
    """Ack processed events to the bus. Returns True on success."""
    cmd = [
        _BUS_CMD, "wicked-bus", "ack",
        "--cursor-id", cursor_id,
        "--last-event-id", str(last_event_id),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_ACK_TIMEOUT_S
        )
        if result.returncode != 0:
            _log.warning("wicked-bus ack failed (rc=%d): %s",
                         result.returncode, result.stderr.strip())
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        _log.warning("wicked-bus ack error: %s", exc)
        return False


def _backoff_sleep(attempt: int, stop_event: threading.Event) -> None:
    delay = min(_BACKOFF_INITIAL_S * (_BACKOFF_FACTOR ** attempt), _BACKOFF_MAX_S)
    _log.debug("Backoff %.1fs (attempt %d)", delay, attempt)
    stop_event.wait(timeout=delay)


# ---------------------------------------------------------------------------
# Public: process_batch
# ---------------------------------------------------------------------------

def process_batch(
    conn: sqlite3.Connection,
    events: list[dict],
) -> tuple[int, int, int]:
    """Project each event and write to event_log.

    Decision #6: never skip events on retry — re-fire is safe (idempotent projector).
    Decision #8: unknown events still advance the cursor; project_event returns
    'ignored' for unknown types and we treat that as success.

    Returns (applied, ignored, errored).
    """
    applied = ignored = errored = 0

    for event in events:
        event_id: int = event.get("event_id", 0)
        event_type: str = event.get("event_type", "")
        chain_id: Optional[str] = event.get("chain_id")
        payload: dict = event.get("payload", {})
        error_message: Optional[str] = None
        status: str = _STATUS_ERROR

        try:
            status = projector.project_event(conn, event)
        except Exception as exc:  # noqa: BLE001 — log and record, never swallow
            error_message = str(exc)
            _log.error("project_event raised for event_id=%d type=%s: %s",
                       event_id, event_type, exc)

        if status == _STATUS_APPLIED:
            applied += 1
        elif status == _STATUS_IGNORED:
            ignored += 1
        else:
            errored += 1

        try:
            db.append_event_log(
                conn,
                event_id=event_id,
                event_type=event_type,
                chain_id=chain_id,
                payload=payload,
                projection_status=status,
                error_message=error_message,
            )
        except Exception as exc:  # noqa: BLE001
            _log.error("append_event_log failed for event_id=%d: %s", event_id, exc)

    _log.debug("process_batch: %d events → applied=%d ignored=%d errored=%d",
               len(events), applied, ignored, errored)
    return applied, ignored, errored


# ---------------------------------------------------------------------------
# Public: cursor_lag
# ---------------------------------------------------------------------------

def cursor_lag(conn: sqlite3.Connection) -> int:
    """Return max_known_event_id - cursor.last_event_id, or -1 if bus unavailable.

    Decision #4: -1 when the bus cannot be reached.

    TODO(v8-pr1-followup): 'wicked-bus head' subcommand does not exist in the
    current wicked-bus release (coordination item #6, #589).  The subprocess
    call below will always fail and return -1.  Once wicked-bus exposes 'head',
    this function will compute accurate lag.  /health returns -1 until then.
    """
    row = db.get_cursor(conn, _BUS_SOURCE)
    if not row or not row.get("cursor_id"):
        return -1

    last_known: int = row.get("last_event_id", 0)
    cursor_id: str = row["cursor_id"]
    cmd = [_BUS_CMD, "wicked-bus", "head", "--cursor-id", cursor_id, "--json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_ACK_TIMEOUT_S
        )
        if result.returncode != 0:
            return -1
        data = json.loads(result.stdout.strip())
        max_id: int = data.get("last_event_id", data.get("event_id", last_known))
        return max(0, max_id - last_known)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError):
        return -1


# ---------------------------------------------------------------------------
# ConsumerThread
# ---------------------------------------------------------------------------

class ConsumerThread(threading.Thread):
    """Background thread: polls wicked-bus, projects events, persists cursor.

    One SQLite connection per thread — caller supplies a factory so the thread
    creates its own connection (sqlite3 connections are not thread-safe).
    """

    def __init__(
        self,
        conn_factory: Callable[[], sqlite3.Connection],
        stop_event: threading.Event,
        poll_interval_ms: int = _DEFAULT_POLL_INTERVAL_MS,
    ) -> None:
        super().__init__(name="wg-daemon-consumer", daemon=True)
        self._conn_factory = conn_factory
        self._stop_event = stop_event
        self._poll_interval_ms = poll_interval_ms
        self._cursor_id: Optional[str] = None
        self._last_event_id: int = 0
        self._connected: bool = False

    def _init_cursor(self, conn: sqlite3.Connection) -> bool:
        """Load persisted cursor or register fresh. Returns True when ready."""
        row = db.get_cursor(conn, _BUS_SOURCE)
        if row and row.get("cursor_id"):
            self._cursor_id = row["cursor_id"]
            self._last_event_id = row.get("last_event_id", 0)
            _log.info("Resumed cursor %s at event_id=%d",
                      self._cursor_id, self._last_event_id)
            return True
        cursor_id = _register_cursor()
        if not cursor_id:
            return False
        self._cursor_id = cursor_id
        self._last_event_id = 0
        db.set_cursor(conn, _BUS_SOURCE, cursor_id, 0)
        _log.info("Registered new cursor %s", cursor_id)
        return True

    def run(self) -> None:  # noqa: C901
        """Poll loop — runs until stop_event is set."""
        _log.info("ConsumerThread starting (poll_interval=%dms)", self._poll_interval_ms)
        conn: Optional[sqlite3.Connection] = None
        backoff_attempt: int = 0

        try:
            conn = self._conn_factory()

            while not self._stop_event.is_set():
                # Ensure we have a valid cursor before replaying
                if self._cursor_id is None:
                    if not self._init_cursor(conn):
                        self._connected = False
                        _log.warning("Bus unavailable during cursor init; backing off")
                        _backoff_sleep(backoff_attempt, self._stop_event)
                        backoff_attempt = min(backoff_attempt + 1, 10)
                        continue
                    backoff_attempt = 0

                assert self._cursor_id is not None  # type narrowing
                events = _replay_events(self._cursor_id, self._last_event_id + 1)

                if events is None:
                    self._connected = False
                    _log.warning("Bus unavailable on replay (cursor=%s); backing off",
                                 self._cursor_id)
                    _backoff_sleep(backoff_attempt, self._stop_event)
                    backoff_attempt = min(backoff_attempt + 1, 10)
                    continue

                self._connected = True
                backoff_attempt = 0

                if events:
                    applied, ignored, errored = process_batch(conn, events)
                    max_id = max(e.get("event_id", 0) for e in events)

                    # Persist cursor BEFORE ack — crash recovery gives at-least-once
                    # redelivery, which is safe because the projector is idempotent.
                    # db.set_cursor already commits internally; no extra commit needed.
                    db.set_cursor(conn, _BUS_SOURCE, self._cursor_id, max_id)
                    self._last_event_id = max_id

                    if not _ack_cursor(self._cursor_id, max_id):
                        _log.warning("ack failed for cursor=%s last_event_id=%d",
                                     self._cursor_id, max_id)

                    _log.info(
                        "Batch: events=%d applied=%d ignored=%d errored=%d cursor=%d",
                        len(events), applied, ignored, errored, max_id,
                    )

                self._stop_event.wait(timeout=self._poll_interval_ms / 1_000.0)

        except Exception as exc:  # noqa: BLE001 — log, propagate to thread runner
            _log.error("ConsumerThread fatal: %s", exc, exc_info=True)
            raise
        finally:
            self._connected = False
            if conn is not None:
                try:
                    conn.close()
                except Exception as close_exc:  # noqa: BLE001
                    _log.debug("Error closing consumer connection: %s", close_exc)
            _log.info("ConsumerThread stopped")

    @property
    def is_connected(self) -> bool:
        """True when the last replay call succeeded (bus reachable)."""
        return self._connected


# ---------------------------------------------------------------------------
# Module-level convenience launcher
# ---------------------------------------------------------------------------

def start(
    stop_event: threading.Event,
    db_path: Optional[str] = None,
    poll_interval_ms: Optional[int] = None,
) -> ConsumerThread:
    """Create and start a ConsumerThread.

    stop_event: set to trigger clean shutdown.
    db_path: override DB path; falls back to WG_DAEMON_DB / default.
    poll_interval_ms: override poll interval; falls back to env / 1000 ms.
    """
    interval = poll_interval_ms if poll_interval_ms is not None else _env_poll_interval_ms()

    def _factory() -> sqlite3.Connection:
        return db.connect(db_path)

    thread = ConsumerThread(
        conn_factory=_factory,
        stop_event=stop_event,
        poll_interval_ms=interval,
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# __main__ — standalone debug harness
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import signal

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    _stop = threading.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        _log.info("Signal %d received — stopping", sig)
        _stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _log.info("Starting consumer standalone (Ctrl-C to stop)")
    _thread = start(_stop)
    _thread.join()
    _log.info("Done")
