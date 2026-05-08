#!/usr/bin/env python3
"""phase_manager.py — v11 slim project-state manager.

The v6-v10 universal-pipeline implementation (gate-result.json schema
validators, addendum freshness, conditions-manifest enforcement, BLEND-
RULE dispatch, banned-reviewer enforcement, dispatch-log HMAC,
convergence-verify, semantic-alignment, propose-process facilitator
rubric, rigor tiers, gate-policy.json) lived in this module across many
thousands of lines. v11 collapsed all of that into per-archetype playbooks
under skills/archetype/refs/{archetype}.md, with the catalog at
.claude-plugin/archetypes.json driving phase shape, produces, HITL
discipline, and cost band per archetype.

What's left here:
- ProjectState dataclass: name, current_phase, phase_plan, phases dict,
  extras, created_at.
- create_project / load_project_state / save_project_state.
- start_phase / complete_phase / approve_phase / skip_phase — slim state
  transitions, no gate machinery.
- CLI: status, create, start, complete, approve, skip, advance.

Archetype mode is the v11 default for new projects; legacy projects
(no phase_plan_mode) still load and read but don't get the legacy gate
checks back — they were the bug, not the value.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Make scripts/ importable for _domain_store
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore, get_local_path  # noqa: E402

_sm = DomainStore("projects")
logger = __import__("logging").getLogger("wicked-garden.phase-manager")


# ---------------------------------------------------------------------------
# Naming & resolution
# ---------------------------------------------------------------------------

_PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_safe_project_name(name: str) -> bool:
    """Names are kebab/snake/alphanumeric, max 64 chars."""
    return bool(_PROJECT_NAME_RE.match(name or ""))


# Phase aliases used historically — keep the resolver so old project files
# still load correctly.
_PHASE_ALIASES: Dict[str, str] = {
    "implement": "implement",
    "implementation": "implement",
    "plan": "plan",
    "test": "test",
    "review": "review",
    "build": "build",
    "clarify": "clarify",
    "design": "design",
    "operate": "operate",
}


def resolve_phase(phase: str) -> str:
    """Normalize a phase name. Returns the input unchanged when no alias matches."""
    if not phase:
        return phase
    return _PHASE_ALIASES.get(phase.lower(), phase)


def get_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Project state
# ---------------------------------------------------------------------------

@dataclass
class PhaseState:
    """Per-phase status. Status is one of: pending | in_progress | completed | approved | skipped."""
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None


@dataclass
class ProjectState:
    name: str
    current_phase: str
    created_at: str
    version: str = "v11"
    phase_plan: List[str] = field(default_factory=list)
    phases: Dict[str, PhaseState] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


def get_project_dir(project_name: str) -> Path:
    """Resolve and create the on-disk project directory."""
    if not is_safe_project_name(project_name):
        raise ValueError(f"Invalid project name: {project_name!r}")
    base = get_local_path("wicked-crew", "projects")
    project_dir = (base / project_name).resolve()
    try:
        project_dir.relative_to(base.resolve())
    except ValueError:
        raise ValueError("Path traversal detected")
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def save_project_state(state: ProjectState) -> None:
    """Persist state to the DomainStore.

    Uses ``id = state.name`` as the canonical key. Update is idempotent
    via ``DomainStore.update`` when the record exists; otherwise we
    create.
    """
    payload = {
        "id": state.name,
        "name": state.name,
        "current_phase": state.current_phase,
        "created_at": state.created_at,
        "version": state.version,
        "phase_plan": list(state.phase_plan),
        "phases": {k: asdict(v) for k, v in state.phases.items()},
        "extras": dict(state.extras),
    }
    existing = _sm.get("projects", state.name)
    if existing:
        _sm.update("projects", state.name, payload)
    else:
        _sm.create("projects", payload)


def load_project_state(project_name: str) -> Optional[ProjectState]:
    """Load state from DomainStore, hydrating phases dict from raw."""
    if not is_safe_project_name(project_name):
        return None
    data = _sm.get("projects", project_name)
    if not data:
        return None
    phases: Dict[str, PhaseState] = {}
    for k, v in (data.get("phases") or {}).items():
        if isinstance(v, dict):
            phases[resolve_phase(k)] = PhaseState(
                status=v.get("status", "pending"),
                started_at=v.get("started_at"),
                completed_at=v.get("completed_at"),
                approved_at=v.get("approved_at"),
            )
    return ProjectState(
        name=data.get("name", project_name),
        current_phase=resolve_phase(data.get("current_phase", "")),
        created_at=data.get("created_at", get_utc_timestamp()),
        version=data.get("version", "v11"),
        phase_plan=[resolve_phase(p) for p in (data.get("phase_plan") or [])],
        phases=phases,
        extras=dict(data.get("extras") or {}),
    )


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------

def create_project(
    name: str,
    description: str = "",
    archetype_mode: Optional[str] = None,
) -> Tuple[ProjectState, Path]:
    """Create a new project. When ``archetype_mode`` is set, hydrate the
    phase_plan from .claude-plugin/archetypes.json and stamp the project
    as v11 archetype-driven."""
    if not is_safe_project_name(name):
        raise ValueError(f"Invalid project name: {name!r}")

    state = ProjectState(
        name=name,
        current_phase="",
        created_at=get_utc_timestamp(),
        version="v11",
    )
    if description:
        state.extras["description"] = description

    if archetype_mode:
        try:
            from archetypes_v11 import load_catalog
            catalog = load_catalog()
            arch_def = catalog.get("archetypes", {}).get(archetype_mode)
            if not arch_def:
                raise ValueError(
                    f"Unknown archetype '{archetype_mode}'. "
                    f"Known: {list(catalog.get('archetypes', {}).keys())}"
                )
            state.phase_plan = list(arch_def.get("phases", []))
            state.current_phase = state.phase_plan[0] if state.phase_plan else ""
            state.extras["phase_plan_mode"] = "archetype"
            state.extras["v11_archetype"] = archetype_mode
            state.extras["archetype_produces"] = list(arch_def.get("produces", []))
            state.extras["archetype_hitl"] = arch_def.get("hitl")
        except ImportError:
            raise RuntimeError("archetypes_v11 unavailable — cannot init archetype-mode project")

    project_dir = get_project_dir(name)
    save_project_state(state)
    return state, project_dir


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

def start_phase(state: ProjectState, phase: str) -> ProjectState:
    """Mark a phase as in_progress."""
    phase = resolve_phase(phase)
    ps = state.phases.get(phase) or PhaseState()
    ps.status = "in_progress"
    ps.started_at = ps.started_at or get_utc_timestamp()
    state.phases[phase] = ps
    state.current_phase = phase
    save_project_state(state)
    return state


def complete_phase(state: ProjectState, phase: str) -> ProjectState:
    """Mark a phase as completed (work done; awaiting approval)."""
    phase = resolve_phase(phase)
    ps = state.phases.get(phase) or PhaseState(started_at=get_utc_timestamp())
    ps.status = "completed"
    ps.completed_at = get_utc_timestamp()
    state.phases[phase] = ps
    save_project_state(state)
    return state


def approve_phase(
    state: ProjectState, phase: str, approver: str = "user"
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase. Returns (state, next_phase_name_or_None).

    v11: no gate machinery. The archetype's playbook is responsible for
    enforcing produces and HITL discipline; phase_manager just records
    the state transition. Legacy projects with phase_plan_mode != "archetype"
    behave the same way — the v6 gate gauntlet is gone for everyone.
    """
    phase = resolve_phase(phase)
    ps = state.phases.get(phase) or PhaseState()
    ps.status = "approved"
    ps.approved_at = get_utc_timestamp()
    state.phases[phase] = ps
    state.extras.setdefault("approvals", []).append({
        "phase": phase, "approver": approver, "at": ps.approved_at,
    })

    # Resolve next phase from phase_plan
    next_phase: Optional[str] = None
    if state.phase_plan:
        try:
            idx = state.phase_plan.index(phase)
            if idx + 1 < len(state.phase_plan):
                next_phase = state.phase_plan[idx + 1]
        except ValueError:
            pass

    if next_phase:
        state.current_phase = next_phase
    save_project_state(state)
    return state, next_phase


