#!/usr/bin/env python3
"""persist.py — Write LLM classification result to SessionState.

The wicked-garden:classify skill asks the model to reason through the
prompt and emit a JSON classification. The model invokes this script
with the JSON on stdin (or as --data), and we persist to SessionState
so prompt_submit.py reads it on subsequent turns.

Schema accepted (any subset OK; we coerce defaults):

    {
      "intent": "simple-edit | feature | rigor | research",
      "archetypes": [
        {"name": "build", "score": 0.85, "evidence": ["..."]},
        ...
      ],
      "signals": {
        "blast_radius_high": false,
        "novelty_high": true,
        "state_complexity_high": false,
        "reversibility_low": false,
        "production_impact": false,
        "compliance_scope": false
      }
    }

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS))


VALID_INTENTS = {"simple-edit", "feature", "rigor", "research"}
VALID_ARCHETYPES = {"triage", "explore", "specify", "decide", "ship",
                    "review", "incident", "build", "migrate"}
VALID_SIGNAL_KEYS = {
    "blast_radius_high", "novelty_high", "state_complexity_high",
    "reversibility_low", "reversibility_medium_or_low",
    "production_impact", "compliance_scope",
    "ambiguity_high", "spec_ambiguity_high", "scope_unclear",
    "multiple_viable_options", "post_build", "code_change",
    "independent_assessment_needed",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _normalize(payload: dict) -> dict:
    """Coerce user-supplied JSON to the canonical shape. Drop unknowns."""
    out = {}

    intent = payload.get("intent")
    if isinstance(intent, str) and intent in VALID_INTENTS:
        out["intent"] = intent

    archetypes_raw = payload.get("archetypes") or []
    archetypes = []
    if isinstance(archetypes_raw, list):
        for a in archetypes_raw[:5]:  # cap top-5
            if not isinstance(a, dict):
                continue
            name = a.get("name")
            if name not in VALID_ARCHETYPES:
                continue
            try:
                score = float(a.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(1.0, score))
            evidence = a.get("evidence") or []
            if not isinstance(evidence, list):
                evidence = [str(evidence)]
            evidence = [str(e)[:200] for e in evidence[:5]]
            archetypes.append({
                "name": name, "score": round(score, 3), "evidence": evidence,
            })
    out["archetypes"] = archetypes

    signals_raw = payload.get("signals") or {}
    signals = {}
    if isinstance(signals_raw, dict):
        for k, v in signals_raw.items():
            if k in VALID_SIGNAL_KEYS and isinstance(v, bool):
                signals[k] = v
    out["signals"] = signals

    return out


def persist(payload: dict) -> dict:
    """Write the classification to SessionState. Returns the normalised
    payload for confirmation."""
    normalized = _normalize(payload)
    try:
        from _session import SessionState  # type: ignore
    except ImportError:
        print(json.dumps({"ok": False, "error": "SessionState unavailable"}),
              file=sys.stderr)
        sys.exit(1)

    state = SessionState.load()
    if normalized.get("intent"):
        state.update(intent=normalized["intent"], intent_explicit=False)
    state.update(
        archetypes_v11=normalized.get("archetypes") or [],
        signals_v11=normalized.get("signals") or {},
        classified_at=_utc_now(),
    )

    # v11.1.1: emit a bus event so the classification is in the audit log.
    # Fail-open: bus unavailable must not break the persist call.
    try:
        from _bus import emit_event  # type: ignore
        archetypes = normalized.get("archetypes") or []
        primary = archetypes[0]["name"] if archetypes else "triage"
        emit_event(
            "wicked.archetype.classified",
            {
                "intent": normalized.get("intent"),
                "primary_archetype": primary,
                "archetypes": [a.get("name") for a in archetypes],
                "tier": "llm",
            },
            chain_id=f"classify.{primary}.{state.session_id or 'no-session'}",
        )
    except Exception:
        pass

    return normalized


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Persist a classify-skill JSON result to SessionState."
    )
    parser.add_argument(
        "--data", default=None,
        help="JSON string. If omitted, reads from stdin.",
    )
    args = parser.parse_args()
    raw = args.data if args.data else sys.stdin.read()
    try:
        payload = json.loads(raw) if raw and raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"invalid JSON: {exc}"}),
              file=sys.stderr)
        sys.exit(1)
    if not isinstance(payload, dict):
        print(json.dumps({"ok": False, "error": "expected JSON object"}),
              file=sys.stderr)
        sys.exit(1)
    normalized = persist(payload)
    print(json.dumps({"ok": True, "persisted": normalized}, indent=2))


if __name__ == "__main__":
    _cli()
