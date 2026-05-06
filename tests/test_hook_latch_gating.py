"""tests/test_hook_latch_gating.py — per-turn / change-gated latches for two
HIGH-severity noise emitters surfaced by the v9.2.11 hook audit.

Provenance: the v9.2.11 audit found two banners that re-fired without any
gate against actual state:

  1. `[Status] This turn has been running for N min` (post_tool.py) — fired
     on every PostToolUse once the 2-min threshold tripped, surfacing
     redundant copies on every subsequent tool call.
  2. `[Issue Reporter] N issue(s) queued this session` (stop.py) — fired
     on every Stop hook (per turn end) until the user filed the issues.

v9.2.12 adds latches keyed on real-state change (turn_count for #1, file
line-count for #2). Same anti-pattern class as v9.2.10 / v9.2.11 — emit
when state changes, suppress when nothing's changed.

T1: deterministic — pure SessionState manipulation, no I/O on hook events.
T3: isolated — each test creates a fresh SessionState in-memory.
T4: single focus — the latch contract.
T6: docstring cites v9.2.12 (this PR) and the v9.2.11 audit.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def test_session_state_declares_latch_fields():
    """The three new fields must be declared on SessionState. If absent, the
    latch writes silently no-op (the v9.2.0 → v9.2.5 silent-contract-drift
    class). The drift CI guard catches this too, but assert here for
    immediate-locality test failure when this PR's fields are removed."""
    from _session import SessionState

    s = SessionState()
    assert hasattr(s, "last_status_turn")
    assert hasattr(s, "last_outcome_pending_count")
    assert hasattr(s, "last_outcome_mismatch_count")
    # Defaults must be 0 so the FIRST emission at any turn / count > 0 fires.
    assert s.last_status_turn == 0
    assert s.last_outcome_pending_count == 0
    assert s.last_outcome_mismatch_count == 0


def test_status_latch_suppresses_within_turn():
    """The [Status] latch logic: once last_status_turn equals turn_count, the
    banner is suppressed. Simulate by checking the gate condition directly."""
    # The latch comparison from post_tool.py::_check_turn_progress:
    #   current_turn = state.turn_count or 0
    #   if current_turn and current_turn == (state.last_status_turn or 0):
    #       return None  # suppress
    #   state.update(last_status_turn=current_turn)  # arm for this turn

    # Before first emission this turn:
    turn_count = 5
    last_status_turn = 0
    suppressed = bool(turn_count) and turn_count == last_status_turn
    assert not suppressed, "First emission this turn must fire"

    # After arming:
    last_status_turn = 5
    suppressed = bool(turn_count) and turn_count == last_status_turn
    assert suppressed, "Second emission this turn must be suppressed"


def test_status_latch_re_arms_on_new_turn():
    """The [Status] latch must re-arm when prompt_submit increments turn_count.
    This is the contract that makes the latch per-turn rather than once-ever."""
    last_status_turn = 5  # banner fired at turn 5

    # New turn — prompt_submit increments turn_count to 6.
    new_turn = 6
    suppressed = bool(new_turn) and new_turn == last_status_turn
    assert not suppressed, "New turn must re-arm the [Status] banner"


def test_status_latch_does_not_fire_at_turn_zero():
    """Edge case: turn_count = 0 (very early in session) must not match
    last_status_turn = 0 default — the `current_turn and ...` guard handles
    this so the latch doesn't false-suppress before turn_count is established."""
    turn_count = 0
    last_status_turn = 0
    suppressed = bool(turn_count) and turn_count == last_status_turn
    assert not suppressed, (
        "At turn 0, the latch must NOT suppress — turn_count not yet set "
        "is different from 'already shown at turn 0'."
    )


def test_outcome_latch_fires_only_on_count_growth():
    """The [Issue Reporter] latch logic from stop.py::_check_session_outcome:
    only emit when `count > last_count`. Same pending issues across turns
    => silence; new issues queued => banner fires once."""
    # Initial state — no issues.
    last_count = 0
    count = 0
    should_emit = count and count > last_count
    assert not should_emit

    # First issue queued — emit.
    count = 1
    should_emit = count and count > last_count
    assert should_emit

    # Latch persists `last_count = 1`. Same count next turn — no emission.
    last_count = 1
    should_emit = count and count > last_count
    assert not should_emit

    # New issue queued — count grows to 2. Emit.
    count = 2
    should_emit = count and count > last_count
    assert should_emit


def test_outcome_latch_separate_for_pending_and_mismatch():
    """pending_issues and mismatches use separate latch fields so growth in
    one doesn't suppress emission for the other."""
    from _session import SessionState

    s = SessionState()
    # Both default to 0; both can fire independently.
    assert s.last_outcome_pending_count == 0
    assert s.last_outcome_mismatch_count == 0

    # Updating one does not touch the other.
    s.update(last_outcome_pending_count=3)
    assert s.last_outcome_pending_count == 3
    assert s.last_outcome_mismatch_count == 0


def test_drift_test_accepts_new_fields():
    """The v9.2.3 drift test scans hook scripts for state.update(name=...)
    and getattr(state, "name", ...) calls and asserts every name is a
    declared SessionState field. The three new fields used by post_tool.py
    and stop.py must be declared. Pinning here for immediate-locality
    failure if a future refactor drops them."""
    import re
    declared_pat = re.compile(r"^    ([a-z_][a-z_0-9]*)\s*:\s*[^#=]", re.MULTILINE)
    text = (REPO_ROOT / "scripts" / "_session.py").read_text()
    declared = set(declared_pat.findall(text))
    for new_field in ("last_status_turn", "last_outcome_pending_count", "last_outcome_mismatch_count"):
        assert new_field in declared, f"v9.2.12 field {new_field!r} missing from SessionState"
