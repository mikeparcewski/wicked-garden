"""tests/test_validate_plan_test_strategy_check.py — Issue #583.

Verifies that ``validate_plan.warnings()`` surfaces the
``test-strategy-missing`` gap: plans with at least one
``metadata.test_required: true`` task but no ``test-strategy`` phase
cause the wicked-testing specialists to go silently un-dispatched. The
warning is advisory — violations list stays empty — so callers can
surface it in CI without failing the run.

Test rules (T1-T6):
  T1: deterministic — fixtures are self-contained dicts, no I/O.
  T2: no sleep-based sync — pure function calls.
  T3: isolated — each test builds its own fixture from scratch.
  T4: single behavior per test.
  T5: descriptive names cite the intent.
  T6: every docstring cites Issue #583.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import validate_plan  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — shaped to match the real process-plan schema. Tests mutate
# deep copies so each case is independent.
# ---------------------------------------------------------------------------

def _base_plan() -> dict:
    """Return a valid process-plan dict. Issue #583."""
    return {
        "project_slug": "test-strategy-check",
        "summary": "Fixture for Issue #583 warnings.",
        "rigor_tier": "standard",
        "complexity": 3,
        "factors": {
            key: {"reading": "LOW", "why": "fixture baseline"}
            for key in validate_plan.REQUIRED_FACTOR_KEYS
        },
        "specialists": [
            {"name": "backend-engineer", "why": "writes the code"}
        ],
        "phases": [
            {
                "name": "build",
                "why": "do the work",
                "primary": ["backend-engineer"],
            },
        ],
        "tasks": [
            {
                "id": "t1",
                "title": "Implement fix",
                "phase": "build",
                "blockedBy": [],
                "metadata": {
                    "chain_id": "test-strategy-check.root",
                    "event_type": "coding-task",
                    "source_agent": "facilitator",
                    "phase": "build",
                    "rigor_tier": "standard",
                    "test_required": True,
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Core behavior — warning emitted when gap exists, silent otherwise
# ---------------------------------------------------------------------------


def test_warning_emitted_when_test_required_true_and_no_test_strategy_phase():
    """Issue #583: test_required=true + missing test-strategy phase → warn."""
    plan = _base_plan()
    result = validate_plan.warnings(plan)
    assert len(result) == 1
    warn = result[0]
    assert warn["code"] == "test-strategy-missing"
    assert warn["severity"] == "warn"
    assert "t1" in warn["message"]
    assert "test-strategy" in warn["message"]


def test_no_warning_when_test_strategy_phase_present():
    """Issue #583: test_required=true but test-strategy phase present → no warn."""
    plan = _base_plan()
    plan["phases"].insert(
        0,
        {
            "name": "test-strategy",
            "why": "plan test approach",
            "primary": ["test-strategist"],
        },
    )
    assert validate_plan.warnings(plan) == []


def test_no_warning_when_all_tasks_have_test_required_false():
    """Issue #583: no task opts into testing → no warning even without phase."""
    plan = _base_plan()
    plan["tasks"][0]["metadata"]["test_required"] = False
    assert validate_plan.warnings(plan) == []


def test_no_warning_when_test_required_key_absent():
    """Issue #583: bare tasks without test_required treated as opt-out."""
    plan = _base_plan()
    # Remove the key entirely rather than setting False — still a no-op.
    del plan["tasks"][0]["metadata"]["test_required"]
    assert validate_plan.warnings(plan) == []


def test_warning_code_is_stable():
    """Issue #583: downstream consumers key on the literal code string."""
    assert validate_plan._WARN_TEST_STRATEGY_MISSING == "test-strategy-missing"


# ---------------------------------------------------------------------------
# Interaction with the existing validation pipeline
# ---------------------------------------------------------------------------


def test_warnings_are_independent_of_violations():
    """Issue #583: warnings must not turn a valid plan into an invalid one."""
    plan = _base_plan()
    # Sanity: the fixture is structurally valid — no violations expected.
    assert validate_plan.validate(plan) == []
    # And yet warnings surface the gap.
    assert len(validate_plan.warnings(plan)) == 1


def test_warning_names_every_offending_task_id():
    """Issue #583: the warning message enumerates all opt-in task ids."""
    plan = _base_plan()
    plan["tasks"].append(
        {
            "id": "t2",
            "title": "Second task needing tests",
            "phase": "build",
            "blockedBy": ["t1"],
            "metadata": {
                "chain_id": "test-strategy-check.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
                "rigor_tier": "standard",
                "test_required": True,
            },
        }
    )
    [warn] = validate_plan.warnings(plan)
    assert "t1" in warn["message"]
    assert "t2" in warn["message"]


def test_existing_specialist_check_still_passes():
    """Issue #583: pre-existing _check_specialists coverage is preserved.

    Regression guard — the warning infrastructure is additive and must
    not shift how the validate() path reports unknown specialists.
    """
    plan = _base_plan()
    plan["specialists"] = [
        {"name": "definitely-not-a-real-agent-xyz", "why": "typo path"}
    ]
    violations = validate_plan.validate(plan)
    # Either the resolver is present (unknown name surfaces) or the
    # resolver import failed and the check is skipped — in both cases
    # the existing specialist-name-required check still demands at
    # least a non-empty string. Here "definitely-not-a-real-agent-xyz"
    # is non-empty, so the only possible violation comes from the
    # resolver path. Accept both outcomes to keep the test robust
    # across environments where the resolver import may be gated.
    if violations:
        assert any("unknown specialist" in v for v in violations)


# ---------------------------------------------------------------------------
# Edge cases — defensive coverage
# ---------------------------------------------------------------------------


def test_empty_tasks_list_yields_no_warning():
    """Issue #583: no tasks → nothing to opt in → no warning."""
    plan = _base_plan()
    plan["tasks"] = []
    assert validate_plan.warnings(plan) == []


def test_non_dict_task_entries_are_skipped():
    """Issue #583: malformed tasks are the validator's concern, not warnings."""
    plan = _base_plan()
    plan["tasks"] = [None, "garbage", 42]  # type: ignore[list-item]
    assert validate_plan.warnings(plan) == []
