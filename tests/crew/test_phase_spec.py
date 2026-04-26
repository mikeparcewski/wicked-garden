"""tests/crew/test_phase_spec.py — issue #566 phase-spec inspector.

Covers the read-only phase-spec action: derives purely from phases.json +
gate-policy.json, returns all the fields a caller needs to decide what to
attempt (skip, approve, dispatch) before attempting it.

Rules:
  T1: deterministic — reads static config
  T3: isolated — no live project state
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
from phase_manager import get_phase_spec  # noqa: E402


def test_phase_spec_clarify_has_required_fields():
    """Issue #566: phase-spec must expose the fields a caller needs before acting."""
    spec = get_phase_spec("clarify")
    # Shape contract
    assert spec["phase"] == "clarify"
    assert spec["known"] is True
    for key in (
        "is_skippable",
        "gate_required",
        "min_gate_score",
        "required_deliverables",
        "depends_on",
        "valid_skip_reasons",
        "gate_policy",
    ):
        assert key in spec, f"phase-spec must expose '{key}'"


def test_phase_spec_clarify_values():
    """Known clarify phase config values surface verbatim from phases.json."""
    spec = get_phase_spec("clarify")
    assert spec["is_skippable"] is False
    assert spec["gate_required"] is True
    assert spec["gate_name"] == "requirements-quality"


def test_phase_spec_required_deliverables_normalized():
    """required_deliverables are dicts with file/min_bytes — the caller shouldn't need to re-parse."""
    spec = get_phase_spec("clarify")
    deliverables = spec["required_deliverables"]
    assert len(deliverables) > 0
    for entry in deliverables:
        assert isinstance(entry, dict)
        assert "file" in entry
        assert "min_bytes" in entry


def test_phase_spec_unknown_phase_reports_not_known():
    """An unknown phase name returns known=False without crashing."""
    spec = get_phase_spec("does-not-exist-phase-xyz")
    assert spec["known"] is False
    assert spec["phase"] == "does-not-exist-phase-xyz"
    # Fields still present with safe defaults — caller can rely on the shape.
    assert spec["required_deliverables"] == []
    assert spec["depends_on"] == []


def test_phase_spec_required_deliverables_keys_match_executor_pseudocode():
    """phases.json deliverable entries use 'file'/'min_bytes' keys — the executor must use these (#660).

    Pin against schema mismatch: the phase-executor pseudocode was corrected in
    #660 to access d['file'] and d['min_bytes'] instead of the wrong d['name']
    and d['min_size'].  This test asserts that phases.json still uses 'file' and
    'min_bytes' so any future rename is caught before it silently breaks the
    executor verification logic.
    """
    # Check every phase that has at least one deliverable.
    phases_with_deliverables = [
        p for p in ("clarify", "design", "test-strategy", "challenge", "test", "review", "operate")
    ]
    for phase_name in phases_with_deliverables:
        spec = get_phase_spec(phase_name)
        deliverables = spec["required_deliverables"]
        if not deliverables:
            continue
        for entry in deliverables:
            assert isinstance(entry, dict), (
                f"Phase '{phase_name}': required_deliverables entry must be a dict, "
                f"got {type(entry).__name__!r}"
            )
            assert "file" in entry, (
                f"Phase '{phase_name}': deliverable dict must have 'file' key "
                f"(executor uses d.get('file')), keys present: {list(entry.keys())}"
            )
            assert "min_bytes" in entry, (
                f"Phase '{phase_name}': deliverable dict must have 'min_bytes' key "
                f"(executor uses d.get('min_bytes', 100)), keys present: {list(entry.keys())}"
            )
            assert "name" not in entry, (
                f"Phase '{phase_name}': old 'name' key found — schema drifted back "
                f"to wrong shape.  Executor uses 'file', not 'name'."
            )
            assert "min_size" not in entry, (
                f"Phase '{phase_name}': old 'min_size' key found — schema drifted back "
                f"to wrong shape.  Executor uses 'min_bytes', not 'min_size'."
            )


def test_phase_spec_gate_policy_keyed_by_tier():
    """When gate_required, gate_policy exposes reviewers per rigor tier (minimal/standard/full)."""
    spec = get_phase_spec("clarify")
    policy = spec["gate_policy"]
    assert isinstance(policy, dict)
    # At least one tier present with a reviewers field
    assert any("reviewers" in tier_entry for tier_entry in policy.values())
