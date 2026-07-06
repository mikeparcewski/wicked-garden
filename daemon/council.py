"""
council.py — Council orchestrator for the wicked-garden daemon.

Council is *synchronous* — the caller POSTs a question, gets back votes +
synthesis. For v0.1 the council runs a single synthesis call via the Anthropic
API (requires ANTHROPIC_API_KEY in the environment) and records the session in
the ``council_sessions`` table.

Usage::

    from daemon.council import run_council

    result = run_council(
        conn,
        topic="architecture",
        question="Should we use SQLite or Postgres for the garden DB?",
        criteria=["simplicity", "reliability", "zero-ops"],
        timeout_s=30,
    )
    print(result.verdict, result.confidence)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
from collections import namedtuple
from typing import Any, Optional

from daemon._internal import DaemonError, emit_bus_event, generate_id, now_iso
from daemon.db import get_write_lock

logger = logging.getLogger("wicked-garden.daemon.council")

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

CouncilResult = namedtuple(
    "CouncilResult",
    ["session_id", "verdict", "confidence", "votes", "rationale"],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_S = 30
_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_COUNCIL_EVENT_TYPE = "wicked.garden.council.voted"
_COUNCIL_DOMAIN = "wicked-garden"
_COUNCIL_SUBDOMAIN = "garden.council"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_council(
    conn: sqlite3.Connection,
    topic: str,
    question: str,
    criteria: list[str],
    cli_list: Optional[list[str]] = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> CouncilResult:
    """Run a council session synchronously.

    Creates a council_sessions row, calls the Anthropic API for a synthesis
    verdict, updates the row, emits a ``wicked.council.voted`` bus event, and
    returns a CouncilResult.

    Args:
        conn: Open sqlite3 connection.
        topic: Council topic identifier (e.g. ``"architecture"``).
        question: The question put to council.
        criteria: Evaluation criteria list (e.g. ``["simplicity", "reliability"]``).
        cli_list: Specific CLI names to use as voters. Not used in v0.1 (single
                  synthesis path); reserved for future multi-model expansion.
        timeout_s: Maximum seconds to wait for the API call.

    Returns:
        CouncilResult namedtuple with fields:
        ``session_id``, ``verdict``, ``confidence``, ``votes``, ``rationale``.

    Raises:
        DaemonError: If the API call fails and no fallback is available.
    """
    session_id = generate_id()
    created_at = now_iso()

    # Persist the session as 'pending'
    with get_write_lock():
        conn.execute(
            """
            INSERT INTO council_sessions
                (id, topic, question, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (session_id, topic, question, created_at),
        )
        conn.commit()
    logger.info("Council session %s started: topic=%r", session_id, topic)

    try:
        result = _synthesise(
            session_id=session_id,
            topic=topic,
            question=question,
            criteria=criteria,
            timeout_s=timeout_s,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Council session %s failed: %s", session_id, exc, exc_info=True)
        _update_session(conn, session_id, status="failed", verdict="error", votes=[], rationale=str(exc))
        raise DaemonError(f"Council session failed: {exc}") from exc

    # Persist result
    _update_session(
        conn,
        session_id,
        status="completed",
        verdict=result.verdict,
        votes=result.votes,
        rationale=result.rationale,
    )

    # Emit bus event (fire-and-forget)
    run_hash = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    idempotency_key = f"garden:{_COUNCIL_EVENT_TYPE}:{session_id}:{run_hash}:0"
    emit_bus_event(
        _COUNCIL_EVENT_TYPE,
        _COUNCIL_DOMAIN,
        _COUNCIL_SUBDOMAIN,
        {
            "session_id": session_id,
            "topic": topic,
            "verdict": result.verdict,
            "confidence": result.confidence,
        },
        idempotency_key=idempotency_key,
    )

    logger.info(
        "Council session %s completed: verdict=%r confidence=%.2f",
        session_id, result.verdict, result.confidence,
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _synthesise(
    *,
    session_id: str,
    topic: str,
    question: str,
    criteria: list[str],
    timeout_s: int,
) -> CouncilResult:
    """Call the Anthropic API (via SDK or subprocess) and return a CouncilResult.

    Strategy (v0.1):
    1. Try the ``anthropic`` Python SDK (if installed and ANTHROPIC_API_KEY set).
    2. Fall back to the ``claude`` CLI subprocess.
    3. If neither is available, raise DaemonError.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    prompt = _build_prompt(topic, question, criteria)

    # Try SDK first
    try:
        return _synthesise_via_sdk(session_id, prompt, api_key, timeout_s)
    except ImportError:
        logger.debug("anthropic SDK not installed; trying claude CLI")
    except Exception as exc:  # noqa: BLE001
        logger.warning("anthropic SDK call failed (%s); trying claude CLI", exc)

    # Try claude CLI
    try:
        return _synthesise_via_cli(session_id, prompt, timeout_s)
    except FileNotFoundError:
        raise DaemonError(
            "Council requires either the 'anthropic' Python SDK with ANTHROPIC_API_KEY "
            "or the 'claude' CLI to be available."
        )


def _build_prompt(topic: str, question: str, criteria: list[str]) -> str:
    criteria_str = "\n".join(f"- {c}" for c in criteria) if criteria else "- quality\n- correctness"
    return (
        f"You are a council of advisors evaluating a decision.\n\n"
        f"Topic: {topic}\n\n"
        f"Question: {question}\n\n"
        f"Evaluation criteria:\n{criteria_str}\n\n"
        f"Respond in JSON with this exact structure:\n"
        f'{{"verdict": "<short decision>", "confidence": <0.0-1.0>, '
        f'"rationale": "<explanation>", "votes": [{{"voter": "advisor-1", "vote": "<position>"}}, '
        f'{{"voter": "advisor-2", "vote": "<position>"}}]}}'
    )


def _synthesise_via_sdk(
    session_id: str,
    prompt: str,
    api_key: str,
    timeout_s: int,
) -> CouncilResult:
    """Use the anthropic Python SDK to run the council synthesis."""
    import anthropic  # type: ignore[import]

    client = anthropic.Anthropic(api_key=api_key or None)
    message = client.messages.create(
        model=_DEFAULT_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        timeout=timeout_s,
    )
    raw = message.content[0].text if message.content else "{}"
    return _parse_council_response(session_id, raw)


def _synthesise_via_cli(session_id: str, prompt: str, timeout_s: int) -> CouncilResult:
    """Use the ``claude`` CLI subprocess to run the council synthesis."""
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    raw = result.stdout.strip() if result.returncode == 0 else "{}"
    return _parse_council_response(session_id, raw)


def _parse_council_response(session_id: str, raw: str) -> CouncilResult:
    """Parse the model's JSON response into a CouncilResult."""
    # Extract JSON from response (model may wrap it in markdown fences)
    text = raw.strip()
    if "```" in text:
        lines = text.split("\n")
        json_lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(json_lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse council JSON response; using fallback")
        data = {}

    verdict = str(data.get("verdict", "no consensus"))
    confidence = float(data.get("confidence", 0.5))
    rationale = str(data.get("rationale", raw[:500] if raw else ""))
    votes = data.get("votes", [])
    if not isinstance(votes, list):
        votes = []

    return CouncilResult(
        session_id=session_id,
        verdict=verdict,
        confidence=confidence,
        votes=votes,
        rationale=rationale,
    )


def _update_session(
    conn: sqlite3.Connection,
    session_id: str,
    status: str,
    verdict: str,
    votes: list[Any],
    rationale: str,
) -> None:
    """Update a council_sessions row after the session completes or fails."""
    try:
        with get_write_lock():
            conn.execute(
                """
                UPDATE council_sessions
                SET status = ?,
                    verdict = ?,
                    votes = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    verdict,
                    json.dumps(votes),
                    now_iso(),
                    session_id,
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to update council session %s: %s", session_id, exc)


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict[str, Any]]:
    """Fetch a council session by ID. Returns None if not found."""
    try:
        row = conn.execute(
            "SELECT * FROM council_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get("votes"):
            try:
                d["votes"] = json.loads(d["votes"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
    except Exception as exc:  # noqa: BLE001
        logger.error("get_session failed for %s: %s", session_id, exc)
        return None
