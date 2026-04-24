"""Typed phase state machine — v8-PR-3 (#590).

Canonical phase states and the transition function every phase-state write in
the daemon layer routes through.  The floating ``completed`` state is
explicitly banned — writes that attempt it fail loudly with
``InvalidTransition``.

This module governs the **daemon DB layer** (``daemon/db.py:upsert_phase``
``state`` column and ``daemon/projector.py`` handler constants).  The
``phase_manager.py`` internal ``PhaseState`` dataclass uses a separate
vocabulary (``in_progress``, ``complete``) for its own JSON file store and is
NOT governed here (non-goal per #590: "intercepts writes at the boundary").

States
------
pending   — phase declared but not started
active    — phase in progress
approved  — phase completed via gate approval (ACs satisfied)
skipped   — phase completed without ACs (valid skip reason)
rejected  — phase failed and requires rework

Transition graph (event → new state)
-------------------------------------
start   : pending  → active
approve : active   → approved
reject  : active   → rejected
skip    : pending  → skipped
skip    : active   → skipped
rework  : rejected → active   (rework restarts the phase)

Terminal states (approved, skipped) have no outgoing transitions.
``rejected`` has exactly one outgoing transition (rework).
``completed`` is banned — historical dead-end bug source (#588 thesis 3).

Usage
-----
>>> from scripts.crew.phase_state import transition, PhaseState
>>> new_state = transition("pending", "start")
>>> assert new_state == PhaseState.ACTIVE
>>> transition("completed", "approve")  # raises InvalidTransition
"""
from __future__ import annotations

from enum import StrEnum


class PhaseState(StrEnum):
    """Canonical phase states for the daemon projection layer.

    StrEnum so values compare equal to plain strings — existing db.py /
    projector.py string comparisons continue to work without modification.
    """
    PENDING = "pending"
    ACTIVE = "active"
    APPROVED = "approved"
    SKIPPED = "skipped"
    REJECTED = "rejected"


class InvalidTransition(Exception):
    """Raised when a phase-state write attempts a disallowed transition.

    Callers should catch this to surface a meaningful error rather than
    writing an illegal state to the DB.
    """


# ---------------------------------------------------------------------------
# Transition table: (event_name, current_state) → new_state
# ---------------------------------------------------------------------------
# Keep this as a flat dict — O(1) lookup, no conditionals in transition().
# Adding a new transition means adding one entry here; the type checker and
# test_all_transitions_covered will catch omissions.

TRANSITIONS: dict[tuple[str, PhaseState], PhaseState] = {
    ("start",   PhaseState.PENDING):  PhaseState.ACTIVE,
    ("approve", PhaseState.ACTIVE):   PhaseState.APPROVED,
    ("reject",  PhaseState.ACTIVE):   PhaseState.REJECTED,
    ("skip",    PhaseState.PENDING):  PhaseState.SKIPPED,
    ("skip",    PhaseState.ACTIVE):   PhaseState.SKIPPED,
    # rework restarts a rejected phase — the only outgoing edge from REJECTED
    ("rework",  PhaseState.REJECTED): PhaseState.ACTIVE,
}

# States that are terminal (no outgoing transitions except rework from REJECTED).
TERMINAL_STATES: frozenset[PhaseState] = frozenset({
    PhaseState.APPROVED,
    PhaseState.SKIPPED,
})

# Values that must never appear as a target state — historical dead-end source.
BANNED_STATES: frozenset[str] = frozenset({"completed"})

# Valid event names for documentation / introspection.
VALID_EVENTS: frozenset[str] = frozenset(e for e, _ in TRANSITIONS)


def transition(current: PhaseState | str | None, event: str) -> PhaseState:
    """Apply *event* to *current* state and return the new state.

    Parameters
    ----------
    current:
        Current phase state.  ``None`` is treated as ``PhaseState.PENDING``
        (a phase that has not been initialised yet).  Plain strings are coerced
        to ``PhaseState``; ``"completed"`` raises ``InvalidTransition``.
    event:
        The event to apply (e.g. ``"start"``, ``"approve"``).

    Returns
    -------
    PhaseState
        The resulting canonical state after the transition.

    Raises
    ------
    InvalidTransition
        If *current* is a banned state, an unknown state string, or if
        ``(event, current)`` has no entry in ``TRANSITIONS``.
    """
    if current is None:
        current = PhaseState.PENDING

    if isinstance(current, str):
        if current in BANNED_STATES:
            raise InvalidTransition(
                f"Phase state {current!r} is banned. "
                "Migration required to map existing rows to a canonical state "
                "(see scripts/crew/phase_state_migration.py)."
            )
        try:
            current = PhaseState(current)
        except ValueError as exc:
            raise InvalidTransition(
                f"Unknown phase state: {current!r}. "
                f"Valid states: {sorted(PhaseState)}"
            ) from exc

    key = (event, current)
    if key not in TRANSITIONS:
        raise InvalidTransition(
            f"No transition from {current!r} via event {event!r}. "
            f"Valid transitions from {current!r}: "
            f"{[ev for ev, st in TRANSITIONS if st == current]}"
        )
    return TRANSITIONS[key]
