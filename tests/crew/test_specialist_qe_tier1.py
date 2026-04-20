"""tests/crew/test_specialist_qe_tier1.py — AC-22 testability routing shape test.

Covers:
  AC-22 — QE category in specialist.json contains only Tier-1 names from
           _wicked_testing_tier1.TIER1_AGENTS. This is a config-shape test that
           validates routing fidelity without requiring a live facilitator run.

Rules:
  T1: deterministic — reads static files only
  T3: isolated — no external dependencies
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite ACs
"""

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _wicked_testing_tier1 import TIER1_AGENTS  # noqa: E402

_SPECIALIST_JSON = _REPO_ROOT / ".claude-plugin" / "specialist.json"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def specialist_data():
    return json.loads(_SPECIALIST_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qe_specialist(specialist_data):
    specialists = specialist_data if isinstance(specialist_data, list) else specialist_data.get("specialists", [])
    matches = [s for s in specialists if s.get("role") == "quality-engineering"]
    assert matches, "No quality-engineering specialist found in specialist.json"
    return matches[0]


# ---------------------------------------------------------------------------
# AC-22: QE category agents are all Tier-1 wicked-testing names
# ---------------------------------------------------------------------------

def test_qe_specialist_exists(specialist_data):
    """AC-22 — specialist.json has a quality-engineering entry."""
    specialists = specialist_data if isinstance(specialist_data, list) else specialist_data.get("specialists", [])
    roles = [s.get("role") for s in specialists]
    assert "quality-engineering" in roles, (
        "specialist.json must contain a quality-engineering specialist for testability routing"
    )


def test_qe_agents_all_tier1(qe_specialist):
    """
    AC-22 — every agent name listed in the QE specialist entry is a valid
    Tier-1 wicked-testing agent. Non-wicked-testing names are permitted
    (is_valid_wt_reviewer returns True for them) but all wicked-testing:*
    names must be in TIER1_AGENTS.
    """
    from _wicked_testing_tier1 import is_valid_wt_reviewer
    agents = qe_specialist.get("tier1_agents", qe_specialist.get("agents", []))
    assert agents, "QE specialist must declare at least one agent"
    violations = [a for a in agents if not is_valid_wt_reviewer(a)]
    assert not violations, (
        f"QE specialist.json references non-Tier-1 wicked-testing agents: {violations}"
    )


def test_qe_agents_include_testability_signals(qe_specialist):
    """
    AC-22 — QE specialist includes at least one of the four named
    testability-routing agents: test-strategist, testability-reviewer,
    requirements-quality-analyst, risk-assessor.
    These are the agents the facilitator routes to when testability signals
    are present in the task.
    """
    testability_tier1 = {
        "wicked-testing:test-strategist",
        "wicked-testing:testability-reviewer",
        "wicked-testing:requirements-quality-analyst",
        "wicked-testing:risk-assessor",
    }
    agents = set(qe_specialist.get("tier1_agents", qe_specialist.get("agents", [])))
    overlap = agents & testability_tier1
    assert overlap, (
        f"QE specialist must include at least one testability-routing Tier-1 agent "
        f"({sorted(testability_tier1)}); found none in {sorted(agents)}"
    )


def test_qe_agents_no_legacy_wg_qe_names(qe_specialist):
    """
    AC-22 — QE specialist must not contain any stale wicked-garden:qe:* names.
    These were migrated to wicked-testing:* in v7.0.
    """
    agents = qe_specialist.get("tier1_agents", qe_specialist.get("agents", []))
    legacy = [a for a in agents if a.startswith("wicked-garden:qe:")]
    assert not legacy, (
        f"QE specialist still contains legacy wicked-garden:qe:* names: {legacy}"
    )
