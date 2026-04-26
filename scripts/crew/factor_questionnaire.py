#!/usr/bin/env python3
"""Questionnaire-based facilitator scorer — replaces post-#428 manual rubric tax (#625).

Architecture:
  questionnaire (data) -> answers (model) -> deterministic scorer -> factor readings (JSON)

Replaces ~10min manual rubric reasoning with ~30sec structured Q&A + mechanical scoring.

Public API:
    score_factor(rubric, answers) -> tuple[Reading, str]
    score_all(answers) -> dict[str, dict]
    render_questionnaire() -> str
    parse_answers(model_response) -> dict[str, dict[str, bool]]

Stdlib-only (re, dataclasses, typing, json).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Literal, Tuple

Reading = Literal["HIGH", "MEDIUM", "LOW"]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# R3: No magic values — all thresholds are named on FactorRubric.

@dataclass(frozen=True)
class Question:
    id: str
    q: str
    yes_weight: int  # contribution to LOW score (higher weight = riskier when YES)


@dataclass(frozen=True)
class FactorRubric:
    name: str
    questions: Tuple[Question, ...]
    # Threshold convention: 0 pts → HIGH (safest), max pts → LOW (riskiest)
    medium_threshold: int   # total points >= this → at least MEDIUM
    low_threshold: int      # total points >= this → LOW

    def __post_init__(self) -> None:
        if not (self.low_threshold > self.medium_threshold > 0):
            raise ValueError(
                f"FactorRubric {self.name!r}: thresholds must satisfy "
                f"low_threshold ({self.low_threshold}) > medium_threshold "
                f"({self.medium_threshold}) > 0"
            )
        if not all(q.yes_weight > 0 for q in self.questions):
            raise ValueError(
                f"FactorRubric {self.name!r}: all yes_weight values must be > 0"
            )


# ---------------------------------------------------------------------------
# Questionnaire — all 9 canonical factors
# Calibrated against factor-definitions.md (reversibility = LOW means hard to reverse)
# ---------------------------------------------------------------------------

QUESTIONNAIRE: Dict[str, FactorRubric] = {
    "reversibility": FactorRubric(
        name="reversibility",
        questions=(
            Question("r1", "Does this work modify production state that can't be undone via git revert?", 3),
            Question("r2", "Does this work involve data migration that drops or transforms existing rows?", 2),
            Question("r3", "Are there external API consumers (other plugins, end-users with cached responses) depending on a surface being removed/renamed?", 2),
            Question("r4", "Could a customer experience the change in production before we'd notice and roll back?", 1),
        ),
        medium_threshold=1,
        low_threshold=3,
    ),
    "blast_radius": FactorRubric(
        name="blast_radius",
        questions=(
            Question("b1", "Does this change touch shared infrastructure used by more than one team?", 3),
            Question("b2", "Does this change affect an auth, billing, or storage subsystem?", 3),
            Question("b3", "Could a bug in this change trigger a page or on-call alert?", 2),
            Question("b4", "Does this change affect more than one customer-facing surface simultaneously?", 2),
            Question("b5", "Is this change distributed via CDN, mobile app, or other cached client artifact?", 1),
        ),
        medium_threshold=2,
        low_threshold=5,
    ),
    "compliance_scope": FactorRubric(
        name="compliance_scope",
        questions=(
            Question("c1", "Does this work directly handle PII, PHI, payment card data, or authentication credentials?", 4),
            Question("c2", "Does this work create or modify audit logs, consent records, or data export/deletion endpoints?", 3),
            Question("c3", "Does this work involve cross-border data transfer or data residency constraints?", 2),
            Question("c4", "Does this code path serialize user-provided objects, request bodies, or entity models into logs or traces?", 1),
        ),
        medium_threshold=1,
        low_threshold=4,
    ),
    "user_facing_impact": FactorRubric(
        name="user_facing_impact",
        questions=(
            # u1 weight 2 (was 3) — calibrated 2026-04-25 after cluster-A field test:
            # a single visible change should land MEDIUM, not LOW. LOW reading requires
            # multiple visible surfaces affected. See discovery-conventions audit.
            Question("u1", "Does this change produce a visible UI change, copy change, or new user-visible flow?", 2),
            Question("u2", "Does this change affect a public API response shape that callers consume directly?", 2),
            Question("u3", "Does this change affect an email, notification, or export format seen by end-users?", 2),
            Question("u4", "Does this change affect perceived latency, reliability, or cost in a way users will notice?", 1),
        ),
        medium_threshold=1,
        low_threshold=3,
    ),
    "novelty": FactorRubric(
        name="novelty",
        questions=(
            Question("n1", "Have there been rollbacks or failures on similar changes in this codebase's history?", 3),
            Question("n2", "Is this the first time this team is applying this pattern in this codebase?", 2),
            Question("n3", "Are there fewer than 2 strong prior examples (memory/wiki) for this type of change?", 2),
            Question("n4", "Does this require integrating a library or service new to this stack?", 1),
        ),
        medium_threshold=2,
        low_threshold=4,
    ),
    "scope_effort": FactorRubric(
        name="scope_effort",
        questions=(
            Question("s1", "Does this change touch more than 20 files?", 3),
            Question("s2", "Does this change span 3 or more services or repos?", 3),
            Question("s3", "Does this change require coordination across 2 or more teams?", 2),
            Question("s4a", "Does this work touch more than 5 files?", 1),
            Question("s4b", "Does this work touch more than 20 files OR more than one service?", 2),
        ),
        medium_threshold=1,
        low_threshold=5,
    ),
    "state_complexity": FactorRubric(
        name="state_complexity",
        questions=(
            Question("sc1", "Does this change add a schema migration, column backfill, or data transformation?", 4),
            Question("sc2", "Does this change break or change an existing serialization format stored on disk or in a DB?", 3),
            Question("sc3", "Does this change alter a cache invalidation strategy or introduce a new cache layer?", 2),
            Question("sc4", "Does this change read from persistent state without altering its shape (read-only index, new query)?", 1),
        ),
        medium_threshold=1,
        low_threshold=4,
    ),
    "operational_risk": FactorRubric(
        name="operational_risk",
        questions=(
            Question("o1", "Does this change add a new network call on a hot path that runs synchronously in production?", 3),
            Question("o2", "Does this change modify queuing, rate-limiting, or circuit-breaker behavior?", 3),
            Question("o3", "Does this change introduce a new external dependency (API, library) into the production runtime?", 2),
            Question("o4", "Does this change alter retry, timeout, or backoff parameters?", 2),
            # calibrated 2026-04-26 per issue #639 — reword restricts to scale criterion, weight=2 allows solo MEDIUM
            Question("o5", "Is this change deployed without a feature flag AND expected to directly affect more than 1M users/rows in production on day 1?", 2),
        ),
        medium_threshold=2,
        low_threshold=5,
    ),
    "coordination_cost": FactorRubric(
        name="coordination_cost",
        questions=(
            Question("cc1", "Does this change require 3 or more specialists to agree before it can ship?", 3),
            Question("cc2", "Does this change require a contract negotiation between two services or teams?", 2),
            # cc3 reworded 2026-04-25 after cluster-A field test: the original "across
            # different specialists" trips YES whenever the facilitator picks 2+ agents,
            # even when one contributor dispatches all of them with no human handoff.
            # Coordination cost is about humans negotiating, not agents being dispatched.
            Question("cc3", "Does this change require a design + build handoff across different humans (not just different agents dispatched by the same person)?", 2),
            Question("cc4", "Does this change require a product + engineering alignment on scope or acceptance criteria?", 1),
        ),
        medium_threshold=1,
        low_threshold=4,
    ),
}

# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def score_factor(rubric: FactorRubric, answers: Dict[str, bool]) -> Tuple[Reading, str]:
    """Score one factor from yes/no answers.

    Args:
        rubric: The FactorRubric for this factor.
        answers: Mapping of question-id → bool (missing ids treated as False).

    Returns:
        (reading, why) — reading is LOW|MEDIUM|HIGH; why is a human-readable trace.
    """
    yes_questions = [q for q in rubric.questions if answers.get(q.id, False)]
    points = sum(q.yes_weight for q in yes_questions)

    if points >= rubric.low_threshold:
        reading: Reading = "LOW"
    elif points >= rubric.medium_threshold:
        reading = "MEDIUM"
    else:
        reading = "HIGH"

    if yes_questions:
        ids = ", ".join(q.id for q in yes_questions)
        why = f"{points} pts from: {ids}"
    else:
        why = "no risk-flagging questions answered yes"

    return reading, why


# R3: named constant for reading → risk language translation.
# Convention: HIGH reading = least risky (best safety); LOW reading = most risky.
# risk_level uses standard risk language so downstream consumers aren't misled by
# the counter-intuitive HIGH=safe direction of Reading.
_RISK_INVERSION: Dict[Reading, str] = {
    "HIGH": "low_risk",
    "MEDIUM": "medium_risk",
    "LOW": "high_risk",
}


def score_all(answers: Dict[str, Dict[str, bool]]) -> Dict[str, Dict]:
    """Score all 9 factors from a nested answers dict.

    Args:
        answers: Outer key = factor name, inner key = question id, value = bool.
                 Missing factors default to empty (all-no).

    Returns:
        Dict matching the factors block of output-schema.md:
        {
            "reversibility": {
                "reading": "HIGH|MEDIUM|LOW",  # backward compat — HIGH=safest
                "risk_level": "low_risk|medium_risk|high_risk",  # human-friendly
                "why": "..."
            },
            ...
        }
        Existing consumers reading `reading` are unaffected. New consumers should
        prefer `risk_level` to avoid the direction-inversion footgun.
    """
    result = {}
    for name, rubric in QUESTIONNAIRE.items():
        reading, why = score_factor(rubric, answers.get(name, {}))
        result[name] = {
            "reading": reading,
            "risk_level": _RISK_INVERSION[reading],
            "why": why,
        }
    return result


# ---------------------------------------------------------------------------
# Questionnaire renderer
# ---------------------------------------------------------------------------

def render_questionnaire() -> str:
    """Render the full questionnaire as markdown for the model to answer.

    The model should respond with a YAML block (or JSON) mapping factor names
    to dicts of question-id → true|false. Use parse_answers() to parse the response.
    """
    lines = [
        "## Facilitator Scorer Questionnaire",
        "",
        "Answer each question YES (true) or NO (false) based on the project description",
        "and any priors you have fetched. When uncertain, call `wicked-garden:ground`",
        "before answering. Respond with a YAML block in the exact format shown.",
        "",
        "```yaml",
        "answers:",
    ]

    for factor_name, rubric in QUESTIONNAIRE.items():
        lines.append(f"  {factor_name}:")
        for q in rubric.questions:
            lines.append(f"    {q.id}: false  # {q.q}")

    lines.append("```")
    lines.append("")
    lines.append(
        "_Tip: if you are uncertain about any answer, invoke `wicked-garden:ground`_"
        " _with the question text before answering._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Answer parser
# ---------------------------------------------------------------------------

# R3: named constant instead of bare magic literal.
_YAML_BOOL_TRUE = frozenset({"true", "yes", "1"})
_YAML_BOOL_FALSE = frozenset({"false", "no", "0"})

_FACTOR_NAMES = frozenset(QUESTIONNAIRE.keys())


def _parse_yaml_answers(text: str) -> Dict[str, Dict[str, bool]]:
    """Parse a simple flat YAML answers block (no external deps).

    Expected shape:
        answers:
          reversibility:
            r1: true
            r2: false
          ...

    Raises:
        ValueError on malformed input (unknown factor, unknown question id,
        unrecognised boolean value).
    """
    # Strip code fences if present.
    text = re.sub(r"```[a-z]*\n?", "", text).strip()

    # Find the `answers:` block.
    match = re.search(r"answers\s*:\s*\n(.*)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("parse_answers: could not find 'answers:' block in response")
    body = match.group(1)

    result: Dict[str, Dict[str, bool]] = {}
    current_factor: str | None = None

    for raw_line in body.splitlines():
        # Strip inline comments.
        line = raw_line.split("#")[0]
        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        if indent <= 2 and stripped.endswith(":"):
            # Factor-level key.
            factor = stripped.rstrip(":").strip()
            if factor not in _FACTOR_NAMES:
                raise ValueError(
                    f"parse_answers: unknown factor '{factor}'; "
                    f"expected one of {sorted(_FACTOR_NAMES)}"
                )
            current_factor = factor
            result[current_factor] = {}

        elif indent >= 4 and ":" in stripped and current_factor is not None:
            # Question-level key: value.
            key, _, val_raw = stripped.partition(":")
            key = key.strip()
            val_str = val_raw.strip().lower()

            if val_str in _YAML_BOOL_TRUE:
                val = True
            elif val_str in _YAML_BOOL_FALSE:
                val = False
            else:
                raise ValueError(
                    f"parse_answers: unrecognised boolean '{val_raw.strip()}' "
                    f"for {current_factor}.{key}"
                )
            result[current_factor][key] = val

    if not result:
        raise ValueError(
            "parse_answers: no factor answers found — check YAML indentation"
        )
    return result


def _parse_json_answers(text: str) -> Dict[str, Dict[str, bool]]:
    """Parse a JSON answers block.

    Expected shape: {"answers": {"reversibility": {"r1": true, ...}, ...}}
    or just the inner dict {"reversibility": {"r1": true, ...}, ...}.

    Raises:
        ValueError on malformed input.
    """
    # Strip code fences.
    text = re.sub(r"```[a-z]*\n?", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"parse_answers: invalid JSON — {exc}") from exc

    # Support both {"answers": {...}} and bare factor dict.
    if isinstance(data, dict) and "answers" in data:
        data = data["answers"]

    if not isinstance(data, dict):
        raise ValueError("parse_answers: JSON root must be an object")

    result: Dict[str, Dict[str, bool]] = {}
    for factor, qs in data.items():
        if factor not in _FACTOR_NAMES:
            raise ValueError(
                f"parse_answers: unknown factor '{factor}'; "
                f"expected one of {sorted(_FACTOR_NAMES)}"
            )
        if not isinstance(qs, dict):
            raise ValueError(
                f"parse_answers: factor '{factor}' value must be an object"
            )
        result[factor] = {}
        for qid, val in qs.items():
            if not isinstance(val, bool):
                raise ValueError(
                    f"parse_answers: {factor}.{qid} must be a boolean, got {val!r}"
                )
            result[factor][qid] = val

    return result


def parse_answers(model_response: str) -> Dict[str, Dict[str, bool]]:
    """Parse the model's questionnaire response into a nested answers dict.

    Tries JSON first, then YAML. Raises ValueError on malformed input — callers
    should surface the error to the model to retry rather than swallowing it.

    Returns:
        { "reversibility": {"r1": True, "r2": False, ...}, ... }
    """
    # R4: no swallowed errors — ValueError propagates to caller.
    stripped = re.sub(r"```[a-z]*\n?", "", model_response).strip()

    # Detect JSON by first non-whitespace char.
    first_char = stripped.lstrip()[0] if stripped.strip() else ""
    if first_char == "{":
        return _parse_json_answers(model_response)

    return _parse_yaml_answers(model_response)
