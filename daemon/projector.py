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
from daemon._internal import IllegalPhaseTransition, transition_phase

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

# One-time WARN latch for the `_bus` ImportError path (#753).  The first time
# `_dispatch_log_appended` (or any future cutover-site handler that imports
# `_bus_as_truth_enabled`) cannot import the helper, we log a single WARN so
# operators see the misconfiguration in logs.  Subsequent calls keep the same
# fail-open behaviour but stay silent — re-logging on every projection run
# would flood the log under sustained traffic.
_BUS_IMPORT_WARNED = False


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
    #
    # Drives event: "approve" against the existing source-phase row.  The
    # historical bus stream does NOT emit a separate "phase started" event
    # before the gate decision, so the source row may legitimately be at
    # state='pending' (created lazily by an earlier wicked.gate.decided
    # APPROVE that only set gate metadata).  Forcing transition_phase("approve")
    # here would reject those pending→approved completions even though they
    # are the canonical projector behaviour today (#614 split decision).
    # Keep upsert_phase: vocabulary still enforced, graph enforcement is the
    # writer's responsibility at the event source not the projector.
    db.upsert_phase(conn, str(project_id), str(phase_from), {
        "state": _STATE_APPROVED,
        "terminal_at": ts,
        "updated_at": ts,
    })
    # Target phase → active (when present).
    # Drives event: "start" — graph-enforced.  Either the row does not exist
    # yet (INSERT fallback inside transition_phase) or it is at PENDING
    # (start→active is the only legal move) or it is already ACTIVE
    # (idempotent replay short-circuit).  Any other current state would be a
    # real bug and IllegalPhaseTransition surfaces it.
    if phase_to is not None:
        transition_phase(
            conn,
            str(project_id),
            str(phase_to),
            new_state=_STATE_ACTIVE,
            event="start",
            extra_fields={"started_at": ts, "updated_at": ts},
        )
    # Advance project pointer.
    current = str(phase_to) if phase_to is not None else str(phase_from)
    db.upsert_project(conn, str(project_id), {"current_phase": current, "updated_at": ts})
    logger.debug(
        "projector: applied %s project_id=%r %r -> %r", et, project_id, phase_from, phase_to
    )

    # Site W10b fan-out (#746): when the transition is SKIPPED, ALSO
    # materialise phases/{phase_from}/status.md from the same event.
    # Gated on WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS.  Wrapped in
    # try/except so a status-md write failure NEVER taints the DB-row
    # work above (Decision #8).
    try:
        if str(_opt(payload, "gate_result", "")).upper() == "SKIPPED":
            _phase_skipped_status_md(conn, event)
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        logger.exception(
            "projector: _phase_skipped_status_md fan-out raised — "
            "DB-row projection preserved; status.md may not have been written"
        )


