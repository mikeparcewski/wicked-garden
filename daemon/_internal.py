"""Internal helpers for the daemon projection layer.  Not part of the public API.

Per epic #679 brainstorm decision D1 (#614): graph-path enforcement of phase
transitions lives here, in the layer that knows *why* state is changing.
``daemon.db.upsert_phase`` stays INSERT-friendly with vocabulary checking only;
this module owns UPDATE-path enforcement of the canonical transition graph
defined in ``scripts/crew/phase_state.py``.

Module-private placement (leading underscore) is intentional: only
``daemon.projector`` should import from here.  External call sites that need
to write phase state must either:

  1. Use ``upsert_phase`` directly (INSERT path, vocabulary-only), or
  2. Route through the projector by emitting a bus event.

This split closes the gap flagged by 4 of 5 PR #613 council voters: the typed
state machine was acting as an advisory vocabulary guard rather than a graph
invariant enforcer.  ``upsert_phase(state="approved")`` against a ``pending``
row succeeded silently — now ``transition_phase`` rejects that move.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import daemon.db as db

# ---------------------------------------------------------------------------
# phase_state import — same path bootstrapping as daemon/db.py and projector.
# ---------------------------------------------------------------------------
_SCRIPTS_CREW = Path(__file__).resolve().parents[1] / "scripts" / "crew"
if str(_SCRIPTS_CREW) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CREW))

from phase_state import (  # type: ignore[import]  # noqa: E402
    InvalidTransition,
    PhaseState,
    transition as _transition,
)


class IllegalPhaseTransition(InvalidTransition):
    """Raised when ``transition_phase`` is asked to apply a graph-illegal move.

    Subclasses ``InvalidTransition`` so existing callers that already catch
    the vocabulary-level exception keep working — graph violations are a
    strict superset of vocabulary violations.
    """


def transition_phase(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
    new_state: PhaseState | str,
    event: str,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Update a phase's state with full graph-path validation.

    Algorithm
    ---------
    1.  Read the current phase row via ``db.get_phase``.
    2.  If no row exists, fall back to ``db.upsert_phase`` — graph enforcement
        only applies to UPDATEs, since INSERTs have no prior state to validate
        against.  The vocabulary check inside ``upsert_phase`` still runs.
    3.  If a row exists, call ``_transition(current_state, event)`` and verify
        the result equals ``new_state``.  Raise ``IllegalPhaseTransition`` on
        mismatch.
    4.  On success, delegate the actual write to ``db.upsert_phase`` so all
        column-level logic (mutable_cols, COALESCE preservation, commit) lives
        in one place.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    project_id, phase:
        Composite key identifying the phase row to update.
    new_state:
        The canonical PhaseState (or matching string) that the caller wants
        to write.  The function verifies this is the legal product of
        applying ``event`` to the current state.
    event:
        The transition event driving the move.  See
        ``scripts/crew/phase_state.py:TRANSITIONS`` for the full table.
        Common values: ``"start"``, ``"approve"``, ``"reject"``, ``"skip"``,
        ``"rework"``.
    extra_fields:
        Additional columns to set on the row (e.g. ``terminal_at``,
        ``started_at``, ``rework_iterations``).  Merged with ``state`` and
        passed through to ``upsert_phase``.

    Raises
    ------
    IllegalPhaseTransition
        If the requested ``new_state`` is not the legal result of applying
        ``event`` to the current state (e.g. ``pending`` → ``approved``
        without going through ``active``).
    InvalidTransition
        If ``event`` is unknown for the current state, or if the current
        state itself is banned.  Inherits from the same base as
        ``IllegalPhaseTransition`` so a single ``except InvalidTransition``
        covers both.
    """
    # Normalise new_state to a plain string for comparison + downstream upsert.
    requested_value = str(new_state)
    fields: dict[str, Any] = dict(extra_fields or {})
    fields["state"] = requested_value

    current_row = db.get_phase(conn, project_id, phase)
    if current_row is None:
        # No prior state — INSERT path, vocabulary check only (per the split).
        db.upsert_phase(conn, project_id, phase, fields)
        return

    current_state = current_row.get("state")

    # Replay-safe idempotency (projector Decision #6): if the row is already at
    # the requested state, treat the call as a no-op for the state column and
    # let any extra_fields (timestamps, gate metadata) flow through.  Without
    # this guard, replaying e.g. _phase_auto_advanced would call
    # _transition(APPROVED, "approve") which has no entry and would raise.
    if str(current_state) == requested_value:
        db.upsert_phase(conn, project_id, phase, fields)
        return

    # _transition() raises InvalidTransition on banned / unknown current states
    # or on (event, current_state) pairs missing from the table.  Re-wrap as
    # IllegalPhaseTransition so callers can distinguish "vocabulary problem"
    # from "graph problem" — both cases are bugs in the caller's event choice.
    try:
        legal_next = _transition(current_state, event)
    except InvalidTransition as exc:
        raise IllegalPhaseTransition(
            f"transition_phase: illegal move for ({project_id!r}, {phase!r}). "
            f"current_state={current_state!r} event={event!r} requested={requested_value!r} "
            f"— no legal transition: {exc}"
        ) from exc

    if str(legal_next) != requested_value:
        raise IllegalPhaseTransition(
            f"transition_phase: illegal move for ({project_id!r}, {phase!r}). "
            f"current_state={current_state!r} event={event!r} requested={requested_value!r} "
            f"would be illegal — _transition() returned {str(legal_next)!r}."
        )

    db.upsert_phase(conn, project_id, phase, fields)
