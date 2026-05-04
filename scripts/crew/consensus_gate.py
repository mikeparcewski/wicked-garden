#!/usr/bin/env python3
"""
consensus_gate.py — Bridge between jam consensus protocol and crew gate decisions.

Enables multi-perspective consensus evaluation for gate decisions on
high-complexity crew projects (complexity >= consensus_threshold).

Stdlib-only. Cross-platform.

Usage (Python):
    from consensus_gate import should_use_consensus, evaluate_consensus_gate
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import siblings from scripts/ root
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jam.consensus import (  # noqa: E402
    ConsensusResult,
    Proposal,
    store_council_result,
    synthesize,
)

logger = logging.getLogger("wicked-crew.consensus-gate")


# ---------------------------------------------------------------------------
# Specialist perspective framing
# ---------------------------------------------------------------------------
# Maps specialist roles to the lens they apply when reviewing gate results.
# Used to frame proposals from each proposer's perspective.

_PERSPECTIVE_FRAMES: Dict[str, str] = {
    "engineering": (
        "As a senior engineer, evaluate the technical soundness, code quality, "
        "architecture alignment, and maintainability of this gate result."
    ),
    "devsecops": (
        "As a security and platform engineer, evaluate the security posture, "
        "operational readiness, deployment safety, and infrastructure concerns."
    ),
    "product": (
        "As a product strategist, evaluate the user impact, business value, "
        "requirement coverage, and alignment with product goals."
    ),
    "quality-engineering": (
        "As a quality engineer, evaluate the test coverage, verification rigor, "
        "edge case handling, and evidence completeness."
    ),
    "data-engineering": (
        "As a data engineer, evaluate data integrity, pipeline reliability, "
        "schema safety, and data governance compliance."
    ),
    "project-management": (
        "As a project manager, evaluate delivery risk, timeline feasibility, "
        "dependency management, and stakeholder alignment."
    ),
    "brainstorming": (
        "As a creative facilitator, evaluate solution creativity, alternative "
        "approaches considered, and innovation potential."
    ),
    "agentic-architecture": (
        "As an agentic systems architect, evaluate agent safety, tool boundaries, "
        "autonomy guardrails, and system composability."
    ),
}

_DEFAULT_FRAME = (
    "As a specialist reviewer, evaluate the quality, completeness, "
    "and readiness of this gate result."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_use_consensus(project_state: Dict[str, Any], phase_config: Dict[str, Any]) -> bool:
    """Determine whether consensus evaluation should be used for this gate.

    Returns True when:
    - Gate enforcement is not in legacy mode
    - The phase has a consensus_threshold configured
    - The project's complexity_score >= consensus_threshold
    - The phase has consensus_proposers configured

    Args:
        project_state: Dict with at least 'complexity_score' key.
        phase_config: Phase config dict from phases.json.

    Returns:
        True if consensus evaluation should run.
    """
    threshold = phase_config.get("consensus_threshold")
    if threshold is None:
        return False

    proposers = phase_config.get("consensus_proposers")
    if not proposers:
        return False

    complexity = project_state.get("complexity_score", 0) or 0
    try:
        complexity = int(complexity)
        threshold = int(threshold)
    except (TypeError, ValueError):
        return False

    return complexity >= threshold


def build_gate_proposals(
    gate_result: Dict[str, Any],
    phase: str,
    project_state: Dict[str, Any],
    proposers: List[str],
) -> List[Proposal]:
    """Build Proposal objects for each proposer specialist from gate result data.

    Each proposer evaluates the gate result through their specialist lens,
    producing an independent proposal for the gate decision.

    Args:
        gate_result: Parsed gate-result.json dict.
        phase: Phase name being evaluated.
        project_state: Project state dict (complexity, signals, etc.).
        proposers: List of specialist role names to build proposals for.

    Returns:
        List of Proposal objects, one per proposer.
    """
    gate_decision = gate_result.get("result", "UNKNOWN")
    gate_score = gate_result.get("score", 0.0)
    gate_findings = gate_result.get("findings", [])
    gate_summary = gate_result.get("summary", "")
    reviewer = gate_result.get("reviewer", "unknown")

    # Build context string from gate data
    findings_text = ""
    if gate_findings:
        findings_lines = []
        for i, finding in enumerate(gate_findings, 1):
            if isinstance(finding, dict):
                findings_lines.append(
                    f"  {i}. [{finding.get('severity', 'info')}] "
                    f"{finding.get('description', finding.get('finding', str(finding)))}"
                )
            else:
                findings_lines.append(f"  {i}. {finding}")
        findings_text = "\n".join(findings_lines)

    context = (
        f"Phase: {phase}\n"
        f"Gate Decision: {gate_decision}\n"
        f"Gate Score: {gate_score}\n"
        f"Reviewer: {reviewer}\n"
        f"Complexity: {project_state.get('complexity_score', 'unknown')}\n"
        f"Signals: {', '.join(project_state.get('signals_detected', []))}\n"
    )
    if gate_summary:
        context += f"Summary: {gate_summary}\n"
    if findings_text:
        context += f"Findings:\n{findings_text}\n"

    proposals: List[Proposal] = []
    for role in proposers:
        frame = _PERSPECTIVE_FRAMES.get(role, _DEFAULT_FRAME)

        # Build a perspective-specific proposal
        proposal_text = (
            f"{frame}\n\n"
            f"Gate context:\n{context}\n"
            f"Based on this evaluation, the gate should "
            f"{'proceed' if gate_decision == 'APPROVE' else 'be reviewed carefully'}."
        )

        # Derive confidence from gate score adjusted by perspective
        try:
            base_confidence = float(gate_score) if gate_score else 0.5
        except (TypeError, ValueError):
            base_confidence = 0.5

        # Security/QE perspectives are more cautious on borderline scores
        if role in ("devsecops", "quality-engineering") and base_confidence < 0.8:
            adjusted_confidence = max(0.1, base_confidence - 0.1)
        else:
            adjusted_confidence = base_confidence

        # Build concerns from findings relevant to this specialist's domain
        concerns: List[str] = []
        for finding in gate_findings:
            if isinstance(finding, dict):
                severity = finding.get("severity", "info")
                desc = finding.get("description", finding.get("finding", ""))
                if severity in ("high", "critical"):
                    concerns.append(desc)
                elif severity == "medium" and role in ("devsecops", "quality-engineering"):
                    concerns.append(desc)
            elif isinstance(finding, str) and len(finding) > 20:
                concerns.append(finding)

        proposals.append(Proposal(
            persona=role,
            proposal=proposal_text,
            rationale=f"Evaluation from {role} perspective on {phase} gate (score: {gate_score})",
            confidence=round(min(1.0, max(0.0, adjusted_confidence)), 3),
            concerns=concerns,
        ))

    return proposals


def evaluate_consensus_gate(
    project_dir: str,
    phase: str,
    project_state: Dict[str, Any],
    phases_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run consensus evaluation on a gate decision for a high-complexity project.

    Loads gate-result.json, builds proposals from each configured proposer
    specialist, runs the consensus protocol, and maps results to gate outcomes.

    Args:
        project_dir: Path to the project directory.
        phase: Phase name being evaluated.
        project_state: Project state dict.
        phases_config: Full phases config dict from phases.json.

    Returns:
        Enriched gate result dict with consensus data, or None if consensus
        cannot be evaluated (missing gate result, etc.).

        Result dict keys:
        - result: "APPROVE", "REJECT", or "CONDITIONAL"
        - reason: Human-readable reason string
        - consensus_confidence: Float confidence score
        - consensus_points: List of consensus point dicts
        - dissenting_views: List of dissent dicts
        - open_questions: List of unresolved questions
        - participants: Number of proposer specialists
    """
    phase_config = phases_config.get(phase, {})
    proposers = phase_config.get("consensus_proposers", [])
    strong_dissent_blocks = phase_config.get("strong_dissent_blocks", True)
    confidence_threshold = phase_config.get("confidence_threshold", 0.7)

    # Load gate result through phase_manager._load_gate_result so the
    # same schema + sanitizer + orphan-detection defenses apply in the
    # consensus path (design-addendum-1 § D-4). A malformed file that
    # approve_phase would reject must NOT silently flow into consensus.
    project_path = Path(project_dir)
    try:
        from phase_manager import _load_gate_result  # local import avoids cycles
        from gate_result_schema import GateResultSchemaError
    except ImportError as exc:  # pragma: no cover — defensive, should never happen
        logger.warning(
            "[consensus-gate] gate-result-schema module unavailable "
            "(phase='%s'): %s — falling back to best-effort raw parse",
            phase, exc,
        )
        _load_gate_result = None
        GateResultSchemaError = Exception  # type: ignore[assignment,misc]

    if _load_gate_result is not None:
        try:
            gate_result = _load_gate_result(project_path, phase)
        except GateResultSchemaError as exc:
            logger.warning(
                "[consensus-gate] gate-result.json for phase '%s' failed "
                "validation: %s — skipping consensus evaluation",
                phase, exc,
            )
            return None
        if gate_result is None:
            logger.warning(
                "[consensus-gate] No gate-result.json found for phase '%s' — "
                "skipping consensus evaluation",
                phase,
            )
            return None
    else:
        # Defensive fallback — only reachable if the import above failed.
        gate_file = project_path / "phases" / phase / "gate-result.json"
        if not gate_file.exists():
            logger.warning(
                "[consensus-gate] No gate-result.json found for phase '%s' — "
                "skipping consensus evaluation",
                phase,
            )
            return None
        try:
            gate_result = json.loads(gate_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "[consensus-gate] Failed to load gate-result.json "
                "for phase '%s': %s", phase, exc,
            )
            return None

    # Build proposals from each specialist perspective
    proposals = build_gate_proposals(gate_result, phase, project_state, proposers)
    if not proposals:
        logger.warning(
            "[consensus-gate] No proposals built for phase '%s' — "
            "skipping consensus evaluation",
            phase,
        )
        return None

    # Run consensus synthesis
    question = (
        f"Should the {phase} phase gate decision of "
        f"'{gate_result.get('result', 'UNKNOWN')}' "
        f"(score: {gate_result.get('score', 'N/A')}) be accepted?"
    )
    consensus_result = synthesize(proposals, cross_reviews=None, question=question)

    # Derive agreement_ratio from the consensus_points already computed by synthesize()
    total_points = len(consensus_result.consensus_points)
    agreement_ratio = consensus_result.confidence if total_points else 0.0

    # Store consensus result for audit trail
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    try:
        store_council_result(consensus_result, session_id)
    except Exception as exc:
        logger.warning("[consensus-gate] Failed to store council result: %s", exc)

    # Mint a per-evaluation discriminator and thread it through both writes.
    #
    # Site 2 of the bus-cutover (#746) — Council Condition C9 (latent dedup
    # bug fix).  Pre-#746 both emits used ``chain_id=f"{project_id}.{phase}"``,
    # so a second consensus eval on the same phase would collide on the bus
    # dedupe ledger (see ``_bus.py`` ``is_processed`` keyed on
    # ``(event_type, chain_id)``).  ``eval_id`` is unique per call to
    # ``evaluate_consensus_gate`` and is woven into BOTH the report and
    # evidence chain_ids:
    #   * report   chain_id = f"{project_id}.{phase}.consensus.{eval_id}"
    #   * evidence chain_id = f"{project_id}.{phase}.consensus.{eval_id}.evidence"
    #
    # The ``.evidence`` discriminator on the second chain_id keeps the report
    # and evidence emits distinct even within the same eval (otherwise both
    # would dedupe against each other).  See brain memory
    # ``bus-chain-id-must-include-uniqueness-segment-gotcha``.
    eval_id = uuid.uuid4().hex[:16]

    # Write consensus report to project dir
    scores = {"agreement_ratio": agreement_ratio, "divergent_points": []}
    _write_consensus_report(project_path, phase, consensus_result, scores, eval_id=eval_id)

    # Build base result dict (shared across all outcomes).  ``eval_id`` is
    # carried in the dict so callers (notably phase_manager.py) thread it
    # into ``_write_consensus_evidence`` for the matching chain_id.
    base = {
        "consensus_confidence": consensus_result.confidence,
        "consensus_points": consensus_result.consensus_points,
        "dissenting_views": [asdict(d) for d in consensus_result.dissenting_views],
        "open_questions": consensus_result.open_questions,
        "participants": consensus_result.participants,
        "agreement_ratio": agreement_ratio,
        "eval_id": eval_id,
    }

    # Map consensus result to gate outcome
    strong_dissents = [
        d for d in consensus_result.dissenting_views
        if d.strength == "strong"
    ]

    # Rule 1: Strong dissent blocks if configured
    if strong_dissents and strong_dissent_blocks:
        dissent_summary = "; ".join(
            f"{d.persona}: {d.view}" for d in strong_dissents[:3]
        )
        return {**base, "result": "REJECT",
                "reason": f"Strong dissent from consensus council: {dissent_summary}"}

    # Rule 2: Low agreement ratio triggers CONDITIONAL
    try:
        conf_threshold = float(confidence_threshold)
    except (TypeError, ValueError):
        conf_threshold = 0.7

    if agreement_ratio < conf_threshold:
        conditions = []
        for dv in consensus_result.dissenting_views:
            conditions.append({
                "description": f"[{dv.strength}] {dv.persona}: {dv.view}",
                "source": "consensus-council",
                "severity": dv.strength,
            })
        for q in consensus_result.open_questions[:5]:
            conditions.append({
                "description": f"Unresolved question: {q}",
                "source": "consensus-council",
                "severity": "moderate",
            })
        return {**base, "result": "CONDITIONAL", "conditions": conditions,
                "reason": (f"Consensus agreement ratio ({agreement_ratio:.2f}) "
                           f"below threshold ({conf_threshold:.2f})")}

    # Rule 3: Sufficient agreement -> APPROVE
    return {**base, "result": "APPROVE",
            "reason": (f"Consensus council approved with {agreement_ratio:.2f} "
                       f"agreement ratio ({consensus_result.participants} participants)")}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_consensus_report(
    project_dir: Path,
    phase: str,
    result: ConsensusResult,
    scores: Dict[str, Any],
    eval_id: Optional[str] = None,
) -> None:
    """Emit wicked.consensus.report_created — projector materialises the file.

    Site 2 of the bus-cutover (#746).  Bus is the source of truth: this
    function builds the canonical report dict, emits the bus event, and
    returns.  The legacy ``report_path.write_text()`` call was deleted in
    PR #798 — the projector handler ``_consensus_report_created`` now
    materialises ``consensus-report.json`` on disk via
    ``_consensus_disk_write()`` (atomic temp+rename, content-hash
    idempotency).  That handler is gated on
    ``WG_BUS_AS_TRUTH_CONSENSUS_REPORT`` (default-on per
    ``_BUS_AS_TRUTH_DEFAULT_ON``).

    ``eval_id`` was added per Council Condition C9 — the chain_id MUST
    include a per-evaluation discriminator so a second consensus eval on
    the same phase does not collide on the bus dedupe ledger.  When the
    caller does not supply one (legacy callers in tests), we mint one
    locally so the chain_id stays unique.
    """
    if eval_id is None:
        # Defensive: legacy callers pre-#746 did not pass eval_id.  Mint
        # one inline so the chain_id contract still holds.
        eval_id = uuid.uuid4().hex[:16]

    report = {
        "phase": phase,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": result.decision,
        "confidence": result.confidence,
        "participants": result.participants,
        "rounds": result.rounds,
        "consensus_points": result.consensus_points,
        "dissenting_views": [asdict(d) for d in result.dissenting_views],
        "open_questions": result.open_questions,
        "agreement_ratio": scores.get("agreement_ratio", 0.0),
        "divergent_points": scores.get("divergent_points", []),
    }

    # Bus emit — projector handler materialises the file on disk.
    # Fail-open per Decision #8: bus failure must NOT block the caller.
    try:
        from _bus import emit_event  # type: ignore[import]
        project_id = project_dir.name
        # ``indent=2`` + ``default=str`` produces the canonical on-disk
        # bytes per Council Condition C10.  Worst-case pre-flight C8 sized
        # this at ~3-8 KB (5 participants, 3 dissents, 5 open questions).
        raw_payload = json.dumps(report, default=str, indent=2)
        emit_event(
            "wicked.consensus.report_created",
            {
                "project_id": project_id,
                "phase": phase,
                "decision": result.decision,
                "confidence": result.confidence,
                "agreement_ratio": scores.get("agreement_ratio", 0.0),
                "participants": result.participants,
                "rounds": result.rounds,
                "eval_id": eval_id,
                "raw_payload": raw_payload,
            },
            chain_id=f"{project_id}.{phase}.consensus.{eval_id}",
        )
        logger.info(
            "[consensus-gate] Emitted consensus report event "
            "(project=%s phase=%s eval_id=%s)",
            project_id, phase, eval_id,
        )
    except Exception as exc:  # pragma: no cover — defensive fail-open
        logger.warning(
            "[consensus-gate] bus emit failed (fail-open): %s", exc,
        )


