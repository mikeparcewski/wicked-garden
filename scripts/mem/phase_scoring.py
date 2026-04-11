#!/usr/bin/env python3
"""Lifecycle-aware scoring functions for search and memory recall.

Composable scorers that boost/penalize results based on crew phase,
artifact freshness, traceability links, and gate status.

Usage:
    lifecycle_scoring.py score --phase build --scorers phase_weighted,recency_decay < items.json
    lifecycle_scoring.py score --phase test --project P < items.json
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Allow sibling-package imports (e.g. crew.traceability)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass
class ScoredItem:
    id: str
    score: float
    data: dict
    score_breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Phase-weighted scoring
# ---------------------------------------------------------------------------

PHASE_AFFINITY: Dict[str, Dict[str, float]] = {
    "clarify": {"requirement": 1.4, "acceptance_criteria": 1.3, "brainstorm": 1.2},
    "design": {"requirement": 1.3, "design": 1.5, "architecture": 1.4, "acceptance_criteria": 1.2},
    "build": {"design": 1.5, "requirement": 1.3, "test_strategy": 1.1, "task": 1.2},
    "test": {"test_strategy": 1.5, "requirement": 1.3, "acceptance_criteria": 1.5, "test_scenario": 1.4},
    "review": {"evidence": 1.5, "test_result": 1.4, "requirement": 1.2, "design": 1.1},
}


def phase_weighted(items: List[ScoredItem], context: dict) -> List[ScoredItem]:
    """Boost items matching the active crew phase."""
    phase = context.get("phase")
    if not phase or phase not in PHASE_AFFINITY:
        return items
    affinity = PHASE_AFFINITY[phase]
    for item in items:
        art_type = item.data.get("type") or item.data.get("artifact_type") or ""
        multiplier = affinity.get(art_type, 1.0)
        item.score *= multiplier
        item.score_breakdown["phase_weighted"] = multiplier
    return items


# ---------------------------------------------------------------------------
# 2. Recency decay
# ---------------------------------------------------------------------------

def _parse_datetime(s: str) -> Optional[datetime]:
    """Parse ISO datetime string, tolerant of common variations."""
    if not s:
        return None
    try:
        # Python 3.7+ fromisoformat handles most ISO strings
        # but not trailing Z — replace it
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def recency_decay(items: List[ScoredItem], context: dict) -> List[ScoredItem]:
    """Exponential decay based on item age in days."""
    decay_rate = context.get("decay_rate", 0.01)
    now = datetime.now(timezone.utc)
    for item in items:
        ts_str = item.data.get("created_at") or item.data.get("updated_at")
        dt = _parse_datetime(ts_str) if ts_str else None
        if dt is None:
            item.score_breakdown["recency_decay"] = 1.0
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days_old = max((now - dt).total_seconds() / 86400, 0)
        multiplier = math.exp(-decay_rate * days_old)
        item.score *= multiplier
        item.score_breakdown["recency_decay"] = round(multiplier, 4)
    return items


# ---------------------------------------------------------------------------
# 3. Traceability boost
# ---------------------------------------------------------------------------

def traceability_boost(items: List[ScoredItem], context: dict) -> List[ScoredItem]:
    """Boost items that have traceability links."""
    try:
        from crew.traceability import get_links  # type: ignore[import-not-found]
    except ImportError:
        # Graceful degradation — no-op if traceability module not available
        for item in items:
            item.score_breakdown["traceability_boost"] = 1.0
        return items

    for item in items:
        try:
            links = get_links(item.id)
            count = len(links) if links else 0
        except Exception:
            count = 0
        if count >= 3:
            multiplier = 1.5
        elif count >= 1:
            multiplier = 1.3
        else:
            multiplier = 1.0
        item.score *= multiplier
        item.score_breakdown["traceability_boost"] = multiplier
    return items


# ---------------------------------------------------------------------------
# 4. Gate status multiplier
# ---------------------------------------------------------------------------

STATE_MULTIPLIERS: Dict[str, float] = {
    "APPROVED": 1.3,
    "VERIFIED": 1.4,
    "CLOSED": 1.2,
    "IN_REVIEW": 1.0,
    "IMPLEMENTED": 1.1,
    "DRAFT": 0.7,
}


def gate_status_multiplier(items: List[ScoredItem], context: dict) -> List[ScoredItem]:
    """Boost or penalize items based on their gate/artifact state."""
    for item in items:
        state = item.data.get("state")
        if not state:
            item.score_breakdown["gate_status"] = 1.0
            continue
        multiplier = STATE_MULTIPLIERS.get(state.upper(), 1.0)
        item.score *= multiplier
        item.score_breakdown["gate_status"] = multiplier
    return items


# ---------------------------------------------------------------------------
# 5. Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(items: List[ScoredItem], context: dict) -> List[ScoredItem]:
    """Fuse multiple independent rankings via RRF.

    Expects context["rankings"] as a dict of {ranker_name: [item_id, ...]}.
    Falls back to using score_breakdown keys as implicit single rankings.
    """
    k = context.get("rrf_k", 60)
    rankings: Optional[dict] = context.get("rankings")

    if rankings:
        # External rankings provided
        rrf_scores: Dict[str, float] = {}
        for _ranker_name, ranked_ids in rankings.items():
            for rank, item_id in enumerate(ranked_ids, start=1):
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + 1.0 / (k + rank)
        for item in items:
            fused = rrf_scores.get(item.id, 0.0)
            item.score = fused
            item.score_breakdown["rrf"] = round(fused, 6)
    else:
        # Derive rankings from score_breakdown keys
        scorer_names = set()
        for item in items:
            scorer_names.update(item.score_breakdown.keys())
        if not scorer_names:
            return items
        rrf_scores = {}
        for scorer_name in scorer_names:
            ranked = sorted(items, key=lambda it: it.score_breakdown.get(scorer_name, 0), reverse=True)
            for rank, item in enumerate(ranked, start=1):
                rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + 1.0 / (k + rank)
        for item in items:
            fused = rrf_scores.get(item.id, 0.0)
            item.score = fused
            item.score_breakdown["rrf"] = round(fused, 6)
    return items


# ---------------------------------------------------------------------------
# Scorer registry and pipeline
# ---------------------------------------------------------------------------

SCORERS: Dict[str, Callable] = {
    "phase_weighted": phase_weighted,
    "recency_decay": recency_decay,
    "traceability_boost": traceability_boost,
    "gate_status": gate_status_multiplier,
    "rrf": reciprocal_rank_fusion,
}

DEFAULT_SCORERS = ["phase_weighted", "recency_decay", "traceability_boost", "gate_status"]


def score_pipeline(
    items: List[dict],
    context: dict,
    scorers: Optional[List[str]] = None,
) -> List[dict]:
    """Run scoring pipeline over items.

    Args:
        items: list of dicts (search results or memory records).
        context: dict with keys like "phase", "project_id", "decay_rate".
        scorers: list of scorer names to apply. Default: all except rrf.

    Returns:
        Sorted list of dicts with added "_score" and "_score_breakdown" keys.
    """
    scorer_names = scorers if scorers is not None else DEFAULT_SCORERS

    scored = [
        ScoredItem(
            id=item.get("id", str(i)),
            score=item.get("_score", 1.0),
            data=item,
            score_breakdown={},
        )
        for i, item in enumerate(items)
    ]

    for name in scorer_names:
        fn = SCORERS.get(name)
        if fn:
            scored = fn(scored, context)

    scored.sort(key=lambda s: s.score, reverse=True)

    result = []
    for s in scored:
        out = dict(s.data)
        out["_score"] = round(s.score, 6)
        out["_score_breakdown"] = s.score_breakdown
        result.append(out)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lifecycle_scoring",
        description="Lifecycle-aware scoring for search and memory results.",
    )
    sub = parser.add_subparsers(dest="command")

    score_p = sub.add_parser("score", help="Score items from stdin JSON array")
    score_p.add_argument("--phase", help="Active crew phase (clarify/design/build/test/review)")
    score_p.add_argument("--project", help="Project ID for context")
    score_p.add_argument("--scorers", help="Comma-separated scorer names", default=None)
    score_p.add_argument("--decay-rate", type=float, default=0.01, help="Recency decay rate per day")
    score_p.add_argument("--rrf-k", type=int, default=60, help="RRF constant k")

    args = parser.parse_args()
    if args.command != "score":
        parser.print_help()
        sys.exit(1)

    raw = sys.stdin.read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write("Error: invalid JSON on stdin: %s\n" % exc)
        sys.exit(1)

    if not isinstance(items, list):
        sys.stderr.write("Error: stdin must be a JSON array\n")
        sys.exit(1)

    context: dict = {}
    if args.phase:
        context["phase"] = args.phase
    if args.project:
        context["project_id"] = args.project
    context["decay_rate"] = args.decay_rate
    context["rrf_k"] = args.rrf_k

    scorer_list = args.scorers.split(",") if args.scorers else None

    result = score_pipeline(items, context, scorer_list)
    sys.stdout.write(json.dumps(result, indent=2))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
