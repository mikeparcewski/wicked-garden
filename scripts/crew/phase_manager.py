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


def _bus_emit_safe(event_type: str, payload: dict, *,
                   chain_id: Optional[str] = None) -> None:
    """Fire-and-forget bus emit. Fail-open on every error.

    The phase_manager is the v11 source-of-truth surface for project
    state transitions. Each transition emits an event for downstream
    consumers (audit, dashboards, future replay). Bus unavailable
    must never block the disk write — bus failure is recorded only
    in emit_stats.
    """
    try:
        from _bus import emit_event  # type: ignore
        emit_event(event_type, payload, chain_id=chain_id)
    except Exception:
        pass  # Bus is optional infrastructure.


# Strangler shim toward wicked-loom (cutover phase). Read-only parity mirror:
# the in-process hard-gate enforcement below STAYS authoritative; loom is
# consulted only to cross-check the park-at-hard-gate decision during cutover.
try:
    import _loom  # scripts/ is on sys.path
except ImportError:  # pragma: no cover
    _loom = None  # type: ignore


def _loom_confirms_hard_gate(archetype: str, phase: str) -> "Optional[bool]":
    """Ask loom (via the compiled flow def) whether (archetype, phase) is a
    hard gate. Returns True/False, or None when loom is unavailable/uncertain
    (in which case the in-process _HARD_GATE_PHASES map remains authoritative).
    Best-effort, fail-soft — never raises, never blocks the state write."""
    if _loom is None or not _loom.use_loom():
        return None
    try:
        from flow_compiler import compile_flow
        flow_def = compile_flow(archetype, flow_id=f"{archetype}-parity")
        for p in flow_def.get("phases", []):
            if p.get("name") == phase:
                hitl = p.get("hitl")
                return isinstance(hitl, str) and hitl.startswith("hard:")
        return False
    except Exception:
        return None  # fail-soft: in-process map stays authoritative


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

    # v11.1.1: bus emit for archetype-mode creation. Legacy (no archetype)
    # projects also emit project.created via the v6 path; archetype-mode
    # gets its own event so dashboards can distinguish.
    if archetype_mode:
        _bus_emit_safe(
            "wicked.garden.archetype.created",
            {
                "project_id": name,
                "archetype": archetype_mode,
                "phase_plan": state.phase_plan,
                "produces": list(state.extras.get("archetype_produces") or []),
                "hitl": state.extras.get("archetype_hitl"),
            },
            chain_id=f"{name}.{archetype_mode}.root",
        )
    else:
        _bus_emit_safe(
            "wicked.garden.project.created",
            {"project_id": name},
            chain_id=f"{name}.root",
        )
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


_HARD_GATE_PHASES: Dict[str, Tuple[str, ...]] = {
    # The (archetype, phase) pairs that genuinely need the user in the loop
    # AT RUNTIME — not just in playbook prose. These MUST mirror the archetypes
    # declared ``hard:<gate>`` in .claude-plugin/archetypes.json (the source of
    # truth). migrate/modernize/incident/review are hard; specify
    # (discrete:validate) and decide (discrete:select) are discrete gates that
    # auto-pass when the produces contract re-derives — promoting them here
    # over-reached the catalog and contradicted the "steering, not blocking"
    # doctrine, so they were removed. modernize's cutover is the legacy→new-stack
    # parity-proved switch — the same hard-gate discipline as migrate.cutover.
    # test_hard_gate_map_matches_catalog locks this alignment.
    "migrate": ("cutover",),
    "modernize": ("cutover",),
    "incident": ("mitigate",),
    "review": ("remediate-or-accept",),
}


def _is_hard_gate(state: ProjectState, phase: str) -> bool:
    """True iff (archetype, phase) is a hard gate per _HARD_GATE_PHASES."""
    archetype = (state.extras or {}).get("v11_archetype")
    if not archetype:
        return False
    return resolve_phase(phase) in _HARD_GATE_PHASES.get(archetype, ())


