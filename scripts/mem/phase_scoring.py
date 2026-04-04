"""
Phase-aware memory scoring for crew-context recall.

Adds phase affinity boosts so that memories created in related phases
rank higher when recalled during a specific crew phase.

Stdlib-only, cross-platform.  Backward compatible: None phase = no boost.
"""

import json
import os
import sys
from pathlib import Path

# Allow sibling imports (e.g. crew.crew)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Phase Affinity Matrix ────────────────────────────────────────────

PHASE_AFFINITY = {
    "ideate": {
        "high": ["brainstorm", "ideate"],
        "medium": ["clarify"],
        "low": ["design", "build", "test", "review"],
    },
    "clarify": {
        "high": ["clarify", "ideate", "requirement"],
        "medium": ["design"],
        "low": ["build", "test", "review"],
    },
    "design": {
        "high": ["design", "clarify", "architecture"],
        "medium": ["ideate", "build"],
        "low": ["test", "review"],
    },
    "build": {
        "high": ["design", "clarify", "build"],
        "medium": ["test-strategy", "test"],
        "low": ["ideate", "review"],
    },
    "test": {
        "high": ["test-strategy", "test", "build"],
        "medium": ["clarify", "requirement"],
        "low": ["design", "ideate"],
    },
    "review": {
        "high": [],
        "medium": [],
        "low": [],
    },
}

AFFINITY_BOOSTS = {"high": 1.5, "medium": 1.0, "low": 0.7}


# ── Public API ───────────────────────────────────────────────────────

def get_phase_boost(memory_phase, active_phase):
    """Return the phase affinity multiplier for *memory_phase* given *active_phase*.

    Returns 1.5 (high), 1.0 (medium), or 0.7 (low).
    Returns 1.0 when either phase is ``None`` (backward compatible).
    """
    if not memory_phase or not active_phase:
        return 1.0

    affinity = PHASE_AFFINITY.get(active_phase)
    if not affinity:
        return 1.0

    for level, phases in affinity.items():
        if memory_phase in phases:
            return AFFINITY_BOOSTS[level]

    # No explicit mapping — treat as medium (neutral)
    return 1.0


def score_memories_by_phase(memories, active_phase, phase_field="phase"):
    """Score and sort *memories* by phase affinity to *active_phase*.

    Adds ``_phase_boost`` and ``_phase_score`` to each record.
    Multiplies existing ``_score`` or ``importance`` by the boost.
    Returns the list sorted by ``_phase_score`` descending.
    """
    if not active_phase:
        for m in memories:
            m["_phase_boost"] = 1.0
            base = m.get("_score", m.get("importance", 1.0))
            m["_phase_score"] = float(base) if base is not None else 1.0
        return memories

    for m in memories:
        boost = get_phase_boost(m.get(phase_field), active_phase)
        m["_phase_boost"] = boost
        base = m.get("_score", m.get("importance", 1.0))
        m["_phase_score"] = (float(base) if base is not None else 1.0) * boost

    memories.sort(key=lambda m: m["_phase_score"], reverse=True)
    return memories


def filter_memories_by_phase(memories, phase, phase_field="phase"):
    """Return only memories created in the given *phase*."""
    return [m for m in memories if m.get(phase_field) == phase]


def enrich_memory_with_phase(memory_data, active_phase=None):
    """Stamp the current crew phase onto *memory_data*.

    If *active_phase* is ``None``, attempts auto-detection.
    Returns the dict with a ``phase`` field added.
    """
    if active_phase is None:
        active_phase = detect_active_phase()
    if active_phase:
        memory_data["phase"] = active_phase
    return memory_data


def detect_active_phase():
    """Detect the active crew phase.

    1. ``WICKED_CREW_PHASE`` env var (set by hooks).
    2. ``crew.crew.find_active_project()`` to read project state.

    Returns phase name or ``None``.
    """
    env_phase = os.environ.get("WICKED_CREW_PHASE")
    if env_phase:
        return env_phase

    try:
        from crew.crew import find_active_project

        result = find_active_project()
        project = result.get("project")
        if project:
            return project.get("current_phase")
    except Exception:
        pass

    return None


# ── CLI ──────────────────────────────────────────────────────────────

def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase-aware memory scoring utilities"
    )
    sub = parser.add_subparsers(dest="command")

    score_p = sub.add_parser("score", help="Score memories by phase affinity")
    score_p.add_argument("--phase", required=True, help="Active crew phase")

    filter_p = sub.add_parser("filter", help="Filter memories by phase")
    filter_p.add_argument("--phase", required=True, help="Phase to filter by")

    sub.add_parser("detect-phase", help="Detect the active crew phase")

    boost_p = sub.add_parser("boost", help="Get boost for a phase pair")
    boost_p.add_argument("--memory-phase", required=True)
    boost_p.add_argument("--active-phase", required=True)

    args = parser.parse_args()

    if args.command == "score":
        memories = json.loads(sys.stdin.read())
        result = score_memories_by_phase(memories, args.phase)
        sys.stdout.write(json.dumps(result, default=str))
    elif args.command == "filter":
        memories = json.loads(sys.stdin.read())
        result = filter_memories_by_phase(memories, args.phase)
        sys.stdout.write(json.dumps(result, default=str))
    elif args.command == "detect-phase":
        phase = detect_active_phase()
        sys.stdout.write(json.dumps({"phase": phase}))
    elif args.command == "boost":
        boost = get_phase_boost(args.memory_phase, args.active_phase)
        sys.stdout.write(json.dumps({"boost": boost}))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _cli()
