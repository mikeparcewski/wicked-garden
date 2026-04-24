"""scripts/crew/yolo_constants.py — revoke-attribution taxonomy (Issue #581).

Live wicked-bus telemetry shows ``wicked.crew.yolo_revoked`` firing on ~49%
of gate decisions (111 revokes / 225 decisions). Before we tune thresholds
we need **attribution**: which trigger fires the revoke most often?

This module defines the fixed taxonomy of revoke reasons that every
yolo-revoke emit site MUST carry. Downstream telemetry (bus payload +
``yolo-audit.jsonl``) groups by ``revoke_reason`` so the next run's
distribution pinpoints where the bias lives.

Stdlib-only. Frozenset for immutability + O(1) membership check.
No emojis. No behavior changes — this is instrumentation-first.
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
#
# Every ``wicked.crew.yolo_revoked`` payload and every ``yolo-audit.jsonl``
# ``event == "revoked"`` record MUST carry a ``revoke_reason`` drawn from
# this set. Unknown values are rejected at emit time via
# :func:`validate_revoke_reason`.
#
# Values:
#   gate.conditional — a CONDITIONAL verdict auto-revoked yolo
#   gate.reject      — a REJECT verdict auto-revoked yolo
#   scope.change     — facilitator re-eval detected scope increase (augment)
#   retier.up        — re-eval re-tiered the project upward (e.g. to 'full')
#   cooldown.hit     — a recent revoke cooldown window re-triggered
#   user.override    — explicit user revocation via CLI
#   other            — fallback; MUST be accompanied by a non-empty
#                      ``revoke_note`` so the instrumentation gap is named.
VALID_REVOKE_REASONS = frozenset({
    "gate.conditional",
    "gate.reject",
    "scope.change",
    "retier.up",
    "cooldown.hit",
    "user.override",
    "other",
})


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_revoke_reason(
    reason: str,
    note: Optional[str] = None,
) -> None:
    """Raise ValueError when ``reason`` is not in :data:`VALID_REVOKE_REASONS`.

    Additionally, ``reason == "other"`` MUST be accompanied by a non-empty,
    non-whitespace ``note`` — the taxonomy's escape hatch exists to name the
    instrumentation gap, not to silently absorb unattributed revokes.

    Parameters
    ----------
    reason:
        The revoke-attribution tag. Must be a member of
        :data:`VALID_REVOKE_REASONS`.
    note:
        Optional free-text note. Required when ``reason == "other"``.

    Raises
    ------
    ValueError
        - When ``reason`` is not a recognised taxonomy member.
        - When ``reason == "other"`` and ``note`` is missing or whitespace-only.
    """
    if reason not in VALID_REVOKE_REASONS:
        valid = ", ".join(sorted(VALID_REVOKE_REASONS))
        raise ValueError(
            f"invalid-revoke-reason: {reason!r} not in taxonomy. "
            f"Expected one of: {valid}."
        )
    if reason == "other":
        if note is None or not str(note).strip():
            raise ValueError(
                "revoke-reason-other-requires-note: reason='other' is the "
                "taxonomy's escape hatch and MUST be accompanied by a "
                "non-empty revoke_note naming the instrumentation gap."
            )
