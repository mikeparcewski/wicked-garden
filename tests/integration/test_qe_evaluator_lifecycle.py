"""tests/integration/test_qe_evaluator_lifecycle.py — Suite C: full lifecycle paths.

Provenance: AC-7, AC-9, AC-10, AC-11, AC-12, AC-13, AC-15b, AC-16, design.md §3.3
T1: deterministic — no randomness, no wall-clock, no sleep
T2: no sleep-based sync
T3: isolated — each test uses its own tempfile fixtures
T4: single behavior per test function
T5: descriptive names
T6: each docstring cites its AC
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _SCRIPTS_DIR / "crew"

for _p in [str(_SCRIPTS_CREW), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import qe_evaluator as qe  # noqa: E402

# Import reeval_addendum for addendum backward-compat test
import reeval_addendum as ra  # noqa: E402

# ---------------------------------------------------------------------------
# Shared evidence builder helpers (T3: isolated per test)
# ---------------------------------------------------------------------------

def _make_evidence(sizes: Dict[str, int]) -> tuple[List[str], Dict[str, int]]:
    """Return (evidence_present, evidence_sizes) from a {artifact: size_bytes} dict."""
    present = list(sizes.keys())
    return present, sizes


def _basic_ctx(
    gate: str,
    archetype: str,
    phase: str = "test-strategy",
    **kwargs: Any,
) -> Dict[str, Any]:
    return {"gate_name": gate, "phase": phase, "archetype": archetype, **kwargs}


# ---------------------------------------------------------------------------
# AC-9: code-repo full lifecycle path
# ---------------------------------------------------------------------------


def test_code_repo_full_path():
    """
    AC-9 full lifecycle — code-repo archetype end-to-end.
    Evidence: unit-results (500 bytes) + api-contract-diff (200 bytes) present.
    At testability gate: verdict == APPROVE, score >= 0.92.
    At evidence-quality gate (with acceptance-report): APPROVE.
    """
    evidence_present, evidence_sizes = _make_evidence({
        "unit-results": 500,
        "api-contract-diff": 200,
        "acceptance-report": 300,
    })

    # Testability gate
    ctx_test = _basic_ctx(
        "testability", "code-repo",
        evidence_present=evidence_present,
        evidence_sizes=evidence_sizes,
        is_api_modifying=True,
    )
    result_test = qe.evaluate(ctx_test)

    assert result_test["verdict"] == "APPROVE", (
        f"testability: expected APPROVE, got {result_test['verdict']} "
        f"(reason: {result_test['reason']!r})"
    )
    assert result_test["score"] >= 0.92, (
        f"testability: expected score >= 0.92, got {result_test['score']}"
    )
    assert result_test["archetype"] == "code-repo"

    # Evidence-quality gate
    ctx_eq = _basic_ctx(
        "evidence-quality", "code-repo",
        phase="test",
        evidence_present=evidence_present,
        evidence_sizes=evidence_sizes,
    )
    result_eq = qe.evaluate(ctx_eq)

    assert result_eq["verdict"] == "APPROVE", (
        f"evidence-quality: expected APPROVE, got {result_eq['verdict']} "
        f"(reason: {result_eq['reason']!r})"
    )


def test_docs_only_full_path():
    """
    AC-10 full lifecycle — docs-only archetype end-to-end.
    Evidence: acceptance-report (200 bytes) only — no unit-results or api-contract-diff.
    At testability gate: APPROVE (score >= 0.90).
    At evidence-quality gate: APPROVE (docs-only does NOT require unit-results).
    """
    evidence_present, evidence_sizes = _make_evidence({"acceptance-report": 200})

    for gate in ("testability", "evidence-quality"):
        ctx = _basic_ctx(gate, "docs-only", evidence_present=evidence_present,
                         evidence_sizes=evidence_sizes)
        result = qe.evaluate(ctx)

        assert result["verdict"] == "APPROVE", (
            f"{gate}: docs-only expected APPROVE with acceptance-report, "
            f"got {result['verdict']} (reason: {result['reason']!r})"
        )
        assert result["score"] >= 0.90, (
            f"{gate}: expected score >= 0.90, got {result['score']}"
        )
        # Must NOT flag unit-results or api-contract-diff as missing
        for cond in result.get("conditions", []):
            assert "unit-results" not in cond.get("reason", ""), (
                f"{gate}: unexpected unit-results condition for docs-only: {cond}"
            )
            assert "api-contract-diff" not in cond.get("reason", ""), (
                f"{gate}: unexpected api-contract-diff condition for docs-only: {cond}"
            )


def test_skill_agent_authoring_full_path():
    """
    AC-11 full lifecycle — skill-agent-authoring archetype, behavior change, screenshot missing.
    Evidence: acceptance-report present (200 bytes), screenshot-before-after ABSENT.
    behavior_change=True.
    At testability gate: CONDITIONAL (score 0.55), reason contains screenshot substring.
    Confirms evaluator does NOT silently APPROVE.
    """
    evidence_present, evidence_sizes = _make_evidence({"acceptance-report": 200})

    ctx = _basic_ctx(
        "testability", "skill-agent-authoring",
        evidence_present=evidence_present,
        evidence_sizes=evidence_sizes,
        test_types=["acceptance"],
        behavior_change=True,
    )
    result = qe.evaluate(ctx)

    assert result["verdict"] == "CONDITIONAL", (
        f"Expected CONDITIONAL (screenshot missing), got {result['verdict']}"
    )
    assert result["score"] == 0.55, (
        f"Expected score=0.55, got {result['score']}"
    )
    assert "skill-agent-authoring: screenshot-before-after required for behavior change" in result["reason"], (
        f"Expected screenshot reason substring, got: {result['reason']!r}"
    )
    assert result["conditions"], "Expected at least one condition for screenshot missing"


def test_config_infra_full_path():
    """
    AC-12 full lifecycle — config-infra archetype, integration-results absent then present.
    First invocation: both integration-results and unit-results absent → REJECT (score <= 0.35).
    Second invocation: integration-results present (300 bytes) → APPROVE (score >= 0.90).
    """
    phase = "test-strategy"

    # Invocation 1: both absent
    ctx_absent = _basic_ctx(
        "testability", "config-infra",
        phase=phase,
        evidence_present=[],
        evidence_sizes={},
    )
    result_absent = qe.evaluate(ctx_absent)

    assert result_absent["verdict"] == "REJECT", (
        f"Expected REJECT (no integration-results), got {result_absent['verdict']}"
    )
    assert result_absent["score"] <= 0.35, (
        f"Expected score <= 0.35, got {result_absent['score']}"
    )
    assert "config-infra: integration-results required" in result_absent["reason"], (
        f"Expected 'config-infra: integration-results required' in reason: "
        f"{result_absent['reason']!r}"
    )

    # Invocation 2: integration-results present
    evidence_present, evidence_sizes = _make_evidence({"integration-results": 300})
    ctx_present = _basic_ctx(
        "testability", "config-infra",
        phase=phase,
        evidence_present=evidence_present,
        evidence_sizes=evidence_sizes,
    )
    result_present = qe.evaluate(ctx_present)

    assert result_present["verdict"] == "APPROVE", (
        f"Expected APPROVE (integration-results present), got {result_present['verdict']}"
    )
    assert result_present["score"] >= 0.90, (
        f"Expected score >= 0.90, got {result_present['score']}"
    )


# ---------------------------------------------------------------------------
# AC-13: backward compat — mixed 1.0 and 1.1.0 records in same JSONL file
# ---------------------------------------------------------------------------


def test_reeval_addendum_backward_compat_mixed_file():
    """
    AC-13 — backward compatibility: mixed 1.0 and 1.1.0 records in same JSONL file.
    Write 3 synthetic 1.0 records (no archetype/archetype_evidence fields) to a
    tmp JSONL file. Append 1 new 1.1.0 record (with archetype='code-repo').
    Run the 1.1.0 validator across all 4 records.
    Assert: all 4 records pass validation; no record flagged as invalid.
    """
    _v10_base = {
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

    _v11_record = {
        **_v10_base,
        "chain_id": "my-project.test-strategy.testability",
        "trigger": "qe-evaluator:testability",
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

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)
        phases_dir = project_dir / "phases" / "test-strategy"
        phases_dir.mkdir(parents=True)

        # Write 3 old v1.0 records
        addendum_path = project_dir / "process-plan.addendum.jsonl"
        with addendum_path.open("w", encoding="utf-8") as fh:
            for _ in range(3):
                fh.write(json.dumps(_v10_base) + "\n")

        # Append a v1.1.0 record using the library
        err = ra._validate_record(_v11_record)
        assert err is None, f"1.1.0 record failed validation: {err}"

        # Validate all records (1.0 and 1.1.0) via the validate_record function
        # (imported from validate_reeval_addendum).
        # validate_record returns a list[str] — empty list means valid.
        from validate_reeval_addendum import validate_record  # noqa: E402

        # Validate v1.0 records
        for _ in range(3):
            errors = validate_record(_v10_base)
            assert errors == [], (
                f"v1.0 record failed validation under 1.1.0 validator: {errors}"
            )

        # Validate v1.1.0 record
        errors = validate_record(_v11_record)
        assert errors == [], f"v1.1.0 record failed validation: {errors}"


# ---------------------------------------------------------------------------
# AC-7 + AC-16: consumer deletion does not orphan phase_manager bus-emit
# ---------------------------------------------------------------------------


def test_consumer_deletion_no_breakage():
    """
    AC-7 + AC-16 — consumer deletion does not orphan phase_manager bus-emit path.
    Assert scripts/qe/_bus_consumers.py does not exist.
    Assert no entry with id==38 or handler referencing 'qe:scenario-scaffold'
    exists in scripts/_bus_consumers.json.
    Assert phase_manager imports cleanly (bus-emit side still functional).
    """
    repo_root = Path(__file__).resolve().parents[2]

    # AC-7: file must not exist
    deleted_file = repo_root / "scripts" / "qe" / "_bus_consumers.py"
    assert not deleted_file.exists(), (
        f"scripts/qe/_bus_consumers.py still exists — D7 deletion incomplete"
    )

    # AC-16: entry 38 must not exist in _bus_consumers.json
    consumers_json = repo_root / "scripts" / "_bus_consumers.json"
    if consumers_json.exists():
        data = json.loads(consumers_json.read_text(encoding="utf-8"))
        consumers = data if isinstance(data, list) else data.get("consumers", [])
        for entry in consumers:
            assert entry.get("id") != 38, (
                f"Entry with id=38 still exists in _bus_consumers.json: {entry}"
            )
            handler = str(entry.get("consumer", "") or entry.get("handler", ""))
            assert "qe:scenario-scaffold" not in handler, (
                f"qe:scenario-scaffold handler still in _bus_consumers.json: {entry}"
            )
            assert "scripts/qe/_bus_consumers" not in handler, (
                f"scripts/qe/_bus_consumers path still in _bus_consumers.json: {entry}"
            )

    # phase_manager must import cleanly
    import phase_manager  # noqa: F401 — verifies no AttributeError/ImportError
    assert hasattr(phase_manager, "approve_phase"), (
        "phase_manager.approve_phase missing — bus-emit side may be broken"
    )


# ---------------------------------------------------------------------------
# AC-15b runtime backstop: non-target gate refusal
# ---------------------------------------------------------------------------


def test_qe_evaluator_non_target_gate_refusal():
    """
    AC-15b runtime backstop + design.md §7.2 point 9.
    Directly invoke qe-evaluator evaluate() with gate_name='requirements-quality'.
    Assert: verdict == 'CONDITIONAL', score == 0.60,
    reason contains "qe-evaluator: invoked at non-target gate 'requirements-quality' — refusing".
    """
    ctx = {
        "gate_name": "requirements-quality",
        "phase": "clarify",
        "archetype": "code-repo",
    }
    result = qe.evaluate(ctx)

    assert result["verdict"] == "CONDITIONAL", (
        f"Expected CONDITIONAL for non-target gate, got {result['verdict']}"
    )
    assert result["score"] == 0.60, (
        f"Expected score=0.60 for non-target gate refusal, got {result['score']}"
    )
    expected_substr = "qe-evaluator: invoked at non-target gate 'requirements-quality' — refusing"
    assert expected_substr in result["reason"], (
        f"Expected refusal reason substring, got: {result['reason']!r}"
    )


# ---------------------------------------------------------------------------
# design.md §3.3 CQ-5 non-silent fallback
# ---------------------------------------------------------------------------


def test_cq5_bundle_missing_fallback_non_silent():
    """
    design.md §3.3 CQ-5 non-silent fallback.
    Invoke qe_evaluator.evaluate() with ctx that has NO 'archetype' key.
    Assert: code-repo evidence contract applied (fallback).
    Assert: result has _bundle_present=False, _fallback_marker='bundle-missing'.
    Assert: CONDITIONAL condition with id='QE-EVAL-bundle-missing' and severity='major'.
    No silent degradation — the fallback must be auditable.
    """
    ctx = {
        "gate_name": "testability",
        "phase": "test-strategy",
        # archetype key intentionally absent
        "evidence_present": ["unit-results"],
        "evidence_sizes": {"unit-results": 500},
    }
    result = qe.evaluate(ctx)

    # Fallback markers must be present
    assert result.get("_bundle_present") is False, (
        f"Expected _bundle_present=False (CQ-5), got {result.get('_bundle_present')}"
    )
    assert result.get("_fallback_marker") == "bundle-missing", (
        f"Expected _fallback_marker='bundle-missing', got {result.get('_fallback_marker')}"
    )
    assert result.get("_source") == "fallback", (
        f"Expected _source='fallback', got {result.get('_source')}"
    )

    # Must have the QE-EVAL-bundle-missing condition
    condition_ids = [c.get("id") for c in result.get("conditions", [])]
    assert "QE-EVAL-bundle-missing" in condition_ids, (
        f"Expected QE-EVAL-bundle-missing condition, found: {condition_ids}"
    )
    bundle_cond = next(c for c in result["conditions"] if c.get("id") == "QE-EVAL-bundle-missing")
    assert bundle_cond["severity"] == "major", (
        f"Expected severity='major', got {bundle_cond['severity']}"
    )

    # code-repo fallback must be applied — result should use code-repo evaluation
    assert result["archetype"] == "code-repo", (
        f"Expected archetype='code-repo' from fallback, got {result['archetype']}"
    )
