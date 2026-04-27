"""Tests for daemon._internal.transition_phase — graph-enforced phase UPDATE.

Issue #614 / epic #679 brainstorm decision D1: split upsert_phase semantics.
``upsert_phase`` stays INSERT-friendly (vocabulary check only); the new
``transition_phase`` reads current state, calls _transition(), and rejects
illegal graph moves.

Test coverage (all 10 numbered requirements from the issue brief):
  1. transition_phase with no current row → INSERT path → succeeds
  2. Legal transition (pending → active via "start" event) → UPDATE succeeds
  3. Illegal transition (pending → approved directly) → IllegalPhaseTransition
  4. Same-state move (active → active via re-eval) → succeeds (idempotent)
  5. Custom event that _transition doesn't recognize → raises with clear error
  6. upsert_phase can still INSERT directly (backward compat)
  7. upsert_phase does NOT enforce graph paths even on UPDATE (preserved
     INSERT-friendly behaviour — split is intentional)
  8. Docstring fix: upsert_phase.__doc__ honestly says "vocabulary" only
  9. Regression scan: no projector call site smuggles upsert_phase for what
     should be a graph-enforced UPDATE — every state-mutating call site is
     either marked with the comment block or routes through transition_phase
 10. IllegalPhaseTransition subclasses InvalidTransition (caller convenience)

T1: deterministic — no wall clock, no random, no network.
T3: isolated — uses the mem_conn fixture (in-memory SQLite per test).
T6: provenance #614, epic #679.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `import daemon.*` works from tests.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import daemon.db as db  # noqa: E402
from daemon._internal import IllegalPhaseTransition, transition_phase  # noqa: E402

_SCRIPTS_CREW = _REPO_ROOT / "scripts" / "crew"
if str(_SCRIPTS_CREW) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CREW))

from phase_state import InvalidTransition, PhaseState  # type: ignore[import]  # noqa: E402


_PROJECT_ID = "p-test"
_PHASE = "build"


@pytest.fixture(autouse=True)
def _seed_project(mem_conn: sqlite3.Connection) -> None:
    """Every test needs a parent project row (FK constraint on phases.project_id)."""
    db.upsert_project(mem_conn, _PROJECT_ID, {"name": _PROJECT_ID})


def _seed_phase(conn: sqlite3.Connection, state: str) -> None:
    """Insert a starting phase row at ``state`` via the vocabulary-only path."""
    db.upsert_phase(conn, _PROJECT_ID, _PHASE, {"state": state})


# ---------------------------------------------------------------------------
# 1. INSERT path — no current row, transition_phase falls through to upsert.
# ---------------------------------------------------------------------------
def test_transition_phase_inserts_when_no_current_row(mem_conn: sqlite3.Connection) -> None:
    transition_phase(
        mem_conn,
        _PROJECT_ID,
        _PHASE,
        new_state=PhaseState.APPROVED,
        event="approve",
    )
    rows = db.list_phases(mem_conn, _PROJECT_ID)
    assert len(rows) == 1
    assert rows[0]["state"] == "approved"


# ---------------------------------------------------------------------------
# 2. Legal UPDATE — pending → active via "start" event.
# ---------------------------------------------------------------------------
def test_transition_phase_pending_to_active_via_start(mem_conn: sqlite3.Connection) -> None:
    _seed_phase(mem_conn, "pending")
    transition_phase(
        mem_conn,
        _PROJECT_ID,
        _PHASE,
        new_state=PhaseState.ACTIVE,
        event="start",
    )
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "active"


# ---------------------------------------------------------------------------
# 3. Illegal UPDATE — pending → approved directly raises IllegalPhaseTransition.
# ---------------------------------------------------------------------------
def test_transition_phase_pending_to_approved_directly_is_illegal(
    mem_conn: sqlite3.Connection,
) -> None:
    _seed_phase(mem_conn, "pending")
    with pytest.raises(IllegalPhaseTransition) as exc_info:
        transition_phase(
            mem_conn,
            _PROJECT_ID,
            _PHASE,
            new_state=PhaseState.APPROVED,
            event="approve",
        )
    msg = str(exc_info.value)
    assert "illegal" in msg.lower()
    assert "pending" in msg
    assert "approve" in msg
    # Row must NOT have been mutated.
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "pending"


# ---------------------------------------------------------------------------
# 4. Idempotent same-state replay — current==new short-circuits cleanly.
# ---------------------------------------------------------------------------
def test_transition_phase_same_state_replay_is_noop(mem_conn: sqlite3.Connection) -> None:
    _seed_phase(mem_conn, "active")
    # Replay an "approve" or "start" against a row already at ACTIVE — the
    # idempotent guard treats it as a no-op for state and lets extra_fields flow.
    transition_phase(
        mem_conn,
        _PROJECT_ID,
        _PHASE,
        new_state=PhaseState.ACTIVE,
        event="start",  # would raise without the same-state shortcut
        extra_fields={"started_at": 1700000000},
    )
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "active"
    assert row["started_at"] == 1700000000


# ---------------------------------------------------------------------------
# 5. Unknown event → InvalidTransition with a clear error.
# ---------------------------------------------------------------------------
def test_transition_phase_unknown_event_raises(mem_conn: sqlite3.Connection) -> None:
    _seed_phase(mem_conn, "active")
    with pytest.raises(InvalidTransition) as exc_info:
        transition_phase(
            mem_conn,
            _PROJECT_ID,
            _PHASE,
            new_state=PhaseState.APPROVED,
            event="please-approve-me-thanks",  # not in TRANSITIONS
        )
    msg = str(exc_info.value)
    assert "please-approve-me-thanks" in msg


# ---------------------------------------------------------------------------
# 6. Backward compat — upsert_phase can INSERT at any canonical state.
# ---------------------------------------------------------------------------
def test_upsert_phase_can_insert_at_any_canonical_state(mem_conn: sqlite3.Connection) -> None:
    db.upsert_phase(mem_conn, _PROJECT_ID, _PHASE, {"state": "approved"})
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "approved"


# ---------------------------------------------------------------------------
# 7. Split is intentional — upsert_phase does NOT enforce graph paths
#    even on an UPDATE that would be illegal under transition_phase.
# ---------------------------------------------------------------------------
def test_upsert_phase_does_not_enforce_graph_on_update(mem_conn: sqlite3.Connection) -> None:
    _seed_phase(mem_conn, "pending")
    # This move is graph-illegal (pending→approved skips active).  upsert_phase
    # MUST allow it because the split places graph enforcement in
    # transition_phase, NOT in upsert_phase.  Removing this allowance silently
    # would break recovery / rollback / replay paths that intentionally bypass
    # the graph.
    db.upsert_phase(mem_conn, _PROJECT_ID, _PHASE, {"state": "approved"})
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "approved"


# ---------------------------------------------------------------------------
# 8. Docstring fix — upsert_phase docs honestly describe vocabulary-only check.
# ---------------------------------------------------------------------------
def test_upsert_phase_docstring_does_not_lie() -> None:
    doc = (db.upsert_phase.__doc__ or "").lower()
    assert doc, "upsert_phase must have a docstring"
    # Honest framing must mention the vocabulary-only behaviour.
    assert "vocabulary" in doc
    # And it must NOT claim graph-path validation is performed here.
    assert "graph-path" not in doc or "transition_phase" in doc, (
        "upsert_phase docstring still claims graph-path validation without "
        "redirecting to transition_phase — that was the original lie (#614)."
    )
    # Explicit redirect to the new helper.
    assert "transition_phase" in doc


# ---------------------------------------------------------------------------
# 9. Regression scan — projector.py state-mutating upsert_phase calls must
#    either route through transition_phase or carry the explicit (#614)
#    documentation marker on the line above.
# ---------------------------------------------------------------------------
def test_projector_state_mutating_upserts_are_audited() -> None:
    projector_path = _REPO_ROOT / "daemon" / "projector.py"
    text = projector_path.read_text(encoding="utf-8")

    # Every db.upsert_phase(...) call that sets "state" must be preceded by
    # an explanatory comment containing "#614" within the prior 12 lines.
    # transition_phase calls are exempt — they are the new graph-enforced path.
    lines = text.splitlines()
    findings: list[str] = []
    state_call_re = re.compile(r"db\.upsert_phase\(")
    for i, line in enumerate(lines):
        if not state_call_re.search(line):
            continue
        # Look ahead a few lines to see if "state" appears in the dict body.
        body = "\n".join(lines[i : i + 8])
        if '"state"' not in body:
            continue
        # Look back up to 12 lines for the #614 audit marker.
        preamble = "\n".join(lines[max(0, i - 12) : i])
        if "#614" not in preamble:
            findings.append(f"line {i + 1}: {line.strip()}")

    assert not findings, (
        "Projector handlers must either use transition_phase for graph-enforced "
        "UPDATEs OR carry an explicit #614 audit comment justifying the "
        "vocabulary-only upsert_phase call.  Offenders:\n  "
        + "\n  ".join(findings)
    )


# ---------------------------------------------------------------------------
# 10. IllegalPhaseTransition subclasses InvalidTransition.
# ---------------------------------------------------------------------------
def test_illegal_phase_transition_subclasses_invalid_transition() -> None:
    assert issubclass(IllegalPhaseTransition, InvalidTransition)


# ---------------------------------------------------------------------------
# 11. (bonus) extra_fields flow through on the legal-update path.
# ---------------------------------------------------------------------------
def test_transition_phase_extra_fields_flow_through_on_legal_update(
    mem_conn: sqlite3.Connection,
) -> None:
    _seed_phase(mem_conn, "active")
    transition_phase(
        mem_conn,
        _PROJECT_ID,
        _PHASE,
        new_state=PhaseState.APPROVED,
        event="approve",
        extra_fields={"terminal_at": 1700000123, "gate_score": 0.92},
    )
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "approved"
    assert row["terminal_at"] == 1700000123
    assert row["gate_score"] == 0.92


# ---------------------------------------------------------------------------
# 12. (bonus) banned state is still rejected on the INSERT fallback path.
# ---------------------------------------------------------------------------
def test_transition_phase_banned_state_rejected_on_insert(mem_conn: sqlite3.Connection) -> None:
    # No prior row; transition_phase falls back to upsert_phase which still
    # vocabulary-checks the banned "completed" state.
    with pytest.raises(InvalidTransition):
        transition_phase(
            mem_conn,
            _PROJECT_ID,
            _PHASE,
            new_state="completed",  # banned
            event="approve",
        )


# ---------------------------------------------------------------------------
# 13. (bonus) rework path: rejected → active via "rework" succeeds.
# ---------------------------------------------------------------------------
def test_transition_phase_rejected_to_active_via_rework(mem_conn: sqlite3.Connection) -> None:
    _seed_phase(mem_conn, "rejected")
    transition_phase(
        mem_conn,
        _PROJECT_ID,
        _PHASE,
        new_state=PhaseState.ACTIVE,
        event="rework",
        extra_fields={"rework_iterations": 1},
    )
    row = db.get_phase(mem_conn, _PROJECT_ID, _PHASE)
    assert row is not None
    assert row["state"] == "active"
    assert row["rework_iterations"] == 1
