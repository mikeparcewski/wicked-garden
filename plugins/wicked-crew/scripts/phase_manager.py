#!/usr/bin/env python3
"""
Phase Manager - State machine for wicked-crew phase transitions.

Handles:
1. Phase state tracking (dynamic phases from phases.json)
2. Gate enforcement
3. Transition validation
4. Project state persistence
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wicked-crew.phase-manager')

# Legacy phase aliases for backward compatibility
LEGACY_ALIASES = {"qe": "test-strategy"}


def resolve_phase(name: str) -> str:
    """Resolve legacy phase aliases."""
    return LEGACY_ALIASES.get(name, name)


def load_phases_config() -> dict:
    """Load phase definitions from phases.json."""
    config_path = Path(__file__).parent.parent / "phases.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f).get("phases", {})
    # Minimal fallback if phases.json missing
    return {
        "clarify": {"is_skippable": False, "depends_on": [], "required_deliverables": ["outcome.md"]},
        "build": {"is_skippable": False, "depends_on": ["clarify"], "required_deliverables": []},
        "review": {"is_skippable": False, "depends_on": ["build"], "required_deliverables": ["review-findings.md"]},
    }


def _topological_sort(phases_config: dict) -> List[str]:
    """Sort phases by depends_on relationships. Detects cycles."""
    order = []
    visited = set()
    in_stack = set()

    def visit(name):
        if name in in_stack:
            raise ValueError(f"Circular dependency detected involving phase: {name}")
        if name in visited:
            return
        visited.add(name)
        in_stack.add(name)
        phase = phases_config.get(name, {})
        for dep in phase.get("depends_on", []):
            resolved = resolve_phase(dep)
            if resolved in phases_config:
                visit(resolved)
        in_stack.discard(name)
        order.append(name)

    for name in phases_config:
        visit(name)
    return order


def get_phase_order(state: 'ProjectState') -> List[str]:
    """Get phase execution order from project plan or phases.json."""
    if state.phase_plan:
        return [resolve_phase(p) for p in state.phase_plan]
    return _topological_sort(load_phases_config())


class PhaseStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    APPROVED = "approved"
    SKIPPED = "skipped"


@dataclass
class PhaseState:
    """State of a single phase."""
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    specialists_engaged: List[str] = field(default_factory=list)
    deliverables_complete: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ProjectState:
    """Full project state."""
    name: str
    current_phase: str
    created_at: str
    version: str = "v3-capability-based"
    signals_detected: List[str] = field(default_factory=list)
    complexity_score: int = 0
    specialists_recommended: List[str] = field(default_factory=list)
    phase_plan: List[str] = field(default_factory=list)
    phases: Dict[str, PhaseState] = field(default_factory=dict)


def get_utc_timestamp() -> str:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_safe_project_name(name: str) -> bool:
    """Validate project name is safe (no path traversal)."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,64}$', name))


def get_project_dir(project_name: str) -> Path:
    """Get project directory path with path traversal protection."""
    if not project_name or not is_safe_project_name(project_name):
        raise ValueError(f"Invalid project name: {project_name}. Use only alphanumeric, hyphens, underscores (max 64 chars).")

    base = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    project_dir = (base / project_name).resolve()

    try:
        project_dir.relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"Invalid project path: path traversal detected")

    return project_dir


def load_project_state(project_name: str) -> Optional[ProjectState]:
    """Load project state from disk."""
    project_dir = get_project_dir(project_name)
    project_file = project_dir / "project.json"

    if not project_file.exists():
        project_md = project_dir / "project.md"
        if project_md.exists():
            return load_from_markdown(project_md)
        return None

    with open(project_file) as f:
        data = json.load(f)

    phases = {}
    for phase_name, phase_data in data.get("phases", {}).items():
        normalized = resolve_phase(phase_name)
        phases[normalized] = PhaseState(**phase_data)

    return ProjectState(
        name=data["name"],
        current_phase=resolve_phase(data["current_phase"]),
        created_at=data.get("created_at", get_utc_timestamp()),
        version=data.get("version", "v3-capability-based"),
        signals_detected=data.get("signals_detected", []),
        complexity_score=data.get("complexity_score", 0),
        specialists_recommended=data.get("specialists_recommended", []),
        phase_plan=data.get("phase_plan", []),
        phases=phases
    )


