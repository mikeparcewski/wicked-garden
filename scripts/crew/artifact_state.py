#!/usr/bin/env python3
"""
Artifact State Machine — enforced lifecycle transitions for crew deliverables.

Manages artifact lifecycle states (DRAFT → IN_REVIEW → APPROVED → IMPLEMENTED →
VERIFIED → CLOSED) with strict transition validation. Invalid transitions raise
ValueError with a clear message.

Artifacts are stored via DomainStore("wicked-crew") under source "artifacts".

Usage (Python API):
    from artifact_state import register_artifact, transition, get_artifact

    art = register_artifact("architecture.md", "design", "my-project", "design")
    transition(art["id"], "IN_REVIEW", by="design-phase")
    transition(art["id"], "APPROVED", by="gate-check")

Usage (CLI):
    artifact_state.py register --name arch.md --type design --project P --phase design
    artifact_state.py transition --id X --to APPROVED --by gate-check
    artifact_state.py get --id X
    artifact_state.py list --project P [--phase design] [--state APPROVED]
    artifact_state.py check --id X --required-state APPROVED
    artifact_state.py bulk-check --project P --phase design --required-state APPROVED

All CLI commands support --json for machine-readable output.

Stdlib-only. Cross-platform.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import DomainStore from parent scripts/ directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATES = ("DRAFT", "IN_REVIEW", "APPROVED", "IMPLEMENTED", "VERIFIED", "CLOSED")

VALID_TRANSITIONS: Dict[str, set] = {
    "DRAFT":       {"IN_REVIEW"},
    "IN_REVIEW":   {"APPROVED", "DRAFT"},
    "APPROVED":    {"IMPLEMENTED"},
    "IMPLEMENTED": {"VERIFIED", "IN_REVIEW"},
    "VERIFIED":    {"CLOSED"},
    "CLOSED":      set(),
}

ARTIFACT_TYPES = (
    "requirements", "design", "test-strategy", "evidence",
    "implementation", "report", "other",
)

SOURCE = "artifacts"

# ---------------------------------------------------------------------------
# Store singleton (lazy init to avoid side effects at import time in tests)
# ---------------------------------------------------------------------------

_store: Optional[DomainStore] = None


def _get_store() -> DomainStore:
    """Return the shared DomainStore instance, creating it on first call."""
    global _store
    if _store is None:
        _store = DomainStore("wicked-crew")
    return _store


def _now() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_state(state: str) -> str:
    """Normalize and validate a state string. Returns the canonical uppercase form."""
    canonical = state.upper().replace("-", "_")
    if canonical not in STATES:
        raise ValueError(
            "Invalid state '{}'. Valid states: {}".format(state, ", ".join(STATES))
        )
    return canonical


def _validate_transition(from_state: str, to_state: str) -> None:
    """Raise ValueError if the transition is not allowed."""
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        allowed_list = ", ".join(sorted(allowed)) if allowed else "(none — terminal state)"
        raise ValueError(
            "Invalid transition: {} -> {}. Allowed transitions from {}: {}".format(
                from_state, to_state, from_state, allowed_list
            )
        )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def register_artifact(
    name: str,
    artifact_type: str,
    project_id: str,
    phase: str,
) -> dict:
    """Register a new artifact in DRAFT state.

    Args:
        name:          Artifact filename or label (e.g. "architecture.md").
        artifact_type: One of ARTIFACT_TYPES (validated loosely — unknown types
                       are accepted with a warning to stderr).
        project_id:    Crew project identifier.
        phase:         Phase that produced this artifact (e.g. "design", "build").

    Returns:
        The created artifact record dict (includes generated "id").
    """
    if artifact_type not in ARTIFACT_TYPES:
        print(
            "[artifact-state] Warning: unknown artifact_type '{}'. "
            "Known types: {}".format(artifact_type, ", ".join(ARTIFACT_TYPES)),
            file=sys.stderr,
        )

    now = _now()
    record = {
        "name": name,
        "artifact_type": artifact_type,
        "project_id": project_id,
        "phase": phase,
        "state": "DRAFT",
        "state_history": [],
        "created_at": now,
        "updated_at": now,
    }
    created = _get_store().create(SOURCE, record)
    return created if created is not None else record


def transition(artifact_id: str, to_state: str, *, by: str) -> dict:
    """Transition an artifact to a new state.

    Args:
        artifact_id: UUID of the artifact.
        to_state:    Target state (case-insensitive, hyphens accepted).
        by:          Actor or phase that triggered the transition.

    Returns:
        Updated artifact record dict.

    Raises:
        ValueError: If the transition is invalid or the artifact is not found.
    """
    to_state = _validate_state(to_state)
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError("Artifact not found: {}".format(artifact_id))

    from_state = artifact["state"]
    _validate_transition(from_state, to_state)

    now = _now()
    history_entry = {
        "from": from_state,
        "to": to_state,
        "at": now,
        "by": by,
    }

    # Append to state_history (append-only)
    state_history = list(artifact.get("state_history", []))
    state_history.append(history_entry)

    diff = {
        "state": to_state,
        "state_history": state_history,
        "updated_at": now,
    }

    updated = _get_store().update(SOURCE, artifact_id, diff)
    if updated is None:
        raise ValueError("Failed to update artifact: {}".format(artifact_id))
    return updated


def get_artifact(artifact_id: str) -> Optional[dict]:
    """Retrieve a single artifact by ID.

    Returns:
        Artifact record dict, or None if not found.
    """
    return _get_store().get(SOURCE, artifact_id)


def get_artifacts(
    *,
    project_id: Optional[str] = None,
    phase: Optional[str] = None,
    state: Optional[str] = None,
    artifact_type: Optional[str] = None,
) -> List[dict]:
    """List artifacts with optional filters.

    All filter parameters are optional. When omitted, no filtering is applied
    for that field. Filters are combined with AND logic.

    Returns:
        List of matching artifact record dicts.
    """
    params: Dict[str, Any] = {}
    if project_id is not None:
        params["project_id"] = project_id
    if phase is not None:
        params["phase"] = phase
    if state is not None:
        params["state"] = _validate_state(state)
    if artifact_type is not None:
        params["artifact_type"] = artifact_type

    return _get_store().list(SOURCE, **params)


def check_state(artifact_id: str, required_state: str) -> bool:
    """Check whether an artifact is in the required state.

    Args:
        artifact_id:    UUID of the artifact.
        required_state: Expected state (case-insensitive).

    Returns:
        True if the artifact exists and is in the required state, False otherwise.
    """
    required_state = _validate_state(required_state)
    artifact = get_artifact(artifact_id)
    if artifact is None:
        return False
    return artifact.get("state") == required_state


def bulk_check(project_id: str, phase: str, required_state: str) -> dict:
    """Check all artifacts for a project+phase meet the required state.

    Args:
        project_id:     Crew project identifier.
        phase:          Phase to check (e.g. "design").
        required_state: Expected state for all artifacts.

    Returns:
        Dict with keys:
            "pass":     bool — True if ALL artifacts meet the required state.
            "total":    int  — total artifacts found for project+phase.
            "passing":  int  — count meeting the required state.
            "failing":  list — artifact IDs that do NOT meet the required state.
    """
    required_state = _validate_state(required_state)
    artifacts = get_artifacts(project_id=project_id, phase=phase)

    passing = 0
    failing: List[str] = []

    for art in artifacts:
        if art.get("state") == required_state:
            passing += 1
        else:
            failing.append(art.get("id", "unknown"))

    return {
        "pass": len(failing) == 0 and len(artifacts) > 0,
        "total": len(artifacts),
        "passing": passing,
        "failing": failing,
    }


# ---------------------------------------------------------------------------
# Gate integration helpers
# ---------------------------------------------------------------------------


def on_gate_reject(artifact_id: str, *, by: str) -> dict:
    """Handle gate REJECT — transition artifact back to DRAFT.

    The artifact must be in IN_REVIEW state. If it is not, this raises
    ValueError (the caller should only invoke this during gate evaluation).

    Returns:
        Updated artifact record.
    """
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError("Artifact not found: {}".format(artifact_id))

    current = artifact.get("state")
    if current != "IN_REVIEW":
        raise ValueError(
            "on_gate_reject requires artifact in IN_REVIEW state, "
            "but artifact '{}' is in {} state".format(artifact_id, current)
        )
    return transition(artifact_id, "DRAFT", by=by)


def on_gate_conditional(artifact_id: str, *, by: str) -> dict:
    """Handle gate CONDITIONAL — keep IN_REVIEW, log event to history.

    No state transition occurs. A log entry is appended to state_history
    to record the conditional gate result.

    Returns:
        Updated artifact record.
    """
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError("Artifact not found: {}".format(artifact_id))

    now = _now()
    state_history = list(artifact.get("state_history", []))
    state_history.append({
        "from": artifact["state"],
        "to": artifact["state"],
        "at": now,
        "by": by,
        "note": "gate-conditional: no state change, conditions pending",
    })

    diff = {
        "state_history": state_history,
        "updated_at": now,
    }
    updated = _get_store().update(SOURCE, artifact_id, diff)
    if updated is None:
        raise ValueError("Failed to update artifact: {}".format(artifact_id))
    return updated


def on_gate_approve(artifact_id: str, *, by: str) -> dict:
    """Handle gate APPROVE — transition artifact to APPROVED.

    The artifact must be in IN_REVIEW state.

    Returns:
        Updated artifact record.
    """
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError("Artifact not found: {}".format(artifact_id))

    current = artifact.get("state")
    if current != "IN_REVIEW":
        raise ValueError(
            "on_gate_approve requires artifact in IN_REVIEW state, "
            "but artifact '{}' is in {} state".format(artifact_id, current)
        )
    return transition(artifact_id, "APPROVED", by=by)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for CLI usage."""
    parser = argparse.ArgumentParser(
        prog="artifact_state.py",
        description="Artifact lifecycle state machine for wicked-crew deliverables.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output results as JSON (default: human-readable)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # register
    reg = sub.add_parser("register", help="Register a new artifact in DRAFT state")
    reg.add_argument("--name", required=True, help="Artifact name or filename")
    reg.add_argument("--type", required=True, dest="artifact_type", help="Artifact type")
    reg.add_argument("--project", required=True, dest="project_id", help="Project ID")
    reg.add_argument("--phase", required=True, help="Phase that produced this artifact")

    # transition
    trans = sub.add_parser("transition", help="Transition an artifact to a new state")
    trans.add_argument("--id", required=True, dest="artifact_id", help="Artifact ID")
    trans.add_argument("--to", required=True, dest="to_state", help="Target state")
    trans.add_argument("--by", required=True, help="Actor or phase triggering the transition")

    # get
    get_cmd = sub.add_parser("get", help="Get a single artifact by ID")
    get_cmd.add_argument("--id", required=True, dest="artifact_id", help="Artifact ID")

    # list
    ls = sub.add_parser("list", help="List artifacts with optional filters")
    ls.add_argument("--project", dest="project_id", help="Filter by project ID")
    ls.add_argument("--phase", help="Filter by phase")
    ls.add_argument("--state", help="Filter by state")
    ls.add_argument("--type", dest="artifact_type", help="Filter by artifact type")

    # check
    chk = sub.add_parser("check", help="Check if an artifact is in the required state")
    chk.add_argument("--id", required=True, dest="artifact_id", help="Artifact ID")
    chk.add_argument("--required-state", required=True, help="Required state")

    # bulk-check
    bulk = sub.add_parser("bulk-check", help="Check all artifacts for a phase meet required state")
    bulk.add_argument("--project", required=True, dest="project_id", help="Project ID")
    bulk.add_argument("--phase", required=True, help="Phase to check")
    bulk.add_argument("--required-state", required=True, help="Required state")

    return parser


def _output(data: Any, *, json_mode: bool) -> None:
    """Print output in JSON or human-readable format."""
    if json_mode:
        sys.stdout.write(json.dumps(data, indent=2))
        sys.stdout.write("\n")
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 3:
                sys.stdout.write("{}: ({} items)\n".format(key, len(value)))
            else:
                sys.stdout.write("{}: {}\n".format(key, value))
    elif isinstance(data, list):
        if not data:
            sys.stdout.write("(no results)\n")
        for item in data:
            if isinstance(item, dict):
                summary = "  {} [{}] {} ({})".format(
                    item.get("id", "?")[:12],
                    item.get("state", "?"),
                    item.get("name", "?"),
                    item.get("artifact_type", "?"),
                )
                sys.stdout.write(summary + "\n")
            else:
                sys.stdout.write(str(item) + "\n")
    elif isinstance(data, bool):
        sys.stdout.write("PASS\n" if data else "FAIL\n")
    else:
        sys.stdout.write(str(data) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns exit code (0 = success, 1 = error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    json_mode = args.json_output

    try:
        if args.command == "register":
            result = register_artifact(
                name=args.name,
                artifact_type=args.artifact_type,
                project_id=args.project_id,
                phase=args.phase,
            )
            _output(result, json_mode=json_mode)

        elif args.command == "transition":
            result = transition(
                args.artifact_id,
                args.to_state,
                by=args.by,
            )
            _output(result, json_mode=json_mode)

        elif args.command == "get":
            result = get_artifact(args.artifact_id)
            if result is None:
                print("Artifact not found: {}".format(args.artifact_id), file=sys.stderr)
                return 1
            _output(result, json_mode=json_mode)

        elif args.command == "list":
            results = get_artifacts(
                project_id=args.project_id,
                phase=args.phase,
                state=args.state,
                artifact_type=args.artifact_type,
            )
            _output(results, json_mode=json_mode)

        elif args.command == "check":
            result = check_state(args.artifact_id, args.required_state)
            _output(result, json_mode=json_mode)
            return 0 if result else 1

        elif args.command == "bulk-check":
            result = bulk_check(
                args.project_id,
                args.phase,
                args.required_state,
            )
            _output(result, json_mode=json_mode)
            return 0 if result["pass"] else 1

        else:
            parser.print_help()
            return 1

    except ValueError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        if json_mode:
            sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
