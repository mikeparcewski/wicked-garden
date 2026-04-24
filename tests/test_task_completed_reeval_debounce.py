"""tests/test_task_completed_reeval_debounce.py — re-eval debounce rule (Issue #572).

Provenance: Issue #572 — wicked-garden's task_completed hook used to set
``facilitator_reeval_due`` on every task completion that carried a chain_id,
including gate-finding shell completions the orchestrator just acked. That
caused the facilitator re-evaluation directive to fire on every prompt for
meaningless state changes (observed: 3 re-eval fires in ~10 minutes during a
single ``crew:just-finish`` run, plus 41,640 events of accumulated bus lag).

The new rule debounces the trigger so re-eval fires ONLY when the completed
task's metadata satisfies one of:
    1. event_type == phase-transition
    2. event_type == gate-finding AND verdict == REJECT

T1: deterministic — pure in-memory, no I/O for the rule tests
T3: isolated — each test builds its own metadata dict
T4: single focus per test (one event_type/verdict combination)
T5: descriptive names — each name spells out the input and expected outcome
T6: each docstring cites Issue #572
"""

import json
import sys
from pathlib import Path

import pytest

# The hook script is not on sys.path by default — add it before import.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOK_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
if str(_HOOK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOK_SCRIPTS))

from task_completed import (  # noqa: E402
    EVENT_TYPE_GATE_FINDING,
    EVENT_TYPE_PHASE_TRANSITION,
    VERDICT_REJECT,
    _read_task_metadata,
    _should_trigger_reeval,
)


# ---------------------------------------------------------------------------
# Issue #572 — _should_trigger_reeval rule (the four AC combinations)
# ---------------------------------------------------------------------------

