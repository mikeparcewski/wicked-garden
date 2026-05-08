#!/usr/bin/env python3
"""archetypes_v11.py — Work-shape archetype detection + steering engine.

v11 reframes the crew workflow: instead of a fixed
clarify->design->build->test->review pipeline with a "rigor tier" dial,
each prompt is classified into one or more **work-shape archetypes**
(triage / explore / specify / decide / ship / review / incident /
build / migrate). Each archetype owns its own phase shape, produces,
HITL discipline, and cost band. Steering directives fire per archetype,
not per fixed-pipeline phase.

This is the v6.3 archetype-detect's spiritual successor — but v6.3
classified the *target kind* (code-repo / docs-only / config-infra /
multi-repo / etc.) and used it to pick gate thresholds. v11 classifies
the *work shape* and uses it to pick the entire workflow.

The two coexist during transition:
  * scripts/crew/archetype_detect.py — v6.3 target-kind classifier,
    consumed by gate-adjudicator.
  * scripts/crew/archetypes_v11.py    — v11 work-shape classifier,
    consumed by steering-aware skills.

Stdlib-only. CLI shim at bottom of file.

Usage (library):
    from archetypes_v11 import detect_archetypes, steering_directives

    matches = detect_archetypes(
        prompt="add caching to the dashboard",
        signals={"complexity": 3, "blast_radius": "low"},
    )
    # matches -> [("build", 0.85, ["phrase: add"])]

    directives = steering_directives(matches, signals)
    # directives -> [{"archetype": "build", "phases": [...], "next_action": ...}]

Usage (CLI):
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \\
      "${CLAUDE_PLUGIN_ROOT}/scripts/crew/archetypes_v11.py" \\
      detect --prompt "add caching to the dashboard"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_THIS_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parents[1]
_CATALOG_PATH = _PLUGIN_ROOT / ".claude-plugin" / "archetypes.json"


# Confidence thresholds — kept as named constants so callers can grep
# for the doctrine and tests can lock them.
HIGH_CONFIDENCE = 0.7
MEDIUM_CONFIDENCE = 0.5
LOW_CONFIDENCE = 0.3


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the archetype catalog dict. Raises FileNotFoundError when
    the catalog isn't present — callers should not silently fall back."""
    catalog_path = path or _CATALOG_PATH
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def _phrase_score(prompt_lower: str, phrases: List[str]) -> Tuple[float, List[str]]:
    """Score how strongly the prompt matches a phrase list.

    First match scores 0.55 (above MEDIUM_CONFIDENCE so a single strong
    keyword trips a directive). Each additional match adds 0.2 up to a
    0.9 cap. Returns (score, hits) so the steering directive can name
    the matched phrases.

    Calibration rationale: archetype phrases are *category words* like
    'implement' / 'outage' / 'migrate' — they are intentionally
    high-signal. One should be enough to fire 'suggest' strength; two
    should escalate to 'recommend'.
    """
    hits: List[str] = []
    for phrase in phrases:
        # Word-boundary match for short phrases; substring for multi-word
        # (multi-word phrases are inherently boundary-safe).
        if " " in phrase:
            if phrase in prompt_lower:
                hits.append(phrase)
        else:
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            if pattern.search(prompt_lower):
                hits.append(phrase)
    if not hits:
        return 0.0, []
    score = 0.55 + 0.2 * (len(hits) - 1)
    return min(score, 0.9), hits


def _signal_score(
    archetype_signals: Dict[str, Any],
    signals: Dict[str, Any],
) -> Tuple[float, List[str]]:
    """Score how the caller-provided signals agree with the archetype's
    declared signals. Each agreement adds 0.3 capped at 0.9.

    Recognized boolean signal flags (any subset is fine):
      - novelty_high, blast_radius_high, ambiguity_high,
        spec_ambiguity_high, scope_unclear, multiple_viable_options,
        reversibility_medium_or_low, reversibility_low,
        state_complexity_high, post_build, code_change,
        production_impact, independent_assessment_needed.

    Boolean True in the archetype declaration is a *requirement* —
    if the caller didn't pass that signal it scores 0.
    """
    hits: List[str] = []
    score = 0.0
    for key, declared in archetype_signals.items():
        if key in ("phrases", "always_on"):
            continue
        if declared is True and signals.get(key) is True:
            score += 0.3
            hits.append(f"signal: {key}")
    return min(score, 0.9), hits


def _detect_one_archetype(
    name: str,
    archetype: Dict[str, Any],
    prompt_lower: str,
    signals: Dict[str, Any],
) -> Tuple[float, List[str]]:
    """Score a single archetype against the prompt + signals.

    Returns (combined_score, evidence). Combined score is the max of
    phrase score and signal score plus 0.1 if both are non-zero
    (concordance bonus), capped at 1.0.
    """
    arch_signals = archetype.get("signals") or {}
    if arch_signals.get("always_on"):
        return 1.0, ["always_on"]

    phrase_list = list(arch_signals.get("phrases") or [])
    p_score, p_hits = _phrase_score(prompt_lower, phrase_list)
    s_score, s_hits = _signal_score(arch_signals, signals)

    if p_score == 0 and s_score == 0:
        return 0.0, []

    combined = max(p_score, s_score)
    if p_score > 0 and s_score > 0:
        combined = min(combined + 0.1, 1.0)
    return combined, p_hits + s_hits


