#!/usr/bin/env python3
"""
Spec Quality Rubric — scored evaluation of clarify-phase deliverables.

Produces a numeric score (0-20) across 10 dimensions (0-2 pts each) and maps
that score to a tier-aware verdict:

  minimal rigor  -> requires >= 12 (grade C)
  standard rigor -> requires >= 15 (grade B)
  full    rigor  -> requires >= 18 (grade A)

Enforcement applied by ``phase_manager._validate_spec_rubric``:

  * below threshold at minimal/standard -> downgrade gate verdict to at least
    CONDITIONAL (conditions = the failing dimensions).
  * below threshold at full rigor -> upgrade gate verdict to REJECT.

Stdlib-only (no external deps). Canonical rubric description lives in
``skills/propose-process/refs/spec-quality-rubric.md`` — this module is the
executable mirror.

Public API:
  - TIER_THRESHOLDS             -> {tier: min_score}
  - DIMENSION_DEFINITIONS       -> [{id, name, max, description, weight}]
  - MAX_SCORE                   -> 20
  - grade_for_score(score)      -> "A" | "B" | "C" | "D" | "F"
  - score_breakdown_to_grid(...)-> markdown grid for reviewer output
  - evaluate_verdict(score, rigor_tier, base_verdict) -> (verdict, reason, conditions)
  - validate_breakdown(breakdown) -> (ok, error_or_None)

This module MUST stay pure (no filesystem, no logging side-effects) so it is
trivially testable.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Dimension catalog — 10 dimensions, 0-2 points each, 20 total.
# ---------------------------------------------------------------------------

DIMENSION_DEFINITIONS: List[Dict[str, object]] = [
    {
        "id": "user_story",
        "name": "User story present",
        "max": 2,
        "description": (
            "A user-facing story in the 'As a <role>, I want <capability>, so "
            "that <outcome>' form (or equivalent) that names the actor and "
            "motivation."
        ),
    },
    {
        "id": "context_framed",
        "name": "Context framed",
        "max": 2,
        "description": (
            "Problem statement, current state, and scope boundaries stated "
            "explicitly. Non-goals listed when the scope is ambiguous."
        ),
    },
    {
        "id": "numbered_functional_requirements",
        "name": "Numbered functional requirements",
        "max": 2,
        "description": (
            "Functional requirements are enumerated with stable IDs "
            "(FR-N or REQ-{domain}-{n}) so tests and design can cite them. "
            "A single prose paragraph without IDs scores 0."
        ),
    },
    {
        "id": "measurable_nfrs",
        "name": "NFRs with measurable targets",
        "max": 2,
        "description": (
            "Non-functional requirements (performance, reliability, security, "
            "accessibility, compliance) carry quantitative targets or cite an "
            "explicit standard. 'Should be fast' scores 0."
        ),
    },
    {
        "id": "acceptance_criteria",
        "name": "Acceptance criteria",
        "max": 2,
        "description": (
            "Acceptance criteria are SMART (specific, measurable, achievable, "
            "relevant, testable) and cover both the happy path and at least "
            "one failure/edge case."
        ),
    },
    {
        "id": "gherkin_scenarios",
        "name": "Gherkin scenarios",
        "max": 2,
        "description": (
            "Given/When/Then scenarios exist for the key behaviors. "
            "Negative paths and error conditions are represented."
        ),
    },
    {
        "id": "test_plan_outline",
        "name": "Test plan outline",
        "max": 2,
        "description": (
            "Test strategy sketched — at minimum the test levels (unit, "
            "integration, acceptance) and the evidence types to be captured."
        ),
    },
    {
        "id": "api_contract",
        "name": "API contract (if applicable)",
        "max": 2,
        "description": (
            "For work that touches an API surface, request/response shape "
            "and error cases are pinned down. Non-API work scores full "
            "credit automatically (see `is_applicable`)."
        ),
    },
    {
        "id": "dependencies_identified",
        "name": "Dependencies identified",
        "max": 2,
        "description": (
            "External systems, libraries, data sources, and upstream tickets "
            "called out. Unknowns are listed as open questions rather than "
            "silently omitted."
        ),
    },
    {
        "id": "design_section",
        "name": "Design section",
        "max": 2,
        "description": (
            "A preliminary design sketch is present (components touched, data "
            "flow, or interface signatures) — enough that an engineer can "
            "start implementation without guessing."
        ),
    },
]

DIMENSION_IDS: List[str] = [d["id"] for d in DIMENSION_DEFINITIONS]  # type: ignore[misc]

MAX_SCORE: int = sum(int(d["max"]) for d in DIMENSION_DEFINITIONS)  # 20


# ---------------------------------------------------------------------------
# Tier thresholds
# ---------------------------------------------------------------------------

# Minimum rubric score by rigor tier. Scores at-or-above are acceptable.
TIER_THRESHOLDS: Dict[str, int] = {
    "minimal": 12,   # grade C — advisory-ish but still enforced as CONDITIONAL floor
    "standard": 15,  # grade B
    "full": 18,      # grade A
}

# Letter grades — inclusive lower bounds.
GRADE_BOUNDS: List[Tuple[int, str]] = [
    (18, "A"),
    (15, "B"),
    (12, "C"),
    (9, "D"),
    (0, "F"),
]


def grade_for_score(score: int) -> str:
    """Return the letter grade for a 0-20 rubric score."""
    for floor, letter in GRADE_BOUNDS:
        if score >= floor:
            return letter
    return "F"


# ---------------------------------------------------------------------------
# Breakdown validation + scoring
# ---------------------------------------------------------------------------


def validate_breakdown(breakdown: Dict[str, object]) -> Tuple[bool, Optional[str]]:
    """Validate a rubric breakdown dict.

    Breakdown shape::

        {
          "user_story": {"score": 2, "notes": "..."},
          "context_framed": {"score": 1, "notes": "..."},
          ...
        }

    Each entry must:
      - key be a known dimension id
      - value be a dict with an int ``score`` in ``[0, max]``

    Returns ``(True, None)`` on success or ``(False, reason)`` on failure.
    Missing dimensions are allowed (scored 0 implicitly) so partial grading
    is still usable.
    """
    if not isinstance(breakdown, dict):
        return False, "breakdown must be a dict"

    known = {d["id"]: int(d["max"]) for d in DIMENSION_DEFINITIONS}  # type: ignore[misc]
    for dim_id, entry in breakdown.items():
        if dim_id not in known:
            return False, f"unknown rubric dimension '{dim_id}'"
        if not isinstance(entry, dict):
            return False, f"dimension '{dim_id}' must be a dict"
        if "score" not in entry:
            return False, f"dimension '{dim_id}' missing 'score'"
        raw_score = entry["score"]
        if not isinstance(raw_score, int) or isinstance(raw_score, bool):
            return False, f"dimension '{dim_id}' score must be an int"
        if raw_score < 0 or raw_score > known[dim_id]:
            return (
                False,
                f"dimension '{dim_id}' score {raw_score} out of range "
                f"[0, {known[dim_id]}]",
            )

    return True, None


def total_score(breakdown: Dict[str, object]) -> int:
    """Sum all dimension scores in a breakdown, treating missing dims as 0."""
    total = 0
    for dim_id in DIMENSION_IDS:
        entry = breakdown.get(dim_id)
        if isinstance(entry, dict) and isinstance(entry.get("score"), int):
            total += entry["score"]
    return total


def failing_dimensions(breakdown: Dict[str, object], floor: int = 1) -> List[str]:
    """Return dimension ids whose score is below ``floor`` (default 1 — i.e. zero)."""
    out: List[str] = []
    for dim_id in DIMENSION_IDS:
        entry = breakdown.get(dim_id)
        score = entry.get("score", 0) if isinstance(entry, dict) else 0
        if not isinstance(score, int):
            score = 0
        if score < floor:
            out.append(dim_id)
    return out


# ---------------------------------------------------------------------------
# Verdict evaluation
# ---------------------------------------------------------------------------


def evaluate_verdict(
    score: int,
    rigor_tier: str,
    base_verdict: str = "APPROVE",
    breakdown: Optional[Dict[str, object]] = None,
) -> Tuple[str, Optional[str], List[str]]:
    """Decide the final verdict for a rubric-scored spec gate.

    Returns ``(verdict, reason, conditions)`` where:

      * ``verdict`` is one of ``APPROVE`` | ``CONDITIONAL`` | ``REJECT``.
      * ``reason`` is a human-readable explanation (None when the rubric
        does not modify the base verdict).
      * ``conditions`` is a list of condition strings derived from failing
        dimensions (empty on APPROVE/REJECT pass-through).

    Rules:
      - If the base_verdict is already REJECT, return as-is.
      - At full rigor, a score below the full threshold escalates to REJECT.
      - At minimal/standard rigor, a score below the tier threshold downgrades
        APPROVE to CONDITIONAL (CONDITIONAL stays CONDITIONAL).
      - If score >= threshold, the base verdict is preserved.
    """
    normalized_base = (base_verdict or "APPROVE").upper()
    if normalized_base == "REJECT":
        return "REJECT", None, []

    tier = (rigor_tier or "standard").lower()
    threshold = TIER_THRESHOLDS.get(tier)
    if threshold is None:
        # Unknown tier — be conservative: use standard.
        tier = "standard"
        threshold = TIER_THRESHOLDS["standard"]

    if score >= threshold:
        return normalized_base, None, []

    # Below threshold — compute conditions from missing / low dimensions.
    conditions: List[str] = []
    if breakdown is not None:
        for dim_id in failing_dimensions(breakdown, floor=1):
            label = _dimension_label(dim_id)
            conditions.append(f"Strengthen '{label}' (currently scored 0).")

    if tier == "full":
        reason = (
            f"Spec rubric score {score}/{MAX_SCORE} is below the full-rigor "
            f"minimum of {threshold}. Rejected — rework required."
        )
        return "REJECT", reason, conditions

    reason = (
        f"Spec rubric score {score}/{MAX_SCORE} is below the {tier} minimum "
        f"of {threshold}. Downgrading to CONDITIONAL — fix the listed "
        f"dimensions before the next phase advances."
    )
    return "CONDITIONAL", reason, conditions


def _dimension_label(dim_id: str) -> str:
    for d in DIMENSION_DEFINITIONS:
        if d["id"] == dim_id:
            return str(d["name"])
    return dim_id


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def score_breakdown_to_grid(
    breakdown: Dict[str, object],
    rigor_tier: str = "standard",
) -> str:
    """Render a markdown grid for the rubric breakdown.

    Intended for inclusion in ``gate-result.json`` ``summary`` or in
    reviewer task descriptions.
    """
    total = total_score(breakdown)
    grade = grade_for_score(total)
    tier = (rigor_tier or "standard").lower()
    threshold = TIER_THRESHOLDS.get(tier, TIER_THRESHOLDS["standard"])

    lines = [
        f"### Spec Quality Rubric — {total}/{MAX_SCORE} (grade {grade})",
        f"*Rigor tier: `{tier}` (minimum {threshold})*",
        "",
        "| # | Dimension | Score | Notes |",
        "|---|-----------|-------|-------|",
    ]

    for idx, dim in enumerate(DIMENSION_DEFINITIONS, start=1):
        dim_id = str(dim["id"])
        max_pts = int(dim["max"])
        entry = breakdown.get(dim_id)
        if isinstance(entry, dict):
            score = entry.get("score", 0)
            if not isinstance(score, int):
                score = 0
            notes = str(entry.get("notes", "")).replace("|", r"\|")
        else:
            score = 0
            notes = "_not evaluated_"
        lines.append(
            f"| {idx} | {dim['name']} | {score}/{max_pts} | {notes} |"
        )

    lines.append("")
    if total >= threshold:
        lines.append(f"**Meets `{tier}` threshold.**")
    elif tier == "full":
        lines.append(
            f"**Below `full` threshold — REJECT. Rework required before "
            f"clarify advances.**"
        )
    else:
        lines.append(
            f"**Below `{tier}` threshold — CONDITIONAL. Address low-scored "
            f"dimensions before the next phase advances.**"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI helper (for ad-hoc scoring from a JSON file)
# ---------------------------------------------------------------------------


def _cli(argv: List[str]) -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Score a spec quality rubric.")
    parser.add_argument(
        "breakdown_path",
        help="Path to a JSON file containing the rubric breakdown dict.",
    )
    parser.add_argument(
        "--rigor-tier",
        choices=list(TIER_THRESHOLDS.keys()),
        default="standard",
    )
    parser.add_argument(
        "--base-verdict",
        choices=["APPROVE", "CONDITIONAL", "REJECT"],
        default="APPROVE",
    )
    parser.add_argument("--output", choices=["json", "markdown"], default="json")
    args = parser.parse_args(argv)

    with open(args.breakdown_path, "r", encoding="utf-8") as fh:
        breakdown = json.load(fh)

    ok, err = validate_breakdown(breakdown)
    if not ok:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2

    score = total_score(breakdown)
    verdict, reason, conditions = evaluate_verdict(
        score, args.rigor_tier, args.base_verdict, breakdown
    )

    if args.output == "markdown":
        print(score_breakdown_to_grid(breakdown, args.rigor_tier))
        print()
        print(f"Verdict: **{verdict}**")
        if reason:
            print(f"Reason: {reason}")
        if conditions:
            print("Conditions:")
            for c in conditions:
                print(f"  - {c}")
    else:
        payload = {
            "score": score,
            "max_score": MAX_SCORE,
            "grade": grade_for_score(score),
            "rigor_tier": args.rigor_tier,
            "threshold": TIER_THRESHOLDS.get(args.rigor_tier),
            "verdict": verdict,
            "reason": reason,
            "conditions": conditions,
        }
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