def test_plain_task_with_chain_id_does_not_trigger_reeval():
    """Issue #572 AC-1: a completed event_type=task with a chain_id must NOT
    set facilitator_reeval_due. The old rule (any chain_id => trigger) was the
    root cause of 41k+ queued bus events and spurious re-eval directives.
    """
    metadata = {
        "chain_id": "proj.root",
        "event_type": "task",
        "source_agent": "researcher",
        "phase": "discovery",
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is False, f"plain task must not trigger; reason={reason}"
    assert reason == "event_type_task"


def test_gate_finding_with_approve_verdict_does_not_trigger_reeval():
    """Issue #572 AC-2: a completed gate-finding with verdict=APPROVE must NOT
    set the flag. This was the dominant noise source — gate auto-approvals
    fired re-eval twice in a single just-finish run for no reason.
    """
    metadata = {
        "chain_id": "proj.clarify.requirements-quality",
        "event_type": EVENT_TYPE_GATE_FINDING,
        "source_agent": "facilitator",
        "phase": "clarify",
        "verdict": "APPROVE",
        "min_score": 0.7,
        "score": 0.85,
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is False, f"APPROVE must not trigger; reason={reason}"
    assert reason == "gate_verdict_APPROVE"


def test_gate_finding_with_reject_verdict_triggers_reeval():
    """Issue #572 AC-3: a completed gate-finding with verdict=REJECT MUST set
    the flag — a rejection is a meaningful state change that warrants the
    facilitator re-planning the chain.
    """
    metadata = {
        "chain_id": "proj.design.architecture-quality",
        "event_type": EVENT_TYPE_GATE_FINDING,
        "source_agent": "senior-engineer",
        "phase": "design",
        "verdict": VERDICT_REJECT,
        "min_score": 0.7,
        "score": 0.4,
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is True, f"REJECT must trigger; reason={reason}"
    assert reason == "gate_reject"


def test_phase_transition_event_triggers_reeval():
    """Issue #572 AC-4: a completed event_type=phase-transition MUST set the
    flag — phase boundaries are exactly when the facilitator should re-plan.
    """
    metadata = {
        "chain_id": "proj.design",
        "event_type": EVENT_TYPE_PHASE_TRANSITION,
        "source_agent": "facilitator",
        "phase": "design",
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is True, f"phase-transition must trigger; reason={reason}"
    assert reason == "phase_transition"


# ---------------------------------------------------------------------------
# Issue #572 — additional rule edges (fail-open, conditional verdicts)
# ---------------------------------------------------------------------------

def test_gate_finding_with_conditional_verdict_does_not_trigger_reeval():
    """Issue #572: CONDITIONAL is not REJECT — the conditions-manifest path
    handles its own follow-up; the facilitator should not be re-invoked.
    """
    metadata = {
        "chain_id": "proj.build.evidence-quality",
        "event_type": EVENT_TYPE_GATE_FINDING,
        "source_agent": "qe-reviewer",
        "phase": "build",
        "verdict": "CONDITIONAL",
        "min_score": 0.7,
        "score": 0.65,
        "conditions_manifest_path": "phases/build/conditions-manifest.json",
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is False, f"CONDITIONAL must not trigger; reason={reason}"
    assert reason == "gate_verdict_CONDITIONAL"


def test_missing_metadata_does_not_trigger_reeval():
    """Issue #572: fail-open rule — if metadata is unreadable, do NOT set the
    flag. The old behaviour (set on truthy chain_id) was the root cause; the
    new rule requires positive evidence of a phase-transition or REJECT.
    """
    should, reason = _should_trigger_reeval(None)
    assert should is False
    assert reason == "no_metadata"

    should, reason = _should_trigger_reeval({})
    assert should is False
    assert reason == "no_metadata"


def test_gate_finding_without_verdict_does_not_trigger_reeval():
    """Issue #572: a gate-finding shell with no verdict (mid-review) must not
    fire re-eval — the reviewer is still working.
    """
    metadata = {
        "chain_id": "proj.review.quality",
        "event_type": EVENT_TYPE_GATE_FINDING,
        "source_agent": "reviewer",
        "phase": "review",
    }
    should, reason = _should_trigger_reeval(metadata)
    assert should is False
    assert reason == "gate_verdict_missing"


# ---------------------------------------------------------------------------
# Issue #572 — _read_task_metadata fail-open behaviour
# ---------------------------------------------------------------------------

def test_read_task_metadata_returns_none_for_missing_session():
    """Issue #572: empty session_id must return None — not raise."""
    assert _read_task_metadata("", "task-id") is None


def test_read_task_metadata_returns_none_for_missing_task_id():
    """Issue #572: empty task_id must return None — not raise."""
    assert _read_task_metadata("session-id", "") is None


def test_read_task_metadata_returns_none_for_missing_file(tmp_path, monkeypatch):
    """Issue #572: missing task file must return None — fail-open."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    # No file written under tmp_path/tasks/<session>/<task>.json
    assert _read_task_metadata("sess-1", "task-1") is None


def test_read_task_metadata_returns_metadata_dict_when_present(tmp_path, monkeypatch):
    """Issue #572: when the task file exists with a metadata dict, it is
    returned exactly so a single read serves both event_type and verdict.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    task_dir = tmp_path / "tasks" / "sess-1"
    task_dir.mkdir(parents=True)
    payload = {
        "task_id": "task-1",
        "subject": "Phase: design",
        "status": "completed",
        "metadata": {
            "chain_id": "proj.design",
            "event_type": EVENT_TYPE_PHASE_TRANSITION,
            "source_agent": "facilitator",
            "phase": "design",
        },
    }
    (task_dir / "task-1.json").write_text(json.dumps(payload), encoding="utf-8")

    metadata = _read_task_metadata("sess-1", "task-1")
    assert metadata == payload["metadata"]


def test_read_task_metadata_returns_none_for_corrupt_json(tmp_path, monkeypatch):
    """Issue #572: corrupt JSON must return None — task completion is never
    blocked by a re-eval signal error.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    task_dir = tmp_path / "tasks" / "sess-1"
    task_dir.mkdir(parents=True)
    (task_dir / "task-1.json").write_text("{not valid json", encoding="utf-8")
    assert _read_task_metadata("sess-1", "task-1") is None


def test_read_task_metadata_returns_none_when_metadata_field_missing(tmp_path, monkeypatch):
    """Issue #572: a task file with no metadata key must return None — the
    rule explicitly requires positive evidence to trigger re-eval.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    task_dir = tmp_path / "tasks" / "sess-1"
    task_dir.mkdir(parents=True)
    (task_dir / "task-1.json").write_text(
        json.dumps({"task_id": "task-1", "status": "completed"}),
        encoding="utf-8",
    )
    assert _read_task_metadata("sess-1", "task-1") is None


# ---------------------------------------------------------------------------
# Issue #572 — bus drain helper in prompt_submit.py is fail-silent
# ---------------------------------------------------------------------------

def test_drain_bus_cursor_never_raises_when_npx_missing(monkeypatch):
    """Issue #572: the bus drain must fail-silent when npx is unavailable.
    A missing wicked-bus install must never break prompt submission.
    """
    import importlib

    # prompt_submit lives in hooks/scripts — import it via the same path setup
    if "prompt_submit" in sys.modules:
        prompt_submit = importlib.reload(sys.modules["prompt_submit"])
    else:
        import prompt_submit  # noqa: F401
        prompt_submit = sys.modules["prompt_submit"]

    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda _name: None)

    # Must not raise
    prompt_submit._drain_bus_cursor()


def test_drain_bus_cursor_swallows_subprocess_exceptions(monkeypatch):
    """Issue #572: even if npx exists but the subprocess explodes (timeout,
    non-zero exit, OSError), the drain must swallow the failure.
    """
    import importlib
    import subprocess as _subprocess

    if "prompt_submit" in sys.modules:
        prompt_submit = importlib.reload(sys.modules["prompt_submit"])
    else:
        import prompt_submit  # noqa: F401
        prompt_submit = sys.modules["prompt_submit"]

    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda _name: "/usr/local/bin/npx")

    def _boom(*_args, **_kwargs):
        raise _subprocess.TimeoutExpired(cmd="npx", timeout=3)

    monkeypatch.setattr(_subprocess, "run", _boom)

    # Must not raise
    prompt_submit._drain_bus_cursor()
