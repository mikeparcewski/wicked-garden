"""
daemon/server.py — Read-only HTTP projection server for wicked-garden v8 daemon.

Exposes 5 GET endpoints backed by the SQLite projection DB (daemon/db.py).
Defaults to 127.0.0.1 per locked decision #10; WG_DAEMON_HOST can override but
is documented as not encouraged. Default port 4244.

Public API
----------
ProjectionRequestHandler  — BaseHTTPRequestHandler subclass; implements do_GET.
make_server(host, port, db_path) -> ThreadingHTTPServer
run(host, port, db_path) -> int  — blocking entrypoint, returns exit code.
"""

from __future__ import annotations

import http.server
import json
import logging
import os
import signal
import traceback
import urllib.parse
from typing import Any

import daemon.consumer as consumer
import daemon.db as db
from daemon import VERSION as DAEMON_VERSION

# ---------------------------------------------------------------------------
# Constants (R3: no magic values)
# ---------------------------------------------------------------------------
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 4244

CONTENT_TYPE_JSON: str = "application/json; charset=utf-8"

PROJECTS_LIMIT_DEFAULT: int = 100
PROJECTS_LIMIT_MAX: int = 500
EVENTS_LIMIT_DEFAULT: int = 100
EVENTS_LIMIT_MAX: int = 1000
# Stream 1 — #596 v8-PR-2: /tasks endpoint limits
TASKS_LIMIT_DEFAULT: int = 200
TASKS_LIMIT_MAX: int = 500

