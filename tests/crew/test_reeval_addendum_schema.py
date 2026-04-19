"""tests/crew/test_reeval_addendum_schema.py — Schema tests for reeval_addendum 1.1.0 (D4).

Provenance: AC-4, AC-13
T1: deterministic — no randomness, no I/O beyond tempfile writes
T3: isolated — each test uses independent in-memory records or temp dirs
T4: single focus per test
T5: descriptive names
T6: each docstring cites its AC
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from crew.reeval_addendum import _validate_record, append, read, VALID_ARCHETYPES  # noqa: E402
from crew.validate_reeval_addendum import validate_record  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_V10_RECORD = {
    "chain_id": "my-project.design",
    "triggered_at": "2026-04-19T10:00:00Z",
    "trigger": "phase-end",
    "prior_rigor_tier": "standard",
    "new_rigor_tier": "standard",
    "mutations": [],
    "mutations_applied": [],
    "mutations_deferred": [],
    "validator_version": "1.0.0",
}

_V11_RECORD = {
    **_V10_RECORD,
    "validator_version": "1.1.0",
    "archetype": "code-repo",
    "archetype_evidence": {
        "source": "bundle",
        "bundle_present": True,
        "phase": "test-strategy",
        "gate": "testability",
        "verdict": "APPROVE",
        "score": 0.92,
        "reason": "code-repo: unit-results present + tests passing",
        "min_score": 0.70,
        "evidence_required": ["unit-results"],
        "evidence_present": ["unit-results"],
        "evidence_absent": [],
        "test_types_declared": ["unit"],
        "conditions_cleared": [],
        "conditions_deferred": [],
        "fallback_marker": None,
    },
}


# ---------------------------------------------------------------------------
# AC-4: Backward compatibility — 1.0 records valid under 1.1.0 validator
# ---------------------------------------------------------------------------

def test_backward_compat_v10_record_validates_without_error():
    """AC-13: 1.0 record (no archetype fields) must pass the 1.1.0 validator."""
    err = _validate_record(_V10_RECORD)
    assert err is None, f"1.0 record should be valid under 1.1.0 validator, got: {err}"


def test_backward_compat_v11_record_validates_with_archetype():
    """AC-4: 1.1.0 record with archetype and archetype_evidence passes validation."""
    err = _validate_record(_V11_RECORD)
    assert err is None, f"1.1.0 record should be valid, got: {err}"


def test_backward_compat_mixed_file():
    """AC-13: mixed JSONL file with 1.0 and 1.1.0 records — all must validate.

    Simulates AC-13: 3 old-format records + 1 new-format record in the same JSONL.
    """
    tmp = Path(tempfile.mkdtemp())
    project_dir = tmp / "my-project"
    phase_dir = project_dir / "phases" / "design"
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Append 3 v1.0 records and 1 v1.1.0 record
    for i in range(3):
        append(project_dir, phase="design", record=dict(_V10_RECORD, chain_id=f"my-project.design.{i}"))
    append(project_dir, phase="design", record=_V11_RECORD)

    records = read(project_dir, phase_filter="design")
    assert len(records) == 4
    # All records should be dicts (no parse errors)
    for r in records:
        assert isinstance(r, dict)
    # Last record has archetype
    assert records[-1].get("archetype") == "code-repo"


# ---------------------------------------------------------------------------
# AC-4: qe-evaluator trigger validation (MINOR-1 from challenge)
# ---------------------------------------------------------------------------

def test_qe_evaluator_trigger_forbids_mutations():
    """AC-4 / MINOR-1: qe-evaluator trigger must have empty mutations list."""
    bad = {
        **_V10_RECORD,
        "trigger": "qe-evaluator:testability",
        "mutations": [{"op": "prune", "why": "sneaky authority creep"}],
    }
    err = _validate_record(bad)
    assert err is not None, "Should reject qe-evaluator trigger with non-empty mutations"
    assert "mutations" in err.lower()


def test_qe_evaluator_trigger_forbids_mutations_applied():
    """AC-4 / MINOR-1: qe-evaluator trigger must have empty mutations_applied list."""
    bad = {
        **_V10_RECORD,
        "trigger": "qe-evaluator:evidence-quality",
        "mutations_applied": [{"op": "augment", "why": "sneaky"}],
    }
    err = _validate_record(bad)
    assert err is not None, "Should reject qe-evaluator trigger with non-empty mutations_applied"
    assert "mutations_applied" in err.lower()


def test_qe_evaluator_conditions_manifest_path_prefix_enforced():
    """AC-4 / MINOR-1: conditions_deferred manifest_path must be phases/testability/ or phases/evidence-quality/."""
    bad = {
        **_V10_RECORD,
        "trigger": "qe-evaluator:testability",
        "archetype_evidence": {
            "conditions_deferred": [
                {
                    "id": "QE-EVAL-bad",
                    "severity": "major",
                    "reason": "some reason",
                    "manifest_path": "phases/clarify/conditions-manifest.json",
                }
            ]
        },
    }
    err = _validate_record(bad)
    assert err is not None, "Should reject manifest_path under phases/clarify/ for qe-evaluator trigger"
    assert "phases/clarify" in err or "manifest_path" in err


def test_valid_qe_evaluator_trigger_passes_validation():
    """AC-4: valid qe-evaluator:testability trigger with correct manifest_path passes."""
    good = {
        **_V10_RECORD,
        "trigger": "qe-evaluator:testability",
        "archetype_evidence": {
            "conditions_deferred": [
                {
                    "id": "QE-EVAL-ok",
                    "severity": "major",
                    "reason": "some reason",
                    "manifest_path": "phases/testability/conditions-manifest.json",
                }
            ]
        },
    }
    err = _validate_record(good)
    assert err is None, f"Valid qe-evaluator record should pass, got: {err}"
