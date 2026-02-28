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
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager

_sm = StorageManager("wicked-crew")

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


def _get_plugin_root() -> Path:
    """Resolve the plugin root directory (repo root).

    Walks up from scripts/crew/ to find phases.json or .claude-plugin/.
    Falls back to 3 levels up from this file.
    """
    here = Path(__file__).resolve().parent  # scripts/crew/
    # Walk up looking for marker files
    candidate = here
    for _ in range(5):
        candidate = candidate.parent
        if (candidate / "phases.json").exists():
            return candidate
        if (candidate / ".claude-plugin").is_dir():
            return candidate
    # Fallback: scripts/crew/ -> scripts/ -> repo root
    return here.parent.parent


def load_phases_config() -> dict:
    """Load phase definitions from phases.json at plugin root."""
    config_path = _get_plugin_root() / "phases.json"
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


# ---------------------------------------------------------------------------
# Enforcement: phase plan validation, checkpoint re-analysis, pre-review gate
# ---------------------------------------------------------------------------

# Phases that must be present when complexity >= this threshold
_TEST_PHASE_COMPLEXITY_THRESHOLD = 2
_TEST_PHASES = ("test-strategy", "test")


def validate_phase_plan(state: 'ProjectState') -> Tuple[List[str], List[str]]:
    """Validate and fix the phase plan based on complexity.

    If complexity_score >= 2 and test-strategy/test are missing from
    phase_plan, inject them in dependency-correct positions.

    Returns:
        (injected_phases, warnings) — list of phases added and any warnings.
    """
    if state.complexity_score < _TEST_PHASE_COMPLEXITY_THRESHOLD:
        return ([], [])

    if not state.phase_plan:
        return ([], ["No phase_plan set — cannot validate"])

    plan = [resolve_phase(p) for p in state.phase_plan]
    phases_config = load_phases_config()
    injected = []

    for test_phase in _TEST_PHASES:
        if test_phase in plan:
            continue
        if test_phase not in phases_config:
            continue

        # Find correct insertion point based on depends_on
        deps = phases_config[test_phase].get("depends_on", [])
        insert_after_idx = -1
        for dep in deps:
            dep = resolve_phase(dep)
            if dep in plan:
                insert_after_idx = max(insert_after_idx, plan.index(dep))

        # Insert after last dependency, or at end if no deps found
        insert_idx = insert_after_idx + 1 if insert_after_idx >= 0 else len(plan)

        # Don't insert after review (review should always be last)
        if "review" in plan:
            review_idx = plan.index("review")
            if insert_idx > review_idx:
                insert_idx = review_idx

        plan.insert(insert_idx, test_phase)
        injected.append(test_phase)
        logger.info(f"[validate_phase_plan] Injected '{test_phase}' at position {insert_idx} "
                     f"(complexity={state.complexity_score} >= {_TEST_PHASE_COMPLEXITY_THRESHOLD})")

    if injected:
        state.phase_plan = plan

    warnings = []
    if injected:
        warnings.append(
            f"Injected {', '.join(injected)} into phase plan "
            f"(complexity {state.complexity_score} >= {_TEST_PHASE_COMPLEXITY_THRESHOLD})"
        )

    return (injected, warnings)


def _check_test_phases_before_review(state: 'ProjectState') -> List[str]:
    """Pre-review gate: verify test phases ran or were explicitly skipped.

    Returns list of blocking reasons (empty = OK to proceed).
    """
    if state.complexity_score < _TEST_PHASE_COMPLEXITY_THRESHOLD:
        return []

    reasons = []
    for test_phase in _TEST_PHASES:
        if test_phase not in state.phase_plan:
            continue

        phase_state = state.phases.get(test_phase)
        if not phase_state:
            reasons.append(
                f"Test phase '{test_phase}' is in the plan but was never started. "
                f"Run it or skip with: phase_manager.py {{project}} skip --phase {test_phase} --reason '...'"
            )
            continue

        if phase_state.status in ("approved", "complete"):
            continue

        if phase_state.status == "skipped":
            if not phase_state.notes:
                reasons.append(
                    f"Test phase '{test_phase}' was skipped without a reason. "
                    f"Re-skip with --reason to document why."
                )
            continue

        reasons.append(
            f"Test phase '{test_phase}' has status '{phase_state.status}' — "
            f"must be approved or explicitly skipped before review."
        )

    return reasons


