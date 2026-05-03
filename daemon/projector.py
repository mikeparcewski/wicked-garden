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


def _consensus_report_created(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.report_created → consensus_reports.

    Site 2 of the bus-cutover staging plan (#746).  Behaviour is gated on
    `WG_BUS_AS_TRUTH_CONSENSUS_REPORT` via `_bus_as_truth_enabled("CONSENSUS_REPORT")`:

      * flag-off (default): handler is a no-op.  The projector wrapper still
        records the event_log row as `applied` (Decision #6); the projection
        table is intentionally untouched while the disk file remains source
        of truth.
      * flag-on: INSERT OR IGNORE one row per (event_id) into
        `consensus_reports`.  Idempotent on duplicate event_id.

    The `raw_payload` field is REQUIRED per Council Condition C10 — it
    carries the canonical on-disk bytes (json.dumps with indent=2) so the
    projector can reproduce `consensus-report.json` byte-for-byte.
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


# --- bus-cutover Site 3 (#768) handlers -----------------------------------
#
# Two handlers materialise phases/{phase}/reviewer-report.md from bus events,
# producing the same on-disk file that hooks/scripts/post_tool.py's
# _write_reviewer_report / _write_pending_reviewer_report write directly.
#
# Idempotency strategy (Decision #6 compatibility):
#   The projector wrapper handles duplicate events via event_log INSERT OR IGNORE
#   keyed on (event_id) — the same event is never presented to a handler twice
#   in production.  Under test-harness replay (no event_log dedup), the
#   handlers are still safe because raw_payload already contains the FULL
#   target file content in all branches (create, append, pending).  Writing
#   the same bytes twice is idempotent by nature.
#
# project_dir resolution:
#   The payload carries project_id + phase.  We look up the project row in the
#   DB (db.get_project) to find the `directory` field.  If the project row is
#   absent or directory is NULL, we log a warning and skip — never infer a path
#   from local filesystem conventions in the daemon.
#
# Council Condition C8 addendum (N=3 warning):
#   With Site 3 we have three handler pairs.  The shared import pattern
#   (_BUS_IMPORT_WARNED latch, import-fail = flag-off) is now clearly
#   stable.  ADR for N=3 base-class extraction is deferred to Issue #771.

_CONSENSUS_GATE_SEPARATOR = "\n\n---\n## Consensus Gate Evaluation\n\n"


def _consensus_gate_completed(conn: sqlite3.Connection, event: dict) -> None:
    """Project wicked.consensus.gate_completed → reviewer-report.md on disk.

    Site 3 of the bus-cutover staging plan (#746, #768).  Behaviour is gated
    on ``WG_BUS_AS_TRUTH_REVIEWER_REPORT`` via
    ``_bus_as_truth_enabled("REVIEWER_REPORT")``:

      * flag-off (default): handler is a no-op.  The projector wrapper still
        records the event_log row as ``applied`` (Decision #6); the disk file
        remains source of truth.
      * flag-on: write raw_payload to phases/{phase}/reviewer-report.md.
        - create branch (``payload.branch == "create"``): write raw_payload as
          the full file — mirrors _write_reviewer_report's else-branch.
        - append branch (``payload.branch == "append"``): write raw_payload as
          the full file — raw_payload already contains the pre-appended
          separator + yaml_block per the hook's write-then-emit contract, so a
          simple write is byte-identical to the legacy hook.

    Idempotency: writing the same raw_payload bytes twice produces the same
    file — no duplicate-append risk.  The projector wrapper's event_log INSERT
    OR IGNORE prevents re-presenting the same event_id to this handler.

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

    # Write raw_payload as the full file content.
    # raw_payload is the canonical on-disk bytes: for the create branch it is
    # the yaml_block; for the append branch it already includes the separator
    # + yaml_block appended to the existing content.  Either way a plain write
    # produces the byte-identical file that the legacy hook wrote.
    try:
        phase_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(str(raw_payload), encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "projector: wicked.consensus.gate_completed — could not write %s: %s",
            report_path,
            exc,
        )
        return

    branch = _opt(payload, "branch", "unknown")
    logger.debug(
        "projector: applied wicked.consensus.gate_completed "
        "project_id=%r phase=%r branch=%r report_path=%s",
        project_id, phase, branch, report_path,
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
    # Site 3 of bus-cutover (#746, #768): reviewer-report.md file projection.
    # Both handlers gate on WG_BUS_AS_TRUTH_REVIEWER_REPORT (single flag,
    # same env var the hook reads via _bus_as_truth_flag_on() in post_tool.py).
    # flag-off → no-op; flag-on → write phases/{phase}/reviewer-report.md
    # byte-identical to _write_reviewer_report / _write_pending_reviewer_report.
    # Registered always per Decision #6 — gating happens inside each handler.
    "wicked.consensus.gate_completed": _consensus_gate_completed,
    "wicked.consensus.gate_pending": _consensus_gate_pending,
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