def skip_phase(state: ProjectState, phase: str, reason: str = "") -> ProjectState:
    phase = resolve_phase(phase)
    ps = state.phases.get(phase) or PhaseState()
    ps.status = "skipped"
    ps.completed_at = get_utc_timestamp()
    state.phases[phase] = ps
    state.extras.setdefault("skips", []).append({
        "phase": phase, "reason": reason, "at": ps.completed_at,
    })
    save_project_state(state)
    return state


def is_complete(state: ProjectState) -> bool:
    """All phases in the plan are approved or skipped."""
    if not state.phase_plan:
        return False
    for p in state.phase_plan:
        ps = state.phases.get(p)
        if not ps or ps.status not in ("approved", "skipped"):
            return False
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _emit(payload: Dict[str, Any], as_json: bool, fallback: str = "") -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    elif fallback:
        print(fallback)


def main() -> None:
    parser = argparse.ArgumentParser(description="v11 slim project state manager")
    parser.add_argument("project")
    parser.add_argument(
        "action",
        choices=["status", "create", "start", "complete", "approve", "skip",
                 "advance", "delete"],
    )
    parser.add_argument("--phase", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--approver", default="user")
    parser.add_argument(
        "--archetype-mode",
        default=None,
        choices=["triage", "explore", "specify", "decide", "ship",
                 "review", "incident", "build", "migrate"],
        help="Hydrate phase_plan from .claude-plugin/archetypes.json on create.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.action == "create":
        try:
            state, _project_dir = create_project(
                args.project,
                description=args.description,
                archetype_mode=args.archetype_mode,
            )
        except (ValueError, RuntimeError) as exc:
            _emit({"ok": False, "error": str(exc)}, args.json,
                  f"Error: {exc}")
            sys.exit(1)
        _emit(
            {"ok": True, "name": state.name, "phase_plan": state.phase_plan,
             "current_phase": state.current_phase,
             "v11_archetype": state.extras.get("v11_archetype")},
            args.json,
            f"Created project '{state.name}' "
            f"(phases: {' -> '.join(state.phase_plan) or 'none'})",
        )
        return

    state = load_project_state(args.project)
    if state is None:
        _emit({"ok": False, "error": f"Project not found: {args.project}"},
              args.json, f"Error: project not found: {args.project}")
        sys.exit(1)

    phase = args.phase or state.current_phase

    if args.action == "status":
        complete = is_complete(state)
        _emit(
            {
                "name": state.name,
                "current_phase": state.current_phase,
                "phase_plan": state.phase_plan,
                "phases": {k: asdict(v) for k, v in state.phases.items()},
                "extras": state.extras,
                "is_complete": complete,
                "v11_archetype": state.extras.get("v11_archetype"),
            },
            args.json,
            f"Project: {state.name}\n"
            f"Phase: {state.current_phase}\n"
            f"Plan: {' -> '.join(state.phase_plan) or 'none'}\n"
            f"Complete: {complete}",
        )
        return

    if args.action == "start":
        state = start_phase(state, phase)
        _emit({"ok": True, "phase": phase, "status": "in_progress"},
              args.json, f"Started phase '{phase}'.")
        return

    if args.action == "complete":
        state = complete_phase(state, phase)
        _emit({"ok": True, "phase": phase, "status": "completed"},
              args.json, f"Completed phase '{phase}'.")
        return

    if args.action == "approve":
        state, next_phase = approve_phase(state, phase, approver=args.approver)
        _emit(
            {"ok": True, "phase": phase, "status": "approved",
             "next_phase": next_phase, "is_complete": is_complete(state)},
            args.json,
            f"Approved phase '{phase}'. "
            f"{'Next: ' + next_phase if next_phase else 'Project complete.'}",
        )
        return

    if args.action == "skip":
        state = skip_phase(state, phase, reason=args.reason)
        _emit({"ok": True, "phase": phase, "status": "skipped",
               "reason": args.reason},
              args.json, f"Skipped phase '{phase}'.")
        return

    if args.action == "advance":
        state, next_phase = approve_phase(state, phase, approver=args.approver)
        if next_phase:
            state = start_phase(state, next_phase)
        _emit(
            {"ok": True, "approved": phase, "started": next_phase,
             "is_complete": is_complete(state)},
            args.json,
            f"Approved '{phase}', started '{next_phase}'." if next_phase
            else f"Approved '{phase}'. Project complete.",
        )
        return

    if args.action == "delete":
        _sm.delete("projects", args.project)
        _emit({"ok": True, "deleted": args.project},
              args.json, f"Deleted project '{args.project}'.")
        return


if __name__ == "__main__":
    main()