def resolve_hard_gate(state: ProjectState, phase: str) -> bool:
    """Authoritative hard-gate decision for ``(archetype, phase)`` (flow cutover).

    The flow surface is now loom-AUTHORITATIVE for *where the human stops*:
    loom's verdict (derived from the compiled flow-def, which reproduces loom's
    own ``hitl.startswith("hard:")`` park rule) decides whether this phase is a
    hard gate — WHEN loom is available. The in-process ``_HARD_GATE_PHASES`` map
    is two things at once:

      - the FALLBACK: when loom is unavailable/uncertain
        (``_loom_confirms_hard_gate`` returns None — off, auto-unresolvable, or
        a compile error), the map answers (fail-soft, rollback-safe).
      - the FLOOR: even when loom answers, the resolved decision is
        ``loom or in_process`` — loom may ADD a park the map omits, but can
        NEVER remove a park the map asserts. This is the fail-closed posture of
        the flow surface: we never silently skip a human-in-the-loop stop that
        the in-process doctrine demands. A loom that (wrongly) says "not hard"
        for migrate.cutover cannot disarm the cutover gate.

    A divergence (loom != in_process, with loom present) is surfaced as a
    ``wicked.garden.loom.parity_mismatched`` signal — retained from the parity mirror —
    so operators see drift even though the resolved decision is the safe OR.
    """
    in_process = _is_hard_gate(state, phase)
    archetype = (state.extras or {}).get("v11_archetype")
    if not archetype:
        return in_process

    loom_says = _loom_confirms_hard_gate(archetype, phase)
    if loom_says is None:
        return in_process  # fail-soft: in-process map is authoritative

    if loom_says != in_process:
        print(f"[wicked-garden] loom/in-process hard-gate parity mismatch: "
              f"archetype={archetype} phase={phase} "
              f"loom={loom_says} in_process={in_process}", file=sys.stderr)
        _bus_emit_safe(
            "wicked.garden.loom.parity_mismatched",
            {"project_id": state.name, "archetype": archetype,
             "phase": phase, "loom": loom_says, "in_process": in_process,
             "resolved": loom_says or in_process},
            chain_id=f"{state.name}.{archetype}.{phase}.parity",
        )
    # loom authoritative, but fail-closed floor: a park is required if EITHER
    # source says hard. loom can add a park; it can never remove the map's.
    return loom_says or in_process