ENV_HOST: str = "WG_DAEMON_HOST"
ENV_PORT: str = "WG_DAEMON_PORT"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class ProjectionRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the wicked-garden projection daemon.

    Routes GET requests to per-endpoint helper methods.  Never logs request
    bodies (there are none — all endpoints are read-only GET).
    """

    # db_path is injected by make_server via a subclass; default None means
    # the handler opens the DB using the env / default path on every request.
    db_path: str | None = None

    # ------------------------------------------------------------------ #
    # BaseHTTPRequestHandler overrides
    # ------------------------------------------------------------------ #

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        """Route access log through stdlib logging instead of stderr."""
        logger.debug("HTTP %s", fmt % args)

    def do_GET(self) -> None:  # noqa: D102
        """Dispatch incoming GET requests to endpoint helpers."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)

        try:
            if path == "/health":
                self._handle_health(query)
            elif path == "/projects":
                self._handle_list_projects(query)
            elif path.startswith("/projects/"):
                tail = path[len("/projects/"):]
                if "/" not in tail:
                    self._handle_get_project(tail, query)
                elif tail.endswith("/phases"):
                    project_id = tail[: -len("/phases")]
                    self._handle_list_phases(project_id, query)
                else:
                    self._send_not_found("Unknown endpoint")
            elif path == "/events":
                self._handle_list_events(query)
            elif path == "/tasks":
                # Stream 1 — #596 v8-PR-2: task list endpoint
                self._handle_list_tasks(query)
            elif path.startswith("/tasks/"):
                task_id = path[len("/tasks/"):]
                if task_id and "/" not in task_id:
                    self._handle_get_task(task_id, query)
                else:
                    self._send_not_found("Unknown endpoint")
            else:
                self._send_not_found("Unknown endpoint")
        except Exception:
            logger.error("Unhandled exception in do_GET:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")

    # ------------------------------------------------------------------ #
    # Endpoint helpers
    # ------------------------------------------------------------------ #

    def _handle_health(self, _query: dict[str, list[str]]) -> None:
        """GET /health — liveness + cursor lag.

        cursor_lag delegates to consumer.cursor_lag(conn) which is a pure,
        stateless module function (no thread state) — safe to call from the
        server's read path per coordination item #2 (#589).
        """
        conn = None
        try:
            conn = db.connect(self.db_path)
            lag: int = consumer.cursor_lag(conn)
            db_path_used: str = conn.execute("PRAGMA database_list").fetchone()[2]
            self._send_json(200, {
                "ok": True,
                "cursor_lag": lag,
                "version": DAEMON_VERSION,
                "db_path": db_path_used,
            })
        except Exception:
            logger.error("Health check DB failure:\n%s", traceback.format_exc())
            self._send_json(503, {"ok": False, "error": "DB unreachable"})
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_projects(self, query: dict[str, list[str]]) -> None:
        """GET /projects[?status=...&limit=N]."""
        try:
            status_filter, limit = self._parse_projects_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = db.list_projects(conn, status=status_filter, limit=limit)
            self._send_json(200, [_project_list_shape(r) for r in rows])
        except Exception:
            logger.error("list_projects DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_get_project(self, project_id: str, _query: dict[str, list[str]]) -> None:
        """GET /projects/{id}."""
        if not project_id:
            self._send_error(400, "Missing project id")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            row = db.get_project(conn, project_id)
            if row is None:
                self._send_not_found(f"Project '{project_id}' not found")
                return
            self._send_json(200, _project_detail_shape(row))
        except Exception:
            logger.error("get_project DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_phases(self, project_id: str, _query: dict[str, list[str]]) -> None:
        """GET /projects/{id}/phases."""
        if not project_id:
            self._send_error(400, "Missing project id")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            # Verify project exists (404 semantics per contract)
            project_row = db.get_project(conn, project_id)
            if project_row is None:
                self._send_not_found(f"Project '{project_id}' not found")
                return
            rows = db.list_phases(conn, project_id)
            self._send_json(200, [_phase_shape(r) for r in rows])
        except Exception:
            logger.error("list_phases DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_events(self, query: dict[str, list[str]]) -> None:
        """GET /events[?since=N&limit=N&event_type=prefix]."""
        try:
            since, limit, event_type_prefix = self._parse_events_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = db.list_events(conn, since=since, limit=limit, event_type_prefix=event_type_prefix)
            self._send_json(200, [_event_shape(r) for r in rows])
        except Exception:
            logger.error("list_events DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_tasks(self, query: dict[str, list[str]]) -> None:
        """GET /tasks[?session=<id>&status=<filter>&chain_id=<filter>].

        Stream 1 — #596 v8-PR-2.  READ-ONLY — daemon never writes task state;
        projection comes from wicked.task.* bus events.
        """
        try:
            session_id, status_filter, chain_id_filter, limit = self._parse_tasks_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = db.list_tasks(
                conn,
                session_id=session_id,
                status_filter=status_filter,
                chain_id_filter=chain_id_filter,
                limit=limit,
            )
            self._send_json(200, [_task_shape(r) for r in rows])
        except Exception:
            logger.error("list_tasks DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_get_task(self, task_id: str, _query: dict[str, list[str]]) -> None:
        """GET /tasks/<task_id>.

        Stream 1 — #596 v8-PR-2.  Returns the single task projection row,
        or 404 if the task has not been projected yet.
        """
        if not task_id:
            self._send_error(400, "Missing task id")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            row = db.get_task(conn, task_id)
            if row is None:
                self._send_not_found(f"Task '{task_id}' not found")
                return
            self._send_json(200, _task_shape(row))
        except Exception:
            logger.error("get_task DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------ #
    # Query-param parsers (raise ValueError on bad input → 400)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_projects_query(
        query: dict[str, list[str]],
    ) -> tuple[str | None, int]:
        """Parse and validate /projects query params.

        Returns (status_filter, limit).
        Raises ValueError for invalid values.
        """
        valid_statuses = {"active", "completed", "archived"}
        status_filter: str | None = None
        if "status" in query:
            raw = query["status"][0]
            if raw not in valid_statuses:
                raise ValueError(
                    f"Invalid status '{raw}'; must be one of: {', '.join(sorted(valid_statuses))}"
                )
            status_filter = raw

        limit = PROJECTS_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > PROJECTS_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {PROJECTS_LIMIT_MAX}; got {limit}"
                )

        return status_filter, limit

    @staticmethod
    def _parse_events_query(
        query: dict[str, list[str]],
    ) -> tuple[int, int, str | None]:
        """Parse and validate /events query params.

        Returns (since, limit, event_type_prefix).
        Raises ValueError for invalid values.
        """
        since = 0
        if "since" in query:
            raw = query["since"][0]
            if not raw.lstrip("-").isdigit():
                raise ValueError(f"Invalid since '{raw}'; must be an integer event_id")
            since = int(raw)
            if since < 0:
                raise ValueError(f"since must be >= 0; got {since}")

        limit = EVENTS_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > EVENTS_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {EVENTS_LIMIT_MAX}; got {limit}"
                )

        event_type_prefix: str | None = None
        if "event_type" in query:
            event_type_prefix = query["event_type"][0]

        return since, limit, event_type_prefix

    @staticmethod
    def _parse_tasks_query(
        query: dict[str, list[str]],
    ) -> tuple[str | None, str | None, str | None, int]:
        """Parse and validate /tasks query params.

        Returns (session_id, status_filter, chain_id_filter, limit).
        Raises ValueError for invalid values.
        """
        _VALID_STATUSES = frozenset({"pending", "in_progress", "completed"})

        session_id: str | None = query["session"][0] if "session" in query else None

        status_filter: str | None = None
        if "status" in query:
            raw = query["status"][0]
            if raw not in _VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{raw}'; must be one of: {', '.join(sorted(_VALID_STATUSES))}"
                )
            status_filter = raw

        chain_id_filter: str | None = query["chain_id"][0] if "chain_id" in query else None

        limit = TASKS_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > TASKS_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {TASKS_LIMIT_MAX}; got {limit}"
                )

        return session_id, status_filter, chain_id_filter, limit

    # ------------------------------------------------------------------ #
    # Response helpers
    # ------------------------------------------------------------------ #

    def _send_json(self, status: int, payload: Any) -> None:
        """Serialize payload to JSON and send with appropriate headers."""
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPE_JSON)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        """Send a JSON error response."""
        self._send_json(status, {"ok": False, "error": message})

    def _send_not_found(self, message: str) -> None:
        """Send a 404 JSON response."""
        self._send_error(404, message)


