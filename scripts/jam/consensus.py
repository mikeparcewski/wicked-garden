#!/usr/bin/env python3
"""
consensus.py — Structured consensus scoring, dissent tracking, and synthesis
for jam council sessions.

Stdlib-only. Cross-platform.

CLI:
    consensus.py synthesize --proposals proposals.json [--reviews reviews.json] [--question "..."]
    consensus.py score --proposals proposals.json
    consensus.py format --result result.json [--show-dissent]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Council raw-vote surfacing (Issue #584)
#
# The council agent produces a synthesised verdict from per-model responses,
# but the individual per-model votes + one-line rationales are never surfaced
# to the caller. Even on a unanimous verdict, each model may flag a different
# concern the caller would want to see. ``build_council_output`` assembles an
# envelope carrying both layers, switched by ``WG_COUNCIL_OUTPUT``.
# ---------------------------------------------------------------------------

#: Maximum characters kept when deriving a per-model rationale from the
#: model's raw response. Named constant so the value cannot drift between
#: the extractor and the tests (R3 — no magic values).
_RATIONALE_MAX_CHARS: int = 240

#: Env var controlling which layers ``build_council_output`` emits. Values are
#: normalised lower-case; unknown values fall back to ``both`` so we never
#: starve the caller of data because of a typo (graceful degradation).
ENV_COUNCIL_OUTPUT: str = "WG_COUNCIL_OUTPUT"
COUNCIL_OUTPUT_BOTH: str = "both"
COUNCIL_OUTPUT_SYNTH: str = "synth"
COUNCIL_OUTPUT_RAW: str = "raw"
_VALID_COUNCIL_OUTPUTS: frozenset[str] = frozenset(
    {COUNCIL_OUTPUT_BOTH, COUNCIL_OUTPUT_SYNTH, COUNCIL_OUTPUT_RAW}
)

#: Label line prefixes a model may emit to mark its own terse summary. When
#: present, the text following the label wins over the raw-response prefix
#: so the caller sees the model's own one-liner rather than our slice.
_SUMMARY_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:summary|tl;dr|verdict|recommendation)\s*[:\-]\s*(.+)$", re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# Import siblings (scripts/ root)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _domain_store import DomainStore  # noqa: E402


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    persona: str
    proposal: str
    rationale: str
    confidence: float  # 0.0 to 1.0
    concerns: list[str] = field(default_factory=list)


@dataclass
class CrossReview:
    reviewer: str
    target_persona: str
    agreements: list[str] = field(default_factory=list)
    disagreements: list[dict] = field(default_factory=list)  # [{"point": ..., "counter": ...}]
    questions: list[str] = field(default_factory=list)


@dataclass
class DissentingView:
    persona: str
    view: str
    strength: str  # "strong", "moderate", "mild"
    acknowledged: bool = False


@dataclass
class ConsensusResult:
    decision: str
    confidence: float
    consensus_points: list[dict] = field(default_factory=list)  # [{"point": ..., "agreement": N, "of": M}]
    dissenting_views: list[DissentingView] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    rounds: int = 1
    participants: int = 0
    proposals: list[Proposal] = field(default_factory=list)
    cross_reviews: list[CrossReview] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_MIN_WORD_LEN = 4  # words shorter than this are treated as stop words


def _meaningful_words(text: str) -> set[str]:
    """Extract meaningful words (length >= 4) from text, lowercased."""
    return {
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) >= _MIN_WORD_LEN
    }


def _similarity(a: str, b: str) -> float:
    """Word-overlap similarity between two strings (Jaccard on meaningful words)."""
    wa = _meaningful_words(a)
    wb = _meaningful_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _extract_phrases(text: str) -> list[str]:
    """Split text into key phrases (sentences or bullet points)."""
    # Split on sentence-ending punctuation or newlines with bullets
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    # Clean and filter
    phrases = []
    for p in parts:
        cleaned = re.sub(r"^[\s\-*#>]+", "", p).strip()
        if len(cleaned) > 10:  # skip trivially short fragments
            phrases.append(cleaned)
    return phrases


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def _find_consensus_points(
    proposals: list[Proposal],
) -> tuple[list[dict], list[dict]]:
    """Find consensus and divergent points across proposals.

    Returns (consensus_points, divergent_points) where each entry is:
        {"point": str, "agreement": int, "of": int}
    """
    n = len(proposals)
    if n == 0:
        return [], []

    # Gather all phrases from all proposals
    all_phrases: list[tuple[str, int]] = []  # (phrase, proposal_index)
    for i, prop in enumerate(proposals):
        for phrase in _extract_phrases(prop.proposal):
            all_phrases.append((phrase, i))

    # Deduplicate similar phrases, keeping the longest representative
    clusters: list[dict] = []  # {"representative": str, "sources": set[int]}
    for phrase, idx in all_phrases:
        merged = False
        for cluster in clusters:
            if _similarity(phrase, cluster["representative"]) > 0.35:
                cluster["sources"].add(idx)
                # Keep longer phrase as representative
                if len(phrase) > len(cluster["representative"]):
                    cluster["representative"] = phrase
                merged = True
                break
        if not merged:
            clusters.append({"representative": phrase, "sources": {idx}})

    consensus = []
    divergent = []
    for cluster in clusters:
        count = len(cluster["sources"])
        entry = {
            "point": cluster["representative"],
            "agreement": count,
            "of": n,
        }
        ratio = count / n
        if ratio >= 0.6:
            consensus.append(entry)
        elif ratio < 0.4:
            divergent.append(entry)

    # Sort by agreement descending
    consensus.sort(key=lambda x: x["agreement"], reverse=True)
    divergent.sort(key=lambda x: x["agreement"])
    return consensus, divergent


def score_consensus(proposals: list[Proposal]) -> dict:
    """Calculate consensus metrics from independent proposals.

    Returns:
        {
            "consensus_points": [...],
            "confidence": float,
            "agreement_ratio": float,
            "divergent_points": [...],
        }
    """
    consensus_pts, divergent_pts = _find_consensus_points(proposals)

    # Average confidence across proposals
    avg_confidence = (
        sum(p.confidence for p in proposals) / len(proposals)
        if proposals else 0.0
    )

    # Agreement ratio: proportion of points that are consensus vs total
    total_pts = len(consensus_pts) + len(divergent_pts)
    agreement_ratio = (
        len(consensus_pts) / total_pts if total_pts > 0 else 0.0
    )

    return {
        "consensus_points": consensus_pts,
        "confidence": round(avg_confidence, 3),
        "agreement_ratio": round(agreement_ratio, 3),
        "divergent_points": divergent_pts,
    }


def extract_dissent(
    proposals: list[Proposal],
    cross_reviews: list[CrossReview] | None = None,
) -> list[DissentingView]:
    """Extract dissenting views from proposals and cross-reviews.

    Strength classification:
    - "strong": raised by 2+ personas or has detailed counter-rationale
    - "moderate": raised by 1 persona with rationale
    - "mild": noted as concern without strong objection
    """
    dissents: list[DissentingView] = []
    concern_tracker: dict[str, list[str]] = {}  # concern_text -> [personas]

    # Stage 1: Gather concerns from proposals
    for prop in proposals:
        for concern in prop.concerns:
            key = concern.strip().lower()
            if key not in concern_tracker:
                concern_tracker[key] = []
            concern_tracker[key].append(prop.persona)

    for concern_text, personas in concern_tracker.items():
        # Find the original-case version
        original = concern_text
        for prop in proposals:
            for c in prop.concerns:
                if c.strip().lower() == concern_text:
                    original = c.strip()
                    break

        if len(personas) >= 2:
            strength = "strong"
        else:
            strength = "moderate"

        dissents.append(DissentingView(
            persona=", ".join(sorted(set(personas))),
            view=original,
            strength=strength,
            acknowledged=False,
        ))

    # Stage 2: Extract from cross-reviews
    if cross_reviews:
        for review in cross_reviews:
            for disagreement in review.disagreements:
                point = disagreement.get("point", "")
                counter = disagreement.get("counter", "")
                if not point:
                    continue

                # Check if already captured as a concern
                already_captured = any(
                    _similarity(point, d.view) > 0.5 for d in dissents
                )
                if already_captured:
                    # Upgrade to strong if it appears in cross-review too
                    for d in dissents:
                        if _similarity(point, d.view) > 0.5:
                            d.strength = "strong"
                            break
                    continue

                # Detailed counter-rationale makes it strong
                strength = "strong" if len(counter) > 50 else "moderate"
                dissents.append(DissentingView(
                    persona=review.reviewer,
                    view=point,
                    strength=strength,
                    acknowledged=False,
                ))

            # Unresolved questions are mild dissent
            for question in review.questions:
                if len(question.strip()) > 10:
                    dissents.append(DissentingView(
                        persona=review.reviewer,
                        view=question.strip(),
                        strength="mild",
                        acknowledged=False,
                    ))

    return dissents


def synthesize(
    proposals: list[Proposal],
    cross_reviews: list[CrossReview] | None = None,
    question: str = "",
) -> ConsensusResult:
    """Run the full 3-stage consensus protocol.

    Stage 1: Analyze independent proposals
    Stage 2: Process cross-reviews (if provided)
    Stage 3: Produce structured synthesis
    """
    # Stage 1: Score consensus from proposals
    scores = score_consensus(proposals)

    # Stage 2: Extract dissent (includes cross-review processing)
    dissents = extract_dissent(proposals, cross_reviews)

    # Stage 3: Synthesize decision
    consensus_pts = scores["consensus_points"]

    # Build decision summary from top consensus points
    if consensus_pts:
        top_points = [cp["point"] for cp in consensus_pts[:5]]
        decision = ". ".join(top_points)
        if not decision.endswith("."):
            decision += "."
    elif proposals:
        # No clear consensus — use highest-confidence proposal
        best = max(proposals, key=lambda p: p.confidence)
        decision = best.proposal
    else:
        decision = "No proposals provided."

    # Collect open questions from cross-reviews
    open_questions: list[str] = []
    if cross_reviews:
        for review in cross_reviews:
            open_questions.extend(review.questions)
    # Deduplicate
    seen: set[str] = set()
    unique_questions: list[str] = []
    for q in open_questions:
        q_lower = q.strip().lower()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique_questions.append(q.strip())

    return ConsensusResult(
        decision=decision,
        confidence=scores["confidence"],
        consensus_points=consensus_pts,
        dissenting_views=dissents,
        open_questions=unique_questions,
        rounds=1 if not cross_reviews else 2,
        participants=len(proposals),
        proposals=proposals,
        cross_reviews=cross_reviews or [],
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_for_memory(result: ConsensusResult) -> dict:
    """Format consensus result for storage in wicked-brain:memory.

    Returns dict suitable for memory.create() with:
    - content: decision summary
    - type: "decision"
    - metadata: consensus details including dissent
    """
    strong_dissents = [
        d for d in result.dissenting_views if d.strength == "strong"
    ]
    return {
        "content": result.decision,
        "type": "decision",
        "metadata": {
            "confidence": result.confidence,
            "participants": result.participants,
            "rounds": result.rounds,
            "consensus_point_count": len(result.consensus_points),
            "dissent_count": len(result.dissenting_views),
            "strong_dissent_count": len(strong_dissents),
            "strong_dissents": [
                {"persona": d.persona, "view": d.view}
                for d in strong_dissents
            ],
            "open_question_count": len(result.open_questions),
        },
    }


def format_for_display(
    result: ConsensusResult, show_dissent: bool = False,
) -> str:
    """Format consensus result as human-readable markdown."""
    lines: list[str] = []
    lines.append("## Council Consensus")
    lines.append("")
    lines.append(f"**Confidence:** {result.confidence:.0%}")
    lines.append(f"**Participants:** {result.participants}")
    lines.append(f"**Rounds:** {result.rounds}")
    lines.append("")

    lines.append("### Decision")
    lines.append("")
    lines.append(result.decision)
    lines.append("")

    if result.consensus_points:
        lines.append("### Consensus Points")
        lines.append("")
        for cp in result.consensus_points:
            lines.append(
                f"- ({cp['agreement']}/{cp['of']}) {cp['point']}"
            )
        lines.append("")

    if show_dissent and result.dissenting_views:
        lines.append("### Dissenting Views")
        lines.append("")
        for dv in result.dissenting_views:
            icon = {"strong": "!!", "moderate": "!", "mild": "~"}.get(
                dv.strength, "~"
            )
            lines.append(f"- [{icon}] **{dv.persona}**: {dv.view}")
        lines.append("")

    if result.open_questions:
        lines.append("### Open Questions")
        lines.append("")
        for q in result.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_council_result(result: ConsensusResult, session_id: str) -> dict:
    """Store council result via DomainStore("wicked-jam").

    Stores under source "council-results" with full consensus data.
    """
    ds = DomainStore("wicked-jam")
    payload = {
        "session_id": session_id,
        "decision": result.decision,
        "confidence": result.confidence,
        "consensus_points": result.consensus_points,
        "dissenting_views": [asdict(d) for d in result.dissenting_views],
        "open_questions": result.open_questions,
        "rounds": result.rounds,
        "participants": result.participants,
        "proposals": [asdict(p) for p in result.proposals],
        "cross_reviews": [asdict(r) for r in result.cross_reviews],
    }
    return ds.create("council-results", payload)


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------

def _proposals_from_json(data: list[dict]) -> list[Proposal]:
    return [
        Proposal(
            persona=d["persona"],
            proposal=d["proposal"],
            rationale=d.get("rationale", ""),
            confidence=float(d.get("confidence", 0.5)),
            concerns=d.get("concerns", []),
        )
        for d in data
    ]


def _reviews_from_json(data: list[dict]) -> list[CrossReview]:
    return [
        CrossReview(
            reviewer=d["reviewer"],
            target_persona=d["target_persona"],
            agreements=d.get("agreements", []),
            disagreements=d.get("disagreements", []),
            questions=d.get("questions", []),
        )
        for d in data
    ]


def _result_from_json(data: dict) -> ConsensusResult:
    return ConsensusResult(
        decision=data["decision"],
        confidence=float(data["confidence"]),
        consensus_points=data.get("consensus_points", []),
        dissenting_views=[
            DissentingView(**dv)
            for dv in data.get("dissenting_views", [])
        ],
        open_questions=data.get("open_questions", []),
        rounds=data.get("rounds", 1),
        participants=data.get("participants", 0),
        proposals=_proposals_from_json(data.get("proposals", [])),
        cross_reviews=_reviews_from_json(data.get("cross_reviews", [])),
    )


# ---------------------------------------------------------------------------
# Council raw-vote surfacing (Issue #584)
# ---------------------------------------------------------------------------

def _extract_rationale(
    raw_text: str,
    max_chars: int = _RATIONALE_MAX_CHARS,
) -> str:
    """Derive a one-line rationale from a model's raw response (Issue #584).

    Selection rules (deterministic — same input always yields same output):

    1. If the response contains a ``summary:`` / ``tl;dr:`` / ``verdict:`` /
       ``recommendation:`` label line, take the text after the first such
       label.  Models frequently emit their own terse one-liner we should
       prefer over our own slice.
    2. Otherwise take the first ``max_chars`` characters of the trimmed
       response, collapsing internal whitespace to single spaces so the
       rationale fits on one line.

    The returned string is always ``<= max_chars`` characters.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()
    # Rule 1: look for a model-authored summary label on any line.
    for line in text.splitlines():
        for pattern in _SUMMARY_LABEL_PATTERNS:
            match = pattern.match(line)
            if match:
                candidate = re.sub(r"\s+", " ", match.group(1)).strip()
                if candidate:
                    return candidate[:max_chars]

    # Rule 2: fall back to a prefix of the flattened response.
    flattened = re.sub(r"\s+", " ", text).strip()
    return flattened[:max_chars]


