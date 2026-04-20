"""tests/crew/test_gate_adjudicator_dispatch.py — Suite B: dispatch wiring + multi-repo safety.

Provenance: AC-3, AC-14a, AC-14b, AC-15a, AC-15b
T1: deterministic — no randomness, no wall-clock, no sleep
T2: condition-based waits only (none needed here)
T3: isolated — reads gate-policy.json from repo root; uses in-memory fixtures
T4: single behavior per test
T5: descriptive names
T6: each docstring cites its AC
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Path setup — use the same pattern as test_phase_manager.py (R3: no magic)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _SCRIPTS_DIR / "crew"

for _p in [str(_SCRIPTS_CREW), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gate_adjudicator as qe  # noqa: E402

# ---------------------------------------------------------------------------
# Gate-policy.json fixture (loaded once)
# ---------------------------------------------------------------------------

_GATE_POLICY_PATH = _REPO_ROOT / ".claude-plugin" / "gate-policy.json"


def _load_gate_policy() -> Dict[str, Any]:
    return json.loads(_GATE_POLICY_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Suite B — AC-3 static assertions
# ---------------------------------------------------------------------------


def test_gate_policy_testability_reviewer_is_gate_adjudicator():
    """
    AC-3 + AC-17 — gate-policy.json static assertion.
    gates.testability.standard.reviewers must contain gate-adjudicator,
    expressed as the fully-qualified 'wicked-garden:crew:gate-adjudicator' (AC-17,
    post-t10 rename) or the bare form for backward compat with pre-t10 snapshots.
    test-strategist must be absent from all testability reviewer lists.
    """
    gp = _load_gate_policy()
    testability = gp["gates"]["testability"]

    _GA_NAMES = {"gate-adjudicator", "wicked-garden:crew:gate-adjudicator"}
    std_reviewers = testability["standard"]["reviewers"]
    assert any(r in _GA_NAMES for r in std_reviewers), (
        f"Expected gate-adjudicator (bare or FQ) in testability.standard.reviewers, "
        f"got {std_reviewers}"
    )
    for tier in ("minimal", "standard", "full"):
        reviewers = testability[tier].get("reviewers", [])
        assert "test-strategist" not in reviewers, (
            f"test-strategist found in testability.{tier}.reviewers: {reviewers}"
        )


def test_gate_policy_evidence_quality_reviewer_is_gate_adjudicator():
    """
    AC-3 + AC-17 — gate-policy.json static assertion.
    gates.evidence-quality.standard.reviewers must contain gate-adjudicator
    (bare or fully-qualified wicked-garden:crew:gate-adjudicator).
    test-strategist must be absent from all evidence-quality reviewer lists.
    """
    gp = _load_gate_policy()
    eq = gp["gates"]["evidence-quality"]

    _GA_NAMES = {"gate-adjudicator", "wicked-garden:crew:gate-adjudicator"}
    std_reviewers = eq["standard"]["reviewers"]
    assert any(r in _GA_NAMES for r in std_reviewers), (
        f"Expected gate-adjudicator (bare or FQ) in evidence-quality.standard.reviewers, "
        f"got {std_reviewers}"
    )
    for tier in ("minimal", "standard", "full"):
        reviewers = eq[tier].get("reviewers", [])
        assert "test-strategist" not in reviewers, (
            f"test-strategist found in evidence-quality.{tier}.reviewers: {reviewers}"
        )


def test_gate_policy_context_bundle_contains_archetype():
    """
    AC-3 + design.md §4.4 (A1 resolution: context_fields key name).
    Both testability and evidence-quality at standard and full tiers must include
    'archetype' in their context_fields list.
    """
    gp = _load_gate_policy()
    for gate_name in ("testability", "evidence-quality"):
        gate = gp["gates"][gate_name]
        for tier in ("standard", "full"):
            fields = gate[tier].get("context_fields", [])
            assert "archetype" in fields, (
                f"'archetype' missing from gates.{gate_name}.{tier}.context_fields: {fields}"
            )


def test_gate_adjudicator_absent_from_requirements_quality():
    """
    AC-15a static check.
    Parse gate-policy.json. Inspect gates.requirements-quality at all rigor tiers.
    'gate-adjudicator' must not appear in any reviewers list.
    """
    gp = _load_gate_policy()
    rq = gp["gates"]["requirements-quality"]
    for tier in ("minimal", "standard", "full"):
        reviewers = rq[tier].get("reviewers", [])
        assert "gate-adjudicator" not in reviewers, (
            f"gate-adjudicator found in requirements-quality.{tier}.reviewers: {reviewers}"
        )


def test_gate_adjudicator_absent_from_design_quality():
    """
    AC-15a static check.
    Parse gate-policy.json. Inspect gates.design-quality at all rigor tiers.
    'gate-adjudicator' must not appear in any reviewers list.
    """
    gp = _load_gate_policy()
    dq = gp["gates"]["design-quality"]
    for tier in ("minimal", "standard", "full"):
        reviewers = dq[tier].get("reviewers", [])
        assert "gate-adjudicator" not in reviewers, (
            f"gate-adjudicator found in design-quality.{tier}.reviewers: {reviewers}"
        )


# ---------------------------------------------------------------------------
# Suite B — AC-14a, AC-14b multi-repo safety
# ---------------------------------------------------------------------------


def test_multi_repo_archetype_missing_affected_repos_conditional():
    """
    AC-14a — evaluator CONDITIONAL when multi-repo archetype is set but
    affected_repos key is absent from process-plan.json.
    Fixture: ctx with archetype='multi-repo', plan dict has no affected_repos key.
    Verdict must be 'CONDITIONAL' and reason must contain
    'multi-repo: affected_repos missing' (exact substring per AC-14a).
    """
    ctx = {"gate_name": "testability", "phase": "test-strategy", "archetype": "multi-repo"}
    plan = {"name": "some-project"}  # no affected_repos key

    result = qe.evaluate(ctx, plan=plan)

    assert result["verdict"] == "CONDITIONAL", f"Expected CONDITIONAL, got {result['verdict']}"
    assert "multi-repo: affected_repos missing" in result["reason"], (
        f"Expected 'multi-repo: affected_repos missing' in reason: {result['reason']!r}"
    )


def test_affected_repos_empty_list_conditional():
    """
    AC-14b — evaluator CONDITIONAL when process-plan.json declares affected_repos
    as an empty list []. Reason must contain 'multi-repo: affected_repos empty'
    to distinguish from the missing-key case (AC-14a).
    """
    ctx = {"gate_name": "testability", "phase": "test-strategy", "archetype": "multi-repo"}
    plan = {"name": "some-project", "affected_repos": []}

    result = qe.evaluate(ctx, plan=plan)

    assert result["verdict"] == "CONDITIONAL", f"Expected CONDITIONAL, got {result['verdict']}"
    assert "multi-repo: affected_repos empty" in result["reason"], (
        f"Expected 'multi-repo: affected_repos empty' in reason: {result['reason']!r}"
    )


def test_single_repo_no_false_multi_repo_conditional():
    """
    AC-14b non-trigger negative assertion.
    A single-repo project (archetype='code-repo', no affected_repos key) must
    NOT receive a multi-repo CONDITIONAL verdict. Ensures the AC-14 check is
    gated on multi-repo archetype, not mere key absence.
    """
    ctx = {
        "gate_name": "testability",
        "phase": "test-strategy",
        "archetype": "code-repo",
        "evidence_present": ["unit-results"],
        "evidence_sizes": {"unit-results": 500},
    }
    plan = {"name": "single-repo-project"}  # no affected_repos — but archetype is code-repo

    result = qe.evaluate(ctx, plan=plan)

    # Must NOT have a multi-repo reason
    assert "multi-repo" not in result.get("reason", ""), (
        f"Unexpected multi-repo reason in single-repo result: {result['reason']!r}"
    )
    # And must not CONDITIONAL purely due to multi-repo
    for cond in result.get("conditions", []):
        assert "multi-repo" not in cond.get("reason", ""), (
            f"Unexpected multi-repo condition in single-repo result: {cond}"
        )


# ---------------------------------------------------------------------------
# Suite B — AC-15b runtime dispatcher check
# ---------------------------------------------------------------------------


def test_dispatcher_never_invokes_gate_adjudicator_at_non_target_gates():
    """
    AC-15b — runtime dispatcher recording test.
    Verify that gate-adjudicator's own non-target-gate refusal fires when gate_name
    is set to requirements-quality or design-quality. This is the agent-side
    backstop (AC-15b) independent of gate-policy.json.

    Wraps the evaluate() function directly: call with gate='requirements-quality'
    and gate='design-quality' for each of the 4 MVP archetypes at all 3 rigor
    tiers (simulated by passing the gate name directly). Assert zero APPROVE or
    non-CONDITIONAL-refusing verdicts are returned.
    """
    non_target_gates = ["requirements-quality", "design-quality"]
    archetypes = ["code-repo", "docs-only", "skill-agent-authoring", "config-infra"]

    for gate in non_target_gates:
        for archetype in archetypes:
            ctx = {
                "gate_name": gate,
                "phase": "clarify",
                "archetype": archetype,
            }
            result = qe.evaluate(ctx)

            # Must be CONDITIONAL-0.60 refusal
            assert result["verdict"] == "CONDITIONAL", (
                f"Expected CONDITIONAL at non-target gate {gate!r} "
                f"for archetype {archetype!r}, got {result['verdict']}"
            )
            assert result["score"] == 0.60, (
                f"Expected score=0.60 at non-target gate {gate!r}, got {result['score']}"
            )
            assert "refusing" in result["reason"], (
                f"Expected 'refusing' in reason for non-target gate {gate!r}: "
                f"{result['reason']!r}"
            )
            # Verify the reason names the gate explicitly
            assert gate in result["reason"], (
                f"Expected gate name {gate!r} in reason: {result['reason']!r}"
            )
