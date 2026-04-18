"""Event metadata contract for native TaskCreate/TaskUpdate.

Defines the shape of the `metadata` dict that wicked-garden attaches to
Claude Code native tasks. Replaces the `wicked-kanban` sidecar's
event-envelope fields with validated metadata on native task JSON.

Stdlib-only so the PreToolUse hook can import it.

Field semantics mirror the previous kanban envelope:
  chain_id     — dotted causality: ``{proj}.root``, ``{proj}.{phase}``,
                 ``{proj}.{phase}.{gate}``
  event_type   — task | coding-task | gate-finding | phase-transition |
                 procedure-trigger | subtask
  source_agent — the agent that authored the event
  phase        — crew phase name (must appear in phases.json catalog)
"""

from __future__ import annotations

import re

CHAIN_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}"             # project slug
    r"(\.(root|[a-z0-9][a-z0-9_-]{0,63}))"   # .root or .{phase}
    r"(\.[a-z0-9][a-z0-9_-]{0,63})?$"        # optional .{gate} (uuid8 hex allowed)
)

VALID_EVENT_TYPES = frozenset({
    "task",
    "coding-task",
    "gate-finding",
    "phase-transition",
    "procedure-trigger",
    "subtask",
})

VALID_VERDICTS = frozenset({"APPROVE", "CONDITIONAL", "REJECT"})

# Banned source_agent values for gate findings and other write paths.
# Prefix matches handled separately (see BANNED_SOURCE_AGENT_PREFIXES).
BANNED_REVIEWERS = frozenset({"just-finish-auto", "fast-pass"})
BANNED_SOURCE_AGENT_PREFIXES = ("auto-approve-",)

# Per-event_type required and optional metadata fields.
SCHEMA: dict[str, dict[str, list[str]]] = {
    "task": {
        "required": ["chain_id", "event_type", "source_agent"],
        "optional": ["phase", "priority", "initiative"],
    },
    "coding-task": {
        "required": ["chain_id", "event_type", "source_agent", "phase"],
        "optional": ["priority", "requirement_id", "blast_radius"],
    },
    "gate-finding": {
        "required": [
            "chain_id", "event_type", "source_agent",
            "phase", "verdict", "min_score", "score",
        ],
        "optional": ["conditions_manifest_path", "findings"],
    },
    "phase-transition": {
        "required": [
            "chain_id", "event_type", "source_agent",
            "phase", "from_phase", "to_phase",
        ],
        "optional": ["evidence_path"],
    },
    "procedure-trigger": {
        "required": ["chain_id", "event_type", "source_agent", "procedure"],
        "optional": ["phase", "args"],
    },
    "subtask": {
        "required": [
            "chain_id", "event_type", "source_agent", "parent_chain_id",
        ],
        "optional": ["phase"],
    },
}


def _is_banned_source_agent(source_agent: str) -> bool:
    if source_agent in BANNED_REVIEWERS:
        return True
    return any(source_agent.startswith(p) for p in BANNED_SOURCE_AGENT_PREFIXES)


def validate_metadata(
    metadata: dict,
    valid_phases: set[str] | None = None,
) -> str | None:
    """Validate a TaskCreate/TaskUpdate metadata dict.

    Returns an error string on failure, or None if the metadata is valid
    (or if event_type is absent, which signals an un-enriched task — the
    caller decides whether that's a warning or a hard block).

    ``valid_phases`` — optional set of phase names from phases.json. When
    supplied, ``phase`` must be a member. When omitted, phase is only
    validated for presence per the event_type's required list.
    """
    if not isinstance(metadata, dict):
        return "metadata must be a dict"

    event_type = metadata.get("event_type")
    if not event_type:
        return None  # un-enriched task; caller handles

    if event_type not in VALID_EVENT_TYPES:
        return (
            f"event_type={event_type!r} invalid. "
            f"Allowed: {sorted(VALID_EVENT_TYPES)}"
        )

    spec = SCHEMA[event_type]
    # Presence check, not truthiness — score=0 and phase="" are legitimate
    # "missing" only when the key is absent or explicitly None.
    missing = [f for f in spec["required"] if metadata.get(f) is None]
    if missing:
        return f"{event_type}: missing required metadata fields {missing}"

    chain_id = metadata.get("chain_id", "")
    if not CHAIN_ID_RE.match(chain_id):
        return (
            f"chain_id {chain_id!r} must match "
            "^{project}.(root|{phase})(.{gate})?$ "
            "(lowercase, kebab-case segments)"
        )

    source_agent = metadata.get("source_agent", "")
    if _is_banned_source_agent(source_agent):
        return (
            f"source_agent {source_agent!r} is a banned reviewer "
            f"(banned: {sorted(BANNED_REVIEWERS)}, "
            f"banned prefixes: {list(BANNED_SOURCE_AGENT_PREFIXES)})"
        )

    phase = metadata.get("phase")
    if valid_phases and phase and phase not in valid_phases:
        sample = sorted(valid_phases)[:6]
        return f"phase {phase!r} not in phases.json catalog (sample: {sample})"

    if event_type == "gate-finding":
        verdict = metadata.get("verdict")
        if verdict not in VALID_VERDICTS:
            return (
                f"gate-finding.verdict={verdict!r} invalid. "
                f"Allowed: {sorted(VALID_VERDICTS)}"
            )
        if verdict == "CONDITIONAL" and not metadata.get("conditions_manifest_path"):
            return "CONDITIONAL verdict requires metadata.conditions_manifest_path"
        if verdict == "APPROVE":
            try:
                if float(metadata["score"]) < float(metadata["min_score"]):
                    return (
                        f"APPROVE verdict requires score >= min_score "
                        f"({metadata['score']} < {metadata['min_score']})"
                    )
            except (TypeError, ValueError):
                return "gate-finding.score and min_score must be numeric"

    if event_type == "subtask":
        parent = metadata.get("parent_chain_id", "")
        if not chain_id.startswith(parent + ".") and chain_id != parent:
            return (
                f"subtask.chain_id {chain_id!r} must extend "
                f"parent_chain_id {parent!r}"
            )

    return None


__all__ = [
    "CHAIN_ID_RE",
    "VALID_EVENT_TYPES",
    "VALID_VERDICTS",
    "BANNED_REVIEWERS",
    "BANNED_SOURCE_AGENT_PREFIXES",
    "SCHEMA",
    "validate_metadata",
]
