"""
daemon/server.py — HTTP server for the wicked-garden v8 daemon.

Exposes GET endpoints backed by the SQLite projection DB (daemon/db.py), plus
the council POST endpoint which is an explicit mutation carve-out from PR-1
decision #6 (see Stream 3 comment below).

PR-1 decision #6 (daemon read-only) applies to all projection tables
(projects, phases, tasks, cursor, event_log).  Council sessions are *originated*
here — not projected from bus events — so POST /council is a deliberate, bounded
exception.  PR-2 introduced the first write path (event ingestion).  PR-4 adds
the second: council orchestration.  Both are documented at their call sites.

Defaults to 127.0.0.1 per locked decision #10; WG_DAEMON_HOST can override but
is documented as not encouraged. Default port 4244.

Public API
----------
ProjectionRequestHandler  — BaseHTTPRequestHandler subclass; implements do_GET/do_POST.
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
import daemon.council as council_module
import daemon.test_dispatch as test_dispatch_module
import daemon.hook_dispatch as hook_dispatch_module
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
# Stream 3 — #594 v8-PR-4: /councils list limits
COUNCILS_LIMIT_DEFAULT: int = 50
COUNCILS_LIMIT_MAX: int = 200
# Maximum request body size for POST /council (R5: no unbounded reads)
COUNCIL_POST_MAX_BODY_BYTES: int = 65_536
# Stream 6 — #595 v8-PR-7: /test-dispatch limits
TEST_DISPATCH_POST_MAX_BODY_BYTES: int = 65_536
TEST_DISPATCHES_LIST_LIMIT_DEFAULT: int = 50
TEST_DISPATCHES_LIST_LIMIT_MAX: int = 500
# Stream 4 — #592 v8-PR-8: /subscriptions limits
SUBSCRIPTIONS_INVOCATIONS_LIMIT_DEFAULT: int = 50
SUBSCRIPTIONS_INVOCATIONS_LIMIT_MAX: int = 500
# POST /subscriptions/<id>/toggle body size limit (R5: no unbounded reads)
SUBSCRIPTION_TOGGLE_MAX_BODY_BYTES: int = 4_096

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
            # Stream 3 — #594 v8-PR-4: council read endpoints
            elif path == "/councils":
                self._handle_list_councils(query)
            elif path.startswith("/council/"):
                session_id = path[len("/council/"):]
                if session_id and "/" not in session_id:
                    self._handle_get_council(session_id, query)
                else:
                    self._send_not_found("Unknown endpoint")
            # Stream 6 — #595 v8-PR-7: test-dispatch read endpoint
            elif path == "/test-dispatches":
                self._handle_list_test_dispatches(query)
            # Stream 4 — #592 v8-PR-8: subscription observability endpoints
            elif path == "/subscriptions":
                self._handle_list_subscriptions(query)
            elif path.startswith("/subscriptions/"):
                tail = path[len("/subscriptions/"):]
                if "/invocations" in tail:
                    parts = tail.split("/invocations")
                    sub_id = parts[0]
                    if sub_id:
                        self._handle_list_invocations(sub_id, query)
                    else:
                        self._send_not_found("Missing subscription id")
                elif tail and "/" not in tail:
                    self._handle_get_subscription(tail, query)
                else:
                    self._send_not_found("Unknown subscription endpoint")
            else:
                self._send_not_found("Unknown endpoint")
        except Exception:
            logger.error("Unhandled exception in do_GET:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")

    def do_POST(self) -> None:  # noqa: D102
        """Dispatch incoming POST requests to endpoint helpers.

        Stream 3 — #594 v8-PR-4.

        POST /council is an explicit mutation carve-out from PR-1 decision #6
        (daemon read-only for projection tables).  Council sessions are *originated*
        by the daemon — not projected from bus events — so mutation is required.
        The caller POSTs a question and synchronously receives the full council
        result including raw votes, synthesis, and HITL decision.

        See daemon/council.py module docstring for the full carve-out rationale.
        """
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            if path == "/council":
                self._handle_post_council()
            # Stream 6 — #595 v8-PR-7: test-dispatch POST endpoint
            elif path == "/test-dispatch":
                self._handle_post_test_dispatch()
            # Stream 4 — #592 v8-PR-8: subscription toggle (4th write carve-out)
            elif path.startswith("/subscriptions/") and path.endswith("/toggle"):
                sub_id = path[len("/subscriptions/"):-len("/toggle")]
                if sub_id and "/" not in sub_id:
                    self._handle_post_subscription_toggle(sub_id)
                else:
                    self._send_not_found("Invalid subscription toggle path")
            else:
                self._send_not_found("Unknown POST endpoint")
        except Exception:
            logger.error("Unhandled exception in do_POST:\n%s", traceback.format_exc())
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
    # Council endpoints (Stream 3 — #594 v8-PR-4)
    # ------------------------------------------------------------------ #

    def _handle_post_council(self) -> None:
        """POST /council — Run a council session synchronously.

        Body: {"topic": str, "question": str, "criteria"?: str,
               "cli_list"?: list[str], "timeout_s"?: int}
        Returns: CouncilResult envelope {session_id, raw_votes, synthesized,
                                          hitl_decision, agreement_ratio}

        MUTATION CARVE-OUT: This endpoint writes to council_sessions + council_votes.
        It is the explicit exception to the daemon read-only principle from PR-1
        decision #6.  All projection tables remain read-only.

        NOTE: POST /council can be long-running (up to timeout_s * parallel CLIs
        wall-clock time on slow hardware, though in practice CLIs run in parallel
        so the ceiling is timeout_s + scheduling overhead).  Clients should set
        an appropriate HTTP client timeout.
        """
        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except (ValueError, TypeError):
            self._send_error(400, "Invalid Content-Length")
            return

        if content_length > COUNCIL_POST_MAX_BODY_BYTES:
            self._send_error(413, f"Request body exceeds limit of {COUNCIL_POST_MAX_BODY_BYTES} bytes")
            return

        if content_length == 0:
            self._send_error(400, "Request body required")
            return

        raw_body = self.rfile.read(content_length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error(400, f"Invalid JSON body: {exc}")
            return

        if not isinstance(body, dict):
            self._send_error(400, "Body must be a JSON object")
            return

        topic = body.get("topic", "")
        question = body.get("question", "")
        if not topic or not isinstance(topic, str):
            self._send_error(400, "Field 'topic' (non-empty string) is required")
            return
        if not question or not isinstance(question, str):
            self._send_error(400, "Field 'question' (non-empty string) is required")
            return

        criteria = body.get("criteria", "") or ""
        cli_list = body.get("cli_list")
        timeout_s = body.get("timeout_s", council_module.DEFAULT_TIMEOUT_S)

        if cli_list is not None:
            if not isinstance(cli_list, list) or not all(isinstance(c, str) for c in cli_list):
                self._send_error(400, "'cli_list' must be a list of strings")
                return

        try:
            timeout_s = int(timeout_s)
            if timeout_s < 1:
                raise ValueError("timeout_s must be >= 1")
        except (ValueError, TypeError) as exc:
            self._send_error(400, f"Invalid timeout_s: {exc}")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            result = council_module.run_council(
                conn=conn,
                topic=topic,
                question=question,
                criteria=criteria,
                cli_list=cli_list,
                timeout_s=timeout_s,
            )
            self._send_json(200, result.to_dict())
        except Exception:
            logger.error("POST /council error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_get_council(self, session_id: str, _query: dict[str, list[str]]) -> None:
        """GET /council/<session_id> — Retrieve a historical council session + votes."""
        if not session_id:
            self._send_error(400, "Missing session id")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            row = db.get_council_session(conn, session_id)
            if row is None:
                self._send_not_found(f"Council session '{session_id}' not found")
                return
            votes = db.list_council_votes(conn, session_id)
            self._send_json(200, _council_detail_shape(row, votes))
        except Exception:
            logger.error("get_council DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_councils(self, query: dict[str, list[str]]) -> None:
        """GET /councils[?since=<epoch>&topic_prefix=<str>&limit=<N>].

        Returns recent council sessions ordered by started_at DESC.
        """
        try:
            since, topic_prefix, limit = self._parse_councils_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = db.list_council_sessions(
                conn, topic_prefix=topic_prefix, since=since, limit=limit,
            )
            self._send_json(200, [_council_list_shape(r) for r in rows])
        except Exception:
            logger.error("list_councils DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------ #
    # Test-dispatch endpoints (Stream 6 — #595 v8-PR-7)
    # ------------------------------------------------------------------ #

    def _handle_post_test_dispatch(self) -> None:
        """POST /test-dispatch — Trigger wicked-testing dispatch for a phase.

        Body: {"project_id": str, "phase": str, "skills"?: list[str],
               "autonomy"?: str}
        Returns: {"plan": TestDispatchPlan, "records": list[DispatchRecord]}

        MUTATION CARVE-OUT: This endpoint writes to test_dispatches.
        It is an explicit exception to the daemon read-only principle from PR-1
        decision #6.  All projection tables remain read-only.
        See daemon/test_dispatch.py module docstring for the full rationale.

        PLUGIN CONTRACT (v9/drop-in-plugin-contract.md):
        - Dispatches TO wicked-testing; never re-implements its logic.
        - Calls canonical skills (plan/authoring/execution/review).
        - Honours wicked-testing's verdict shape without translation.
        - Graceful degradation when wicked-testing is not installed.
        """
        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except (ValueError, TypeError):
            self._send_error(400, "Invalid Content-Length")
            return

        if content_length > TEST_DISPATCH_POST_MAX_BODY_BYTES:
            self._send_error(
                413,
                f"Request body exceeds limit of {TEST_DISPATCH_POST_MAX_BODY_BYTES} bytes",
            )
            return

        if content_length == 0:
            self._send_error(400, "Request body required")
            return

        raw_body = self.rfile.read(content_length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error(400, f"Invalid JSON body: {exc}")
            return

        if not isinstance(body, dict):
            self._send_error(400, "Body must be a JSON object")
            return

        project_id = body.get("project_id", "")
        phase = body.get("phase", "")
        if not project_id or not isinstance(project_id, str):
            self._send_error(400, "Field 'project_id' (non-empty string) is required")
            return
        if not phase or not isinstance(phase, str):
            self._send_error(400, "Field 'phase' (non-empty string) is required")
            return

        skill_filter = body.get("skills")
        if skill_filter is not None:
            if not isinstance(skill_filter, list) or not all(
                isinstance(s, str) for s in skill_filter
            ):
                self._send_error(400, "'skills' must be a list of strings")
                return

        autonomy = body.get("autonomy", "ask") or "ask"
        if not isinstance(autonomy, str):
            self._send_error(400, "'autonomy' must be a string (ask|balanced|full)")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            # Build the phase row for detection — single-phase dispatch
            phases_list = [{"phase": phase, "name": phase}]
            records = test_dispatch_module.run_test_dispatches(
                conn=conn,
                project_id=project_id,
                phases_list=phases_list,
                autonomy_mode_str=autonomy,
                skill_filter=skill_filter,
            )
            plan = test_dispatch_module.build_dispatch_plan(project_id, phases_list)
            self._send_json(200, {
                "plan": plan.to_dict(),
                "records": [r.to_dict() for r in records],
            })
        except Exception:
            logger.error("POST /test-dispatch error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_test_dispatches(self, query: dict[str, list[str]]) -> None:
        """GET /test-dispatches[?project_id=X&since=Y&limit=N].

        Returns recent test dispatch records ordered by emitted_at DESC.
        """
        try:
            project_id_filter, since, limit = self._parse_test_dispatches_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = test_dispatch_module.list_test_dispatches(
                conn,
                project_id=project_id_filter,
                since=since,
                limit=limit,
            )
            self._send_json(200, [_test_dispatch_shape(r) for r in rows])
        except Exception:
            logger.error("list_test_dispatches DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------ #
    # Subscription endpoints (Stream 4 — #592 v8-PR-8)
    # ------------------------------------------------------------------ #

    def _handle_list_subscriptions(self, _query: dict[str, list[str]]) -> None:
        """GET /subscriptions — list all hook subscriptions.

        Returns all subscriptions (enabled and disabled) ordered by created_at ASC.
        This is a read-only observability endpoint.
        """
        conn = None
        try:
            conn = db.connect(self.db_path)
            rows = db.list_hook_subscriptions(conn, enabled_only=False)
            self._send_json(200, [_subscription_list_shape(r) for r in rows])
        except Exception:
            logger.error("list_subscriptions DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_get_subscription(
        self, subscription_id: str, _query: dict[str, list[str]]
    ) -> None:
        """GET /subscriptions/<id> — retrieve a single subscription row."""
        if not subscription_id:
            self._send_error(400, "Missing subscription id")
            return
        conn = None
        try:
            conn = db.connect(self.db_path)
            row = db.get_hook_subscription(conn, subscription_id)
            if row is None:
                self._send_not_found(f"Subscription '{subscription_id}' not found")
                return
            self._send_json(200, _subscription_detail_shape(row))
        except Exception:
            logger.error("get_subscription DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_list_invocations(
        self, subscription_id: str, query: dict[str, list[str]]
    ) -> None:
        """GET /subscriptions/<id>/invocations[?since=X&limit=N] — recent invocations."""
        if not subscription_id:
            self._send_error(400, "Missing subscription id")
            return
        try:
            since, limit = self._parse_invocations_query(query)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return
        conn = None
        try:
            conn = db.connect(self.db_path)
            # Verify subscription exists
            if db.get_hook_subscription(conn, subscription_id) is None:
                self._send_not_found(f"Subscription '{subscription_id}' not found")
                return
            rows = db.list_hook_invocations(
                conn, subscription_id=subscription_id, since=since, limit=limit
            )
            self._send_json(200, [_invocation_shape(r) for r in rows])
        except Exception:
            logger.error("list_invocations DB error:\n%s", traceback.format_exc())
            self._send_error(500, "Internal server error")
        finally:
            if conn is not None:
                conn.close()

    def _handle_post_subscription_toggle(self, subscription_id: str) -> None:
        """POST /subscriptions/<id>/toggle — enable or disable a subscription.

        Body: {"enabled": true | false}
        Returns: {"ok": true, "subscription_id": str, "enabled": bool}

        MUTATION CARVE-OUT (4th write path, v8-PR-8 #592):
        This is an explicit exception to the daemon read-only principle from
        PR-1 decision #6.  Toggle is a bounded, operator-facing control —
        it only flips the enabled flag on an existing subscription row.
        No new subscriptions can be created via HTTP.
        Documented in daemon/hook_dispatch.py and docs/evidence/pr-v8-8/contract-check.md.
        """
        if not subscription_id:
            self._send_error(400, "Missing subscription id")
            return

        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except (ValueError, TypeError):
            self._send_error(400, "Invalid Content-Length")
            return

        if content_length > SUBSCRIPTION_TOGGLE_MAX_BODY_BYTES:
            self._send_error(413, f"Request body exceeds limit of {SUBSCRIPTION_TOGGLE_MAX_BODY_BYTES} bytes")
            return

        body: dict = {}
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self._send_error(400, f"Invalid JSON body: {exc}")
                return
            if not isinstance(body, dict):
                self._send_error(400, "Body must be a JSON object")
                return

        enabled_val = body.get("enabled")
        if enabled_val is None or not isinstance(enabled_val, bool):
            self._send_error(400, "Field 'enabled' (boolean) is required")
            return

        conn = None
        try:
            conn = db.connect(self.db_path)
            updated = db.toggle_hook_subscription(conn, subscription_id, enabled=enabled_val)
            if not updated:
                self._send_not_found(f"Subscription '{subscription_id}' not found")
                return
            self._send_json(200, {
                "ok": True,
                "subscription_id": subscription_id,
                "enabled": enabled_val,
            })
        except Exception:
            logger.error("toggle_subscription DB error:\n%s", traceback.format_exc())
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

    @staticmethod
    def _parse_councils_query(
        query: dict[str, list[str]],
    ) -> tuple[int, str | None, int]:
        """Parse and validate /councils query params.

        Returns (since, topic_prefix, limit).
        Raises ValueError for invalid values.
        """
        since = 0
        if "since" in query:
            raw = query["since"][0]
            if not raw.lstrip("-").isdigit():
                raise ValueError(f"Invalid since '{raw}'; must be an integer epoch")
            since = int(raw)
            if since < 0:
                raise ValueError(f"since must be >= 0; got {since}")

        topic_prefix: str | None = query["topic_prefix"][0] if "topic_prefix" in query else None

        limit = COUNCILS_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > COUNCILS_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {COUNCILS_LIMIT_MAX}; got {limit}"
                )

        return since, topic_prefix, limit

    @staticmethod
    def _parse_invocations_query(
        query: dict[str, list[str]],
    ) -> tuple[int, int]:
        """Parse and validate /subscriptions/<id>/invocations query params.

        Returns (since, limit).
        Raises ValueError for invalid values.
        """
        since = 0
        if "since" in query:
            raw = query["since"][0]
            if not raw.lstrip("-").isdigit():
                raise ValueError(f"Invalid since '{raw}'; must be an integer epoch")
            since = int(raw)
            if since < 0:
                raise ValueError(f"since must be >= 0; got {since}")

        limit = SUBSCRIPTIONS_INVOCATIONS_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > SUBSCRIPTIONS_INVOCATIONS_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {SUBSCRIPTIONS_INVOCATIONS_LIMIT_MAX}; got {limit}"
                )

        return since, limit

    @staticmethod
    def _parse_test_dispatches_query(
        query: dict[str, list[str]],
    ) -> tuple[str | None, int, int]:
        """Parse and validate /test-dispatches query params.

        Returns (project_id_filter, since, limit).
        Raises ValueError for invalid values.
        """
        project_id_filter: str | None = (
            query["project_id"][0] if "project_id" in query else None
        )

        since = 0
        if "since" in query:
            raw = query["since"][0]
            if not raw.lstrip("-").isdigit():
                raise ValueError(f"Invalid since '{raw}'; must be an integer epoch")
            since = int(raw)
            if since < 0:
                raise ValueError(f"since must be >= 0; got {since}")

        limit = TEST_DISPATCHES_LIST_LIMIT_DEFAULT
        if "limit" in query:
            raw_limit = query["limit"][0]
            if not raw_limit.isdigit():
                raise ValueError(f"Invalid limit '{raw_limit}'; must be a positive integer")
            limit = int(raw_limit)
            if limit < 1 or limit > TEST_DISPATCHES_LIST_LIMIT_MAX:
                raise ValueError(
                    f"limit must be between 1 and {TEST_DISPATCHES_LIST_LIMIT_MAX}; got {limit}"
                )

        return project_id_filter, since, limit

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


def _council_list_shape(row: dict) -> dict:
    """Narrow council_sessions row to the /councils list response shape."""
    return {
        "id": row.get("id"),
        "topic": row.get("topic"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "synthesized_verdict": row.get("synthesized_verdict"),
        "agreement_ratio": row.get("agreement_ratio"),
        "hitl_paused": bool(row.get("hitl_paused", 0)),
        "hitl_rule_id": row.get("hitl_rule_id"),
    }


def _council_detail_shape(session_row: dict, vote_rows: list[dict]) -> dict:
    """Full council session + votes for GET /council/<session_id>."""
    return {
        "id": session_row.get("id"),
        "topic": session_row.get("topic"),
        "question": session_row.get("question"),
        "started_at": session_row.get("started_at"),
        "completed_at": session_row.get("completed_at"),
        "synthesized_verdict": session_row.get("synthesized_verdict"),
        "agreement_ratio": session_row.get("agreement_ratio"),
        "hitl_paused": bool(session_row.get("hitl_paused", 0)),
        "hitl_rule_id": session_row.get("hitl_rule_id"),
        "votes": [_council_vote_shape(v) for v in vote_rows],
    }


def _council_vote_shape(row: dict) -> dict:
    """Vote row for council detail response."""
    return {
        "model": row.get("model"),
        "verdict": row.get("verdict"),
        "confidence": row.get("confidence"),
        "rationale": row.get("rationale"),
        "latency_ms": row.get("latency_ms"),
        "emitted_at": row.get("emitted_at"),
        # raw_response is intentionally excluded from the HTTP response —
        # it can be arbitrarily large.  Callers that need the raw text
        # should query the DB directly or we add a dedicated endpoint.
    }


def _subscription_list_shape(row: dict) -> dict:
    """Hook subscription row for /subscriptions list response.

    Stream 4 — #592 v8-PR-8.
    """
    return {
        "subscription_id": row.get("subscription_id"),
        "filter_pattern": row.get("filter_pattern"),
        "handler_path": row.get("handler_path"),
        "debounce_rule": row.get("debounce_rule"),
        "enabled": bool(row.get("enabled", 1)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _subscription_detail_shape(row: dict) -> dict:
    """Full subscription row for /subscriptions/<id> response."""
    return _subscription_list_shape(row)


def _invocation_shape(row: dict) -> dict:
    """Hook invocation row for /subscriptions/<id>/invocations response.

    Stream 4 — #592 v8-PR-8.
    """
    return {
        "invocation_id": row.get("invocation_id"),
        "subscription_id": row.get("subscription_id"),
        "event_id": row.get("event_id"),
        "event_type": row.get("event_type"),
        "verdict": row.get("verdict"),
        "stdout_digest": row.get("stdout_digest"),
        "stderr_digest": row.get("stderr_digest"),
        "latency_ms": row.get("latency_ms"),
        "emitted_at": row.get("emitted_at"),
    }


def _test_dispatch_shape(row: dict) -> dict:
    """Test dispatch row for /test-dispatches response.

    Stream 6 — #595 v8-PR-7.
    """
    return {
        "dispatch_id": row.get("dispatch_id"),
        "session_id": row.get("session_id"),
        "project_id": row.get("project_id"),
        "phase": row.get("phase"),
        "skill": row.get("skill"),
        "verdict": row.get("verdict"),
        "evidence_path": row.get("evidence_path"),
        "latency_ms": row.get("latency_ms"),
        "emitted_at": row.get("emitted_at"),
        "notes": row.get("notes", ""),
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