def _write_consensus_evidence(
    project_dir: Path,
    phase: str,
    consensus_result: Dict[str, Any],
) -> None:
    """Emit wicked.consensus.evidence_recorded — projector materialises the file.

    Stored alongside gate-result.json in the phase directory.

    Site 2 of bus-cutover (#746).  Bus is the source of truth: this
    function builds the canonical evidence dict, emits the bus event, and
    returns.  The legacy ``evidence_path.write_text()`` call was deleted in
    PR #798 — the projector handler ``_consensus_evidence_recorded`` now
    materialises ``consensus-evidence.json`` on disk via
    ``_consensus_disk_write()`` (atomic temp+rename, content-hash
    idempotency).  Gated on ``WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE``
    (default-on per ``_BUS_AS_TRUTH_DEFAULT_ON``).

    ``eval_id`` is read from ``consensus_result["eval_id"]`` so the
    chain_id matches the report emit's eval_id (Council Condition C9).
    Falls back to a fresh uuid when absent so legacy callers do not crash.
    The ``.evidence`` discriminator on the chain_id keeps the report and
    evidence emits distinct within the same eval.
    """
    eval_id = consensus_result.get("eval_id")
    if not isinstance(eval_id, str) or not eval_id:
        eval_id = uuid.uuid4().hex[:16]

    evidence = {
        "type": "consensus-rejection",
        "phase": phase,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": consensus_result.get("result"),
        "reason": consensus_result.get("reason"),
        "consensus_confidence": consensus_result.get("consensus_confidence"),
        "agreement_ratio": consensus_result.get("agreement_ratio"),
        "dissenting_views": consensus_result.get("dissenting_views", []),
        "participants": consensus_result.get("participants"),
    }

    # Bus emit — projector handler materialises the file on disk.
    # Fail-open per Decision #8: bus failure must NOT block the caller.
    try:
        from _bus import emit_event  # type: ignore[import]
        project_id = project_dir.name
        raw_payload = json.dumps(evidence, default=str, indent=2)
        emit_event(
            "wicked.consensus.evidence_recorded",
            {
                "project_id": project_id,
                "phase": phase,
                "result": consensus_result.get("result"),
                "reason": consensus_result.get("reason"),
                "consensus_confidence": consensus_result.get("consensus_confidence"),
                "agreement_ratio": consensus_result.get("agreement_ratio"),
                "participants": consensus_result.get("participants"),
                "eval_id": eval_id,
                "raw_payload": raw_payload,
            },
            # ``.evidence`` discriminator on the second chain_id keeps
            # the report and evidence emits distinct within the same
            # eval (otherwise both would dedupe against each other).
            chain_id=f"{project_id}.{phase}.consensus.{eval_id}.evidence",
        )
    except Exception as exc:  # pragma: no cover — defensive fail-open
        logger.warning(
            "[consensus-gate] bus emit failed (fail-open): %s", exc,
        )
