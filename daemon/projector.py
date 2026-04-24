"""daemon/projector.py — event_type → projection dispatch.

Dispatch pattern: ``_HANDLERS`` maps event_type string → private handler.
``project_event`` looks up the handler, calls it, and returns one of:
``'applied'`` | ``'ignored'`` | ``'error'``.

Replay-safety (Decision #6): every handler uses UPSERT semantics via db.*
functions.  Replaying the same event twice yields identical row state.

Unknown events (Decision #8): not in ``_HANDLERS`` → ``'ignored'``, never
raises.  Raising would stall the consumer.

Timestamp normalisation (Decision #9): ``_to_epoch`` converts ISO-8601
strings or integers to UTC epoch seconds before calling db functions.

Archetype nullable (Decision #2): absent ``archetype`` field → ``None``.

Phase state constants (v8-PR-3 #590): handler constants are imported from
``phase_state.PhaseState`` so any attempt to use a banned or unknown state
fails at import time rather than at runtime.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Callable

import daemon.db as db

# ---------------------------------------------------------------------------
# phase_state import — same path bootstrapping as daemon/db.py
# ---------------------------------------------------------------------------
_SCRIPTS_CREW = Path(__file__).resolve().parents[1] / "scripts" / "crew"
if str(_SCRIPTS_CREW) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CREW))

from phase_state import PhaseState  # type: ignore[import]  # noqa: E402

logger = logging.getLogger(__name__)

# --- named constants: canonical values from db layer (coordination item #5 — #589) ---
_APPLIED = db._PROJECTION_STATUS_APPLIED
_IGNORED = db._PROJECTION_STATUS_IGNORED
_ERROR = db._PROJECTION_STATUS_ERROR

_STATUS_ACTIVE = "active"
_STATUS_COMPLETED = "completed"

# Phase state constants now sourced from the typed state machine (v8-PR-3 #590).
# Using PhaseState enum values ensures upsert_phase sees canonical strings and
# any rename/removal of a state is a compile-time error rather than a silent
# data corruption.
_STATE_ACTIVE = PhaseState.ACTIVE      # "active"
_STATE_APPROVED = PhaseState.APPROVED  # "approved"
_STATE_REJECTED = PhaseState.REJECTED  # "rejected"

_VERDICT_REJECT = "REJECT"

# Monotonic status rank — higher value = further along the lifecycle.
# An incoming status whose rank is lower than the stored rank is a regression
# caused by out-of-order bus events; the update is silently dropped.
_STATUS_RANK: dict[str, int] = {"pending": 0, "in_progress": 1, "completed": 2}


# --- helpers ---------------------------------------------------------------

def _to_epoch(value: object) -> int | None:
    """Coerce int, float, or ISO-8601 string to UTC epoch seconds. Returns None on failure.

    Timezone-aware strings (e.g. "2026-04-24T12:00:00+02:00") are correctly
    converted to UTC before extracting the epoch.  Naive strings are assumed UTC
    (Decision #9).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        # Normalise the Z suffix so fromisoformat accepts it on Python <3.11.
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # Naive timestamp — assume UTC per Decision #9.
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except (ValueError, OverflowError) as exc:
            logger.warning("projector: cannot parse timestamp %r: %s", value, exc)
            return None
    logger.warning("projector: unexpected timestamp type %s", type(value).__name__)
    return None


def _now() -> int:
    return int(time())


def _require(payload: dict, key: str, event_type: str) -> tuple[object, bool]:
    """Return (value, True) or (None, False) logging a warning when absent."""
    if key not in payload:
        logger.warning(
            "projector: required key %r missing in %s — treating as ignored", key, event_type
        )
        return None, False
    return payload[key], True


def _opt(d: dict, key: str, default: object = None) -> object:
    return d.get(key, default)


# --- handlers --------------------------------------------------------------

def _project_created(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    meta = event.get("metadata", {}) or {}
    # chain_id resolution: prefer metadata.chain_id, then payload.chain_id, then
    # the top-level event chain_id (the canonical location in the bus event envelope).
    chain_id = (
        _opt(meta, "chain_id")
        or _opt(payload, "chain_id")
        or event.get("chain_id")
    )
    db.upsert_project(conn, str(project_id), {
        "name": _opt(payload, "name") or project_id,
        "workspace": _opt(payload, "workspace"),
        "directory": _opt(payload, "directory"),
        "archetype": _opt(payload, "archetype"),
        "complexity_score": _opt(payload, "complexity_score"),
        "rigor_tier": _opt(payload, "rigor_tier"),
        "current_phase": _opt(payload, "current_phase", ""),
        "status": _STATUS_ACTIVE,
        "chain_id": chain_id,
        "created_at": ts,
        "updated_at": ts,
    })
    logger.debug("projector: applied wicked.project.created project_id=%r", project_id)


def _project_complexity_scored(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    score, ok = _require(payload, "complexity_score", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    fields: dict = {"complexity_score": score, "updated_at": ts}
    rigor = _opt(payload, "rigor_tier")
    if rigor is not None:
        fields["rigor_tier"] = rigor
    db.upsert_project(conn, str(project_id), fields)
    logger.debug(
        "projector: applied wicked.project.complexity_scored project_id=%r score=%r",
        project_id, score,
    )


def _phase_transitioned(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase_from, ok = _require(payload, "phase_from", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    phase_to = _opt(payload, "phase_to")

    # Source phase → approved.
    db.upsert_phase(conn, str(project_id), str(phase_from), {
        "state": _STATE_APPROVED,
        "terminal_at": ts,
        "updated_at": ts,
    })
    # Target phase → active (when present).
    if phase_to is not None:
        db.upsert_phase(conn, str(project_id), str(phase_to), {
            "state": _STATE_ACTIVE,
            "started_at": ts,
            "updated_at": ts,
        })
    # Advance project pointer.
    current = str(phase_to) if phase_to is not None else str(phase_from)
    db.upsert_project(conn, str(project_id), {"current_phase": current, "updated_at": ts})
    logger.debug(
        "projector: applied %s project_id=%r %r -> %r", et, project_id, phase_from, phase_to
    )


def _phase_auto_advanced(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.phase.auto_advanced — phase-approved audit event.

    Event shape differs from wicked.phase.transitioned: payload carries
    'phase' (the phase that was auto-advanced) rather than 'phase_from'/'phase_to'.
    No next phase is implied — the project stays on the same phase pointer.

    Expected projection (from fixture auto_advance_low_complexity):
      - phases[phase].state = 'approved', terminal_at = ts
      - projects.current_phase = payload.phase
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()

    db.upsert_phase(conn, str(project_id), str(phase), {
        "state": _STATE_APPROVED,
        "terminal_at": ts,
        "updated_at": ts,
    })
    db.upsert_project(conn, str(project_id), {
        "current_phase": str(phase),
        "updated_at": ts,
    })
    logger.debug(
        "projector: applied wicked.phase.auto_advanced project_id=%r phase=%r",
        project_id, phase,
    )


def _gate_decided(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    result, ok = _require(payload, "result", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    fields: dict = {
        "gate_verdict": result,
        "gate_score": _opt(payload, "score"),
        "gate_reviewer": _opt(payload, "reviewer"),
        "updated_at": ts,
    }
    if str(result) == _VERDICT_REJECT:
        fields["state"] = _STATE_REJECTED
        fields["terminal_at"] = ts
    db.upsert_phase(conn, str(project_id), str(phase), fields)
    logger.debug(
        "projector: applied wicked.gate.decided project_id=%r phase=%r result=%r",
        project_id, phase, result,
    )


def _rework_triggered(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    iters, ok = _require(payload, "iteration_count", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    db.upsert_phase(conn, str(project_id), str(phase), {
        "rework_iterations": iters,
        "updated_at": ts,
    })
    logger.debug(
        "projector: applied wicked.rework.triggered project_id=%r phase=%r iterations=%r",
        project_id, phase, iters,
    )


def _project_completed(conn: sqlite3.Connection, event: dict) -> None:
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    db.upsert_project(conn, str(project_id), {
        "status": _STATUS_COMPLETED,
        "current_phase": "completed",
        "updated_at": ts,
    })
    logger.debug("projector: applied wicked.project.completed project_id=%r", project_id)


def _task_created(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.task.created → tasks row UPSERT.

    Payload shape (mirrors TaskCreate metadata envelope from _event_schema.py):
      task_id       TEXT — required; the native task UUID
      session_id    TEXT — required; the Claude session that created the task
      subject       TEXT — task title / subject line
      status        TEXT — 'pending' | 'in_progress' | 'completed' (default 'pending')
      chain_id      TEXT — optional crew chain (metadata.chain_id)
      event_type    TEXT — optional task metadata.event_type
      metadata      dict — full enriched metadata dict; stored as JSON text

    Idempotent: re-projecting the same event yields identical row state.
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    task_id, ok = _require(payload, "task_id", et)
    if not ok:
        return
    session_id, ok = _require(payload, "session_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    db.upsert_task(conn, str(task_id), {
        "session_id": str(session_id),
        "subject": _opt(payload, "subject", ""),
        "status": _opt(payload, "status", "pending"),
        "chain_id": _opt(payload, "chain_id"),
        "event_type": _opt(payload, "event_type"),
        "metadata": _opt(payload, "metadata"),
        "created_at": ts,
        "updated_at": ts,
    })
    logger.debug("projector: applied wicked.task.created task_id=%r", task_id)


def _task_updated(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.task.updated → tasks row delta update.

    Payload shape:
      task_id    TEXT — required
      session_id TEXT — required (carries session even on update for routing)
      status     TEXT — optional; only applied when present
      subject    TEXT — optional delta
      chain_id   TEXT — optional delta
      event_type TEXT — optional delta
      metadata   dict — optional; merged into existing metadata when present

    Last-write-wins for each supplied field.  Missing keys leave existing
    column values untouched (handled by db.upsert_task's INSERT OR IGNORE +
    UPDATE pattern).
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    task_id, ok = _require(payload, "task_id", et)
    if not ok:
        return
    session_id, ok = _require(payload, "session_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()

    # Guard against out-of-order bus events that would regress task status.
    # Example: created(pending) → completed → updated(in_progress) must NOT
    # overwrite the completed row.  Check current DB state before applying.
    new_status = _opt(payload, "status")
    if new_status is not None:
        current_row = db.get_task(conn, str(task_id))
        if current_row is not None:
            current_rank = _STATUS_RANK.get(current_row.get("status", ""), -1)
            new_rank = _STATUS_RANK.get(str(new_status), -1)
            if new_rank < current_rank:
                logger.info(
                    "projector: skipping wicked.task.updated — status regression refused "
                    "(current=%r, incoming=%r)",
                    current_row.get("status"), new_status,
                )
                return

    fields: dict = {"session_id": str(session_id), "updated_at": ts}
    for key in ("subject", "status", "chain_id", "event_type", "metadata"):
        val = _opt(payload, key)
        if val is not None:
            fields[key] = val
    db.upsert_task(conn, str(task_id), fields)
    logger.debug("projector: applied wicked.task.updated task_id=%r", task_id)


def _task_completed(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.task.completed → tasks row with status='completed'.

    Emitted by the TaskCompleted hook (hooks/scripts/task_completed.py).
    Payload must carry task_id + session_id; status is forced to 'completed'.
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    task_id, ok = _require(payload, "task_id", et)
    if not ok:
        return
    session_id, ok = _require(payload, "session_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    fields: dict = {
        "session_id": str(session_id),
        "status": "completed",
        "updated_at": ts,
    }
    # Propagate any extra enrichment that arrived at completion time.
    for key in ("subject", "chain_id", "event_type", "metadata"):
        val = _opt(payload, key)
        if val is not None:
            fields[key] = val
    db.upsert_task(conn, str(task_id), fields)
    logger.debug("projector: applied wicked.task.completed task_id=%r", task_id)


def _crew_yolo_revoked(conn: sqlite3.Connection, event: dict) -> None:
    """Audit-only: increment revoke counter and record reason.

    Project resolution: payload.project_id → projects.id; fallback to
    payload.project which may be the id or directory basename per contract.
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id = _opt(payload, "project_id") or _opt(payload, "project")
    if not project_id:
        logger.warning(
            "projector: required key 'project_id'/'project' missing in %s — treating as ignored",
            et,
        )
        return
    count, ok = _require(payload, "revoked_count", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    db.upsert_project(conn, str(project_id), {
        "yolo_revoked_count": count,
        "last_revoke_reason": _opt(payload, "revoke_reason"),
        "updated_at": ts,
    })
    logger.debug(
        "projector: applied wicked.crew.yolo_revoked project_id=%r count=%r",
        project_id, count,
    )


# --- dispatch table --------------------------------------------------------

_HANDLERS: dict[str, Callable[[sqlite3.Connection, dict], None]] = {
    "wicked.project.created": _project_created,
    "wicked.project.complexity_scored": _project_complexity_scored,
    "wicked.phase.transitioned": _phase_transitioned,
    "wicked.phase.auto_advanced": _phase_auto_advanced,
    "wicked.gate.decided": _gate_decided,
    "wicked.rework.triggered": _rework_triggered,
    "wicked.project.completed": _project_completed,
    "wicked.crew.yolo_revoked": _crew_yolo_revoked,
    # Stream 1 — #596 v8-PR-2: task state projection
    "wicked.task.created": _task_created,
    "wicked.task.updated": _task_updated,
    "wicked.task.completed": _task_completed,
}


# --- public API ------------------------------------------------------------

def project_event(conn: sqlite3.Connection, event: dict) -> str:
    """Dispatch *event* via ``_HANDLERS`` and return ``'applied'`` | ``'ignored'`` | ``'error'``.

    Never raises (Decision #8).  Caller passes the return value to
    ``db.append_event_log``.  Re-projecting the same event is idempotent
    (Decision #6).
    """
    event_type: str = event.get("event_type", "")
    handler = _HANDLERS.get(event_type)
    if handler is None:
        logger.debug("projector: unknown event_type=%r — ignored", event_type)
        return _IGNORED
    try:
        handler(conn, event)
        return _APPLIED
    except Exception as exc:  # noqa: BLE001 — intentional catch-all; never propagate
        logger.error(
            "projector: error handling event_type=%r event_id=%r: %s",
            event_type,
            event.get("event_id"),
            exc,
            exc_info=True,
        )
        return _ERROR
