"""tests/test_event_schema_gate_finding_lifecycle.py — gate-finding lifecycle validation (Issue #570).

Provenance: Issue #570
T1: deterministic — pure in-memory, no I/O
T3: isolated — no shared state
T4: single focus per test
T5: descriptive names
T6: each docstring cites its contract
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _event_schema import validate_metadata  # noqa: E402


_SHELL_METADATA = {
    "chain_id": "proj.clarify.requirements-quality",
    "event_type": "gate-finding",
    "source_agent": "facilitator",
    "phase": "clarify",
}


# ---------------------------------------------------------------------------
# #570: facilitator shell at plan time validates without verdict/min_score/score
# ---------------------------------------------------------------------------

def test_gate_finding_shell_without_verdict_is_valid_at_creation():
    """#570: facilitator-emitted shell (no verdict/min_score/score) must validate
    at TaskCreate (status defaults to not-completed).
    """
    err = validate_metadata(_SHELL_METADATA)
    assert err is None, f"plan-time shell should validate, got: {err}"


def test_gate_finding_shell_validates_with_pending_status():
    """#570: explicit status=pending must also validate without verdict fields."""
    err = validate_metadata(_SHELL_METADATA, status="pending")
    assert err is None, f"pending shell should validate, got: {err}"


def test_gate_finding_shell_validates_with_in_progress_status():
    """#570: in_progress gate task (reviewer running) must not require verdict yet."""
    err = validate_metadata(_SHELL_METADATA, status="in_progress")
    assert err is None, f"in_progress gate should validate, got: {err}"


# ---------------------------------------------------------------------------
# #570: completion transition enforces the full contract
# ---------------------------------------------------------------------------

def test_gate_finding_completion_without_verdict_fails():
    """#570: TaskUpdate(status=completed) on a gate-finding missing verdict/scores
    must fail validation — reviewer is contractually obligated to fill them.
    """
    err = validate_metadata(_SHELL_METADATA, status="completed")
    assert err is not None, "completed gate without verdict must fail"
    assert "verdict" in err and "min_score" in err and "score" in err, (
        f"error should name all three missing fields, got: {err}"
    )


def test_gate_finding_completion_with_approve_fields_passes():
    """#570: completed gate-finding with APPROVE verdict + satisfying score validates."""
    metadata = {
        **_SHELL_METADATA,
        "verdict": "APPROVE",
        "min_score": 0.7,
        "score": 0.85,
    }
    err = validate_metadata(metadata, status="completed")
    assert err is None, f"completed APPROVE should validate, got: {err}"


def test_gate_finding_completion_approve_below_min_score_fails():
    """#570: completion still enforces APPROVE score >= min_score ordering."""
    metadata = {
        **_SHELL_METADATA,
        "verdict": "APPROVE",
        "min_score": 0.7,
        "score": 0.5,
    }
    err = validate_metadata(metadata, status="completed")
    assert err is not None and "score" in err and "min_score" in err, (
        f"sub-min_score APPROVE should fail, got: {err}"
    )


def test_gate_finding_completion_conditional_without_manifest_fails():
    """#570: CONDITIONAL verdict at completion still requires conditions_manifest_path."""
    metadata = {
        **_SHELL_METADATA,
        "verdict": "CONDITIONAL",
        "min_score": 0.7,
        "score": 0.65,
    }
    err = validate_metadata(metadata, status="completed")
    assert err is not None and "conditions_manifest_path" in err, (
        f"CONDITIONAL without manifest should fail, got: {err}"
    )


# ---------------------------------------------------------------------------
# #570: enum + type checks still fire whenever the field is present
# ---------------------------------------------------------------------------

def test_gate_finding_shell_with_invalid_verdict_fails_even_without_completion():
    """#570: an invalid verdict value is rejected regardless of status —
    you can't poison the shell with a bogus enum value.
    """
    metadata = {**_SHELL_METADATA, "verdict": "MAYBE"}
    err = validate_metadata(metadata)
    assert err is not None and "MAYBE" in err, (
        f"invalid verdict should fail even pre-completion, got: {err}"
    )


def test_gate_finding_shell_with_only_score_is_valid():
    """#570: partial fill (reviewer started but hasn't completed) must validate —
    the plan shell accepts score-only writes during reviewer runs.
    """
    metadata = {**_SHELL_METADATA, "score": 0.9}
    err = validate_metadata(metadata)
    assert err is None, f"partial fill should validate pre-completion, got: {err}"


def test_gate_finding_completion_with_non_numeric_score_fails():
    """#570: numeric type check still fires at completion when verdict is APPROVE."""
    metadata = {
        **_SHELL_METADATA,
        "verdict": "APPROVE",
        "min_score": 0.7,
        "score": "banana",
    }
    err = validate_metadata(metadata, status="completed")
    assert err is not None and "numeric" in err, (
        f"non-numeric score should fail, got: {err}"
    )


# ---------------------------------------------------------------------------
# #570: status param is backward compatible for other event types
# ---------------------------------------------------------------------------

def test_status_completed_does_not_affect_plain_task_event_type():
    """#570: status=completed on event_type=task must not invent extra requirements."""
    metadata = {
        "chain_id": "proj.root",
        "event_type": "task",
        "source_agent": "researcher",
    }
    err = validate_metadata(metadata, status="completed")
    assert err is None, f"completed plain task should validate, got: {err}"