# ---------------------------------------------------------------------------
# Response shape helpers (keep handlers free of field-name literals)
# ---------------------------------------------------------------------------

def _project_list_shape(row: dict) -> dict:
    """Narrow project row to the /projects list response shape."""
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "archetype": row.get("archetype"),
        "current_phase": row.get("current_phase", ""),
        "rigor_tier": row.get("rigor_tier"),
        "complexity_score": row.get("complexity_score"),
        "status": row.get("status"),
        "updated_at": row.get("updated_at"),
    }


def _project_detail_shape(row: dict) -> dict:
    """Full project row for /projects/{id} response."""
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "workspace": row.get("workspace"),
        "directory": row.get("directory"),
        "archetype": row.get("archetype"),
        "complexity_score": row.get("complexity_score"),
        "rigor_tier": row.get("rigor_tier"),
        "current_phase": row.get("current_phase", ""),
        "status": row.get("status"),
        "chain_id": row.get("chain_id"),
        "yolo_revoked_count": row.get("yolo_revoked_count", 0),
        "last_revoke_reason": row.get("last_revoke_reason"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _phase_shape(row: dict) -> dict:
    """Phase row for /projects/{id}/phases response."""
    return {
        "phase": row.get("phase"),
        "state": row.get("state"),
        "gate_score": row.get("gate_score"),
        "gate_verdict": row.get("gate_verdict"),
        "gate_reviewer": row.get("gate_reviewer"),
        "started_at": row.get("started_at"),
        "terminal_at": row.get("terminal_at"),
        "rework_iterations": row.get("rework_iterations", 0),
        "updated_at": row.get("updated_at"),
    }


def _event_shape(row: dict) -> dict:
    """Event log row for /events response."""
    payload = row.get("payload_json")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    return {
        "event_id": row.get("event_id"),
        "event_type": row.get("event_type"),
        "chain_id": row.get("chain_id"),
        "payload": payload,
        "projection_status": row.get("projection_status"),
        "ingested_at": row.get("ingested_at"),
    }


def _task_shape(row: dict) -> dict:
    """Task row for /tasks and /tasks/<id> responses.

    Stream 1 — #596 v8-PR-2.  The ``metadata`` column is already deserialised
    to a dict by db.get_task / db.list_tasks; pass it through as-is.
    """
    return {
        "id": row.get("id"),
        "session_id": row.get("session_id"),
        "subject": row.get("subject", ""),
        "status": row.get("status"),
        "chain_id": row.get("chain_id"),
        "event_type": row.get("event_type"),
        "metadata": row.get("metadata"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Server factory and entrypoint
# ---------------------------------------------------------------------------

def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    db_path: str | None = None,
) -> http.server.ThreadingHTTPServer:
    """Create and return a configured ThreadingHTTPServer (caller calls serve_forever).

    Parameters
    ----------
    host:
        Interface to bind.  Should remain 127.0.0.1 per locked decision #10.
        Overridable via WG_DAEMON_HOST (documented as not encouraged).
    port:
        TCP port to bind.  Default 4244; override via WG_DAEMON_PORT.
    db_path:
        Path to the SQLite projection DB.  None uses the env / default path
        resolved by daemon.db.connect().
    """
    # Build a per-server handler subclass that closes over db_path so
    # individual handler instances can access it without global state.
    handler_class = type(
        "BoundProjectionRequestHandler",
        (ProjectionRequestHandler,),
        {"db_path": db_path},
    )
    server = http.server.ThreadingHTTPServer((host, port), handler_class)
    logger.info("Daemon HTTP server configured on %s:%d (db_path=%s)", host, port, db_path)
    return server


def run(
    host: str | None = None,
    port: int | None = None,
    db_path: str | None = None,
) -> int:
    """Blocking entrypoint; honours WG_DAEMON_PORT / WG_DAEMON_HOST env vars.

    Returns an integer exit code (0 = clean shutdown).
    """
    resolved_host = host or os.environ.get(ENV_HOST, DEFAULT_HOST)
    resolved_port: int
    if port is not None:
        resolved_port = port
    else:
        env_port = os.environ.get(ENV_PORT)
        if env_port is not None:
            if not env_port.isdigit():
                logger.error("WG_DAEMON_PORT='%s' is not a valid port number", env_port)
                return 1
            resolved_port = int(env_port)
        else:
            resolved_port = DEFAULT_PORT

    server = make_server(host=resolved_host, port=resolved_port, db_path=db_path)

    stop_signals = (signal.SIGINT, signal.SIGTERM)

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; shutting down daemon.", signum)
        server.shutdown()

    for sig in stop_signals:
        try:
            signal.signal(sig, _handle_signal)
        except (OSError, ValueError):
            # OSError: not a main thread; ValueError: signal not available on platform.
            pass

    logger.info(
        "wicked-garden daemon v%s listening on %s:%d",
        DAEMON_VERSION,
        resolved_host,
        resolved_port,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received; shutting down.")
    finally:
        server.server_close()

    logger.info("Daemon stopped.")
    return 0