def _normalise_confidence(value: Any) -> float | None:
    """Return a float confidence in [0.0, 1.0] or ``None``.

    ``None``, missing keys, empty strings, and unparseable values all map to
    ``None`` — critically, they must NOT collapse to ``0.0`` because that
    would be indistinguishable from a model that explicitly voted
    low-confidence (Issue #584 — missing != zero).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int in Python; reject it to avoid True -> 1.0.
        return None
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    # Clamp into [0.0, 1.0] — models occasionally emit 0-100 scales; treating
    # out-of-range as None keeps the output honest rather than silently wrong.
    if conf < 0.0 or conf > 1.0:
        return None
    return conf


def _build_raw_vote(vote: Mapping[str, Any]) -> dict[str, Any]:
    """Build a single raw-vote entry from an input vote record.

    Input schema (tolerant — any of these fields may be present):
        {
            "model":       str,                    # required
            "verdict":     str,                    # required (passthrough)
            "confidence":  float | None,           # optional
            "rationale":   str,                    # optional (caller-supplied)
            "raw_text":    str,                    # optional (model response)
            "response":    str,                    # optional alias for raw_text
        }

    Output schema (stable — this is the public surface per Issue #584):
        {"model", "verdict", "confidence", "rationale"}
    """
    # Model + verdict are passed through as strings; ``None`` is preserved as
    # ``None`` so downstream consumers can distinguish "no vote" from "empty".
    model = vote.get("model")
    verdict = vote.get("verdict")

    # Rationale precedence: caller-supplied > model-extracted > empty string.
    supplied = vote.get("rationale")
    if isinstance(supplied, str) and supplied.strip():
        rationale = re.sub(r"\s+", " ", supplied.strip())[:_RATIONALE_MAX_CHARS]
    else:
        raw_text = vote.get("raw_text") or vote.get("response") or ""
        rationale = _extract_rationale(str(raw_text))

    return {
        "model": model,
        "verdict": verdict,
        "confidence": _normalise_confidence(vote.get("confidence")),
        "rationale": rationale,
    }


def _read_council_output_mode(env: Mapping[str, str] | None) -> str:
    """Read ``WG_COUNCIL_OUTPUT`` and return a validated mode string."""
    source = env if env is not None else os.environ
    raw = (source.get(ENV_COUNCIL_OUTPUT) or COUNCIL_OUTPUT_BOTH).strip().lower()
    if raw not in _VALID_COUNCIL_OUTPUTS:
        return COUNCIL_OUTPUT_BOTH
    return raw


def build_council_output(
    votes: list[Mapping[str, Any]],
    synthesized: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble the council output envelope (Issue #584).

    Emits the synthesised verdict and/or the raw per-model votes based on the
    ``WG_COUNCIL_OUTPUT`` env var (default ``both``):

    * ``both``  — top-level ``synthesized`` + ``raw_votes``
    * ``synth`` — ``synthesized`` only (legacy shape; backward-compatible)
    * ``raw``   — ``raw_votes`` only (unvarnished per-model layer)

    Args:
        votes: One dict per model that voted.  Each dict carries at least a
            ``model`` and ``verdict``; ``confidence``, ``rationale``, and
            ``raw_text`` are optional.  See :func:`_build_raw_vote`.
        synthesized: The synthesised verdict shape already produced by the
            council agent.  Passed through unchanged; this function does not
            rewrite which models were called or how votes were counted.
        env: Optional env mapping (testing seam; defaults to ``os.environ``).

    Returns:
        Dict with the requested top-level keys.  Callers depending on the
        legacy single-key shape should set ``WG_COUNCIL_OUTPUT=synth``.
    """
    mode = _read_council_output_mode(env)
    raw_votes = [_build_raw_vote(v) for v in votes]
    synth_payload: dict[str, Any] = dict(synthesized) if synthesized else {}

    output: dict[str, Any] = {}
    if mode in (COUNCIL_OUTPUT_BOTH, COUNCIL_OUTPUT_SYNTH):
        output["synthesized"] = synth_payload
    if mode in (COUNCIL_OUTPUT_BOTH, COUNCIL_OUTPUT_RAW):
        output["raw_votes"] = raw_votes
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Jam council consensus scoring and synthesis",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # synthesize
    syn = sub.add_parser("synthesize", help="Run full consensus protocol")
    syn.add_argument("--proposals", required=True, help="Path to proposals JSON")
    syn.add_argument("--reviews", default=None, help="Path to cross-reviews JSON")
    syn.add_argument("--question", default="", help="Original question")

    # score
    sc = sub.add_parser("score", help="Score consensus from proposals")
    sc.add_argument("--proposals", required=True, help="Path to proposals JSON")

    # format
    fmt = sub.add_parser("format", help="Format a consensus result")
    fmt.add_argument("--result", required=True, help="Path to result JSON")
    fmt.add_argument("--show-dissent", action="store_true", help="Show dissenting views")

    args = parser.parse_args()

    if args.command == "synthesize":
        proposals = _proposals_from_json(
            json.loads(Path(args.proposals).read_text(encoding="utf-8"))
        )
        reviews = None
        if args.reviews:
            reviews = _reviews_from_json(
                json.loads(Path(args.reviews).read_text(encoding="utf-8"))
            )
        result = synthesize(proposals, reviews, args.question)
        sys.stdout.write(json.dumps(asdict(result), indent=2))

    elif args.command == "score":
        proposals = _proposals_from_json(
            json.loads(Path(args.proposals).read_text(encoding="utf-8"))
        )
        scores = score_consensus(proposals)
        sys.stdout.write(json.dumps(scores, indent=2))

    elif args.command == "format":
        data = json.loads(Path(args.result).read_text(encoding="utf-8"))
        result = _result_from_json(data)
        sys.stdout.write(format_for_display(result, show_dissent=args.show_dissent))


if __name__ == "__main__":
    main()