def approve_phase(
    state: ProjectState,
    phase: str,
    approver: str = "user",
    *,
    confirmed_by: Optional[str] = None,
    confirmation_evidence: Optional[str] = None,
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase. Returns (state, next_phase_name_or_None).

    Hard-gate enforcement (v11): when (archetype, phase) is in
    ``_HARD_GATE_PHASES`` (e.g. migrate.cutover, incident.mitigate),
    advancing past the phase REQUIRES non-empty ``confirmed_by`` AND
    ``confirmation_evidence``. The audit log records both. ``approver``
    alone is not enough — the doctrine of "user in the loop" becomes
    runtime: the caller must explicitly attest that confirmation
    happened, and name the artifact (commit / dashboard URL / ticket /
    Slack thread) that proves it.

    Non-hard phases retain the v11 default: lightweight state transition,
    no gate machinery, archetype's playbook owns discipline.
    """
    phase = resolve_phase(phase)

    # --- loom cutover (flow surface): loom-AUTHORITATIVE park decision -------
    # The hard-gate verdict now routes through resolve_hard_gate: loom wins when
    # present, the in-process _HARD_GATE_PHASES map is the fallback (loom
    # unavailable) AND the floor (loom can ADD a park, never remove one the map
    # asserts). The parity-mismatch signal lives inside resolve_hard_gate.
    # -------------------------------------------------------------------------

    # Hard-gate guard: enforce explicit confirmation at runtime.
    if resolve_hard_gate(state, phase):
        if not confirmed_by or not confirmed_by.strip():
            archetype = (state.extras or {}).get("v11_archetype")
            raise ValueError(
                f"Hard gate at archetype={archetype!r} phase={phase!r} "
                f"requires --confirmed-by (user / oncall / approver name). "
                f"This is a v11 enforced HITL gate, not a doctrinal "
                f"hint — the playbook documents this as hard:* and the "
                f"runtime mirrors that. Pass --confirmed-by AND "
                f"--confirmation-evidence (path / URL / ticket id)."
            )
        if not confirmation_evidence or not confirmation_evidence.strip():
            archetype = (state.extras or {}).get("v11_archetype")
            raise ValueError(
                f"Hard gate at archetype={archetype!r} phase={phase!r} "
                f"requires --confirmation-evidence (path to artifact "
                f"proving the gate-specific check passed: rollback "
                f"drill log, dashboard screenshot, mitigation commit, "
                f"approval ticket, etc.)."
            )

    ps = state.phases.get(phase) or PhaseState()
    ps.status = "approved"
    ps.approved_at = get_utc_timestamp()
    state.phases[phase] = ps

    approval_record = {
        "phase": phase, "approver": approver, "at": ps.approved_at,
    }
    if confirmed_by:
        approval_record["confirmed_by"] = confirmed_by
        approval_record["confirmation_evidence"] = confirmation_evidence
        approval_record["hard_gate"] = True

    state.extras.setdefault("approvals", []).append(approval_record)

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

    # v11.1.1: emit hard_gate_passed when a hard gate advanced
    archetype = (state.extras or {}).get("v11_archetype")
    if archetype and confirmed_by:
        _bus_emit_safe(
            "wicked.garden.archetype.hard_gate_passed",
            {
                "project_id": state.name,
                "archetype": archetype,
                "phase": phase,
                "confirmed_by": confirmed_by,
                "confirmation_evidence": confirmation_evidence,
            },
            chain_id=f"{state.name}.{archetype}.{phase}.hard-gate",
        )

    # v11.1.1: emit advance event for any archetype-mode approval
    if archetype:
        _bus_emit_safe(
            "wicked.garden.archetype.advanced",
            {
                "project_id": state.name,
                "archetype": archetype,
                "phase": phase,
                "next_phase": next_phase,
            },
            chain_id=f"{state.name}.{archetype}.{phase}",
        )

    # v11.1.1: emit completed event when project is_complete after this approval
    if archetype and is_complete(state):
        _bus_emit_safe(
            "wicked.garden.archetype.completed",
            {
                "project_id": state.name,
                "archetype": archetype,
                "final_phase": phase,
            },
            chain_id=f"{state.name}.{archetype}.completed",
        )

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
        "--confirmed-by", default=None,
        help="v11 hard-gate confirmation: name of the user/oncall/approver "
             "who confirmed the gate-specific check (required for "
             "migrate:cutover, modernize:cutover, incident:mitigate, "
             "review:remediate-or-accept).",
    )
    parser.add_argument(
        "--confirmation-evidence", default=None,
        help="v11 hard-gate confirmation evidence: path / URL / ticket id "
             "proving the check passed (e.g. rollback drill log, "
             "dashboard screenshot, mitigation commit).",
    )
    parser.add_argument(
        "--archetype-mode",
        default=None,
        choices=["triage", "explore", "specify", "decide", "ship",
                 "review", "incident", "build", "migrate", "modernize"],
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
        try:
            state, next_phase = approve_phase(
                state, phase, approver=args.approver,
                confirmed_by=args.confirmed_by,
                confirmation_evidence=args.confirmation_evidence,
            )
        except ValueError as exc:
            _emit({"ok": False, "error": str(exc)}, args.json,
                  f"Error: {exc}")
            sys.exit(1)
        _emit(
            {"ok": True, "phase": phase, "status": "approved",
             "next_phase": next_phase, "is_complete": is_complete(state),
             "hard_gate_confirmed": bool(args.confirmed_by)},
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
        try:
            state, next_phase = approve_phase(
                state, phase, approver=args.approver,
                confirmed_by=args.confirmed_by,
                confirmation_evidence=args.confirmation_evidence,
            )
        except ValueError as exc:
            _emit({"ok": False, "error": str(exc)}, args.json,
                  f"Error: {exc}")
            sys.exit(1)
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
