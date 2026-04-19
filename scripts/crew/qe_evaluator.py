#!/usr/bin/env python3
"""qe_evaluator.py — Archetype-aware evidence evaluator (D2 Python companion).

Encodes the per-archetype score-band tables from design.md §1 (CQ-3).
This module is the testable Python companion to agents/crew/qe-evaluator.md.
The agent spec is the authoritative human-readable contract; this module
provides deterministic, stdlib-only evaluation logic for unit/integration tests.

Public API:
    evaluate(ctx: dict, plan: dict | None = None) -> dict

    ctx keys (QeEvaluatorContext):
        gate_name:    "testability" | "evidence-quality"  (REQUIRED)
        phase:        str                                  (REQUIRED)
        archetype:    str | absent                         (triggers CQ-5 if missing/invalid)
        reviewer:     "qe-evaluator"
        project:      str (optional)
        shared_context_path: str (optional)

    Returns QeEvaluatorVerdict dict with keys:
        verdict, score, reason, conditions, reviewer, archetype, min_score

Stdlib-only. No side effects on import.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants (R3 — no magic values)
# ---------------------------------------------------------------------------

MIN_SCORE: float = 0.70
EVIDENCE_SIZE_FLOOR: int = 100  # bytes; files below this are treated as absent

VALID_TARGET_GATES = frozenset({"testability", "evidence-quality"})

VALID_ARCHETYPES = frozenset({
    "code-repo",
    "docs-only",
    "skill-agent-authoring",
    "config-infra",
    "multi-repo",
    "testing-only",
    "schema-migration",
})

# Deferred archetypes: full contract not yet implemented; fall back to code-repo.
DEFERRED_ARCHETYPES = frozenset({
    "testing-only",
    "schema-migration",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _condition(cid: str, severity: str, reason: str, phase: str) -> Dict[str, Any]:
    """Build a QeEvaluatorCondition dict."""
    return {
        "id": cid,
        "severity": severity,
        "reason": reason,
        "manifest_path": f"phases/{phase}/conditions-manifest.json",
    }


def _verdict(
    verdict: str,
    score: float,
    reason: str,
    conditions: List[Dict[str, Any]],
    archetype: str,
) -> Dict[str, Any]:
    """Build a QeEvaluatorVerdict dict."""
    return {
        "verdict": verdict,
        "score": score,
        "reason": reason,
        "conditions": conditions,
        "reviewer": "qe-evaluator",
        "archetype": archetype,
        "min_score": MIN_SCORE,
    }


def _evidence_size_ok(size_bytes: Optional[int]) -> bool:
    """Return True if evidence file is large enough to count (>=100 bytes)."""
    if size_bytes is None:
        return False
    return size_bytes >= EVIDENCE_SIZE_FLOOR


# ---------------------------------------------------------------------------
# Per-archetype score-band tables (design.md §1)
# ---------------------------------------------------------------------------

def _eval_code_repo(
    gate: str,
    evidence_present: List[str],
    evidence_sizes: Dict[str, int],
    is_api_modifying: bool,
    phase: str,
) -> Dict[str, Any]:
    """AC-9 — code-repo evidence contract."""
    has_unit = "unit-results" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("unit-results")
    )
    has_api_diff = "api-contract-diff" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("api-contract-diff")
    )
    has_integration = "integration-results" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("integration-results")
    )
    has_acceptance = "acceptance-report" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("acceptance-report")
    )

    # REJECT: both results absent
    if not has_unit and not has_integration:
        return _verdict(
            "REJECT", 0.25,
            "code-repo: unit-results and integration-results both absent",
            [_condition("QE-EVAL-results-absent", "blocker",
                        "code-repo: unit-results and integration-results both absent", phase)],
            "code-repo",
        )

    # CONDITIONAL: unit-results missing or failing
    if not has_unit:
        return _verdict(
            "CONDITIONAL", 0.45,
            "code-repo: unit-results missing or failing",
            [_condition("QE-EVAL-unit-missing", "major",
                        "code-repo: unit-results missing or failing", phase)],
            "code-repo",
        )

    # evidence-quality gate: acceptance-report required
    if gate == "evidence-quality" and not has_acceptance:
        return _verdict(
            "CONDITIONAL", 0.50,
            "code-repo: acceptance-report missing at evidence-quality",
            [_condition("QE-EVAL-acceptance-missing", "major",
                        "code-repo: acceptance-report missing at evidence-quality", phase)],
            "code-repo",
        )

    # API-modifying task: api-contract-diff required
    if is_api_modifying and not has_api_diff:
        return _verdict(
            "CONDITIONAL", 0.65,
            "code-repo: api-contract-diff missing for API-modifying task",
            [_condition("QE-EVAL-api-diff-missing", "low",
                        "code-repo: api-contract-diff missing for API-modifying task", phase)],
            "code-repo",
        )

    # APPROVE
    if has_api_diff:
        return _verdict("APPROVE", 0.92,
                        "code-repo: unit-results present + tests passing; api-contract-diff present",
                        [], "code-repo")
    return _verdict("APPROVE", 0.82,
                    "code-repo: unit-results present + tests passing",
                    [], "code-repo")


def _eval_docs_only(
    gate: str,
    evidence_present: List[str],
    evidence_sizes: Dict[str, int],
    phase: str,
) -> Dict[str, Any]:
    """AC-10 — docs-only evidence contract."""
    acceptance_size = evidence_sizes.get("acceptance-report")

    if "acceptance-report" not in evidence_present or acceptance_size is None:
        return _verdict(
            "CONDITIONAL", 0.50,
            "docs-only: acceptance-report required",
            [_condition("QE-EVAL-acceptance-absent", "major",
                        "docs-only: acceptance-report required", phase)],
            "docs-only",
        )

    if acceptance_size < EVIDENCE_SIZE_FLOOR:
        return _verdict(
            "CONDITIONAL", 0.70,
            "docs-only: acceptance-report under evidence-size floor",
            [_condition("QE-EVAL-acceptance-small", "low",
                        "docs-only: acceptance-report under evidence-size floor", phase)],
            "docs-only",
        )

    return _verdict("APPROVE", 0.90,
                    "docs-only: acceptance-report present (size ok)",
                    [], "docs-only")


def _eval_skill_agent_authoring(
    gate: str,
    evidence_present: List[str],
    evidence_sizes: Dict[str, int],
    test_types: List[str],
    behavior_change: bool,
    phase: str,
) -> Dict[str, Any]:
    """AC-11 — skill-agent-authoring evidence contract."""
    has_acceptance = "acceptance-report" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("acceptance-report")
    )
    has_screenshot = "screenshot-before-after" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("screenshot-before-after")
    )

    if gate == "testability":
        if not has_acceptance:
            return _verdict(
                "CONDITIONAL", 0.45,
                "skill-agent-authoring: acceptance-report required",
                [_condition("QE-EVAL-acceptance-absent", "major",
                            "skill-agent-authoring: acceptance-report required", phase)],
                "skill-agent-authoring",
            )
        if behavior_change and not has_screenshot:
            return _verdict(
                "CONDITIONAL", 0.55,
                "skill-agent-authoring: screenshot-before-after required for behavior change",
                [_condition("QE-EVAL-screenshot-missing", "major",
                            "skill-agent-authoring: screenshot-before-after required for behavior change",
                            phase)],
                "skill-agent-authoring",
            )
        if "acceptance" not in test_types:
            return _verdict(
                "CONDITIONAL", 0.65,
                "skill-agent-authoring: test_types must include 'acceptance'",
                [_condition("QE-EVAL-test-types", "low",
                            "skill-agent-authoring: test_types must include 'acceptance'", phase)],
                "skill-agent-authoring",
            )
        return _verdict("APPROVE", 0.88,
                        "skill-agent-authoring: acceptance-report + acceptance test_type present",
                        [], "skill-agent-authoring")

    # evidence-quality gate
    if not has_acceptance and not has_screenshot:
        return _verdict(
            "REJECT", 0.30,
            "skill-agent-authoring: both acceptance-report and screenshot-before-after absent",
            [_condition("QE-EVAL-both-absent", "blocker",
                        "skill-agent-authoring: both acceptance-report and screenshot-before-after absent",
                        phase)],
            "skill-agent-authoring",
        )
    if not behavior_change or has_screenshot:
        return _verdict("APPROVE", 0.90 if has_screenshot else 0.80,
                        "skill-agent-authoring: evidence sufficient at evidence-quality",
                        [], "skill-agent-authoring")
    # behavior change + no screenshot at evidence-quality
    return _verdict(
        "CONDITIONAL", 0.55,
        "skill-agent-authoring: screenshot-before-after required for behavior change",
        [_condition("QE-EVAL-screenshot-missing", "major",
                    "skill-agent-authoring: screenshot-before-after required for behavior change",
                    phase)],
        "skill-agent-authoring",
    )


def _eval_config_infra(
    gate: str,
    evidence_present: List[str],
    evidence_sizes: Dict[str, int],
    phase: str,
) -> Dict[str, Any]:
    """AC-12 — config-infra evidence contract."""
    has_integration = "integration-results" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("integration-results")
    )
    has_unit = "unit-results" in evidence_present and _evidence_size_ok(
        evidence_sizes.get("unit-results")
    )
    integration_failing = (
        "integration-results" in evidence_present
        and not _evidence_size_ok(evidence_sizes.get("integration-results"))
    )

    if has_integration:
        return _verdict("APPROVE", 0.90,
                        "config-infra: integration-results present + tests passing",
                        [], "config-infra")
    if integration_failing:
        return _verdict(
            "REJECT", 0.40,
            "config-infra: integration-results present but failing",
            [_condition("QE-EVAL-integration-failing", "blocker",
                        "config-infra: integration-results present but failing", phase)],
            "config-infra",
        )
    if has_unit:
        return _verdict(
            "CONDITIONAL", 0.72,
            "config-infra: integration-results preferred; unit-results accepted at boundary",
            [_condition("QE-EVAL-integration-preferred", "low",
                        "config-infra: integration-results preferred; unit-results accepted at boundary",
                        phase)],
            "config-infra",
        )
    # Both absent
    return _verdict(
        "REJECT", 0.35,
        "config-infra: integration-results required",
        [_condition("QE-EVAL-integration-absent", "blocker",
                    "config-infra: integration-results required", phase)],
        "config-infra",
    )


# ---------------------------------------------------------------------------
# Multi-repo safety pre-check (AC-14a, AC-14b)
# ---------------------------------------------------------------------------

def _check_multi_repo_safety(plan: Optional[Dict[str, Any]], phase: str) -> Optional[Dict[str, Any]]:
    """Return a CONDITIONAL verdict if multi-repo safety conditions trigger, else None."""
    if plan is None:
        # No plan dict → treat affected_repos as missing
        return _verdict(
            "CONDITIONAL", 0.55,
            "multi-repo: affected_repos missing",
            [_condition("QE-EVAL-multi-repo-missing", "major",
                        "multi-repo: affected_repos missing", phase)],
            "multi-repo",
        )
    if "affected_repos" not in plan:
        return _verdict(
            "CONDITIONAL", 0.55,
            "multi-repo: affected_repos missing",
            [_condition("QE-EVAL-multi-repo-missing", "major",
                        "multi-repo: affected_repos missing", phase)],
            "multi-repo",
        )
    if plan["affected_repos"] == []:
        return _verdict(
            "CONDITIONAL", 0.55,
            "multi-repo: affected_repos empty",
            [_condition("QE-EVAL-multi-repo-empty", "major",
                        "multi-repo: affected_repos empty", phase)],
            "multi-repo",
        )
    return None  # Safety check passes


# ---------------------------------------------------------------------------
# CQ-5 fallback (non-silent)
# ---------------------------------------------------------------------------

def _apply_cq5_fallback(
    raw_archetype: Any,
    gate: str,
    phase: str,
    project: str,
) -> tuple[str, str, bool, Optional[str]]:
    """Determine effective archetype, handling CQ-5 missing/invalid bundle.

    Returns:
        (effective_archetype, reason, bundle_present, fallback_marker)
    """
    if not raw_archetype:
        reason = "absent" if raw_archetype is None else "empty"
    elif raw_archetype not in VALID_ARCHETYPES:
        reason = f"invalid-enum:{raw_archetype}"
    else:
        # Valid archetype — no fallback
        return raw_archetype, "", True, None

    # Emit structured warning (non-silent)
    warning = {
        "level": "warn",
        "event": "qe-evaluator.archetype-missing",
        "phase": phase,
        "gate": gate,
        "project": project,
        "source": "bundle",
        "reason": reason,
        "fallback_applied": "code-repo",
    }
    print(json.dumps(warning), file=sys.stderr)

    return "code-repo", reason, False, "bundle-missing"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    ctx: Dict[str, Any],
    plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate evidence for a gate invocation and return a QeEvaluatorVerdict.

    Args:
        ctx:  QeEvaluatorContext dict — gate_name, phase, archetype (optional), etc.
        plan: Parsed process-plan.json dict (used for multi-repo safety check).
              Pass None when not available; multi-repo safety fires on absence.

    Returns:
        QeEvaluatorVerdict dict.

    This function NEVER raises. All exceptions are caught and returned as
    CONDITIONAL-0.60 with a structured reason.
    """
    try:
        return _evaluate_inner(ctx, plan)
    except Exception as exc:  # R4 — no swallowed errors
        return _verdict(
            "CONDITIONAL", 0.60,
            f"qe-evaluator: internal error — {exc}",
            [_condition("QE-EVAL-internal-error", "major",
                        f"qe-evaluator: internal error — {exc}",
                        ctx.get("phase", "unknown"))],
            ctx.get("archetype", "unknown"),
        )


