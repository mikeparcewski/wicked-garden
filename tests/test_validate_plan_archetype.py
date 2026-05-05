"""tests/test_validate_plan_archetype.py — Issue #810.

Verifies the top-level ``archetype`` field on the facilitator JSON output
schema. Promoted from ``tasks[*].metadata.archetype`` so downstream Python
consumers can probe ``plan["archetype"]`` directly. The original bug was
that the field existed only inside per-task metadata, so a ``data.get(
"archetype")`` probe at the top level returned ``None`` even though the
agent's narrative reported the archetype correctly.

Coverage:
  * top-level value must be one of the 7-value enum when present
  * ``archetype_confidence`` must be a float in ``[0.0, 1.0]`` when present
  * ``archetype_signals`` must be a list of non-empty strings when present
  * agreement invariant — top-level vs every ``tasks[*].metadata.archetype``
    must match (the silent-disagreement class of bug Issue #810 surfaced)
  * absence of all three new fields validates exactly as today (backward
    compatible — minimum-disruption rollout)

Test rules (T1-T6):
  T1: deterministic — pure dict fixtures, no I/O.
  T2: no sleep-based sync.
  T3: isolated — every test deep-copies a fresh fixture.
  T4: one behavior per test.
  T5: descriptive names.
  T6: docstrings cite Issue #810.
"""

from __future__ import annotations

# sys.path setup (scripts/ at index 0, scripts/crew/ appended) is owned by
# tests/conftest.py — see its module docstring for the shadowing rationale
# (scripts/crew/crew.py would mask the crew/ package if scripts/crew/ were
# inserted at index 0). Don't duplicate the manipulation here.

import validate_plan


def _base_plan() -> dict:
    """Return a valid plan that is silent on archetype. Issue #810."""
    return {
        "project_slug": "archetype-test",
        "summary": "Fixture for Issue #810.",
        "rigor_tier": "standard",
        "complexity": 3,
        "factors": {
            key: {"reading": "LOW", "risk_level": "high_risk", "why": "baseline"}
            for key in validate_plan.REQUIRED_FACTOR_KEYS
        },
        "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
        "phases": [
            {"name": "build", "why": "do the work", "primary": ["backend-engineer"]}
        ],
        "tasks": [
            {
                "id": "t1",
                "title": "Implement fix",
                "phase": "build",
                "blockedBy": [],
                "metadata": {
                    "chain_id": "archetype-test.root",
                    "event_type": "coding-task",
                    "source_agent": "facilitator",
                    "phase": "build",
                    "rigor_tier": "standard",
                },
            }
        ],
    }


def test_plan_without_archetype_validates_exactly_as_today():
    """Issue #810: backward compat — absent archetype must not produce violations."""
    plan = _base_plan()
    assert validate_plan.validate(plan) == []


def test_top_level_archetype_in_enum_validates():
    """Issue #810: every documented enum value must validate at the top level."""
    for arch in validate_plan.VALID_ARCHETYPES:
        plan = _base_plan()
        plan["archetype"] = arch
        assert validate_plan.validate(plan) == [], f"enum value {arch!r} rejected"


def test_top_level_archetype_outside_enum_is_rejected():
    """Issue #810: random strings must be rejected with a citation to the enum."""
    plan = _base_plan()
    plan["archetype"] = "random-thing"
    violations = validate_plan.validate(plan)
    assert any("archetype — must be one of" in v for v in violations)


def test_archetype_confidence_above_one_is_rejected():
    """Issue #810: confidence above 1.0 is invalid (probabilities cap at 1)."""
    plan = _base_plan()
    plan["archetype"] = "code-repo"
    plan["archetype_confidence"] = 1.5
    violations = validate_plan.validate(plan)
    assert any("archetype_confidence" in v for v in violations)


def test_archetype_confidence_bool_is_rejected():
    """Issue #810: bool is a subclass of int in Python — explicitly reject it."""
    plan = _base_plan()
    plan["archetype"] = "code-repo"
    plan["archetype_confidence"] = True
    violations = validate_plan.validate(plan)
    assert any("archetype_confidence" in v for v in violations)


def test_archetype_signals_must_be_list_of_non_empty_strings():
    """Issue #810: shape check on the human-readable signals list."""
    plan = _base_plan()
    plan["archetype"] = "code-repo"
    plan["archetype_signals"] = ["valid signal", "  "]
    violations = validate_plan.validate(plan)
    assert any("archetype_signals[1]" in v for v in violations)


def test_agreement_invariant_top_level_vs_task_metadata():
    """Issue #810: top-level archetype must equal every task's metadata.archetype.

    This is the exact silent-disagreement class of bug the issue surfaced —
    callers probing the top level got `None`, callers probing tasks got a
    value, and the two could drift. Reject disagreement at validation time.
    """
    plan = _base_plan()
    plan["archetype"] = "code-repo"
    plan["tasks"][0]["metadata"]["archetype"] = "docs-only"
    violations = validate_plan.validate(plan)
    assert any("disagrees with top-level archetype" in v for v in violations)


def test_agreement_passes_when_top_level_matches_task_metadata():
    """Issue #810: matching values must validate clean."""
    plan = _base_plan()
    plan["archetype"] = "code-repo"
    plan["tasks"][0]["metadata"]["archetype"] = "code-repo"
    assert validate_plan.validate(plan) == []


def test_task_metadata_archetype_alone_remains_valid():
    """Issue #810: per-task archetype without a top-level field stays valid.

    Many existing plans omit the top-level field; the agreement invariant
    must NOT fire when the top-level value is absent (no source of truth
    to compare against). This test guards against an over-eager invariant.
    """
    plan = _base_plan()
    plan["tasks"][0]["metadata"]["archetype"] = "code-repo"
    assert validate_plan.validate(plan) == []


def test_validator_archetype_enum_in_sync_with_archetype_detect():
    """Issue #810: VALID_ARCHETYPES must mirror archetype_detect's 7 values.

    Drift here means the validator stops catching producer regressions
    (e.g. the detector adds an 8th archetype but the validator silently
    rejects it as unknown). The canonical list lives in
    ``scripts/crew/archetype_detect.py``; the validator copy is duplicated
    intentionally to avoid a hard import dependency in CI sandboxes.
    """
    expected = {
        "schema-migration",
        "multi-repo",
        "testing-only",
        "config-infra",
        "skill-agent-authoring",
        "docs-only",
        "code-repo",
    }
    assert validate_plan.VALID_ARCHETYPES == expected