def _run_checkpoint_reanalysis(state: 'ProjectState', phase: str) -> Tuple[List[str], List[str]]:
    """At checkpoint phases, re-validate the phase plan and inject missing phases.

    Returns:
        (injected_phases, warnings)
    """
    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})

    if not phase_config.get("checkpoint", False):
        return ([], [])

    logger.info(f"[checkpoint] Phase '{phase}' is a checkpoint — running phase plan re-validation")
    return validate_phase_plan(state)


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
    kanban_initiative: Optional[str] = None
    kanban_initiative_id: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


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
    """Load project state from StorageManager."""
    if not project_name or not is_safe_project_name(project_name):
        return None

    data = _sm.get("projects", project_name)
    if not data:
        # Fallback: try legacy file path for markdown
        project_dir = get_project_dir(project_name)
        project_md = project_dir / "project.md"
        if project_md.exists():
            return load_from_markdown(project_md)
        return None

    phases = {}
    for phase_name, phase_data in data.get("phases", {}).items():
        normalized = resolve_phase(phase_name)
        if isinstance(phase_data, dict):
            phases[normalized] = PhaseState(**phase_data)

    known_keys = {
        "id", "name", "current_phase", "created_at", "version",
        "signals_detected", "complexity_score", "specialists_recommended",
        "phase_plan", "phases",
        "kanban_initiative", "kanban_initiative_id",
        "created_at", "updated_at", "deleted", "deleted_at",
    }
    extras = {k: v for k, v in data.items() if k not in known_keys}

    return ProjectState(
        name=data.get("name", project_name),
        current_phase=resolve_phase(data.get("current_phase", "clarify")),
        created_at=data.get("created_at", get_utc_timestamp()),
        version=data.get("version", "v3-capability-based"),
        signals_detected=data.get("signals_detected", []),
        complexity_score=data.get("complexity_score", 0),
        specialists_recommended=data.get("specialists_recommended", []),
        phase_plan=data.get("phase_plan", []),
        phases=phases,
        kanban_initiative=data.get("kanban_initiative"),
        kanban_initiative_id=data.get("kanban_initiative_id"),
        extras=extras,
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
    """Save project state via StorageManager."""
    logger.info(f"Saving project state: {state.name} (phase: {state.current_phase})")

    data = {
        "id": state.name,
        "name": state.name,
        "current_phase": state.current_phase,
        "created_at": state.created_at,
        "version": state.version,
        "signals_detected": state.signals_detected,
        "complexity_score": state.complexity_score,
        "specialists_recommended": state.specialists_recommended,
        "phase_plan": state.phase_plan,
        "phases": {name: asdict(phase) for name, phase in state.phases.items()},
        "kanban_initiative": state.kanban_initiative,
        "kanban_initiative_id": state.kanban_initiative_id,
        **state.extras,
    }

    existing = _sm.get("projects", state.name)
    if existing:
        _sm.update("projects", state.name, data)
    else:
        _sm.create("projects", data)
    logger.debug(f"Project state saved for {state.name}")


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

    # Pre-review gate: verify test phases ran before entering review
    if to_phase == "review":
        test_issues = _check_test_phases_before_review(state)
        reasons.extend(test_issues)

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


def _check_phase_deliverables(state: ProjectState, phase: str) -> List[str]:
    """Check if required deliverables exist for a phase. Returns list of issues."""
    phase = resolve_phase(phase)
    issues = []
    phases_config = load_phases_config()
    deliverables = phases_config.get(phase, {}).get("required_deliverables", [])
    if not deliverables:
        return issues

    project_dir = get_project_dir(state.name)
    for deliverable in deliverables:
        path = project_dir / "phases" / phase / deliverable
        if not path.exists():
            issues.append(f"Missing deliverable for {phase}: {deliverable}")

    return issues


def _check_gate_run(project_dir: Path, phase: str) -> bool:
    """Return True if evidence of a gate run exists for this phase."""
    phase_dir = project_dir / "phases" / phase
    # Primary: gate result file written by /wicked-crew:gate
    if (phase_dir / "gate-result.json").exists():
        return True
    # Secondary: status.md contains gate_status field
    status_md = phase_dir / "status.md"
    if status_md.exists():
        try:
            content = status_md.read_text()
            if "gate_status:" in content or "gate:" in content:
                return True
        except OSError:
            pass
    return False


def _load_session_dispatches() -> List[Dict[str, Any]]:
    """Load specialist dispatch records from session state file."""
    import os
    import tempfile
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    session_file = Path(tempfile.gettempdir()) / f"wicked-crew-session-{session_id}.json"
    try:
        data = json.loads(session_file.read_text())
        return data.get("specialist_dispatches", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return []


def approve_phase(
    state: ProjectState,
    phase: str,
    approver: str = "user"
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase and return next phase (or None if done).

    Performs gate checks and deliverable checks, emitting warnings.
    Always approves — warnings are advisory only (v1 backward compat).
    """
    phase = resolve_phase(phase)
    warnings: List[str] = []

    # Check 1: deliverables for the phase being approved
    deliverable_issues = _check_phase_deliverables(state, phase)
    if deliverable_issues:
        warnings.extend(deliverable_issues)

    # Check 2: gate_required from phases.json
    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})
    gate_required = phase_config.get("gate_required", False)

    if gate_required:
        project_dir = get_project_dir(state.name)
        if not _check_gate_run(project_dir, phase):
            warnings.append(
                f"Gate not run for phase '{phase}' (gate_required=true). "
                f"Run /wicked-crew:gate before approving."
            )

    # Emit warnings to stderr (stdout is for structured output)
    for w in warnings:
        logger.warning(f"[approve] {w}")

    # Record specialist engagements from session dispatches
    session_dispatches = _load_session_dispatches()
    phase_state = state.phases.get(phase)
    if not phase_state:
        phase_state = PhaseState()
        state.phases[phase] = phase_state

    if session_dispatches:
        phase_state.specialists_engaged = sorted({
            *phase_state.specialists_engaged,
            *[d["subagent_type"] for d in session_dispatches if "subagent_type" in d]
        })

    phase_state.status = "approved"
    phase_state.approved_at = get_utc_timestamp()
    phase_state.approved_by = approver

    # Checkpoint enforcement: re-validate phase plan after checkpoint phases
    injected, reanalysis_warnings = _run_checkpoint_reanalysis(state, phase)
    for w in reanalysis_warnings:
        logger.warning(f"[checkpoint] {w}")
    if injected:
        logger.info(f"[checkpoint] Injected phases after '{phase}': {injected}")

    # Determine next phase from dynamic order (may have changed via injection)
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
    parser.add_argument("action", choices=["status", "start", "complete", "approve", "skip", "can-advance", "validate"])
    parser.add_argument("--phase", help="Target phase")
    parser.add_argument("--reason", help="Reason for skip")
    parser.add_argument("--approved-by", default=None, help="Approver identity (default: 'auto' for skip, 'user' for approve)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    state = load_project_state(args.project)
    if not state and args.action != "status":
        print(f"Project not found: {args.project}")
        return

    # Check if project is archived (refuse execution)
    project_dir = get_project_dir(args.project)
    project_file = project_dir / "project.json"
    if project_file.exists():
        try:
            with open(project_file) as f:
                project_data = json.load(f)
            if project_data.get("archived", False):
                print(f"Error: Cannot execute phase operations on archived project: {args.project}")
                print("Use 'python3 scripts/cp.py crew projects unarchive {name}' to unarchive first.")
                return
        except (json.JSONDecodeError, OSError):
            pass

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
                "complexity": state.complexity_score,
                "kanban_initiative": state.kanban_initiative,
                "kanban_initiative_id": state.kanban_initiative_id,
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
        state, next_phase = approve_phase(state, phase, approver=args.approved_by or "user")
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
            state = skip_phase(state, phase, args.reason or "", args.approved_by or "auto")
        except ValueError as e:
            print(f"Error: {e}")
            return
        save_project_state(state)
        print(f"Skipped phase: {resolve_phase(phase)}")

    elif args.action == "validate":
        injected, warnings = validate_phase_plan(state)
        if args.json:
            print(json.dumps({
                "injected": injected,
                "warnings": warnings,
                "phase_plan": state.phase_plan,
                "complexity": state.complexity_score,
            }, indent=2))
        else:
            if injected:
                print(f"Injected phases: {', '.join(injected)}")
                print(f"Updated plan: {' -> '.join(state.phase_plan)}")
            else:
                print("Phase plan is valid — no changes needed")
            for w in warnings:
                print(f"  Warning: {w}")
        if injected:
            save_project_state(state)

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