def _evaluate_inner(
    ctx: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    gate = str(ctx.get("gate_name") or "")
    phase = str(ctx.get("phase") or "unknown")
    project = str(ctx.get("project") or "unknown")
    raw_archetype = ctx.get("archetype")

    # Step 0 — Non-target gate refusal (AC-15b)
    if gate not in VALID_TARGET_GATES:
        return _verdict(
            "CONDITIONAL", 0.60,
            f"qe-evaluator: invoked at non-target gate '{gate}' — refusing",
            [_condition("QE-EVAL-non-target-gate", "major",
                        f"qe-evaluator: invoked at non-target gate '{gate}' — refusing",
                        phase)],
            str(raw_archetype or "unknown"),
        )

    # Step 1 — CQ-5 fallback (non-silent)
    effective_archetype, fallback_reason, bundle_present, fallback_marker = _apply_cq5_fallback(
        raw_archetype, gate, phase, project
    )

    cq5_conditions: List[Dict[str, Any]] = []
    if fallback_marker == "bundle-missing":
        cq5_conditions.append(_condition(
            "QE-EVAL-bundle-missing", "major",
            f"qe-evaluator: archetype missing from bundle (reason: {fallback_reason}); "
            "code-repo fallback applied",
            phase,
        ))

    # Step 2 — Multi-repo safety pre-check (AC-14a, AC-14b)
    if effective_archetype == "multi-repo":
        safety = _check_multi_repo_safety(plan, phase)
        if safety is not None:
            return safety
        # Populated affected_repos → fall through to deferred-archetype handling below

    # Evidence fields from ctx (test-layer convention: pass evidence in ctx directly)
    evidence_present: List[str] = list(ctx.get("evidence_present") or [])
    evidence_sizes: Dict[str, int] = dict(ctx.get("evidence_sizes") or {})
    test_types: List[str] = list(ctx.get("test_types") or [])
    is_api_modifying: bool = bool(ctx.get("is_api_modifying", False))
    behavior_change: bool = bool(ctx.get("behavior_change", False))

    # Step 3 — Archetype score-band tables
    if effective_archetype == "code-repo":
        result = _eval_code_repo(gate, evidence_present, evidence_sizes, is_api_modifying, phase)
    elif effective_archetype == "docs-only":
        result = _eval_docs_only(gate, evidence_present, evidence_sizes, phase)
    elif effective_archetype == "skill-agent-authoring":
        result = _eval_skill_agent_authoring(
            gate, evidence_present, evidence_sizes, test_types, behavior_change, phase
        )
    elif effective_archetype == "config-infra":
        result = _eval_config_infra(gate, evidence_present, evidence_sizes, phase)
    elif effective_archetype in DEFERRED_ARCHETYPES:
        # Deferred: apply code-repo table + add CONDITIONAL finding
        result = _eval_code_repo(gate, evidence_present, evidence_sizes, is_api_modifying, phase)
        deferred_condition = _condition(
            f"QE-EVAL-deferred-{effective_archetype}", "major",
            f"{effective_archetype}: full evidence contract deferred to PR 2; "
            "code-repo fallback applied",
            phase,
        )
        result = dict(result)
        result["conditions"] = list(result.get("conditions") or []) + [deferred_condition]
        if result["verdict"] == "APPROVE" and result["score"] >= MIN_SCORE:
            # Downgrade to CONDITIONAL-0.70 to surface the deferral finding
            result["verdict"] = "CONDITIONAL"
            result["score"] = 0.70
            result["reason"] = (
                f"{effective_archetype}: full evidence contract deferred to PR 2; "
                "code-repo fallback applied"
            )
    elif effective_archetype == "multi-repo":
        # multi-repo with populated affected_repos → deferred treatment same as above
        result = _eval_code_repo(gate, evidence_present, evidence_sizes, is_api_modifying, phase)
        deferred_condition = _condition(
            "QE-EVAL-deferred-multi-repo", "major",
            "multi-repo: full evidence contract deferred to PR 2; code-repo fallback applied",
            phase,
        )
        result = dict(result)
        result["conditions"] = list(result.get("conditions") or []) + [deferred_condition]
        if result["verdict"] == "APPROVE" and result["score"] >= MIN_SCORE:
            result["verdict"] = "CONDITIONAL"
            result["score"] = 0.70
            result["reason"] = "multi-repo: full evidence contract deferred to PR 2; code-repo fallback applied"
    else:
        # Should never reach here — ARCHETYPE_ENUM is exhaustive
        result = _eval_code_repo(gate, evidence_present, evidence_sizes, is_api_modifying, phase)

    # Merge CQ-5 conditions (if any) into result
    if cq5_conditions:
        result = dict(result)
        result["conditions"] = cq5_conditions + list(result.get("conditions") or [])
        result["archetype"] = effective_archetype
        # Mark addendum fields on result for test assertions
        result["_bundle_present"] = bundle_present
        result["_fallback_marker"] = fallback_marker
        result["_source"] = "fallback" if fallback_marker else "bundle"

    return result
