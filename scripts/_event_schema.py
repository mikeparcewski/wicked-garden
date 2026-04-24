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
  archetype    — optional (v1.1.0, AC-5): one of 7 project archetype values
                 emitted by the facilitator at clarify time and carried
                 in TaskCreate metadata for audit trail. Invalid value
                 triggers warn mode warning or strict mode denial.
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

# v1.1.0: Archetype enum for TaskCreate metadata (AC-5, D5).
# Emitted by the facilitator at clarify time and carried through the audit log.
# Invalid value → warn mode warning or strict mode denial (via validate_metadata).
VALID_ARCHETYPES = frozenset({
    "code-repo",
    "docs-only",
    "skill-agent-authoring",
    "config-infra",
    "multi-repo",
    "testing-only",
    "schema-migration",
})

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
        # Lifecycle: the facilitator emits the gate shell at plan time;
        # the reviewer fills verdict/min_score/score at approve time
        # (see skills/propose-process/refs/output-schema.md). So those
        # three fields are required only when the task reaches a
        # terminal ``completed`` state, not at creation.
        "required": [
            "chain_id", "event_type", "source_agent", "phase",
        ],
        "required_at_completion": ["verdict", "min_score", "score"],
        "optional": [
            "verdict", "min_score", "score",
            "conditions_manifest_path", "findings",
        ],
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
    status: str | None = None,
) -> str | None:
    """Validate a TaskCreate/TaskUpdate metadata dict.

    Returns an error string on failure, or None if the metadata is valid
    (or if event_type is absent, which signals an un-enriched task — the
    caller decides whether that's a warning or a hard block).

    ``valid_phases`` — optional set of phase names from phases.json. When
    supplied, ``phase`` must be a member. When omitted, phase is only
    validated for presence per the event_type's required list.

    ``status`` — optional task status (``pending`` | ``in_progress`` |
    ``completed``). When ``"completed"``, event types with a
    ``required_at_completion`` list enforce those fields too. This
    matches the facilitator-emits-shell / reviewer-fills-verdict
    lifecycle for gate-finding tasks (Issue #570).
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
    required_fields = list(spec["required"])
    if status == "completed":
        required_fields.extend(spec.get("required_at_completion", []))
    missing = [f for f in required_fields if metadata.get(f) is None]
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
        # verdict/min_score/score are filled in by the reviewer at approve
        # time, not by the facilitator at plan time (Issue #570). Only
        # apply the enum + ordering checks when the field is present, so a
        # plan-time shell (verdict absent) validates cleanly. Completion
        # enforcement is handled by the ``required_at_completion`` branch
        # above when ``status="completed"``.
        verdict = metadata.get("verdict")
        if verdict is not None:
            if verdict not in VALID_VERDICTS:
                return (
                    f"gate-finding.verdict={verdict!r} invalid. "
                    f"Allowed: {sorted(VALID_VERDICTS)}"
                )
            if verdict == "CONDITIONAL" and not metadata.get("conditions_manifest_path"):
                return "CONDITIONAL verdict requires metadata.conditions_manifest_path"
            if verdict == "APPROVE":
                score = metadata.get("score")
                min_score = metadata.get("min_score")
                if score is not None and min_score is not None:
                    try:
                        if float(score) < float(min_score):
                            return (
                                f"APPROVE verdict requires score >= min_score "
                                f"({score} < {min_score})"
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

    # v1.1.0: optional archetype field validation (AC-5, D5).
    # Present + valid → accept without warning.
    # Present + invalid → warn/strict response handled by caller.
    archetype = metadata.get("archetype")
    if archetype is not None and archetype not in VALID_ARCHETYPES:
        return (
            f"metadata.archetype={archetype!r} is not a valid archetype value. "
            f"Allowed: {sorted(VALID_ARCHETYPES)}"
        )

    return None


__all__ = [
    "CHAIN_ID_RE",
    "VALID_EVENT_TYPES",
    "VALID_VERDICTS",
    "VALID_ARCHETYPES",
    "BANNED_REVIEWERS",
    "BANNED_SOURCE_AGENT_PREFIXES",
    "SCHEMA",
    "validate_metadata",
]