def _phase_skipped_status_md(conn: sqlite3.Connection, event: dict) -> None:
    """Materialise phases/{phase}/status.md for a SKIPPED phase transition.

    Site W10b of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS``.  Mirrors the markdown
    shape that ``phase_manager.skip_phase`` writes at line 4188 so
    projection and direct-write paths produce byte-identical output.

    Payload contract (from skip_phase emit):
      project_id, phase_from (the phase being skipped),
      gate_result == "SKIPPED" (the SKIPPED sentinel),
      approver, skip_reason, skipped_at.

    Idempotency: content-hash short-circuit on rewrite.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("SKIPPED_PHASE_STATUS")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    project_id = payload.get("project_id")
    phase_from = payload.get("phase_from")
    if not project_id or not phase_from:
        return

    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: status.md SKIPPED — project %r has no directory in DB; "
            "skipping",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    target = project_dir / "phases" / str(phase_from) / "status.md"

    approver = payload.get("approver", "auto")
    skip_reason = payload.get("skip_reason", "")
    skipped_at = payload.get("skipped_at", "")

    body = (
        f"---\n"
        f"phase: {phase_from}\n"
        f"status: skipped\n"
        f"skipped_at: {skipped_at}\n"
        f"approved_by: {approver}\n"
        f"---\n\n"
        f"# {str(phase_from).replace('-', ' ').title()} Phase — Skipped\n\n"
        f"**Reason**: {skip_reason or 'Not applicable for this project scope'}\n\n"
        f"**Approved by**: {approver}\n"
    )
    candidate_bytes = body.encode("utf-8")

    import hashlib
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: status.md SKIPPED — content hash matches "
                    "existing %s; skipping rewrite", target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: status.md SKIPPED — could not read %s for "
            "idempotency check: %s; proceeding to write", target, exc,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: status.md SKIPPED — write failed at %s: %s",
            target, exc,
        )
        return

    logger.debug(
        "projector: applied status.md SKIPPED projection "
        "project_id=%r phase=%r path=%s",
        project_id, phase_from, target,
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

    # Drives event: "approve" against the auto-advanced phase row.  Same
    # rationale as the phase_from branch in _phase_transitioned (#614): the
    # source bus stream may not have emitted a "start" before this auto-advance,
    # so the row could be at pending.  Vocabulary check is sufficient here;
    # graph enforcement at the projector boundary would reject the canonical
    # auto-advance pattern.
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
    gate_fields: dict = {
        "gate_verdict": result,
        "gate_score": _opt(payload, "score"),
        "gate_reviewer": _opt(payload, "reviewer"),
        "updated_at": ts,
    }
    if str(result) == _VERDICT_REJECT:
        # Drives event: "reject" — graph-enforced.  REJECT is only legal
        # against an ACTIVE row (or a brand-new INSERT when the gate fires
        # before any prior projection of the phase, which the transition_phase
        # fallback handles cleanly).  IllegalPhaseTransition surfaces the
        # invalid pending→rejected case as a real bug rather than silently
        # corrupting state.
        gate_fields["terminal_at"] = ts
        transition_phase(
            conn,
            str(project_id),
            str(phase),
            new_state=_STATE_REJECTED,
            event="reject",
            extra_fields=gate_fields,
        )
    else:
        # Non-REJECT verdicts only annotate gate metadata; no state mutation,
        # so vocabulary-only upsert is correct.
        db.upsert_phase(conn, str(project_id), str(phase), gate_fields)
    logger.debug(
        "projector: applied wicked.gate.decided project_id=%r phase=%r result=%r",
        project_id, phase, result,
    )
    # Site 4 of bus-cutover (#746, #778) fan-out: disk projection for
    # gate-result.json.  DB-row work above always runs; disk projection runs
    # only when WG_BUS_AS_TRUTH_GATE_RESULT=on and the payload carries the
    # full gate_result dict (PR-2 / #779 widens the emit).  Wrapped in
    # try/except so disk failures NEVER break the DB-row projection
    # (Decision #6 idempotency, Decision #8 never-raise).
    try:
        _gate_decided_disk(conn, event)
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        logger.exception(
            "projector: _gate_decided_disk fan-out raised — DB-row "
            "projection preserved; disk projection skipped"
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
    # Drives event: "rework" — graph-enforced.  Only legal from REJECTED.
    # On replay the phase is already ACTIVE and transition_phase short-circuits
    # via its idempotent same-state guard.  rework_iterations rides along in
    # extra_fields so the whole projection is one transactional upsert.
    transition_phase(
        conn,
        str(project_id),
        str(phase),
        new_state=_STATE_ACTIVE,
        event="rework",
        extra_fields={"rework_iterations": iters, "updated_at": ts},
    )
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


# --- AC handlers (v8-PR-5 #591) -------------------------------------------

def _ac_declared(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.ac.declared → upsert into acceptance_criteria.

    Payload shape:
      project_id   TEXT — required
      ac_id        TEXT — required; canonical identifier (e.g. "AC-3")
      statement    TEXT — human-readable description
      verification TEXT — optional check function name

    Idempotent: re-projecting the same event updates statement + verification
    (see db.upsert_ac UPSERT semantics).
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    ac_id, ok = _require(payload, "ac_id", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    db.upsert_ac(
        conn,
        str(project_id),
        str(ac_id),
        statement=str(_opt(payload, "statement") or ""),
        verification=_opt(payload, "verification") or None,  # type: ignore[arg-type]
        created_at=ts,
    )
    logger.debug(
        "projector: applied wicked.ac.declared project_id=%r ac_id=%r",
        project_id, ac_id,
    )


# --- bus-cutover Site 1 (#746) handler ------------------------------------

def _dispatch_log_appended(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.dispatch.log_entry_appended → dispatch_log_entries.

    Site 1 of the bus-cutover staging plan (#746).  Behaviour is gated on
    `WG_BUS_AS_TRUTH_DISPATCH_LOG` via the `_bus_as_truth_enabled()` helper:

      * flag-off (default): handler is a no-op.  The projector wrapper
        still records the event_log row as ``applied`` (event is projected
        per Decision #6 — reconciliation does not flag the event as
        orphan); the projection table is intentionally untouched while
        the disk file remains source of truth.

      * flag-on: INSERT OR IGNORE one row per (event_id) into
        ``dispatch_log_entries``.  Idempotent on duplicate event_id per
        Decision #6 — replaying the same event yields the same row state.

    HMAC policy (Council Condition C7): the emitter (`dispatch_log.append`)
    signs; this projector stores the verbatim ``hmac`` and ``hmac_present``
    fields from the event payload.  Verification still happens against
    the on-disk JSONL via `dispatch_log.check_orphan` — that path is
    untouched at `dispatch_log.py:476-547`.
    """
    # Defer import to avoid a hard dependency at module load — the projector
    # boots in environments where scripts/_bus.py may not be on sys.path
    # (e.g. some test harnesses).  Failure to import is treated as flag-off
    # so the dual-write contract (disk truth, bus observability) keeps the
    # projection table empty and the wrapper still records the event_log row
    # as `applied`.
    #
    # Observability promotion (#753): the previous implementation swallowed
    # the ImportError silently, which made a real misconfiguration (e.g.
    # PYTHONPATH missing scripts/) invisible.  We now WARN exactly once per
    # process via the `_BUS_IMPORT_WARNED` module-level latch — operators
    # see the misconfiguration in logs without sustained-traffic spam.
    # Cutover Sites 2-5 MUST inherit this WARN-once pattern, not the silent
    # skip, per the staging plan (docs/v9/bus-cutover-staging-plan.md §5).
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        # Site 2 (#746) parameterized the helper.  Pass the explicit site
        # name even though it is the default, because Site 2's two new
        # handlers also live in this module and pass their own site names —
        # making the dispatch-log call explicit avoids any reader confusion
        # over which env var this handler gates on.
        flag_on = _bus_as_truth_enabled("DISPATCH_LOG")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_DISPATCH_LOG "
                "as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open for any other error
        flag_on = False

    if not flag_on:
        # No-op under flag-off — projection table intentionally untouched.
        # The wrapper records the event_log row as `applied` (Decision #6
        # contract: every projected event gets one row) so reconcilers do
        # not flag this as orphan.  Dual-write contract: disk file is
        # truth, bus emit is observability.
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    gate, ok = _require(payload, "gate", et)
    if not ok:
        return
    reviewer, ok = _require(payload, "reviewer", et)
    if not ok:
        return
    dispatch_id, ok = _require(payload, "dispatch_id", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    event_id = event.get("event_id")
    if not isinstance(event_id, int):
        logger.warning(
            "projector: wicked.dispatch.log_entry_appended missing event_id — ignored"
        )
        return

    # `dispatched_at` arrives as an ISO-8601 string per dispatch_log.py:299.
    # Store as INTEGER epoch seconds so the table is queryable by range
    # without ISO comparison gymnastics (council note on the schema add).
    dispatched_at_iso = _opt(payload, "dispatched_at")
    dispatched_at = _to_epoch(dispatched_at_iso) or _now()

    dispatcher_agent = _opt(payload, "dispatcher_agent", "")
    expected_result_path = _opt(payload, "expected_result_path", "")
    hmac_value = _opt(payload, "hmac")
    hmac_present_flag = 1 if _opt(payload, "hmac_present") else 0

    conn.execute(
        """
        INSERT OR IGNORE INTO dispatch_log_entries
            (event_id, project_id, phase, gate, reviewer, dispatch_id,
             dispatcher_agent, expected_result_path, dispatched_at,
             hmac, hmac_present, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(event_id),
            str(project_id),
            str(phase),
            str(gate),
            str(reviewer),
            str(dispatch_id),
            str(dispatcher_agent),
            str(expected_result_path),
            int(dispatched_at),
            str(hmac_value) if hmac_value is not None else None,
            int(hmac_present_flag),
            str(raw_payload),
        ),
    )
    logger.debug(
        "projector: applied wicked.dispatch.log_entry_appended "
        "project_id=%r phase=%r gate=%r event_id=%r",
        project_id, phase, gate, event_id,
    )


# --- bus-cutover Site 2 (#746) handlers -----------------------------------
#
# Council Condition C8 (DO NOT extract a base class at N=2): the two handlers
# below are deliberate twins of `_dispatch_log_appended` (Site 1) — sharing
# the same `_BUS_IMPORT_WARNED` latch (Council Condition C7), the same
# import-fail = flag-off fallback, and the same INSERT OR IGNORE keyed on
# event_id (Decision #6 idempotency).  They differ in:
#
#   * which env var name they pass to `_bus_as_truth_enabled()`
#     (`CONSENSUS_REPORT` vs `CONSENSUS_EVIDENCE`)
#   * which projection table they target (`consensus_reports` vs
#     `consensus_evidence`) — the schemas differ enough to keep separate
#   * their required-key sets (report has `decision/confidence/rounds`;
#     evidence has `result/reason`)
#
# Wait until Site 3 lands a third instance before refactoring shared
# behaviour into a base class — at N=3 the actual divergence shape is
# observable, at N=2 abstraction risks freezing the wrong contract.


def _consensus_disk_write(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    phase: str,
    raw_payload: str,
    relative_filename: str,
    handler_name: str,
) -> None:
    """Materialise a consensus artifact on disk from the raw_payload bytes.

    Site 2 disk-projection helper (#746) — added by the legacy-direct-write
    deletion PR.  The SQL projection (consensus_reports / consensus_evidence
    tables) was historically the only output of these handlers; the on-disk
    JSON was written by ``consensus_gate._write_consensus_report`` /
    ``_write_consensus_evidence``.  After the legacy disk writes were
    deleted, this helper takes over the disk-side projection so:

      * reconcile_v2's drift detector still sees the file in
        ``phases/{phase}/`` (otherwise every consensus event becomes
        ``event-without-projection`` drift).
      * synthetic_drift.py's expected-projection contract still holds.
      * test_consensus_gate.py's ``read_text()`` assertions still resolve.

    Mirrors Site 5's ``_conditions_manifest_from_gate_decided`` shape:
    content-hash idempotency on rewrite, atomic temp+rename write.

    The caller is responsible for resolving ``project_id``/``phase`` and
    confirming the bus-as-truth flag is on; this helper is a pure
    file-write utility.
    """
    # Resolve project_dir from the DB (mirrors Sites 3-5 pattern).
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: %s — project %r has no directory in DB; skipping "
            "disk write (project must be projected via wicked.project.created "
            "before Site 2 disk projection can write files)",
            handler_name, project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    phase_dir = project_dir / "phases" / str(phase)
    target = phase_dir / relative_filename

    # raw_payload is already the canonical on-disk bytes (json.dumps with
    # indent=2) per Council Condition C10.  Encode once for hash + write.
    import hashlib
    candidate_bytes = str(raw_payload).encode("utf-8")

    # Content-hash idempotency: skip rewrite when existing bytes match.
    # Required because the daemon consumer does not dedupe before calling
    # handlers (append_event_log uses INSERT OR REPLACE — handler fires
    # for every event in the batch).
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: %s — content hash matches existing %s; "
                    "skipping rewrite",
                    handler_name, target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: %s — could not read existing %s for idempotency "
            "check: %s; proceeding to write",
            handler_name, target, exc,
        )

    # Atomic write: temp file + rename.  Rename is atomic on POSIX;
    # readers either see the old bytes or the new bytes, never partial.
    try:
        phase_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: %s — could not write %s: %s",
            handler_name, target, exc,
        )
        return

    logger.debug(
        "projector: applied %s disk projection "
        "project_id=%r phase=%r path=%s",
        handler_name, project_id, phase, target,
    )


def _consensus_report_created(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.report_created → consensus_reports + disk.

    Site 2 of the bus-cutover staging plan (#746).  Behaviour is gated on
    `WG_BUS_AS_TRUTH_CONSENSUS_REPORT` via
    `_bus_as_truth_enabled("CONSENSUS_REPORT")`.  CONSENSUS_REPORT is in
    the default-ON shipped set (`_BUS_AS_TRUTH_DEFAULT_ON`), so an unset
    env var resolves to True; explicit ``"off"`` opts out.

      * flag-off (explicit ``"off"``): handler is a no-op.  The projector
        wrapper still records the event_log row as `applied`
        (Decision #6).  Both the SQL projection table AND the disk
        materialisation are skipped — operators get a unified opt-out.
      * flag-on (default OR explicit ``"on"``): INSERT OR IGNORE one row
        per (event_id) into `consensus_reports` AND materialise
        consensus-report.json on disk via `_consensus_disk_write` (the
        legacy direct-write in ``consensus_gate._write_consensus_report``
        was deleted in PR #798; the projector is now the canonical writer).

    The `raw_payload` field is REQUIRED per Council Condition C10 — it
    carries the canonical on-disk bytes (json.dumps with indent=2) so the
    projector reproduces `consensus-report.json` byte-for-byte.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("CONSENSUS_REPORT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    decision, ok = _require(payload, "decision", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    event_id = event.get("event_id")
    if not isinstance(event_id, int):
        logger.warning(
            "projector: wicked.consensus.report_created missing event_id — ignored"
        )
        return

    created_at = _to_epoch(event.get("created_at")) or _now()

    conn.execute(
        """
        INSERT OR IGNORE INTO consensus_reports
            (event_id, project_id, phase, decision, confidence,
             agreement_ratio, participants, rounds, created_at, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(event_id),
            str(project_id),
            str(phase),
            str(decision),
            _opt(payload, "confidence"),
            _opt(payload, "agreement_ratio"),
            _opt(payload, "participants"),
            _opt(payload, "rounds"),
            int(created_at),
            str(raw_payload),
        ),
    )
    logger.debug(
        "projector: applied wicked.consensus.report_created "
        "project_id=%r phase=%r event_id=%r",
        project_id, phase, event_id,
    )

    # Site 2 disk projection (#746): materialise consensus-report.json on
    # disk so reconcile_v2's drift detector + synthetic_drift contract +
    # test_consensus_gate's read_text() assertions still hold after the
    # legacy direct-write in consensus_gate._write_consensus_report was
    # deleted.  Wrapped so a disk-write failure NEVER taints the SQL
    # projection above (SQL row + drift event are still recorded).
    try:
        _consensus_disk_write(
            conn,
            project_id=str(project_id),
            phase=str(phase),
            raw_payload=str(raw_payload),
            relative_filename="consensus-report.json",
            handler_name="wicked.consensus.report_created",
        )
    except Exception as exc:  # noqa: BLE001 — fail-open for disk side-effect
        logger.warning(
            "projector: wicked.consensus.report_created disk projection "
            "raised — SQL projection still applied: %s", exc,
        )


def _consensus_evidence_recorded(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.evidence_recorded → consensus_evidence.

    Site 2 of the bus-cutover staging plan (#746).  Behaviour is gated on
    `WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE` via
    `_bus_as_truth_enabled("CONSENSUS_EVIDENCE")`.  Same idempotency and
    fail-open contract as the report handler above.

    Evidence emits ONLY fire on consensus REJECT outcomes (the two flags
    are independent — operators may flip one without the other).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("CONSENSUS_EVIDENCE")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001
        flag_on = False

    if not flag_on:
        return

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
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    event_id = event.get("event_id")
    if not isinstance(event_id, int):
        logger.warning(
            "projector: wicked.consensus.evidence_recorded missing event_id — ignored"
        )
        return

    created_at = _to_epoch(event.get("created_at")) or _now()

    conn.execute(
        """
        INSERT OR IGNORE INTO consensus_evidence
            (event_id, project_id, phase, result, reason,
             consensus_confidence, agreement_ratio, participants,
             created_at, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(event_id),
            str(project_id),
            str(phase),
            str(result),
            _opt(payload, "reason"),
            _opt(payload, "consensus_confidence"),
            _opt(payload, "agreement_ratio"),
            _opt(payload, "participants"),
            int(created_at),
            str(raw_payload),
        ),
    )
    logger.debug(
        "projector: applied wicked.consensus.evidence_recorded "
        "project_id=%r phase=%r event_id=%r",
        project_id, phase, event_id,
    )

    # Site 2 disk projection (#746): materialise consensus-evidence.json
    # on disk so the drift detector + tests still see it after the legacy
    # direct-write in consensus_gate._write_consensus_evidence was deleted.
    # Same fail-open envelope as the report handler above.
    try:
        _consensus_disk_write(
            conn,
            project_id=str(project_id),
            phase=str(phase),
            raw_payload=str(raw_payload),
            relative_filename="consensus-evidence.json",
            handler_name="wicked.consensus.evidence_recorded",
        )
    except Exception as exc:  # noqa: BLE001 — fail-open for disk side-effect
        logger.warning(
            "projector: wicked.consensus.evidence_recorded disk projection "
            "raised — SQL projection still applied: %s", exc,
        )


# --- bus-cutover Site 3 (#768, #770) handlers -----------------------------------
#
# Two handlers materialise phases/{phase}/reviewer-report.md from bus events,
# producing the same on-disk file that hooks/scripts/post_tool.py's
# _write_reviewer_report / _write_pending_reviewer_report write directly.
#
# Payload contract (#770 — per-section events):
#   raw_payload = the just-written content (yaml_block), NOT the cumulative
#   file.  Matches Site 1 (wicked.dispatch.log_entry_appended) per-entry shape.
#   The _consensus_gate_completed handler applies branch detection:
#   - create (file absent): write raw_payload as the full new file.
#   - append (file exists): read existing + separator + raw_payload.
#   _consensus_gate_pending: raw_payload is always the full pending template
#   (this branch only creates fresh files, so shape is unchanged).
#
# Idempotency strategy (Decision #6 — with #770 correction):
#   The daemon consumer does NOT deduplicate events before calling handlers
#   (append_event_log uses INSERT OR REPLACE, not INSERT OR IGNORE — the
#   handler is called for every event in the batch).  The append branch
#   therefore guards with a substring scan: check whether
#   (separator + raw_payload) is already in the existing file; skip if
#   present.  Create and pending branches are idempotent by nature
#   (writing the same bytes twice yields the same file).
#
# project_dir resolution:
#   The payload carries project_id + phase.  We look up the project row in the
#   DB (db.get_project) to find the `directory` field.  If the project row is
#   absent or directory is NULL, we log a warning and skip — never infer a path
#   from local filesystem conventions in the daemon.
#
# Council Condition C8 addendum (N=3):
#   With Site 3 we have three handler pairs.  The shared import pattern
#   (_BUS_IMPORT_WARNED latch, import-fail = flag-off) is now clearly
#   stable.  ADR for N=3 base-class extraction is deferred to Issue #771.

_REVIEWER_REPORT_SEPARATOR = "\n\n---\n## Consensus Gate Evaluation\n\n"


def _consensus_gate_completed(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.gate_completed → reviewer-report.md on disk.

    Site 3 of the bus-cutover staging plan (#746, #768, #770, PR #799).
    Gated on ``WG_BUS_AS_TRUTH_REVIEWER_REPORT`` via
    ``_bus_as_truth_enabled("REVIEWER_REPORT")``:

      * flag-off (default): handler is a no-op.  The projector wrapper still
        records the event_log row as ``applied`` (Decision #6).
      * flag-on: materialise reviewer-report.md from the per-section payload.
        Branch decision is made HERE based on disk state at projection time
        (NOT from ``payload.branch`` from the source side).  Pre-PR-#799 the
        source-side check raced the projector when the legacy direct-write
        was deleted — see the brain memory
        ``bus-cutover-legacy-write-deletion-is-per-site-architecture``.

    Branch logic (PR #799 — projector self-deciding):
        - file does not exist → create: write raw_payload as the full new file.
        - file exists          → append: prepend the standard
          ``_REVIEWER_REPORT_SEPARATOR``, then raw_payload.  The legacy
          source-side branch hint (``payload.branch``) is now informational
          only; the projector ignores it for the actual write decision so
          replays after legacy-write deletion stay consistent.

    Idempotency on the append branch (Decision #6 + #770):
      The daemon consumer calls project_event for every event in a batch
      without a prior event_id lookup (``append_event_log`` uses INSERT OR
      REPLACE, not INSERT OR IGNORE — it does not short-circuit before the
      handler fires).  Naive re-application of an append event would
      double-append.  Guard: check whether (separator + raw_payload) is
      already a substring of the existing file; skip if present.  This is
      not redundant dead code — it is the only layer that prevents duplicate
      appends on replay.

    project_dir is resolved via db.get_project(conn, project_id).directory.
    If the project row is absent or directory is NULL, the handler warns and
    skips (never infers filesystem paths in the daemon).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("REVIEWER_REPORT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    # Resolve project_dir from the DB.
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.consensus.gate_completed — project %r has no "
            "directory in DB; skipping file write (project must be projected "
            "via wicked.project.created before Site 3 handlers can write files)",
            project_id,
        )
        return

    phase_dir = Path(project_row["directory"]) / "phases" / str(phase)
    report_path = phase_dir / "reviewer-report.md"

    # Branch decision (PR #799): make it HERE from disk state, not from
    # ``payload.branch``.  After legacy-write deletion the source side no
    # longer writes synchronously, so a source-side ``report_path.exists()``
    # check would race the projector.  Projector-side decision is
    # order-correct because events apply in event_id order.
    branch_hint = _opt(payload, "branch", "auto")

    try:
        if report_path.exists():
            existing = report_path.read_text(encoding="utf-8")
            payload_str = str(raw_payload)
            section = _REVIEWER_REPORT_SEPARATOR + payload_str

            # Idempotency 1: file content equals the raw_payload exactly
            # (create-event replay case — projector wrote it before, now
            # firing again).  Required after PR #799 made the projector
            # self-deciding: a replay of the very first event sees the
            # file already exists, but the payload was never appended
            # (it WAS the create write), so the substring check below
            # would miss this case and double-append.
            if existing == payload_str:
                logger.debug(
                    "projector: wicked.consensus.gate_completed — file "
                    "matches raw_payload exactly (create-replay); "
                    "skipping",
                )
                return

            # Idempotency 2: this section was already appended (append-
            # event replay case).  Required because the daemon consumer
            # does not deduplicate before calling handlers
            # (append_event_log uses INSERT OR REPLACE, not INSERT OR
            # IGNORE — handler fires for every event in the batch, #770).
            if section in existing:
                logger.debug(
                    "projector: wicked.consensus.gate_completed — section "
                    "already present in %s; skipping duplicate append",
                    report_path,
                )
                return

            report_path.write_text(existing + section, encoding="utf-8")
        else:
            # Create: write raw_payload as fresh file.  The first event
            # for a (project, phase) lands here regardless of source-side
            # branch hint.
            phase_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(str(raw_payload), encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "projector: wicked.consensus.gate_completed — could not write %s: %s",
            report_path,
            exc,
        )
        return

    logger.debug(
        "projector: applied wicked.consensus.gate_completed "
        "project_id=%r phase=%r branch_hint=%r report_path=%s",
        project_id, phase, branch_hint, report_path,
    )


def _consensus_gate_pending(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.gate_pending → reviewer-report.md on disk.

    Site 3 of the bus-cutover staging plan (#746, #768).  Behaviour is gated
    on ``WG_BUS_AS_TRUTH_REVIEWER_REPORT`` via
    ``_bus_as_truth_enabled("REVIEWER_REPORT")``:

      * flag-off (default): handler is a no-op (same Decision #6 contract).
      * flag-on: write raw_payload (pending template) to reviewer-report.md
        ONLY when the file does not already exist.  Mirrors
        _write_pending_reviewer_report's "Don't clobber an existing report"
        invariant byte-for-byte.

    NO-OP when file already exists — this is by design.  The pending event
    fires on consensus evaluation failure and should never overwrite a real
    gate result that arrived later (or was written by the legacy hook).

    project_dir is resolved via db.get_project(conn, project_id).directory.
    Same warning + skip behaviour as _consensus_gate_completed on absent row.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("REVIEWER_REPORT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    # Resolve project_dir from the DB.
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.consensus.gate_pending — project %r has no "
            "directory in DB; skipping file write",
            project_id,
        )
        return

    phase_dir = Path(project_row["directory"]) / "phases" / str(phase)
    report_path = phase_dir / "reviewer-report.md"

    # NO-OP when file already exists — mirrors _write_pending_reviewer_report's
    # "Don't clobber an existing report" invariant exactly.
    if report_path.exists():
        logger.debug(
            "projector: wicked.consensus.gate_pending NO-OP — %s already exists",
            report_path,
        )
        return

    try:
        phase_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(str(raw_payload), encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "projector: wicked.consensus.gate_pending — could not write %s: %s",
            report_path,
            exc,
        )
        return

    logger.debug(
        "projector: applied wicked.consensus.gate_pending "
        "project_id=%r phase=%r report_path=%s",
        project_id, phase, report_path,
    )


def _ac_evidence_linked(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.ac.evidence_linked → add row to ac_evidence.

    Payload shape:
      project_id    TEXT — required
      ac_id         TEXT — required
      evidence_ref  TEXT — required; file path, test ID, issue ref, or check name
      evidence_type TEXT — optional; inferred from evidence_ref when absent

    The AC row must exist (FK constraint).  If it doesn't — e.g. because
    wicked.ac.declared arrived out of order — the event is logged as ignored
    rather than raising.
    """
    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    ac_id, ok = _require(payload, "ac_id", et)
    if not ok:
        return
    evidence_ref, ok = _require(payload, "evidence_ref", et)
    if not ok:
        return
    ts = _to_epoch(event.get("created_at")) or _now()
    try:
        db.add_ac_evidence(
            conn,
            str(project_id),
            str(ac_id),
            str(evidence_ref),
            evidence_type=_opt(payload, "evidence_type") or None,  # type: ignore[arg-type]
            created_at=ts,
        )
    except Exception as exc:  # noqa: BLE001 — FK violation or other integrity error
        logger.warning(
            "projector: wicked.ac.evidence_linked skipped — AC row missing or integrity "
            "error (project_id=%r, ac_id=%r, evidence_ref=%r): %s",
            project_id, ac_id, evidence_ref, exc,
        )
        return
    logger.debug(
        "projector: applied wicked.ac.evidence_linked project_id=%r ac_id=%r ref=%r",
        project_id, ac_id, evidence_ref,
    )


# --- Site 4 of bus-cutover (#746, #778): gate-result.json disk projection --
#
# Two handlers, both gated on WG_BUS_AS_TRUTH_GATE_RESULT via
# ``_bus_as_truth_enabled("GATE_RESULT")``:
#
#   * ``_gate_decided_disk``  — invoked from the tail of the existing
#     ``_gate_decided`` (DB-row handler).  Materialises gate-result.json
#     from the full gate_result dict carried in ``event["payload"]["data"]``.
#     PR-2 (#779) widens the emit to carry that key; until then this
#     handler is inert (early-returns with a debug log).
#
#   * ``_gate_blocked``       — registered fresh for ``wicked.gate.blocked``.
#     INERT no-op in PR-1: the file is already in REJECT state from the
#     wicked.gate.decided projection that fires immediately before
#     wicked.gate.blocked in approve_phase's REJECT branch.  Registered
#     so reconcile_v2._handler_available_for_file's conservative
#     "ALL event types must have handlers" rule passes for gate-result.json.
#
# Security floor on the projection path mirrors phase_manager._load_gate_result
# composition (AC-9 §5.4):
#   1. validate_gate_result(data)              — schema + sanitizer (embedded)
#   2. check_orphan(data, project_dir, phase)  — soft-window or strict reject
#   3. append_audit_entry(...)                 — every reject path
#
# Idempotency: content-hash on the full serialized JSON.  When the file
# already matches the new payload byte-for-byte, the write is skipped.

def _gate_decided_disk(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.gate.decided → phases/{phase}/gate-result.json on disk.

    Site 4 of the bus-cutover staging plan (#746, #778).  Behaviour gated
    on ``WG_BUS_AS_TRUTH_GATE_RESULT`` via
    ``_bus_as_truth_enabled("GATE_RESULT")``:

      * flag-off (default): no-op.
      * flag-on: validate the full gate_result dict from the event payload,
        run the AC-9 §5.4 security floor (schema + sanitizer via
        ``validate_gate_result``, dispatch-log orphan check via
        ``check_orphan``, audit log on every reject path), then write
        ``gate-result.json`` with content-hash idempotency.

    Payload contract (PR-2 / #779 ships the emit widening):
      ``payload["data"]`` — the full gate_result dict that
      ``phase_manager._persist_gate_result`` would otherwise write.
      When absent (current 5-field emit at phase_manager.py:3931),
      the handler logs at debug level and returns inertly.

    Idempotency guard: content-hash on the canonical JSON serialization.
    The daemon consumer does not deduplicate before calling handlers
    (``append_event_log`` uses INSERT OR REPLACE), so without this guard
    every replay would rewrite the file.

    project_dir resolved via ``db.get_project(conn, project_id).directory``.
    Absent row or NULL directory → warn and skip (mirrors Site 3).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("GATE_RESULT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return

    # Payload contract: the full gate_result dict ships under "data".
    # Until PR-2 (#779) widens the emit, this key is absent and the
    # handler returns inertly — flag-on can be enabled safely.
    data = payload.get("data")
    if not isinstance(data, dict):
        logger.debug(
            "projector: wicked.gate.decided disk projection — payload lacks "
            "'data' dict (project_id=%r phase=%r); inert until #779 ships "
            "emit-payload widening",
            project_id, phase,
        )
        return

    # Resolve project_dir from the DB.
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.gate.decided disk projection — project %r has "
            "no directory in DB; skipping file write (project must be "
            "projected via wicked.project.created before Site 4 handlers can "
            "write files)",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    phase_dir = project_dir / "phases" / str(phase)
    target = phase_dir / "gate-result.json"

    # Lazy imports — security floor modules + stdlib helpers only loaded
    # when the projection actually fires.  Keeps the import-time cost of
    # the projector module low for callers that never opt into Site 4.
    import json
    import hashlib
    try:
        from gate_result_schema import (
            GateResultAuthorizationError,
            GateResultSchemaError,
            validate_gate_result,
        )
        from gate_ingest_audit import append_audit_entry
        from dispatch_log import check_orphan, _get_strict_after_date
    except ImportError as exc:
        logger.warning(
            "projector: wicked.gate.decided disk projection — security "
            "floor modules unavailable: %s; skipping write to avoid "
            "shipping unvalidated bytes",
            exc,
        )
        return

    # Serialize candidate bytes once: used for hash compare, audit
    # raw_bytes, and the actual write.  Keeps the canonical form
    # consistent across all three.
    candidate_bytes = json.dumps(
        data, indent=2, sort_keys=True
    ).encode("utf-8")

    # Schema + sanitizer (sanitizer is embedded inside validate_gate_result
    # per AC-9 §5.4 composition; one call covers both).  Raise on either
    # → audit + skip write.  Surface the schema/content distinction in the
    # audit event tag so downstream tooling can triage.
    try:
        validate_gate_result(data)
    except GateResultSchemaError as exc:
        event_tag = (
            "sanitization_violation" if exc.violation_class == "content"
            else "schema_violation"
        )
        append_audit_entry(
            project_dir, str(phase),
            event=event_tag,
            reason=exc.reason,
            offending_field=exc.offending_field,
            offending_value=exc.offending_value_excerpt,
            raw_bytes=candidate_bytes,
        )
        logger.warning(
            "projector: wicked.gate.decided disk projection — schema/"
            "sanitizer violation (project_id=%r phase=%r): %s; audit "
            "entry written, file NOT updated",
            project_id, phase, exc.reason,
        )
        return

    # Orphan detection — soft-window allows fall-through with audit;
    # strict mode rejects the write.  Mirrors the composition in
    # ``phase_manager._load_gate_result`` byte-for-byte so the projection
    # path enforces the same security contract as direct writes.
    try:
        check_orphan(data, project_dir, str(phase))
    except GateResultAuthorizationError as exc:
        today = datetime.now(timezone.utc).date()
        if today >= _get_strict_after_date():
            append_audit_entry(
                project_dir, str(phase),
                event="unauthorized_dispatch",
                reason=exc.reason,
                offending_field=exc.offending_field,
                offending_value=exc.offending_value_excerpt,
                raw_bytes=candidate_bytes,
            )
            logger.warning(
                "projector: wicked.gate.decided disk projection — "
                "strict-mode orphan reject (project_id=%r phase=%r); "
                "audit entry written, file NOT updated",
                project_id, phase,
            )
            return
        # Soft window — audit as accepted_legacy and fall through to write.
        append_audit_entry(
            project_dir, str(phase),
            event="unauthorized_dispatch_accepted_legacy",
            reason=exc.reason,
            offending_field=exc.offending_field,
            offending_value=exc.offending_value_excerpt,
            raw_bytes=candidate_bytes,
        )

    # Content-hash idempotency: skip rewrite when existing bytes match.
    # Required because the daemon consumer does not dedupe before calling
    # handlers (append_event_log uses INSERT OR REPLACE — handler fires
    # for every event in the batch).  This is the ONLY layer preventing
    # gratuitous re-writes on replay.
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: wicked.gate.decided disk projection — "
                    "content hash matches existing %s; skipping rewrite",
                    target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: wicked.gate.decided disk projection — could not "
            "read existing %s for idempotency check: %s; proceeding to write",
            target, exc,
        )

    # Atomic write: temp file + rename.  Rename is atomic on POSIX;
    # readers either see the old bytes or the new bytes, never partial.
    try:
        phase_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: wicked.gate.decided disk projection — could not "
            "write %s: %s",
            target, exc,
        )
        return

    logger.debug(
        "projector: applied wicked.gate.decided disk projection "
        "project_id=%r phase=%r verdict=%r path=%s",
        project_id, phase, data.get("result") or data.get("verdict"), target,
    )

    # Site 5 fan-out (#746): when the verdict is CONDITIONAL and the
    # payload carries a non-empty conditions list, ALSO materialise
    # conditions-manifest.json from the same event.  One event, multiple
    # files — the new _PROJECTION_MAP shape (Dict[str, FrozenSet[str]])
    # makes this explicit.  Wrapped in try/except so a manifest-write
    # failure NEVER taints the gate-result.json projection above.
    try:
        _conditions_manifest_from_gate_decided(
            conn, project_dir, str(phase), data
        )
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        logger.exception(
            "projector: _conditions_manifest_from_gate_decided fan-out "
            "raised — gate-result.json projection preserved; "
            "conditions-manifest.json may not have been written"
        )


def _conditions_manifest_from_gate_decided(
    conn: sqlite3.Connection,
    project_dir: Path,
    phase: str,
    gate_data: dict,
) -> None:
    """Materialise conditions-manifest.json from a wicked.gate.decided event.

    Site 5 of the bus-cutover staging plan (#746).  Gated on
    ``WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST`` (separate flag from
    ``WG_BUS_AS_TRUTH_GATE_RESULT`` so operators can opt out of one
    cutover without disabling the other).

    Short-circuits when:
      * Flag is off.
      * Verdict is not CONDITIONAL.
      * ``gate_data["conditions"]`` is missing or empty.

    Mirrors the legacy ``phase_manager._write_conditions_manifest()``
    shape exactly (same condition_id format, same field set) so the
    direct-write and projector paths produce byte-identical output.
    Content-hash idempotency on rewrite, atomic temp+rename write —
    same pattern as ``_gate_decided_disk``'s gate-result.json materialisation.

    project_dir is supplied by the caller (already resolved from db).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("CONDITIONS_MANIFEST")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    verdict = gate_data.get("result") or gate_data.get("verdict")
    if verdict != "CONDITIONAL":
        # Only CONDITIONAL verdicts produce a conditions manifest.
        # APPROVE / REJECT have no conditions to materialise.
        return

    conditions_in = gate_data.get("conditions") or []
    if not conditions_in:
        # CONDITIONAL with empty conditions list is a degenerate case;
        # don't materialise an empty manifest (would be misleading).
        logger.debug(
            "projector: conditions-manifest projection — verdict CONDITIONAL "
            "but conditions list is empty; skipping write (phase=%r)", phase,
        )
        return

    # Mirror phase_manager._write_conditions_manifest's shape exactly so
    # direct-write and projector paths produce byte-identical output.
    # CONDITION-{i+1} ids and the same field set (description, verified=
    # False, resolution=None, verified_at=None).
    import json
    import hashlib
    from datetime import datetime, timezone

    def _utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    manifest = {
        "source_gate": phase,
        "created_at": gate_data.get("recorded_at") or _utc_iso(),
        "conditions": [
            {
                "id": f"CONDITION-{i + 1}",
                "description": c.get("description", c.get("condition", str(c)))
                if isinstance(c, dict) else str(c),
                "verified": False,
                "resolution": None,
                "verified_at": None,
            }
            for i, c in enumerate(conditions_in)
        ],
    }

    manifest_path = project_dir / "phases" / phase / "conditions-manifest.json"
    candidate_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    # Content-hash idempotency: skip when existing bytes match.
    try:
        if manifest_path.exists():
            existing_bytes = manifest_path.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: conditions-manifest projection — content hash "
                    "matches existing %s; skipping rewrite", manifest_path,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: conditions-manifest projection — could not read "
            "existing %s for idempotency check: %s; proceeding to write",
            manifest_path, exc,
        )

    # Atomic write.
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(manifest_path)
    except OSError as exc:
        logger.warning(
            "projector: conditions-manifest projection — could not write %s: %s",
            manifest_path, exc,
        )
        return

    logger.debug(
        "projector: applied conditions-manifest projection from "
        "wicked.gate.decided phase=%r conditions=%d path=%s",
        phase, len(conditions_in), manifest_path,
    )


def _condition_marked_cleared(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.condition.marked_cleared → resolution sidecar + manifest flip.

    Site 5 of the bus-cutover staging plan (#746).  Gated on
    ``WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST`` via
    ``_bus_as_truth_enabled("CONDITIONS_MANIFEST")``.

    Replays the same atomic two-step write order as
    ``conditions_manifest.mark_cleared()``:
      1. Write resolution sidecar (.resolution.json) with fsync.
      2. Mutate manifest in memory (flip verified=True, set resolution
         + verified_at fields).
      3. Atomically replace conditions-manifest.json.

    A crash between steps 1 and 3 leaves the sidecar on disk; the
    existing ``conditions_manifest.recover()`` reconciles such orphans
    by re-running step 3 from the sidecar's contents.

    Idempotency: when the manifest already shows the condition as
    verified with the matching resolution_ref, the handler skips both
    writes (no-op replay).  This is correct because the legacy direct
    write at ``conditions_manifest.mark_cleared()`` is also still
    running today (bus + direct-write coexist via this idempotency
    until the legacy path is removed in a future cleanup).

    project_dir resolved via db.get_project; absent row or NULL
    directory → warn and skip (mirrors Site 3 / 4 contract).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("CONDITIONS_MANIFEST")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    condition_id, ok = _require(payload, "condition_id", et)
    if not ok:
        return
    resolution_ref, ok = _require(payload, "resolution_ref", et)
    if not ok:
        return

    note = payload.get("note")
    verified_at = payload.get("verified_at")

    # Resolve project_dir from the DB.
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.condition.marked_cleared — project %r has no "
            "directory in DB; skipping (project must be projected via "
            "wicked.project.created before Site 5 handlers can write files)",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    manifest_path = project_dir / "phases" / str(phase) / "conditions-manifest.json"

    if not manifest_path.exists():
        # No manifest to update — handler is a no-op rather than an error.
        # The manifest is created by the gate.decided CONDITIONAL fan-out
        # above; if it's absent, the gate.decided event hasn't been
        # processed yet.  Replay will catch up when both events flow.
        logger.debug(
            "projector: wicked.condition.marked_cleared — manifest not yet "
            "materialised at %s; skipping (gate.decided likely pending)",
            manifest_path,
        )
        return

    # Lazy import: re-uses the production helper for the atomic write
    # ordering so a single source of truth governs the sidecar+manifest
    # crash semantics.
    import json
    try:
        from conditions_manifest import (  # type: ignore[import]
            atomic_write_json,
            _resolution_sidecar_path,
            _find_condition_index,
            _utc_now_iso,
        )
    except ImportError as exc:
        logger.warning(
            "projector: wicked.condition.marked_cleared — conditions_manifest "
            "module unavailable: %s; skipping projection",
            exc,
        )
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "projector: wicked.condition.marked_cleared — manifest unreadable "
            "at %s: %s; skipping projection",
            manifest_path, exc,
        )
        return

    try:
        idx = _find_condition_index(manifest, str(condition_id))
    except ValueError:
        logger.warning(
            "projector: wicked.condition.marked_cleared — condition %r not "
            "found in manifest %s; skipping (sidecar not orphaned because "
            "we never wrote one)",
            condition_id, manifest_path,
        )
        return

    # Idempotency: if already cleared with the same resolution, skip both writes.
    condition = manifest["conditions"][idx]
    if (
        condition.get("verified") is True
        and condition.get("resolution") == resolution_ref
    ):
        logger.debug(
            "projector: wicked.condition.marked_cleared — condition %r already "
            "cleared with matching resolution_ref; skipping replay",
            condition_id,
        )
        return

    timestamp = str(verified_at) if verified_at else _utc_now_iso()
    sidecar = {
        "condition_id": str(condition_id),
        "resolution_ref": str(resolution_ref),
        "note": note,
        "written_at": timestamp,
    }

    # Step 1: sidecar lands first (mirror mark_cleared crash-safety order).
    sidecar_path = _resolution_sidecar_path(manifest_path, str(condition_id))
    try:
        atomic_write_json(sidecar_path, sidecar)
    except OSError as exc:
        logger.warning(
            "projector: wicked.condition.marked_cleared — sidecar write "
            "failed at %s: %s; skipping manifest flip",
            sidecar_path, exc,
        )
        return

    # Step 2: mutate manifest in memory.
    condition["verified"] = True
    condition["resolution"] = str(resolution_ref)
    condition["verified_at"] = timestamp
    if note is not None:
        condition["resolution_note"] = note

    # Step 3: atomic manifest replace.
    try:
        atomic_write_json(manifest_path, manifest)
    except OSError as exc:
        logger.warning(
            "projector: wicked.condition.marked_cleared — manifest flip "
            "failed at %s: %s; sidecar persisted, recover() will reconcile",
            manifest_path, exc,
        )
        return

    logger.debug(
        "projector: applied wicked.condition.marked_cleared "
        "project_id=%r phase=%r condition_id=%r path=%s",
        project_id, phase, condition_id, manifest_path,
    )


def _inline_review_context_recorded(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.crew.inline_review_context_recorded → inline-review-context.md.

    Site W1 of bus-cutover wave-2 (#787).  Gated on
    ``WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT`` via
    ``_bus_as_truth_enabled("INLINE_REVIEW_CONTEXT")``.

    Solo-mode (``scripts/crew/solo_mode.py``) writes three artifacts
    when the inline-HITL path runs: gate-result.json,
    conditions-manifest.json (CONDITIONAL only), and inline-review-context.md.
    The first two are already covered by ``wicked.gate.decided`` via the
    payload-aware ``_PROJECTION_RESOLVERS["wicked.gate.decided"]`` resolver.
    This handler covers the third.

    Payload contract (from ``solo_mode._emit_inline_review_context``):
      project_id, phase, gate_name, bullets (list[str]), raw_response,
      gate_result_ref (str path).  The handler reconstructs the same
      markdown shape that ``solo_mode._write_inline_review_context``
      produces so projector and direct-write paths produce
      byte-identical output (modulo timestamps when the event includes
      ``recorded_at``).

    Idempotency: content-hash on the rendered markdown.  Atomic write
    via temp+rename.  project_dir resolved via db.get_project; absent
    row or NULL directory → warn and skip.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("INLINE_REVIEW_CONTEXT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    gate_name, ok = _require(payload, "gate_name", et)
    if not ok:
        return

    bullets = payload.get("bullets") or []
    raw_response = payload.get("raw_response") or ""
    gate_result_ref = payload.get("gate_result_ref") or "gate-result.json"
    recorded_at = payload.get("recorded_at")

    # Resolve project_dir.
    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.crew.inline_review_context_recorded — "
            "project %r has no directory in DB; skipping",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    target = project_dir / "phases" / str(phase) / "inline-review-context.md"

    # Render the markdown — mirrors solo_mode._write_inline_review_context.
    if recorded_at is None:
        from datetime import datetime, timezone
        recorded_at = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z",
        )

    lines = [
        f"# Inline Gate Review: {gate_name} ({phase})",
        "",
        f"**Timestamp**: {recorded_at}",
        f"**Gate**: {gate_name}",
        f"**Phase**: {phase}",
        "",
        "## Evidence Summary",
        "",
    ]
    for b in bullets:
        lines.append(f"- {b}")
    lines += [
        "",
        "## User Response",
        "",
        f"> {str(raw_response).strip()}",
        "",
        "## Artifact Reference",
        "",
        f"Gate result: `{gate_result_ref}`",
        "",
    ]

    candidate_bytes = "\n".join(lines).encode("utf-8")

    # Content-hash idempotency.
    import hashlib
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: inline-review-context — content hash matches "
                    "existing %s; skipping rewrite", target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: inline-review-context — could not read %s for "
            "idempotency check: %s; proceeding to write", target, exc,
        )

    # Atomic write.
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: inline-review-context — could not write %s: %s",
            target, exc,
        )
        return

    logger.debug(
        "projector: applied wicked.crew.inline_review_context_recorded "
        "project_id=%r phase=%r gate_name=%r path=%s",
        project_id, phase, gate_name, target,
    )


# --- Wave-2 Tranche B (#746): JSONL append-stream projectors ----------------
#
# Each handler below mirrors the JSONL-append shape from wave-1 Site 1
# (dispatch-log).  The source module's _atomic_append (or open("a"))
# writes one line; this handler replays the same line from raw_payload
# into the same path.  Idempotency: line-presence check (the projector
# must skip when the exact line is already present, since the daemon
# consumer doesn't dedupe before calling handlers).
#
# Common boilerplate is factored into ``_jsonl_append_projection`` —
# each handler resolves its file path + flag token + payload key and
# delegates the actual append + idempotency.


def _jsonl_append_projection(
    conn: sqlite3.Connection,
    event: dict,
    *,
    flag_token: str,
    relative_template: str,
    handler_name: str,
) -> None:
    """Shared body for wave-2 Tranche B JSONL-append projectors.

    Args:
        conn: daemon DB connection.
        event: bus event with payload carrying ``project_id``, ``phase``,
            and ``raw_payload`` (the JSONL line bytes, terminator-less).
        flag_token: WG_BUS_AS_TRUTH_<token> gate.
        relative_template: ``phases/{phase}/<basename>`` template.
        handler_name: short name used in log lines (e.g.
            ``"wicked.amendment.appended"``).

    Behaviour:
        * flag-off → no-op.
        * Missing required payload fields → debug log, no-op.
        * project_id has no DB row / NULL directory → warn, skip.
        * Idempotency: if the exact raw_payload line is already in the
          file, skip the append (replay short-circuit).
        * Append uses ``open("a") + fsync`` mirroring the source modules.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled(flag_token)
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: %s — project %r has no directory in DB; skipping",
            handler_name, project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    target = project_dir / relative_template.replace("{phase}", str(phase))

    line = str(raw_payload)
    if not line.endswith("\n"):
        line = line + "\n"

    # Idempotency: skip if the exact line is already in the file.  Required
    # because the daemon consumer doesn't dedupe before calling handlers
    # (append_event_log uses INSERT OR REPLACE — handler fires per event
    # in the batch).
    try:
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if line in existing:
                logger.debug(
                    "projector: %s — line already present in %s; skipping",
                    handler_name, target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: %s — could not read %s for idempotency check: %s; "
            "proceeding to append",
            handler_name, target, exc,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            try:
                import os
                os.fsync(fh.fileno())
            except OSError:
                pass  # fail-open: fsync unsupported on this FS
    except OSError as exc:
        logger.warning(
            "projector: %s — append failed at %s: %s",
            handler_name, target, exc,
        )
        return

    logger.debug(
        "projector: applied %s project_id=%r phase=%r path=%s",
        handler_name, project_id, phase, target,
    )


def _amendment_appended(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.amendment.appended → phases/{phase}/amendments.jsonl.

    Site W6 of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_AMENDMENTS``.  Replays the raw_payload JSONL line
    from ``amendments.append()`` into the same file.
    """
    _jsonl_append_projection(
        conn, event,
        flag_token="AMENDMENTS",
        relative_template="phases/{phase}/amendments.jsonl",
        handler_name="wicked.amendment.appended",
    )


def _reeval_addendum_appended(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.reeval.addendum_appended → BOTH per-phase + project-root logs.

    Site W7 of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_REEVAL_ADDENDUM``.  ``reeval_addendum.append()``
    writes BOTH ``phases/{phase}/reeval-log.jsonl`` AND
    ``process-plan.addendum.jsonl`` per call; this handler replays
    BOTH writes in the same order for crash-safety parity.

    Both writes use the shared ``_jsonl_append_projection`` helper but
    with different relative paths.  The per-phase log is templated;
    the project-root log is fixed.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("REEVAL_ADDENDUM")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.reeval.addendum_appended — project %r has no "
            "directory in DB; skipping",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    line = str(raw_payload)
    if not line.endswith("\n"):
        line = line + "\n"

    targets = [
        project_dir / "phases" / str(phase) / "reeval-log.jsonl",
        project_dir / "process-plan.addendum.jsonl",
    ]

    import os
    for target in targets:
        # Idempotency per file — each is independent.
        try:
            if target.exists():
                existing = target.read_text(encoding="utf-8")
                if line in existing:
                    logger.debug(
                        "projector: wicked.reeval.addendum_appended — line "
                        "already present in %s; skipping",
                        target,
                    )
                    continue
        except OSError as exc:
            logger.warning(
                "projector: wicked.reeval.addendum_appended — could not read "
                "%s for idempotency check: %s; proceeding to append",
                target, exc,
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass  # fail-open: fsync unsupported on this FS
        except OSError as exc:
            logger.warning(
                "projector: wicked.reeval.addendum_appended — append failed "
                "at %s: %s",
                target, exc,
            )
            # Continue to the next target — best-effort dual-write mirrors
            # the source module's separate _atomic_append calls.

    logger.debug(
        "projector: applied wicked.reeval.addendum_appended "
        "project_id=%r phase=%r targets=%d",
        project_id, phase, len(targets),
    )


def _convergence_transition_recorded(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.convergence.transition_recorded → convergence-log.jsonl.

    Site W8 of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_CONVERGENCE``.  Replays the raw_payload JSONL line
    from ``convergence.record_transition()`` into the same file.
    """
    _jsonl_append_projection(
        conn, event,
        flag_token="CONVERGENCE",
        relative_template="phases/{phase}/convergence-log.jsonl",
        handler_name="wicked.convergence.transition_recorded",
    )


def _semantic_gap_recorded(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.review.semantic_gap_recorded → phases/review/semantic-gap-report.json.

    Site W10a of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_SEMANTIC_GAP``.  This is a JSON file (not JSONL)
    that the source rewrites in full per call — so the projector does
    a content-hash idempotency check + atomic write rather than
    line-append.  The path is fixed at ``phases/review/semantic-gap-report.json``
    (the source always writes here regardless of the gate's actual phase).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("SEMANTIC_GAP")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.review.semantic_gap_recorded — project %r "
            "has no directory in DB; skipping",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    target = project_dir / "phases" / "review" / "semantic-gap-report.json"
    candidate_bytes = str(raw_payload).encode("utf-8")

    import hashlib
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: semantic-gap-report — content hash matches "
                    "existing %s; skipping rewrite", target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: semantic-gap-report — could not read %s for "
            "idempotency check: %s; proceeding to write",
            target, exc,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: semantic-gap-report — write failed at %s: %s",
            target, exc,
        )
        return

    logger.debug(
        "projector: applied wicked.review.semantic_gap_recorded "
        "project_id=%r path=%s",
        project_id, target,
    )


# --- Wave-2 Tranche C (#746): W5 + W9b -------------------------------------


# Whitelist of HITL evidence filenames the projector will materialise.
# Caller-supplied filenames outside this set are rejected to defend
# against path-traversal via payload (e.g. "../../etc/passwd").  See
# wave-2 plan §W5 lines 233-239 for the threat model.
_HITL_FILENAME_WHITELIST: frozenset = frozenset({
    "hitl-decision.json",
    "council-decision.json",
    "hitl-challenge-decision.json",
    "hitl-clarify-decision.json",
    "hitl-council-decision.json",
})


def _hitl_decision_recorded(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.hitl.decision_recorded → phases/{phase}/{filename}.

    Site W5 of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_HITL_DECISION``.  Replays the raw_payload bytes
    (the JSON-serialised JudgeDecision) into the same path
    ``hitl_judge.write_hitl_decision_evidence`` writes to.

    Filename safety: payload["filename"] is caller-supplied (the three
    integration points pass different names — clarify-halt vs council
    vs challenge).  The handler validates the name against
    ``_HITL_FILENAME_WHITELIST`` before writing.  Anything outside the
    whitelist is rejected with a warning — defends against
    path-traversal vectors via crafted payloads.

    Idempotency: content-hash short-circuit (full-file rewrite, not append).
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("HITL_DECISION")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off: %s", exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")

    project_id, ok = _require(payload, "project_id", et)
    if not ok:
        return
    phase, ok = _require(payload, "phase", et)
    if not ok:
        return
    filename, ok = _require(payload, "filename", et)
    if not ok:
        return
    raw_payload, ok = _require(payload, "raw_payload", et)
    if not ok:
        return

    # Filename whitelist defense — reject anything outside the known set.
    # This is the load-bearing security check; caller-supplied filenames
    # could otherwise traverse out of phases/{phase}/ via "../" or write
    # to arbitrary basenames.
    if str(filename) not in _HITL_FILENAME_WHITELIST:
        logger.warning(
            "projector: wicked.hitl.decision_recorded — filename %r is "
            "not in the whitelist; refusing to write (defends against "
            "path-traversal via payload)",
            filename,
        )
        return

    project_row = db.get_project(conn, str(project_id))
    if project_row is None or not project_row.get("directory"):
        logger.warning(
            "projector: wicked.hitl.decision_recorded — project %r has no "
            "directory in DB; skipping",
            project_id,
        )
        return

    project_dir = Path(project_row["directory"])
    target = project_dir / "phases" / str(phase) / str(filename)
    candidate_bytes = str(raw_payload).encode("utf-8")

    import hashlib
    try:
        if target.exists():
            existing_bytes = target.read_bytes()
            if (
                hashlib.sha256(existing_bytes).digest()
                == hashlib.sha256(candidate_bytes).digest()
            ):
                logger.debug(
                    "projector: hitl decision — content hash matches "
                    "existing %s; skipping rewrite", target,
                )
                return
    except OSError as exc:
        logger.warning(
            "projector: hitl decision — could not read %s for idempotency "
            "check: %s; proceeding to write", target, exc,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(candidate_bytes)
        tmp.replace(target)
    except OSError as exc:
        logger.warning(
            "projector: hitl decision — write failed at %s: %s",
            target, exc,
        )
        return

    logger.debug(
        "projector: applied wicked.hitl.decision_recorded "
        "project_id=%r phase=%r filename=%r",
        project_id, phase, filename,
    )


def _subagent_engaged(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.subagent.engaged → phases/{phase}/specialist-engagement.jsonl.

    Site W9b of bus-cutover wave-2 (#746).  Gated on
    ``WG_BUS_AS_TRUTH_SUBAGENT_ENGAGEMENT``.  Replays the raw_payload
    JSONL line from ``subagent_lifecycle._record_specialist_engagement``
    into the same file.

    The W9a precursor (in this same PR) refactored the source from
    ``specialist-engagement.json`` (JSON array, read-modify-write) to
    ``specialist-engagement.jsonl`` (append-only).  This handler uses
    the standard JSONL append pattern.
    """
    _jsonl_append_projection(
        conn, event,
        flag_token="SUBAGENT_ENGAGEMENT",
        relative_template="phases/{phase}/specialist-engagement.jsonl",
        handler_name="wicked.subagent.engaged",
    )


def _gate_blocked(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.gate.blocked → no-op disk handler (PR-1 inert).

    Site 4 of the bus-cutover staging plan (#746, #778).  Behaviour gated
    on ``WG_BUS_AS_TRUTH_GATE_RESULT`` via
    ``_bus_as_truth_enabled("GATE_RESULT")``.

    PR-1 ships this handler INERT.  ``wicked.gate.blocked`` always follows
    ``wicked.gate.decided`` in ``approve_phase``'s REJECT branch — by the
    time this handler fires, ``gate-result.json`` is already in REJECT
    state from the ``_gate_decided_disk`` projection (PR-2 onward).  No
    additional disk mutation is needed under the current contract.

    Why register at all then?  ``wicked.gate.blocked`` IS a real bus
    event the daemon must consume — leaving it out of ``_HANDLERS`` would
    surface every blocked emit as ``unknown event_type`` in the
    projector log.  The registration here is for event handling, NOT
    file materialisation: ``wicked.gate.blocked`` was REMOVED from
    ``reconcile_v2._PROJECTION_MAP`` (PR #782 fold for Copilot finding
    on PR-1) so the drift detector doesn't treat it as a file-producing
    event.  Without the map removal, an event_log row with only
    gate.blocked + an on-disk gate-result.json would silently pass the
    projection-without-event check (false negative).

    Future-compat: structured to be the place where REJECT-only metadata
    (e.g., a ``blocking_reason`` annotation distinct from the gate verdict)
    could be appended to the file if such a contract arrives later.  For
    now: flag-off no-op; flag-on debug log + return.
    """
    global _BUS_IMPORT_WARNED
    try:
        from _bus import _bus_as_truth_enabled  # type: ignore[import]
        flag_on = _bus_as_truth_enabled("GATE_RESULT")
    except ImportError as exc:
        if not _BUS_IMPORT_WARNED:
            logger.warning(
                "projector: _bus import failed — treating WG_BUS_AS_TRUTH_* "
                "flags as off (will not re-warn this process): %s",
                exc,
            )
            _BUS_IMPORT_WARNED = True
        flag_on = False
    except Exception:  # noqa: BLE001 — keep fail-open
        flag_on = False

    if not flag_on:
        return

    payload = event.get("payload", {})
    et = event.get("event_type", "")
    project_id, _ = _require(payload, "project_id", et)
    phase, _ = _require(payload, "phase", et)

    logger.debug(
        "projector: wicked.gate.blocked disk projection NO-OP — "
        "gate-result.json already projected from preceding "
        "wicked.gate.decided in approve_phase REJECT branch "
        "(project_id=%r phase=%r)",
        project_id, phase,
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
    # Stream 2 — #591 v8-PR-5: AC structured records
    "wicked.ac.declared": _ac_declared,
    "wicked.ac.evidence_linked": _ac_evidence_linked,
    # Site 1 of bus-cutover (#746): dispatch-log dual-write.  Handler is
    # registered ALWAYS so the _HANDLERS map stays static and inspectable;
    # gating happens inside the handler via _bus_as_truth_enabled().
    # Flag-off → no-op; flag-on → INSERT OR IGNORE into dispatch_log_entries.
    "wicked.dispatch.log_entry_appended": _dispatch_log_appended,
    # Site 2 of bus-cutover (#746): consensus report + evidence dual-write.
    # Two handlers, two independent env-var flags
    # (WG_BUS_AS_TRUTH_CONSENSUS_REPORT / WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE),
    # two separate projection tables (consensus_reports / consensus_evidence).
    # Same registered-always pattern as Site 1.
    "wicked.consensus.report_created": _consensus_report_created,
    "wicked.consensus.evidence_recorded": _consensus_evidence_recorded,
    # Site 3 of bus-cutover (#746, #768, #770): reviewer-report.md file
    # projection.  Both handlers gate on WG_BUS_AS_TRUTH_REVIEWER_REPORT
    # (single flag, same env var the hook reads via _bus_as_truth_flag_on()
    # in post_tool.py).  flag-off → no-op; flag-on → write
    # phases/{phase}/reviewer-report.md byte-identical to the legacy hook.
    # Payload contract: raw_payload = just-written section (per-section shape,
    # #770).  Append branch applies file-existence branch detection + substring
    # scan idempotency guard (separator + raw_payload already in file → skip).
    # Registered always per Decision #6.
    "wicked.consensus.gate_completed": _consensus_gate_completed,
    "wicked.consensus.gate_pending": _consensus_gate_pending,
    # Site 4 of bus-cutover (#746, #778): gate-result.json file projection.
    # ``wicked.gate.decided`` continues to dispatch to ``_gate_decided`` (DB-row
    # work); the disk projection runs as a try/except fan-out at the tail of
    # ``_gate_decided``.  ``wicked.gate.blocked`` registers a fresh handler
    # (``_gate_blocked``) so reconcile_v2's per-event-type handler-presence
    # gate flips True for both events bound to gate-result.json (#774 fold).
    # Both gate on WG_BUS_AS_TRUTH_GATE_RESULT inside the handler.  PR-1
    # ships INERT — the existing emit at phase_manager.py:3931 lacks the
    # full ``data`` payload, so flag-on triggers an early debug-return until
    # PR-2 (#779) widens the emit shape.
    "wicked.gate.blocked": _gate_blocked,
    # Site 5 of bus-cutover (#746): conditions-manifest.json file projection.
    # ``wicked.condition.marked_cleared`` is fired by
    # ``conditions_manifest.mark_cleared()`` BEFORE its disk writes; the
    # projector handler ``_condition_marked_cleared`` replays the same
    # atomic two-step write order (sidecar → manifest flip).  Gated on
    # ``WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST`` inside the handler.
    # The gate.decided handler also fans out to write the INITIAL
    # conditions-manifest.json on CONDITIONAL verdicts (one event,
    # multiple files — see _PROJECTION_MAP shape change in
    # reconcile_v2.py).
    "wicked.condition.marked_cleared": _condition_marked_cleared,
    # Site W1 of bus-cutover wave-2 (#787): solo_mode inline-HITL
    # evidence record.  ``wicked.crew.inline_review_context_recorded`` is
    # fired by ``solo_mode.dispatch_human_inline()`` BEFORE the legacy
    # disk write at phases/{phase}/inline-review-context.md.  Solo-mode
    # also fires ``wicked.gate.decided`` in the same flow which the
    # existing gate.decided handler maps to gate-result.json (+
    # conditions-manifest.json on CONDITIONAL) — this handler covers the
    # third artifact.  Gated on WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT.
    "wicked.crew.inline_review_context_recorded": _inline_review_context_recorded,
    # Wave-2 Tranche B (#746): JSONL append-stream cutovers.
    # Each handler mirrors the source module's append (or full-write
    # for semantic-gap) into the same path.  Gated per-handler on its
    # own WG_BUS_AS_TRUTH_<TOKEN> flag.
    "wicked.amendment.appended":              _amendment_appended,
    "wicked.reeval.addendum_appended":        _reeval_addendum_appended,
    "wicked.convergence.transition_recorded": _convergence_transition_recorded,
    "wicked.review.semantic_gap_recorded":    _semantic_gap_recorded,
    # Wave-2 Tranche C (#746):
    # W5 hitl pause-decision evidence (payload-aware-on-filename with whitelist).
    # W9b specialist engagement (JSONL append after W9a JSON→JSONL refactor
    # in this same PR).
    # W10b status.md SKIPPED is NOT a separate event — it fans out from
    # the existing _phase_transitioned handler when payload signals
    # gate_result=="SKIPPED" (gated on WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS).
    "wicked.hitl.decision_recorded":          _hitl_decision_recorded,
    "wicked.subagent.engaged":                _subagent_engaged,
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
