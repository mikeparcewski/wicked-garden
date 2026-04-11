"""Phase-aware memory scoring for wicked-mem.

Applies phase affinity boosts to memories during recall, so that memories
created or tagged to relevant phases are surfaced more prominently.

Usage:
  phase_scoring.py boost --memory-phase PHASE --active-phase PHASE
  phase_scoring.py score --phase PHASE < memories.json
  phase_scoring.py filter --phase PHASE < memories.json
  phase_scoring.py detect-phase
"""

import argparse
import json
import sys

# Affinity table: "during phase X, memories from phase Y get this boost"
# high = 1.5, neutral = 1.0, low = 0.7
PHASE_AFFINITY = {
    "clarify": {
        "high": [],
        "low": [],
    },
    "ideate": {
        "high": [],
        "low": [],
    },
    "design": {
        "high": ["clarify"],
        "low": [],
    },
    "build": {
        "high": ["clarify", "design"],
        "low": ["ideate"],
    },
    "test": {
        "high": ["build", "design"],
        "low": ["ideate"],
    },
    "review": {
        "high": [],
        "low": [],
    },
    "operate": {
        "high": ["design", "build"],
        "low": ["ideate"],
    },
}

BOOST_HIGH = 1.5
BOOST_NEUTRAL = 1.0
BOOST_LOW = 0.7


def get_boost(memory_phase: str, active_phase: str) -> float:
    """Return the phase affinity boost multiplier."""
    if not active_phase:
        return BOOST_NEUTRAL
    affinity = PHASE_AFFINITY.get(active_phase, {})
    if memory_phase in affinity.get("high", []):
        return BOOST_HIGH
    if memory_phase in affinity.get("low", []):
        return BOOST_LOW
    return BOOST_NEUTRAL


def score_memories(memories: list, active_phase: str) -> list:
    """Apply phase boost to each memory and sort descending by _phase_score."""
    scored = []
    for m in memories:
        memory_phase = m.get("phase", "")
        boost = get_boost(memory_phase, active_phase)
        importance = float(m.get("importance", 5))
        scored_m = dict(m)
        scored_m["_phase_boost"] = boost
        scored_m["_phase_score"] = round(importance * boost, 4)
        scored.append(scored_m)
    scored.sort(key=lambda x: x["_phase_score"], reverse=True)
    return scored


def filter_memories(memories: list, target_phase: str) -> list:
    """Return only memories whose phase matches target_phase."""
    return [m for m in memories if m.get("phase") == target_phase]


def detect_active_phase() -> str | None:
    """Detect the current crew project phase from session state."""
    try:
        import os
        from pathlib import Path
        home = Path(os.environ.get("HOME", "~")).expanduser()
        state_dir = home / ".something-wicked" / "wicked-garden" / "local" / "wicked-crew" / "projects"
        if not state_dir.exists():
            return None
        # Find most recently modified project
        projects = sorted(state_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for proj_path in projects[:3]:
            try:
                data = json.loads(proj_path.read_text())
                phase = data.get("current_phase")
                if phase:
                    return phase
            except Exception:
                continue
    except Exception:
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-aware memory scoring")
    subparsers = parser.add_subparsers(dest="command")

    # boost subcommand
    boost_p = subparsers.add_parser("boost", help="Calculate phase affinity boost")
    boost_p.add_argument("--memory-phase", required=True)
    boost_p.add_argument("--active-phase", required=True)

    # score subcommand
    score_p = subparsers.add_parser("score", help="Score and sort memories by phase affinity")
    score_p.add_argument("--phase", required=True)

    # filter subcommand
    filter_p = subparsers.add_parser("filter", help="Filter memories by exact phase match")
    filter_p.add_argument("--phase", required=True)

    # detect-phase subcommand
    subparsers.add_parser("detect-phase", help="Detect active crew project phase")

    args = parser.parse_args()

    if args.command == "boost":
        boost = get_boost(args.memory_phase, args.active_phase)
        print(json.dumps({"boost": boost}))

    elif args.command == "score":
        memories = json.load(sys.stdin)
        result = score_memories(memories, args.phase)
        print(json.dumps(result))

    elif args.command == "filter":
        memories = json.load(sys.stdin)
        result = filter_memories(memories, args.phase)
        print(json.dumps(result))

    elif args.command == "detect-phase":
        phase = detect_active_phase()
        print(json.dumps({"phase": phase}))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
