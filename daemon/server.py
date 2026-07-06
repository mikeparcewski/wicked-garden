"""
server.py — HTTP server for the wicked-garden daemon.

Provides a Flask application exposing garden state, council, and HITL endpoints
for the garden dashboard and external tooling.

Endpoints:
    GET  /health                 → daemon health + version
    GET  /state                  → current projector snapshot
    POST /council                → run a council session (synchronous)
    GET  /council/<session_id>   → council session status
    POST /hitl/respond           → record a HITL response

Usage::

    from daemon.server import create_app

    app = create_app(conn, projector)
    app.run(host="127.0.0.1", port=7700)

Or use the factory directly with Flask's WSGI runner, gunicorn, etc.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from daemon._internal import generate_id, now_iso
from daemon.db import get_write_lock
from daemon.projector import Projector

logger = logging.getLogger("wicked-garden.daemon.server")

VERSION = "0.1.0"


def create_app(
    conn: sqlite3.Connection,
    projector: Projector,
) -> Any:
    """Create and return the configured Flask application.

    Args:
        conn: Open sqlite3 connection shared with other daemon components.
        projector: The daemon's Projector instance.

    Returns:
        A Flask application object.
    """
    try:
        from flask import Flask, jsonify, request
    except ImportError as exc:
        raise ImportError(
            "Flask is required for the garden daemon HTTP server. "
            "Install it with: pip install flask"
        ) from exc

    def _err(message: str, code: str = "INTERNAL_ERROR", status: int = 500):
        """Return a nested error response: {"error": {"code": ..., "message": ...}}."""
        return jsonify({"error": {"code": code, "message": message}}), status

    app = Flask("wicked-garden-daemon")
    app.config["PROPAGATE_EXCEPTIONS"] = False

    # ----------------------------------------------------------------
    # GET /health
    # ----------------------------------------------------------------

    @app.get("/health")
    def health():
        """Return daemon health and version."""
        return jsonify({"status": "ok", "version": VERSION})

    # ----------------------------------------------------------------
    # GET /state
    # ----------------------------------------------------------------

    @app.get("/state")
    def state():
        """Return the current projector snapshot."""
        try:
            snapshot = projector.snapshot()
            return jsonify(snapshot)
        except Exception as exc:  # noqa: BLE001
            logger.error("/state failed: %s", exc, exc_info=True)
            return _err("Failed to retrieve state", "INTERNAL_ERROR", 500)

    # ----------------------------------------------------------------
    # POST /council
    # ----------------------------------------------------------------

    @app.post("/council")
    def council_run():
        """Run a council session.

        Request body (JSON):
            {
                "topic": "...",
                "question": "...",
                "criteria": ["...", "..."],
                "timeout_s": 30        (optional)
            }

        Returns:
            {
                "session_id": "...",
                "verdict": "...",
                "confidence": 0.85,
                "rationale": "...",
                "votes": [...]
            }
        """
        from daemon.council import run_council

        body = request.get_json(silent=True) or {}
        topic = body.get("topic", "")
        question = body.get("question", "")
        criteria = body.get("criteria", [])
        timeout_s = int(body.get("timeout_s", 30))

        if not topic or not question:
            return _err("'topic' and 'question' are required", "INVALID_REQUEST", 400)

        try:
            result = run_council(
                conn,
                topic=topic,
                question=question,
                criteria=criteria,
                timeout_s=timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("/council failed: %s", exc, exc_info=True)
            return _err(str(exc), "INTERNAL_ERROR", 500)

        return jsonify({
            "session_id": result.session_id,
            "verdict": result.verdict,
            "confidence": result.confidence,
            "rationale": result.rationale,
            "votes": result.votes,
        })

    # ----------------------------------------------------------------
    # GET /council/<session_id>
    # ----------------------------------------------------------------

    @app.get("/council/<session_id>")
    def council_get(session_id: str):
        """Return council session status by ID."""
        from daemon.council import get_session

        session = get_session(conn, session_id)
        if session is None:
            return _err("Session not found", "NOT_FOUND", 404)
        return jsonify(session)

    # ----------------------------------------------------------------
    # GET /hooks
    # ----------------------------------------------------------------

    @app.get("/hooks")
    def hooks_list():
        """List all registered hooks."""
        try:
            rows = conn.execute(
                "SELECT id, event_pattern, command, description, created_at FROM hooks ORDER BY created_at"
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        except Exception as exc:  # noqa: BLE001
            logger.error("/hooks GET failed: %s", exc, exc_info=True)
            return _err("Failed to list hooks", "INTERNAL_ERROR", 500)

    # ----------------------------------------------------------------
    # POST /hooks
    # ----------------------------------------------------------------

    @app.post("/hooks")
    def hooks_register():
        """Register a hook.

        Request body (JSON):
            {
                "event_pattern": "wicked.garden.*",
                "command": "/path/to/script.sh",
                "description": "optional description"
            }

        Returns:
            {"id": "...", "event_pattern": "...", "command": "...",
             "description": "...", "created_at": "..."}
        """
        body = request.get_json(silent=True) or {}
        event_pattern = body.get("event_pattern", "")
        command = body.get("command", "")
        description = body.get("description", "")

        if not event_pattern or not command:
            return _err("'event_pattern' and 'command' are required", "INVALID_REQUEST", 400)

        hook_id = generate_id()
        created_at = now_iso()
        try:
            with get_write_lock():
                conn.execute(
                    """
                    INSERT INTO hooks (id, event_pattern, command, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (hook_id, event_pattern, command, description, created_at),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("/hooks POST failed: %s", exc, exc_info=True)
            return _err("Failed to register hook", "INTERNAL_ERROR", 500)

        return jsonify({
            "id": hook_id,
            "event_pattern": event_pattern,
            "command": command,
            "description": description,
            "created_at": created_at,
        }), 201

    # ----------------------------------------------------------------
    # DELETE /hooks/<hook_id>
    # ----------------------------------------------------------------

    @app.delete("/hooks/<hook_id>")
    def hooks_deregister(hook_id: str):
        """Deregister a hook by ID."""
        try:
            with get_write_lock():
                row = conn.execute(
                    "SELECT id FROM hooks WHERE id = ?", (hook_id,)
                ).fetchone()
                if row is None:
                    return _err("Hook not found", "NOT_FOUND", 404)

                conn.execute("DELETE FROM hooks WHERE id = ?", (hook_id,))
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("/hooks DELETE failed: %s", exc, exc_info=True)
            return _err("Failed to deregister hook", "INTERNAL_ERROR", 500)

        return jsonify({"ok": True, "id": hook_id})

    # ----------------------------------------------------------------
    # POST /council/vote
    # ----------------------------------------------------------------

    @app.post("/council/vote")
    def council_vote():
        """Cast a vote on a council session.

        Request body (JSON):
            {
                "session_id": "...",
                "voter_id": "...",
                "vote": "...",
                "reason": "..."    (optional)
            }

        Returns:
            {"ok": true, "session_id": "...", "voter_id": "..."}
        """
        body = request.get_json(silent=True) or {}
        session_id = body.get("session_id", "")
        voter_id = body.get("voter_id", "")
        vote = body.get("vote", "")
        reason = body.get("reason", "")

        if not session_id or not voter_id or not vote:
            return _err("'session_id', 'voter_id', and 'vote' are required", "INVALID_REQUEST", 400)

        try:
            with get_write_lock():
                row = conn.execute(
                    "SELECT id, votes, status FROM council_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row is None:
                    return _err("Session not found", "NOT_FOUND", 404)

                existing_votes = []
                if row["votes"]:
                    try:
                        existing_votes = json.loads(row["votes"])
                    except (json.JSONDecodeError, TypeError):
                        existing_votes = []

                new_vote = {"voter": voter_id, "vote": vote}
                if reason:
                    new_vote["reason"] = reason
                existing_votes.append(new_vote)

                conn.execute(
                    "UPDATE council_sessions SET votes = ? WHERE id = ?",
                    (json.dumps(existing_votes), session_id),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("/council/vote failed: %s", exc, exc_info=True)
            return _err("Failed to record vote", "INTERNAL_ERROR", 500)

        return jsonify({"ok": True, "session_id": session_id, "voter_id": voter_id})

    # ----------------------------------------------------------------
    # POST /hitl/respond
    # ----------------------------------------------------------------

    @app.post("/hitl/respond")
    def hitl_respond():
        """Record a HITL response.

        Request body (JSON):
            {
                "prompt_id": "...",
                "response": "..."
            }
        """
        body = request.get_json(silent=True) or {}
        prompt_id = body.get("prompt_id", "")
        response_text = body.get("response", "")

        if not prompt_id:
            return _err("'prompt_id' is required", "INVALID_REQUEST", 400)

        responded_at = now_iso()
        try:
            with get_write_lock():
                cur = conn.execute(
                    "SELECT id FROM hitl_prompts WHERE id = ?", (prompt_id,)
                ).fetchone()
                if cur is None:
                    return _err("Prompt not found", "NOT_FOUND", 404)

                conn.execute(
                    """
                    UPDATE hitl_prompts
                    SET response = ?,
                        status = 'responded',
                        responded_at = ?
                    WHERE id = ?
                    """,
                    (response_text, responded_at, prompt_id),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("/hitl/respond failed: %s", exc, exc_info=True)
            return _err("Failed to record response", "INTERNAL_ERROR", 500)

        return jsonify({"ok": True, "prompt_id": prompt_id, "responded_at": responded_at})

    # ----------------------------------------------------------------
    # Error handlers
    # ----------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(exc):
        return _err("Not found", "NOT_FOUND", 404)

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return _err("Method not allowed", "METHOD_NOT_ALLOWED", 405)

    @app.errorhandler(500)
    def internal_error(exc):
        logger.error("Unhandled server error: %s", exc, exc_info=True)
        return _err("Internal server error", "INTERNAL_ERROR", 500)

    return app