def _load_from_markdown_simple(project_md: Path) -> Optional[ProjectState]:
    """Simple fallback parser when PyYAML is not available."""
    try:
        content = project_md.read_text()
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read {project_md}: {e}")
        return None

    frontmatter_match = re.match(r'^---\n(.*?)\n---', content[:5000], re.DOTALL)
    if not frontmatter_match:
        return None

    data = {}
    for line in frontmatter_match.group(1).split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            data[key.strip()] = value.strip()

    return ProjectState(
        name=data.get("name", project_md.parent.name),
        current_phase=data.get("current_phase", "clarify"),
        created_at=data.get("created", get_utc_timestamp()),
        version=data.get("version", "v3-capability-based"),
        phases={}
    )


def load_from_markdown(project_md: Path) -> Optional[ProjectState]:
    """Load project state from markdown frontmatter using proper YAML parser."""
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, using simple frontmatter parser")
        return _load_from_markdown_simple(project_md)

    try:
        content = project_md.read_text()
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read {project_md}: {e}")
        return None

    frontmatter_match = re.match(r'^---\n(.*?)\n---', content[:5000], re.DOTALL)

    if not frontmatter_match:
        logger.debug(f"No frontmatter found in {project_md}")
        return None

    try:
        data = yaml.safe_load(frontmatter_match.group(1))
        if not isinstance(data, dict):
            logger.warning(f"Invalid frontmatter format in {project_md}")
            return None
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error in {project_md}: {e}")
        return None

    return ProjectState(
        name=data.get("name", project_md.parent.name),
        current_phase=data.get("current_phase", "clarify"),
        created_at=data.get("created", get_utc_timestamp()),
        version=data.get("version", "v3-capability-based"),
        phases={}
    )


def save_project_state(state: ProjectState) -> None:
    """Save project state to disk with atomic write."""
    logger.info(f"Saving project state: {state.name} (phase: {state.current_phase})")

    project_dir = get_project_dir(state.name)
    project_dir.mkdir(parents=True, exist_ok=True)

    project_file = project_dir / "project.json"
    temp_file = project_file.with_suffix('.tmp')

    data = {
        "name": state.name,
        "current_phase": state.current_phase,
        "created_at": state.created_at,
        "version": state.version,
        "signals_detected": state.signals_detected,
        "complexity_score": state.complexity_score,
        "specialists_recommended": state.specialists_recommended,
        "phase_plan": state.phase_plan,
        "phases": {name: asdict(phase) for name, phase in state.phases.items()}
    }

    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.replace(project_file)
        logger.debug(f"Project state saved to {project_file}")
    except OSError as e:
        logger.error(f"Failed to save project state: {e}")
        if temp_file.exists():
            temp_file.unlink()
        raise


