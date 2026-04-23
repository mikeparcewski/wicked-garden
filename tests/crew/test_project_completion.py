"""tests/crew/test_project_completion.py — issue #562 regression.

Verifies compute_project_completion() only reports is_complete=True when
every phase in phase_plan is 'approved'. The approve and advance CLI paths
depend on this helper to avoid the misleading "Project complete!" message
when phases are still pending.

Rules:
  T1: deterministic — pure state inspection
  T3: isolated — no filesystem or subprocess
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite the tracking issue
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402
from phase_manager import PhaseState, ProjectState, compute_project_completion  # noqa: E402


def _state(phase_plan, statuses):
    """Build a ProjectState with the given phase_plan and {phase: status} map."""
    return ProjectState(
        name="t",
        current_phase=phase_plan[0] if phase_plan else "clarify",
        created_at="2026-04-22T00:00:00Z",
        phase_plan=list(phase_plan),
        phases={p: PhaseState(status=s) for p, s in statuses.items()},
    )


def test_completion_false_when_later_phases_pending():
    """Issue #562: approving clarify while build+test pending is NOT complete."""
    state = _state(
        ["clarify", "build", "test"],
        {"clarify": "approved", "build": "pending", "test": "pending"},
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is False
    assert remaining == ["build", "test"]


def test_completion_true_only_when_all_approved():
    """is_complete is True only when every phase in phase_plan is approved."""
    state = _state(
        ["clarify", "build"],
        {"clarify": "approved", "build": "approved"},
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is True
    assert remaining == []


def test_completion_false_on_empty_plan():
    """Empty phase_plan is not 'complete' — there's nothing planned yet."""
    state = _state([], {})
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is False
    assert remaining == []


def test_completion_flags_in_progress_as_remaining():
    """A phase in any non-approved status counts as remaining."""
    state = _state(
        ["clarify", "build"],
        {"clarify": "approved", "build": "in_progress"},
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is False
    assert remaining == ["build"]


def test_completion_handles_missing_phase_state():
    """Phases in the plan but absent from state.phases default to 'pending'."""
    state = _state(
        ["clarify", "build"],
        {"clarify": "approved"},  # build is missing — should be treated as pending
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is False
    assert remaining == ["build"]


def test_completion_treats_skipped_as_terminal():
    """Copilot #568 review: 'skipped' phases satisfy completion alongside 'approved'."""
    state = _state(
        ["clarify", "design", "build"],
        {"clarify": "approved", "design": "skipped", "build": "approved"},
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is True
    assert remaining == []


def test_completion_skipped_first_then_remaining():
    """A skipped phase doesn't appear as remaining; pending later phases still do."""
    state = _state(
        ["clarify", "design", "build"],
        {"clarify": "skipped", "design": "approved", "build": "pending"},
    )
    is_complete, remaining = compute_project_completion(state)
    assert is_complete is False
    assert remaining == ["build"]
