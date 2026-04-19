"""tests/crew/test_atomic_landing_guard.py — MINOR-2: atomic landing CI guard.

Provenance: challenge build-notes.md MINOR-2, design.md §8.1
T1: deterministic — purely filesystem assertions, no I/O beyond Path.exists()
T2: no sleep-based sync
T3: isolated — read-only; checks repo HEAD
T4: single behavior per assertion
T5: descriptive test name
T6: docstring cites build-note
"""

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_atomic_landing_co_presence():
    """
    challenge build-notes.md MINOR-2 — atomic landing guard.
    Verifies co-presence of all three required files that must land atomically
    to avoid the D2/D3 wedge state (design.md §8.1):

    1. scripts/crew/archetype_detect.py must exist (D1).
    2. agents/crew/qe-evaluator.md must exist (D2).
    3. .claude-plugin/gate-policy.json must reference 'qe-evaluator' at both
       testability and evidence-quality stanzas (D3).

    If any check fails, the atomic landing is incomplete and the wedge state
    described in design.md §8.1 could occur.
    """
    # 1. archetype_detect.py exists
    archetype_detect = _REPO_ROOT / "scripts" / "crew" / "archetype_detect.py"
    assert archetype_detect.exists(), (
        f"scripts/crew/archetype_detect.py missing — D1 not landed: {archetype_detect}"
    )

    # 2. qe-evaluator.md exists
    qe_agent = _REPO_ROOT / "agents" / "crew" / "qe-evaluator.md"
    assert qe_agent.exists(), (
        f"agents/crew/qe-evaluator.md missing — D2 not landed: {qe_agent}"
    )

    # 3. gate-policy.json references qe-evaluator at testability + evidence-quality
    gate_policy_path = _REPO_ROOT / ".claude-plugin" / "gate-policy.json"
    assert gate_policy_path.exists(), (
        f".claude-plugin/gate-policy.json missing: {gate_policy_path}"
    )

    gp = json.loads(gate_policy_path.read_text(encoding="utf-8"))
    gates = gp.get("gates", {})

    # testability must have qe-evaluator in at least one reviewer list
    testability = gates.get("testability", {})
    testability_reviewers = set()
    for tier in ("minimal", "standard", "full"):
        testability_reviewers.update(testability.get(tier, {}).get("reviewers", []))
        # Also count fallback
        fallback = testability.get(tier, {}).get("fallback", "")
        if fallback:
            testability_reviewers.add(fallback)
    assert "qe-evaluator" in testability_reviewers, (
        f"qe-evaluator not found in testability gate (any tier or fallback): "
        f"{testability_reviewers}"
    )

    # evidence-quality must have qe-evaluator in at least one reviewer list
    eq = gates.get("evidence-quality", {})
    eq_reviewers = set()
    for tier in ("minimal", "standard", "full"):
        eq_reviewers.update(eq.get(tier, {}).get("reviewers", []))
        fallback = eq.get(tier, {}).get("fallback", "")
        if fallback:
            eq_reviewers.add(fallback)
    assert "qe-evaluator" in eq_reviewers, (
        f"qe-evaluator not found in evidence-quality gate (any tier or fallback): "
        f"{eq_reviewers}"
    )