def can_transition(
    state: ProjectState,
    to_phase: str
) -> Tuple[bool, List[str]]:
    """Check if transition to target phase is valid."""
    reasons = []
    to_phase = resolve_phase(to_phase)
    current = resolve_phase(state.current_phase)

    phase_order = get_phase_order(state)

    if current not in phase_order:
        reasons.append(f"Current phase '{current}' not in phase plan")
        return (False, reasons)
    if to_phase not in phase_order:
        reasons.append(f"Target phase '{to_phase}' not in phase plan")
        return (False, reasons)

    current_idx = phase_order.index(current)
    target_idx = phase_order.index(to_phase)

    if target_idx < current_idx:
        reasons.append(f"Cannot go back from {current} to {to_phase}")
        return (False, reasons)

    # Check all intermediate phases are complete/approved
    for i in range(current_idx, target_idx):
        intermediate = phase_order[i]
        phase_state = state.phases.get(intermediate)

        if not phase_state:
            reasons.append(f"Phase {intermediate} has no state")
            continue

        if phase_state.status not in ["approved", "skipped"]:
            reasons.append(
                f"Phase {intermediate} must be approved before advancing "
                f"(current status: {phase_state.status})"
            )

    # Check current phase deliverables from phases.json
    current_state = state.phases.get(current)
    if current_state and current_state.status == "in_progress":
        phases_config = load_phases_config()
        deliverables = phases_config.get(current, {}).get("required_deliverables", [])
        project_dir = get_project_dir(state.name)

        for deliverable in deliverables:
            path = project_dir / "phases" / current / deliverable
            if not path.exists():
                reasons.append(f"Missing deliverable: {deliverable}")

    return (len(reasons) == 0, reasons)


def start_phase(state: ProjectState, phase: str) -> ProjectState:
    """Mark a phase as in progress."""
    phase = resolve_phase(phase)
    phase_state = state.phases.get(phase, PhaseState())
    phase_state.status = "in_progress"
    phase_state.started_at = get_utc_timestamp()
    state.phases[phase] = phase_state
    state.current_phase = phase
    return state


def complete_phase(state: ProjectState, phase: str) -> ProjectState:
    """Mark a phase as complete (awaiting approval). Ensures status.md exists."""
    phase = resolve_phase(phase)
    phase_state = state.phases.get(phase)
    if not phase_state:
        phase_state = PhaseState()
        state.phases[phase] = phase_state
    if phase_state:
        phase_state.status = "complete"
        phase_state.completed_at = get_utc_timestamp()

    project_dir = get_project_dir(state.name)
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    status_file = phase_dir / "status.md"
    if not status_file.exists():
        status_file.write_text(
            f"---\n"
            f"phase: {phase}\n"
            f"status: awaiting_approval\n"
            f"completed: {phase_state.completed_at if phase_state else get_utc_timestamp()}\n"
            f"---\n\n"
            f"# {phase.replace('-', ' ').title()} Phase\n\n"
            f"Phase completed. Deliverables pending documentation.\n"
        )

    return state


