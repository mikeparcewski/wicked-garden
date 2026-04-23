"""tests/crew/test_gate_overrides_per_project.py — issue #564.

Verifies that per-project gate overrides in state.extras are honored when
resolving the dispatch entry, with precedence:
  1. gate_overrides[gate_name]   (specific)
  2. gate_overrides["*"]          (wildcard)
  3. gate_method                  (legacy shorthand)
  4. gate-policy.json default     (fallback)

Unknown modes are ignored (fail-loud via WARN), preserving the invariant
that misconfiguration cannot silently change dispatch behavior.

Rules:
  T1: deterministic — patches _load_gate_policy to pin the default
  T3: isolated — no filesystem side effects
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite the tracking issue
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402
from phase_manager import PhaseState, ProjectState, _resolve_gate_reviewer  # noqa: E402


_DEFAULT_POLICY = {
    "gates": {
        "requirements-quality": {
            "standard": {
                # 2 reviewers in the default lets council mode overrides
                # satisfy the >=2 invariant without forcing every test to
                # ship its own reviewers list.
                "reviewers": ["requirements-analyst", "senior-engineer"],
                "mode": "sequential",
                "fallback": "senior-engineer",
            }
        }
    }
}


def _state(extras):
    return ProjectState(
        name="t",
        current_phase="clarify",
        created_at="2026-04-22T00:00:00Z",
        phase_plan=["clarify"],
        phases={"clarify": PhaseState(status="pending")},
        extras=dict(extras),
    )


@pytest.fixture(autouse=True)
def _pin_policy():
    """Pin gate-policy.json content so tests are deterministic."""
    with patch.object(phase_manager, "_load_gate_policy", return_value=_DEFAULT_POLICY):
        yield


# ---------------------------------------------------------------------------
# Legacy shorthand — the exact shape the reporter used in #564
# ---------------------------------------------------------------------------


def test_legacy_gate_method_is_honored():
    """Issue #564: state.extras['gate_method']='council' overrides the policy default."""
    state = _state({"gate_method": "council"})
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "council"


def test_no_overrides_preserves_policy_default():
    """When no overrides are set, gate-policy.json wins."""
    state = _state({})
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "sequential"


def test_state_none_preserves_policy_default():
    """Passing state=None (library-level callers) uses the policy default."""
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=None)
    assert entry["mode"] == "sequential"


# ---------------------------------------------------------------------------
# gate_overrides — structured per-gate and wildcard shapes
# ---------------------------------------------------------------------------


def test_gate_overrides_specific_gate_wins():
    """gate_overrides['requirements-quality'] applies to exactly that gate."""
    state = _state({
        "gate_overrides": {"requirements-quality": {"mode": "council"}}
    })
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "council"


def test_gate_overrides_wildcard_applies_to_all():
    """gate_overrides['*'] applies to any gate without a specific override."""
    state = _state({"gate_overrides": {"*": {"mode": "parallel"}}})
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "parallel"


def test_specific_override_beats_wildcard():
    """Precedence: specific gate override outranks wildcard."""
    state = _state({
        "gate_overrides": {
            "*": {"mode": "parallel"},
            "requirements-quality": {"mode": "council", "reviewers": ["a", "b"]},
        }
    })
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "council"


def test_partial_specific_override_layers_on_wildcard(caplog):
    """gemini #568 review: a specific override that only sets 'reviewers' must
    still inherit 'mode' from the wildcard, not silently bypass it."""
    state = _state({
        "gate_overrides": {
            "*": {"mode": "council"},
            "requirements-quality": {"reviewers": ["product-manager", "senior-engineer"]},
        }
    })
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    # Specific layer set reviewers, wildcard layer set mode — both apply.
    assert entry["mode"] == "council"
    assert entry["reviewers"] == ["product-manager", "senior-engineer"]


def test_reviewers_override_applies():
    """gate_overrides can replace the reviewer list too, not just the mode."""
    state = _state({
        "gate_overrides": {
            "requirements-quality": {"reviewers": ["product-manager", "senior-engineer"]}
        }
    })
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["reviewers"] == ["product-manager", "senior-engineer"]


# ---------------------------------------------------------------------------
# Validation — fail loud on bad values
# ---------------------------------------------------------------------------


def test_invalid_mode_is_rejected(caplog):
    """Unknown modes log a WARN and are ignored — never silently applied."""
    state = _state({"gate_method": "turbo-council-9000"})
    with caplog.at_level("WARNING"):
        entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "sequential"  # fell back to policy default
    assert any("turbo-council-9000" in rec.message for rec in caplog.records)


def test_non_list_reviewers_override_is_rejected(caplog):
    """Non-list reviewers override logs a WARN and is ignored."""
    state = _state({
        "gate_overrides": {"requirements-quality": {"reviewers": "not-a-list"}}
    })
    with caplog.at_level("WARNING"):
        entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["reviewers"] == ["requirements-analyst", "senior-engineer"]


def test_override_does_not_mutate_policy_entry():
    """The returned entry is a new dict — the in-memory policy cache is untouched."""
    state = _state({"gate_method": "council", "gate_overrides": {
        "requirements-quality": {"reviewers": ["a", "b"]}
    }})
    _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    # Fetch default again — should still be 'sequential', proving no mutation.
    state2 = _state({})
    entry2 = _resolve_gate_reviewer("requirements-quality", "standard", state=state2)
    assert entry2["mode"] == "sequential"


# ---------------------------------------------------------------------------
# Semantic invariants — Copilot #568 review
# ---------------------------------------------------------------------------


def test_council_with_lt_2_reviewers_reverts_to_policy_default(caplog):
    """council mode requires >=2 reviewers; an invalid override is rejected."""
    state = _state({
        "gate_overrides": {
            "requirements-quality": {"mode": "council", "reviewers": ["only-one"]}
        }
    })
    with caplog.at_level("WARNING"):
        entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    # Reverted to policy default (sequential / [requirements-analyst]).
    assert entry["mode"] == "sequential"
    assert entry["reviewers"] == ["requirements-analyst", "senior-engineer"]
    assert any("invariants" in rec.message for rec in caplog.records)


def test_sequential_with_empty_reviewers_reverts_to_policy_default(caplog):
    """sequential mode requires >=1 reviewer; empty reviewers list is invalid."""
    state = _state({
        "gate_overrides": {
            "requirements-quality": {"mode": "sequential", "reviewers": []}
        }
    })
    with caplog.at_level("WARNING"):
        entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "sequential"
    assert entry["reviewers"] == ["requirements-analyst", "senior-engineer"]


def test_self_check_with_empty_reviewers_is_allowed():
    """self-check mode legitimately runs without reviewers — must NOT be rejected."""
    state = _state({
        "gate_overrides": {
            "requirements-quality": {"mode": "self-check", "reviewers": []}
        }
    })
    entry = _resolve_gate_reviewer("requirements-quality", "standard", state=state)
    assert entry["mode"] == "self-check"
    assert entry["reviewers"] == []