def detect_archetypes(
    prompt: str,
    signals: Optional[Dict[str, Any]] = None,
    *,
    catalog: Optional[Dict[str, Any]] = None,
    threshold: float = MEDIUM_CONFIDENCE,
) -> List[Tuple[str, float, List[str]]]:
    """Classify a prompt into one or more work-shape archetypes.

    Args:
        prompt: User prompt or task description.
        signals: Optional dict with the boolean signal flags listed in
            ``_signal_score``. Typically populated from the
            propose-process 9-factor scoring or from runtime hooks.
        catalog: Override catalog (testing).
        threshold: Drop archetypes scoring below this. Default
            MEDIUM_CONFIDENCE (0.5).

    Returns:
        List of ``(archetype_name, score, evidence)`` tuples sorted by
        score descending. Always includes ``triage`` at the end as the
        fallback when no other archetype scores >= threshold.

    The triage archetype is special: it is always present in the result
    so callers always have a routing target. When triage is the only
    item returned, the caller should ask a clarifying question rather
    than dispatch.
    """
    catalog = catalog or load_catalog()
    archetypes = catalog.get("archetypes", {})
    prompt_lower = (prompt or "").lower()
    signals = signals or {}

    matches: List[Tuple[str, float, List[str]]] = []
    for name, archetype in archetypes.items():
        if name == "triage":
            continue  # always-on; appended last
        score, evidence = _detect_one_archetype(
            name, archetype, prompt_lower, signals,
        )
        if score >= threshold:
            matches.append((name, round(score, 3), evidence))

    matches.sort(key=lambda m: m[1], reverse=True)

    if not matches:
        # No clear shape — return triage so caller knows to clarify
        return [("triage", 1.0, ["no_other_archetype_above_threshold"])]

    matches.append(("triage", 1.0, ["always_on"]))
    return matches


def steering_directives(
    matches: List[Tuple[str, float, List[str]]],
    signals: Optional[Dict[str, Any]] = None,
    *,
    catalog: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Turn a match list into actionable steering directives.

    Each directive is a dict the caller emits as a system reminder,
    a TaskCreate, or a hook output. Shape:

        {
          "archetype": "build",
          "score": 0.85,
          "evidence": ["phrase: add", "signal: code_change"],
          "phases": ["plan", "implement", "test", "review"],
          "produces": ["shipped-code", "test-report"],
          "hitl": "discrete:review-gate",
          "cost_band": "high",
          "maturity": "research",
          "next_action": "Run `wicked-garden:engineering:implement` ...",
          "strength": "recommend"  # suggest | recommend | require
        }

    Strength escalates with score:
        score >= HIGH_CONFIDENCE   -> "recommend"
        score >= MEDIUM_CONFIDENCE -> "suggest"
        else                       -> "suggest" (informational)

    triage at the bottom of the match list adds an informational
    directive only if it is the *sole* match (no clear shape detected).
    """
    catalog = catalog or load_catalog()
    archetypes = catalog.get("archetypes", {})
    signals = signals or {}
    sole_match = len(matches) == 1 and matches[0][0] == "triage"

    directives: List[Dict[str, Any]] = []
    for name, score, evidence in matches:
        if name == "triage" and not sole_match:
            continue
        archetype = archetypes.get(name, {})
        if score >= HIGH_CONFIDENCE:
            strength = "recommend"
        else:
            strength = "suggest"
        directives.append({
            "archetype": name,
            "score": score,
            "evidence": evidence,
            "phases": list(archetype.get("phases", [])),
            "produces": list(archetype.get("produces", [])),
            "hitl": archetype.get("hitl"),
            "cost_band": archetype.get("cost_band"),
            "maturity": archetype.get("maturity"),
            "next_action": _next_action_for(name, archetype, signals),
            "strength": strength,
        })
    return directives


def _next_action_for(
    name: str,
    archetype: Dict[str, Any],
    signals: Dict[str, Any],
) -> str:
    """Render the recommended next-action string for an archetype.

    Kept centralized here so the wording is consistent across system
    reminders, hook output, and CLI display.
    """
    first_phase = (archetype.get("phases") or ["?"])[0]
    return (
        f"Enter '{name}' archetype at phase '{first_phase}'. "
        f"Phases: {' -> '.join(archetype.get('phases', []))}. "
        f"Produces: {', '.join(archetype.get('produces', []))}. "
        f"HITL: {archetype.get('hitl', 'none')}."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="v11 work-shape archetype detector + steering engine."
    )
    sub = parser.add_subparsers(dest="action", required=True)

    detect = sub.add_parser("detect", help="Detect archetypes from prompt + signals.")
    detect.add_argument("--prompt", required=True)
    detect.add_argument("--signals", default=None,
                        help="JSON object of boolean signal flags.")
    detect.add_argument("--threshold", type=float, default=MEDIUM_CONFIDENCE)
    detect.add_argument("--steering", action="store_true",
                        help="Also emit the per-archetype steering directives.")

    catalog_cmd = sub.add_parser("catalog",
                                 help="Print the archetype catalog as JSON.")
    catalog_cmd.add_argument("--name", default=None,
                             help="Print only one archetype by name.")

    args = parser.parse_args()

    if args.action == "detect":
        signals = json.loads(args.signals) if args.signals else {}
        matches = detect_archetypes(args.prompt, signals,
                                    threshold=args.threshold)
        result: Dict[str, Any] = {
            "matches": [
                {"archetype": n, "score": s, "evidence": e}
                for n, s, e in matches
            ]
        }
        if args.steering:
            result["directives"] = steering_directives(matches, signals)
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return

    if args.action == "catalog":
        catalog = load_catalog()
        if args.name:
            archetype = catalog.get("archetypes", {}).get(args.name)
            if archetype is None:
                print(f"Unknown archetype: {args.name}", file=sys.stderr)
                sys.exit(1)
            json.dump({args.name: archetype}, sys.stdout, indent=2)
        else:
            json.dump(catalog, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return


if __name__ == "__main__":
    _cli()