def approve_phase(
    state: ProjectState,
    phase: str,
    approver: str = "user"
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase and return next phase (or None if done)."""
    phase = resolve_phase(phase)
    phase_state = state.phases.get(phase)
    if not phase_state:
        phase_state = PhaseState()
        state.phases[phase] = phase_state
    if phase_state:
        phase_state.status = "approved"
        phase_state.approved_at = get_utc_timestamp()
        phase_state.approved_by = approver

    # Determine next phase from dynamic order
    phase_order = get_phase_order(state)
    if phase in phase_order:
        current_idx = phase_order.index(phase)
        if current_idx < len(phase_order) - 1:
            return (state, phase_order[current_idx + 1])

    return (state, None)


def skip_phase(state: ProjectState, phase: str, reason: str = "", approved_by: str = "auto") -> ProjectState:
    """Skip a phase. Checks is_skippable from phases.json."""
    phase = resolve_phase(phase)

    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})
    if not phase_config.get("is_skippable", True):
        raise ValueError(f"Phase '{phase}' cannot be skipped (is_skippable=false)")

    phase_state = state.phases.get(phase, PhaseState())
    phase_state.status = "skipped"
    phase_state.completed_at = get_utc_timestamp()
    phase_state.approved_by = approved_by
    phase_state.notes = reason
    state.phases[phase] = phase_state

    # Always write a status.md for skipped phases (audit trail)
    project_dir = get_project_dir(state.name)
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    status_file = phase_dir / "status.md"

    status_content = (
        f"---\n"
        f"phase: {phase}\n"
        f"status: skipped\n"
        f"skipped_at: {phase_state.completed_at}\n"
        f"approved_by: {approved_by}\n"
        f"---\n\n"
        f"# {phase.replace('-', ' ').title()} Phase — Skipped\n\n"
        f"**Reason**: {reason or 'Not applicable for this project scope'}\n\n"
        f"**Approved by**: {approved_by}\n"
    )
    status_file.write_text(status_content)

    return state


def get_phase_status_summary(state: ProjectState) -> Dict[str, str]:
    """Get summary of all phase statuses."""
    summary = {}
    for phase in get_phase_order(state):
        phase_state = state.phases.get(phase)
        summary[phase] = phase_state.status if phase_state else "pending"
    return summary


def main():
    """CLI interface for phase management."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase manager for wicked-crew")
    parser.add_argument("project", help="Project name")
    parser.add_argument("action", choices=["status", "start", "complete", "approve", "skip", "can-advance"])
    parser.add_argument("--phase", help="Target phase")
    parser.add_argument("--reason", help="Reason for skip")
    parser.add_argument("--approved-by", default="auto", help="Who approved the skip")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    state = load_project_state(args.project)
    if not state and args.action != "status":
        print(f"Project not found: {args.project}")
        return

    if args.action == "status":
        if not state:
            print(f"No project: {args.project}")
            return

        if args.json:
            summary = {
                "name": state.name,
                "current_phase": state.current_phase,
                "phase_plan": state.phase_plan,
                "phases": get_phase_status_summary(state),
                "signals": state.signals_detected,
                "complexity": state.complexity_score
            }
            print(json.dumps(summary, indent=2))
        else:
            print(f"Project: {state.name}")
            print(f"Current Phase: {state.current_phase}")
            print(f"Complexity: {state.complexity_score}/7")
            print(f"Signals: {', '.join(state.signals_detected) or 'none'}")
            if state.phase_plan:
                print(f"Phase Plan: {' -> '.join(state.phase_plan)}")
            print("\nPhase Status:")
            for phase, status in get_phase_status_summary(state).items():
                marker = ">" if phase == state.current_phase else " "
                print(f"  {marker} {phase}: {status}")

    elif args.action == "start":
        phase = args.phase or state.current_phase
        state = start_phase(state, phase)
        save_project_state(state)
        print(f"Started phase: {resolve_phase(phase)}")

    elif args.action == "complete":
        phase = args.phase or state.current_phase
        state = complete_phase(state, phase)
        save_project_state(state)
        print(f"Completed phase: {resolve_phase(phase)} (awaiting approval)")

    elif args.action == "approve":
        phase = args.phase or state.current_phase
        state, next_phase = approve_phase(state, phase)
        save_project_state(state)
        print(f"Approved phase: {resolve_phase(phase)}")
        if next_phase:
            print(f"Next phase: {next_phase}")
        else:
            print("Project complete!")

    elif args.action == "skip":
        phase = args.phase
        if not phase:
            print("Error: --phase required for skip action")
            return
        try:
            state = skip_phase(state, phase, args.reason or "", args.approved_by)
        except ValueError as e:
            print(f"Error: {e}")
            return
        save_project_state(state)
        print(f"Skipped phase: {resolve_phase(phase)}")

    elif args.action == "can-advance":
        phase_order = get_phase_order(state)
        current = resolve_phase(state.current_phase)
        if args.phase:
            target = resolve_phase(args.phase)
        elif current in phase_order and phase_order.index(current) + 1 < len(phase_order):
            target = phase_order[phase_order.index(current) + 1]
        else:
            print("Already at last phase")
            return
        can, reasons = can_transition(state, target)
        if args.json:
            print(json.dumps({"can_advance": can, "reasons": reasons}))
        else:
            if can:
                print(f"Can advance to {target}")
            else:
                print(f"Cannot advance to {target}:")
                for reason in reasons:
                    print(f"  - {reason}")


if __name__ == "__main__":
    main()
