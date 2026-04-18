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
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Resolve _domain_store and _paths from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore, get_local_path

_sm = DomainStore("wicked-crew")

# Late-import helper for consensus gate (avoids circular imports at module level)
_consensus_gate = None


def _get_consensus_gate():
    """Lazy-load consensus_gate module to avoid import-time side effects."""
    global _consensus_gate
    if _consensus_gate is None:
        try:
            from crew.consensus_gate import (
                should_use_consensus,
                evaluate_consensus_gate,
                _write_consensus_evidence,
            )
            _consensus_gate = {
                "should_use_consensus": should_use_consensus,
                "evaluate_consensus_gate": evaluate_consensus_gate,
                "_write_consensus_evidence": _write_consensus_evidence,
            }
        except ImportError:
            _consensus_gate = {}
    return _consensus_gate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wicked-crew.phase-manager')

# Legacy phase aliases for backward compatibility
LEGACY_ALIASES = {"qe": "test-strategy"}

# ---------------------------------------------------------------------------
# Gate enforcement mode — read once at import
# ---------------------------------------------------------------------------
# "strict" (default): all new enforcement checks are active
# "legacy": all new enforcement checks return early, restoring pre-feature behavior
GATE_ENFORCEMENT_MODE: str = os.environ.get("CREW_GATE_ENFORCEMENT", "strict")

# Banned reviewer name patterns (AC-1.4)
# Exact matches and prefix patterns that indicate auto-approve bypass
BANNED_REVIEWER_NAMES: tuple = (
    "just-finish-auto",
    "fast-pass",
    "auto-approve-design-complete",
)
BANNED_REVIEWER_PREFIXES: tuple = (
    "auto-approve-",
    "auto-review-",
    "self-review-",
)

# Valid skip reasons fallback if phases.json lacks valid_skip_reasons (AC-4.2)
DEFAULT_VALID_SKIP_REASONS: tuple = (
    "complexity_below_threshold",
    "user_explicit_request",
    "ci_equivalent_exists",
    "out_of_scope",
    "legacy",
)


def resolve_phase(name: str) -> str:
    """Resolve legacy phase aliases."""
    return LEGACY_ALIASES.get(name, name)


def _get_plugin_root() -> Path:
    """Resolve the plugin root directory (repo root).

    Walks up from scripts/crew/ to find .claude-plugin/.
    Falls back to 3 levels up from this file.
    """
    here = Path(__file__).resolve().parent  # scripts/crew/
    # Walk up looking for marker files
    candidate = here
    for _ in range(5):
        candidate = candidate.parent
        if (candidate / ".claude-plugin").is_dir():
            return candidate
    # Fallback: 3 levels up from this file (scripts/crew/ -> scripts/ -> repo root)
    return Path(__file__).resolve().parents[2]


def load_phases_config() -> dict:
    """Load phase definitions from phases.json in .claude-plugin/."""
    config_path = _get_plugin_root() / ".claude-plugin" / "phases.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f).get("phases", {})
    # Minimal fallback if phases.json missing
    return {
        "clarify": {"is_skippable": False, "depends_on": [], "required_deliverables": ["outcome.md"]},
        "build": {"is_skippable": False, "depends_on": ["clarify"], "required_deliverables": []},
        "review": {"is_skippable": False, "depends_on": ["build"], "required_deliverables": ["review-findings.md"]},
    }


# ---------------------------------------------------------------------------
# Enforcement threshold accessors — read from phases.json with safe defaults
# ---------------------------------------------------------------------------
# Default fallbacks used when phases.json is missing a field (backward compat)
_DEFAULT_MIN_TEST_COVERAGE: float = 0.80
_DEFAULT_REQUIRED_SPECIALISTS: list = []
_DEFAULT_REQUIRED_DELIVERABLES: list = []


def get_min_test_coverage(phase_name: str) -> Optional[float]:
    """Return the minimum test coverage threshold for a phase.

    Returns the float value from phases.json, or None if the phase does not
    require coverage enforcement (e.g. non-test phases).  Falls back to
    _DEFAULT_MIN_TEST_COVERAGE only for the canonical test/review phases when
    the field is absent from phases.json, so old configs remain backward
    compatible.

    Always returns None when CREW_GATE_ENFORCEMENT=legacy.
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return None

    phases = load_phases_config()
    phase = phases.get(resolve_phase(phase_name), {})

    if "min_test_coverage" in phase:
        return phase["min_test_coverage"]

    # Backward-compat default: apply coverage floor only to test/review phases
    if resolve_phase(phase_name) in ("test", "review"):
        return _DEFAULT_MIN_TEST_COVERAGE

    return None


def get_required_deliverables(phase_name: str) -> List[dict]:
    """Return the structured required-deliverables list for a phase.

    Each entry is a dict with keys: ``file`` (str), ``min_bytes`` (int),
    ``frontmatter`` (list of str).  Falls back to an empty list so callers
    always receive an iterable.

    Legacy string entries (old schema) are promoted to dicts with defaults so
    the function is safe against phases.json files that haven't been migrated.

    Always returns [] when CREW_GATE_ENFORCEMENT=legacy.
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return []

    phases = load_phases_config()
    phase = phases.get(resolve_phase(phase_name), {})
    raw = phase.get("required_deliverables", _DEFAULT_REQUIRED_DELIVERABLES)

    result: List[dict] = []
    for entry in raw:
        if isinstance(entry, dict):
            result.append({
                "file": entry.get("file", ""),
                "min_bytes": entry.get("min_bytes", 100),
                "frontmatter": entry.get("frontmatter", []),
            })
        elif isinstance(entry, str):
            # Promote legacy plain-string entries gracefully
            result.append({"file": entry, "min_bytes": 100, "frontmatter": []})
    return result


def get_required_specialists(phase_name: str) -> List[str]:
    """Return the list of specialist domains that must engage for a phase.

    Falls back to an empty list when the field is absent so low-complexity
    phases (which have no required specialists) continue to work unchanged.

    Always returns [] when CREW_GATE_ENFORCEMENT=legacy.
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return []

    phases = load_phases_config()
    phase = phases.get(resolve_phase(phase_name), {})
    return list(phase.get("required_specialists", _DEFAULT_REQUIRED_SPECIALISTS))


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

    # Honor phase_plan_mode: static and facilitator — don't mutate plans
    # the facilitator explicitly authored. The facilitator's rubric already
    # decides whether test-strategy/test phases are warranted (see issue #435
    # Gap 3; the v6 minimal-rigor 3-phase plan should stay 3 phases even at
    # complexity >= 2).
    if state.extras.get("phase_plan_mode") in ("static", "facilitator"):
        return ([], [])

    if not state.phase_plan:
        return ([], ["No phase_plan set — cannot validate"])

    plan = [resolve_phase(p) for p in state.phase_plan]
    phases_config = load_phases_config()
    injected = []
    warnings = []

    for test_phase in _TEST_PHASES:
        if test_phase in plan:
            continue
        if test_phase not in phases_config:
            warnings.append(
                f"Required test phase '{test_phase}' not found in phases.json — "
                f"cannot inject. Check phases.json configuration."
            )
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

    # Normalize phase names so legacy aliases (e.g., "qe") are handled correctly
    normalized_plan = {resolve_phase(p) for p in state.phase_plan}

    reasons = []
    for test_phase in _TEST_PHASES:
        if test_phase not in normalized_plan:
            continue

        phase_state = state.phases.get(test_phase)
        if not phase_state:
            reasons.append(
                f"Test phase '{test_phase}' is in the plan but was never started. "
                f"Run it or skip with: phase_manager.py {state.name} skip --phase {test_phase} --reason '...'"
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
    cp_project_id: Optional[str] = None
    workspace: Optional[str] = None
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

    base = get_local_path("wicked-crew", "projects")
    project_dir = (base / project_name).resolve()

    try:
        project_dir.relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"Invalid project path: path traversal detected")

    return project_dir


def load_project_state(project_name: str) -> Optional[ProjectState]:
    """Load project state from DomainStore."""
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
    _phase_fields = set(PhaseState.__dataclass_fields__.keys())
    raw_phases = data.get("phases", {})
    # CP may return phases as a list of dicts or as a dict keyed by name
    if isinstance(raw_phases, list):
        for phase_data in raw_phases:
            if isinstance(phase_data, dict) and "name" in phase_data:
                normalized = resolve_phase(phase_data["name"])
                safe_data = {k: v for k, v in phase_data.items() if k in _phase_fields}
                phases[normalized] = PhaseState(**safe_data)
    elif isinstance(raw_phases, dict):
        for phase_name, phase_data in raw_phases.items():
            normalized = resolve_phase(phase_name)
            if isinstance(phase_data, dict):
                safe_data = {k: v for k, v in phase_data.items() if k in _phase_fields}
                phases[normalized] = PhaseState(**safe_data)

    known_keys = {
        "id", "name", "current_phase", "created_at", "version",
        "signals_detected", "complexity_score", "specialists_recommended",
        "phase_plan", "phases",
        "cp_project_id",
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
        cp_project_id=data.get("cp_project_id"),
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

    raw_created = data.get("created", get_utc_timestamp())
    created_str = raw_created.isoformat() if hasattr(raw_created, 'isoformat') else str(raw_created)

    return ProjectState(
        name=data.get("name", project_md.parent.name),
        current_phase=data.get("current_phase", "clarify"),
        created_at=created_str,
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

    raw_created = data.get("created", get_utc_timestamp())
    # YAML parses bare dates (2026-02-28) as datetime.date objects — coerce to str
    created_str = raw_created.isoformat() if hasattr(raw_created, 'isoformat') else str(raw_created)

    return ProjectState(
        name=data.get("name", project_md.parent.name),
        current_phase=data.get("current_phase", "clarify"),
        created_at=created_str,
        version=data.get("version", "v3-capability-based"),
        phases={}
    )


def _sanitize_for_json(obj):
    """Recursively coerce date/datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def save_project_state(state: ProjectState) -> None:
    """Save project state via DomainStore."""
    logger.info(f"Saving project state: {state.name} (phase: {state.current_phase})")

    # Convert phases dict to list-of-dicts with name field (CP expects array format)
    phases_list = []
    for phase_name, phase_obj in state.phases.items():
        phase_dict = asdict(phase_obj)
        phase_dict["name"] = phase_name
        phases_list.append(phase_dict)

    data = _sanitize_for_json({
        "id": state.name,
        "name": state.name,
        "current_phase": state.current_phase,
        "created_at": state.created_at,
        "version": state.version,
        "signals_detected": state.signals_detected,
        "complexity_score": state.complexity_score,
        "specialists_recommended": state.specialists_recommended,
        "phase_plan": state.phase_plan,
        "phases": phases_list,
        "cp_project_id": state.cp_project_id,
        **state.extras,
    })

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
    project_dir = get_project_dir(state.name)

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

    # Check conditions from prior CONDITIONAL gates (AC-1.2)
    for i in range(max(0, current_idx), target_idx):
        intermediate = phase_order[i]
        phase_state_check = state.phases.get(intermediate)
        if phase_state_check and phase_state_check.status == "approved":
            condition_issues = _verify_conditions(project_dir, intermediate)
            reasons.extend(condition_issues)

    # Pre-review gate: verify test phases ran before entering review
    if to_phase == "review":
        test_issues = _check_test_phases_before_review(state)
        reasons.extend(test_issues)

    # Check current phase deliverables from phases.json
    current_state = state.phases.get(current)
    if current_state and current_state.status == "in_progress":
        phases_config = load_phases_config()
        deliverables = phases_config.get(current, {}).get("required_deliverables", [])

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
    """Check if required deliverables exist and have content for a phase.

    Returns list of issues (empty = all deliverables present and non-empty).

    Facilitator-owned plans (phase_plan_mode == "facilitator") use
    process-plan.md/process-plan.json as their canonical artifact. When present
    and non-empty, they satisfy the phases.json required_deliverables check —
    the facilitator's factor readings + task metadata replace the legacy
    complexity.md / acceptance-criteria.md files. See issue #435.
    """
    phase = resolve_phase(phase)
    issues = []
    phases_config = load_phases_config()
    deliverables = phases_config.get(phase, {}).get("required_deliverables", [])
    if not deliverables:
        return issues

    project_dir = get_project_dir(state.name)

    # v6 facilitator-plan short-circuit: if the project's plan is owned by the
    # facilitator and a non-empty process-plan.md is present, accept it as
    # satisfying required_deliverables for any phase.
    if state.extras.get("phase_plan_mode") == "facilitator":
        plan_md = project_dir / "process-plan.md"
        plan_json = project_dir / "process-plan.json"
        if plan_md.exists() and plan_md.stat().st_size > 0:
            # Also require process-plan.json to be present and parseable —
            # proves the plan was fully emitted, not just a stub.
            if plan_json.exists() and plan_json.stat().st_size > 0:
                try:
                    json.loads(plan_json.read_text())
                    return issues
                except (json.JSONDecodeError, OSError):
                    pass  # fall through to legacy check

    for deliverable in deliverables:
        # Support both string and dict deliverable formats (dict has "file" key)
        deliverable_name = deliverable["file"] if isinstance(deliverable, dict) else deliverable
        path = project_dir / "phases" / phase / deliverable_name
        if not path.exists():
            issues.append(f"Missing deliverable for {phase}: {deliverable_name}")
            continue

        # Content validation (AC-1.5) — skip in legacy mode
        if GATE_ENFORCEMENT_MODE != "legacy":
            file_stat = path.stat()
            min_bytes = deliverable.get("min_bytes", 0) if isinstance(deliverable, dict) else 0
            if file_stat.st_size == 0:
                issues.append(f"Empty deliverable for {phase}: {deliverable_name} (0 bytes)")
            elif min_bytes > 0 and file_stat.st_size < min_bytes:
                issues.append(
                    f"Insufficient content in {phase}: {deliverable_name} "
                    f"({file_stat.st_size} bytes, minimum {min_bytes} required)"
                )
            # Evidence reports need substantive content (AC-3.4)
            elif deliverable_name == "evidence/report.md" and file_stat.st_size < 100:
                issues.append(
                    f"Insufficient content in {phase}: {deliverable_name} "
                    f"({file_stat.st_size} bytes, minimum 100 required for evidence reports)"
                )

    return issues


def _check_gate_run(project_dir: Path, phase: str, rigor_tier: Optional[str] = None) -> bool:
    """Return True if evidence of a valid gate run exists for this phase.

    A gate-result.json that exists but cannot be parsed as JSON is treated as
    gate-not-run — malformed output from a crashed gate process should not
    silently allow phase advancement.

    When ``rigor_tier == "minimal"``, a self-signoff block in status.md
    (``signoff:`` with ``result: approved`` or ``result: conditional``)
    satisfies the gate — minimal rigor is explicitly fast-pass per the
    facilitator rubric. See issue #435 (Gap 2).
    """
    phase_dir = project_dir / "phases" / phase
    # Primary: gate result file written by /wicked-crew:gate
    gate_file = phase_dir / "gate-result.json"
    if gate_file.exists():
        try:
            json.loads(gate_file.read_text())
            return True
        except (json.JSONDecodeError, OSError):
            # Malformed or unreadable — treat as gate-not-run
            return False
    # Secondary: status.md contains gate_status field, or a signoff block when
    # the phase is fast-pass (minimal rigor).
    status_md = phase_dir / "status.md"
    if status_md.exists():
        try:
            content = status_md.read_text()
            if "gate_status:" in content or "gate:" in content:
                return True
            if rigor_tier == "minimal" and "signoff:" in content:
                # Accept `result: approved` or `result: conditional` (anywhere
                # after the signoff header — permissive inline-yaml match).
                if ("result: approved" in content
                        or "result: conditional" in content):
                    return True
        except OSError:
            pass  # fail open: gate read failure returns False
    return False


def _load_gate_result(project_dir: Path, phase: str) -> Optional[Dict]:
    """Load gate-result.json if it exists. Returns None if missing or unreadable."""
    gate_file = project_dir / "phases" / phase / "gate-result.json"
    if not gate_file.exists():
        return None
    try:
        return json.loads(gate_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_conditions_manifest(
    project_dir: Path,
    phase: str,
    conditions: List[Dict[str, Any]],
) -> Path:
    """Write conditions from a CONDITIONAL gate result to a manifest file.

    Args:
        project_dir: Project root directory.
        phase: Phase name that produced the CONDITIONAL result.
        conditions: List of condition dicts from gate-result.json.

    Returns:
        Path to the written conditions-manifest.json.
    """
    manifest = {
        "source_gate": phase,
        "created_at": get_utc_timestamp(),
        "conditions": [
            {
                "id": f"CONDITION-{i + 1}",
                "description": c.get("description", c.get("condition", str(c))),
                "verified": False,
                "resolution": None,
                "verified_at": None,
            }
            for i, c in enumerate(conditions)
        ],
    }
    manifest_path = project_dir / "phases" / phase / "conditions-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


def _verify_conditions(
    project_dir: Path,
    prior_phase: str,
) -> List[str]:
    """Check that all conditions from a prior phase's CONDITIONAL gate are verified.

    Args:
        project_dir: Project root directory.
        prior_phase: The phase whose conditions-manifest.json to check.

    Returns:
        List of blocking reason strings. Empty list means all conditions verified
        or no manifest exists (legacy project).
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return []

    manifest_path = project_dir / "phases" / prior_phase / "conditions-manifest.json"
    if not manifest_path.exists():
        # No manifest = no conditions to verify (legacy project or APPROVE gate)
        return []

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    unverified = []
    for condition in manifest.get("conditions", []):
        if not condition.get("verified", False):
            desc = condition.get("description", condition.get("id", "unknown"))
            unverified.append(
                f"Unverified condition from {prior_phase} gate: {desc}"
            )

    return unverified


def _validate_gate_reviewer(
    gate_result: Dict[str, Any],
) -> Optional[str]:
    """Validate that the gate reviewer is not a banned auto-approve identity.

    Args:
        gate_result: Parsed gate-result.json dict.

    Returns:
        Error message string if reviewer is banned, None if OK.
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return None

    reviewer = gate_result.get("reviewer", "")
    if not reviewer:
        return (
            "Gate result is missing 'reviewer' field. "
            "Re-run the gate with a legitimate reviewer identity."
        )

    reviewer_lower = reviewer.lower().strip()

    # Check exact match
    if reviewer_lower in (name.lower() for name in BANNED_REVIEWER_NAMES):
        return (
            f"Banned reviewer name '{reviewer}' detected. "
            f"Auto-approve identities are not permitted as gate reviewers."
        )

    # Check prefix match
    for prefix in BANNED_REVIEWER_PREFIXES:
        if reviewer_lower.startswith(prefix.lower()):
            return (
                f"Banned reviewer name pattern '{reviewer}' matches prefix '{prefix}'. "
                f"Auto-approve identities are not permitted as gate reviewers."
            )

    return None


def _validate_min_gate_score(
    gate_result: Dict[str, Any],
    phase: str,
    phases_config: Dict[str, Any],
) -> Optional[str]:
    """Validate that gate score meets the phase's minimum threshold.

    Args:
        gate_result: Parsed gate-result.json dict.
        phase: Phase name being approved.
        phases_config: Full phases config from phases.json.

    Returns:
        Error message string if score is below threshold, None if OK.
    """
    if GATE_ENFORCEMENT_MODE == "legacy":
        return None

    phase_config = phases_config.get(phase, {})
    min_score = phase_config.get("min_gate_score")
    if min_score is None:
        return None

    actual_score = gate_result.get("score")
    if actual_score is None:
        actual_score = 0.0

    try:
        actual_score = float(actual_score)
        min_score = float(min_score)
    except (TypeError, ValueError):
        return (
            f"Gate score for phase '{phase}' is not numeric: "
            f"score={gate_result.get('score')}, min_gate_score={phase_config.get('min_gate_score')}"
        )

    if actual_score < min_score:
        return (
            f"Gate score {actual_score:.2f} is below minimum threshold "
            f"{min_score:.2f} for phase '{phase}'. "
            f"Improve deliverable quality and re-run the gate."
        )

    return None


def _bump_rework_iteration(project_dir: Path, phase: str) -> int:
    """Increment the per-phase rework iteration counter and return the new value.

    Persists to phases/<phase>/rework-iterations.json. Fail-open: returns 1 on any
    read/write error so callers can still emit an event with a plausible count.
    """
    iteration_file = project_dir / "phases" / phase / "rework-iterations.json"
    count = 0
    try:
        if iteration_file.exists():
            data = json.loads(iteration_file.read_text())
            count = int(data.get("iteration_count", 0))
    except (json.JSONDecodeError, OSError, ValueError):
        count = 0  # treat malformed file as fresh

    count += 1

    try:
        iteration_file.parent.mkdir(parents=True, exist_ok=True)
        iteration_file.write_text(
            json.dumps({
                "iteration_count": count,
                "updated_at": get_utc_timestamp(),
            })
        )
    except OSError:
        pass  # fail open: write failure is non-fatal

    return count


def _record_gate_override(
    project_dir: Path, phase: str, reason: str, approver: str
) -> None:
    """Append a gate override record to status.md."""
    status_file = project_dir / "phases" / phase / "status.md"
    timestamp = get_utc_timestamp()
    override_block = (
        f"\n## Gate Overrides\n\n"
        f"- **Date**: {timestamp}\n"
        f"- **Approver**: {approver}\n"
        f"- **Reason**: {reason or '(none provided)'}\n"
    )
    try:
        existing = status_file.read_text() if status_file.exists() else ""
        status_file.write_text(existing + override_block)
    except OSError:
        pass  # fail open: write failure is non-fatal


def _record_deliverable_override(
    project_dir: Path, phase: str, reason: str, approver: str
) -> None:
    """Append a deliverable override record to status.md."""
    status_file = project_dir / "phases" / phase / "status.md"
    timestamp = get_utc_timestamp()
    override_block = (
        f"\n## Deliverable Overrides\n\n"
        f"- **Date**: {timestamp}\n"
        f"- **Approver**: {approver}\n"
        f"- **Reason**: {reason or '(none provided)'}\n"
    )
    try:
        existing = status_file.read_text() if status_file.exists() else ""
        status_file.write_text(existing + override_block)
    except OSError:
        pass  # fail open: write failure is non-fatal


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
    approver: str = "user",
    override_gate: bool = False,
    override_reason: str = "",
    override_deliverables: bool = False,
    override_deliverables_reason: str = "",
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase and return next phase (or None if done).

    Performs gate checks and deliverable checks.
    Raises ValueError when gate enforcement blocks advancement.
    Caller (CLI handle_approve) catches this and exits non-zero.
    """
    phase = resolve_phase(phase)
    warnings: List[str] = []

    # Check 1: deliverables for the phase being approved — BLOCKING
    deliverable_issues = _check_phase_deliverables(state, phase)
    if deliverable_issues:
        if override_deliverables:
            project_dir_for_override = get_project_dir(state.name)
            _record_deliverable_override(project_dir_for_override, phase, override_deliverables_reason, approver)
            warnings.extend(deliverable_issues)
            warnings.append(
                f"Deliverable override applied for phase '{phase}'. "
                f"Reason: {override_deliverables_reason or '(none provided)'}"
            )
        else:
            missing = ", ".join(deliverable_issues)
            raise ValueError(
                f"Missing required deliverables for phase '{phase}': {missing}. "
                f"Create the deliverables before approving, "
                f"or use --override-deliverables --reason '<why>' to bypass."
            )

    # Check 2: gate_required from phases.json — now BLOCKING
    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})
    gate_required = phase_config.get("gate_required", False)

    # Initialize gate_result so post-block checks (emit, conditions manifest,
    # min-score validation) don't UnboundLocalError when the gate wasn't run
    # (e.g. --override-gate path).
    gate_result = None

    if gate_required:
        gate_override_allowed = phase_config.get("gate_override_allowed", True)
        project_dir = get_project_dir(state.name)
        rigor_tier = state.extras.get("rigor_tier")
        gate_run = _check_gate_run(project_dir, phase, rigor_tier=rigor_tier)

        if not gate_run:
            if override_gate and not gate_override_allowed:
                raise ValueError(
                    f"Gate override not allowed for phase '{phase}'. "
                    f"Run /wicked-garden:crew:gate before approving — "
                    f"QE must evaluate this phase."
                )
            elif override_gate:
                # Record the override in status.md for audit trail
                _record_gate_override(project_dir, phase, override_reason, approver)
                warnings.append(
                    f"Gate override applied for phase '{phase}'. "
                    f"Reason: {override_reason or '(none provided)'}"
                )
            else:
                # BLOCKING: raise ValueError — CLI exits non-zero, output shows to user
                raise ValueError(
                    f"Gate not run for phase '{phase}' (gate_required=true). "
                    f"Run /wicked-garden:crew:gate before approving, "
                    f"or use --override-gate --reason '<why>' to bypass."
                )
        else:
            # Gate was run — check if it passed or failed
            gate_result = _load_gate_result(project_dir, phase)

            # Check 2a: banned reviewer names (AC-1.4) — no override allowed
            if gate_result:
                reviewer_error = _validate_gate_reviewer(gate_result)
                if reviewer_error:
                    raise ValueError(reviewer_error)

            # Check 2a.1: consensus evaluation for high-complexity projects
            if gate_result:
                cg = _get_consensus_gate()
                _should_use = cg.get("should_use_consensus")
                _evaluate = cg.get("evaluate_consensus_gate")
                _write_evidence = cg.get("_write_consensus_evidence")

                if _should_use and _evaluate:
                    project_state_dict = asdict(state) if hasattr(state, '__dataclass_fields__') else {}
                    # Allow --consensus-threshold override stored in extras
                    effective_phase_config = dict(phase_config)
                    custom_threshold = (state.extras or {}).get("consensus_threshold")
                    if custom_threshold is not None:
                        effective_phase_config["consensus_threshold"] = custom_threshold

                    if _should_use(project_state_dict, effective_phase_config):
                        logger.info(
                            "[approve] Running consensus evaluation for phase '%s' "
                            "(complexity=%s, threshold=%s)",
                            phase,
                            state.complexity_score,
                            effective_phase_config.get("consensus_threshold"),
                        )
                        consensus_out = _evaluate(
                            str(project_dir), phase, project_state_dict, phases_config,
                        )
                        if consensus_out:
                            # Attach consensus metadata to gate result
                            gate_result["consensus"] = consensus_out

                            if consensus_out["result"] == "REJECT":
                                if _write_evidence:
                                    _write_evidence(project_dir, phase, consensus_out)
                                if not override_gate:
                                    raise ValueError(
                                        f"Gate REJECTED by consensus council: "
                                        f"{consensus_out.get('reason', 'strong dissent')}"
                                    )
                                else:
                                    _record_gate_override(
                                        project_dir, phase,
                                        f"Consensus REJECT overridden: {consensus_out.get('reason', '')}",
                                        approver,
                                    )
                                    warnings.append(
                                        f"Consensus REJECT overridden. "
                                        f"Reason: {override_reason or '(none provided)'}"
                                    )

                            elif consensus_out["result"] == "CONDITIONAL":
                                conditions = consensus_out.get("conditions", [])
                                if conditions:
                                    _write_conditions_manifest(
                                        project_dir, phase, conditions,
                                    )
                                    logger.info(
                                        "[approve] Consensus CONDITIONAL for '%s' — "
                                        "%d conditions written to manifest",
                                        phase, len(conditions),
                                    )

                            elif consensus_out["result"] == "APPROVE":
                                logger.info(
                                    "[approve] Consensus council APPROVED phase '%s' "
                                    "(confidence=%.2f, agreement=%.2f)",
                                    phase,
                                    consensus_out.get("consensus_confidence", 0),
                                    consensus_out.get("agreement_ratio", 0),
                                )

            if gate_result and gate_result.get("result") == "REJECT":
                if override_gate and not gate_override_allowed:
                    raise ValueError(
                        f"Gate override not allowed for phase '{phase}'. "
                        f"Resolve REJECT findings — QE must evaluate this phase."
                    )
                elif override_gate:
                    _record_gate_override(project_dir, phase, override_reason, approver)
                    warnings.append(f"Gate REJECT overridden. Reason: {override_reason or '(none provided)'}")
                else:
                    raise ValueError(
                        f"Gate returned REJECT for phase '{phase}'. "
                        f"Resolve findings before approving, "
                        f"or use --override-gate --reason '<why>' to bypass."
                    )

            # Check 2b: CONDITIONAL gate — write conditions manifest (AC-1.2)
            if gate_result and gate_result.get("result") == "CONDITIONAL":
                conditions = gate_result.get("conditions", [])
                if conditions:
                    _write_conditions_manifest(project_dir, phase, conditions)
                    logger.info(
                        f"[approve] CONDITIONAL gate for '{phase}' — "
                        f"{len(conditions)} conditions written to manifest"
                    )

            # Check 2c: minimum gate score (AC-1.3)
            if gate_result:
                score_error = _validate_min_gate_score(gate_result, phase, phases_config)
                if score_error:
                    if override_gate:
                        _record_gate_override(project_dir, phase, f"Score override: {score_error}", approver)
                        warnings.append(f"Score check overridden: {score_error}")
                    else:
                        raise ValueError(score_error)

    # Emit gate decision to wicked-bus
    if gate_result:
        try:
            from _bus import emit_event
            gate_decision = gate_result.get("result", "UNKNOWN")
            emit_event("wicked.gate.decided", {
                "project_id": state.name,
                "phase": phase,
                "result": gate_decision,
                "score": gate_result.get("score"),
                "reviewer": gate_result.get("reviewer"),
            }, chain_id=getattr(state, "chain_id", None))
            if gate_decision == "REJECT":
                emit_event("wicked.gate.blocked", {
                    "project_id": state.name,
                    "phase": phase,
                    "blocking_reason": gate_result.get("result"),
                }, chain_id=getattr(state, "chain_id", None))
                # Rework begins the moment a REJECT verdict is stored.
                # Bump a per-phase iteration counter (idempotent across reruns)
                # and fire wicked.rework.triggered alongside the block event.
                try:
                    iteration_count = _bump_rework_iteration(
                        get_project_dir(state.name), phase
                    )
                except Exception:
                    iteration_count = 1  # fail open — still emit with best-effort count
                emit_event("wicked.rework.triggered", {
                    "project_id": state.name,
                    "phase": phase,
                    "iteration_count": iteration_count,
                    "chain_id": getattr(state, "chain_id", None),
                }, chain_id=getattr(state, "chain_id", None))
        except Exception:
            pass  # fail open

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

    # Emit rich event to unified event log
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from _event_store import EventStore
        EventStore.ensure_schema()
        EventStore.append(
            domain="crew",
            action=f"phases.{phase}.approved",
            source="phases",
            record_id=state.name,
            project_id=state.name,
            payload={
                "phase": phase,
                "approver": approver,
                "gate_result": gate_result.get("result") if gate_result else None,
                "specialists_engaged": phase_state.specialists_engaged,
            } if gate_result else {"phase": phase, "approver": approver},
            tags=["phase-transition", f"phase:{phase}"],
        )
    except Exception:
        pass  # fire-and-forget

    # Emit to wicked-bus (additive — does not replace EventStore)
    try:
        from _bus import emit_event
        emit_event("wicked.phase.transitioned", {
            "project_id": state.name,
            "phase_from": phase,
            "phase_to": phase_order[phase_order.index(phase) + 1] if phase in phase_order and phase_order.index(phase) < len(phase_order) - 1 else None,
            "approver": approver,
            "gate_result": gate_result.get("result") if gate_result else None,
        }, chain_id=getattr(state, "chain_id", None))
    except Exception:
        pass  # fail open

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
            next_phase = phase_order[current_idx + 1]
            # Advance current_phase so callers and saved state reflect the new phase
            state.current_phase = next_phase
            return (state, next_phase)

    # No next phase — project is complete.
    # Emit wicked.project.completed alongside the final phase transition.
    try:
        from _bus import emit_event
        duration_secs: Optional[float] = None
        try:
            created_raw = (state.created_at or "").replace("Z", "+00:00")
            if created_raw:
                created_dt = datetime.fromisoformat(created_raw)
                now_dt = datetime.now(timezone.utc)
                duration_secs = max(0.0, (now_dt - created_dt).total_seconds())
        except (ValueError, AttributeError):
            duration_secs = None  # fail open on malformed timestamps
        emit_event("wicked.project.completed", {
            "project_id": state.name,
            "duration_secs": duration_secs,
            "chain_id": getattr(state, "chain_id", None),
            "final_phase": phase,
        }, chain_id=getattr(state, "chain_id", None))
    except Exception:
        pass  # fail open

    return (state, None)


def skip_phase(state: ProjectState, phase: str, reason: str = "", approved_by: str = "auto") -> ProjectState:
    """Skip a phase. Checks is_skippable and skip_complexity_threshold from phases.json."""
    phase = resolve_phase(phase)

    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})
    if not phase_config.get("is_skippable", True):
        raise ValueError(f"Phase '{phase}' cannot be skipped (is_skippable=false)")

    # Complexity guard: block skip if project complexity exceeds threshold (AC-3.2)
    if GATE_ENFORCEMENT_MODE != "legacy":
        skip_threshold = phase_config.get("skip_complexity_threshold")
        if skip_threshold is not None:
            complexity = getattr(state, "complexity_score", 0) or 0
            if complexity >= skip_threshold:
                raise ValueError(
                    f"Phase '{phase}' cannot be skipped at complexity {complexity} "
                    f"(skip_complexity_threshold={skip_threshold}). "
                    f"The phase is required at this complexity level."
                )

    # Structured skip reason validation (AC-4.2)
    if GATE_ENFORCEMENT_MODE != "legacy":
        valid_reasons = phase_config.get("valid_skip_reasons")
        if valid_reasons:
            reason_lower = (reason or "").lower().strip()
            matched = any(
                reason_lower == vr.lower() or reason_lower.startswith(vr.lower())
                for vr in valid_reasons
                if reason_lower
            )
            if not reason_lower or not matched:
                raise ValueError(
                    f"Skip reason '{reason}' is not recognized for phase '{phase}'. "
                    f"Valid skip reasons: {', '.join(valid_reasons)}"
                )

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


def create_project(
    name: str,
    description: str = "",
    initial_data: Optional[Dict[str, Any]] = None,
) -> Tuple[ProjectState, Path]:
    """Create a new project with DomainStore persistence and local directory.

    Args:
        name: Project name (kebab-case, validated)
        description: Human-readable project description
        initial_data: Optional dict of initial fields (signals, complexity, etc.)

    Returns:
        (state, project_dir) tuple

    Raises:
        ValueError: If name is invalid or project already exists
    """
    if not is_safe_project_name(name):
        raise ValueError(f"Invalid project name: {name}. Use only alphanumeric, hyphens, underscores (max 64 chars).")

    existing = _sm.get("projects", name)
    if existing:
        raise ValueError(f"Project already exists: {name}")

    # Build initial state — workspace scopes the project to the current folder
    workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
    state = ProjectState(
        name=name,
        current_phase="clarify",
        created_at=get_utc_timestamp(),
        workspace=workspace,
    )

    # Merge initial_data if provided
    if initial_data:
        state = _merge_data_into_state(state, initial_data)

    if description:
        state.extras["description"] = description

    # Start clarify phase
    state = start_phase(state, "clarify")

    # Persist via DomainStore (local JSON)
    save_project_state(state)

    # Create local directory structure for deliverables
    project_dir = get_project_dir(name)
    project_dir.mkdir(parents=True, exist_ok=True)

    phase_dir = project_dir / "phases" / "clarify"
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Write template files for human readability
    project_md = project_dir / "project.md"
    if not project_md.exists():
        title = name.replace("-", " ").title()
        project_md.write_text(
            f"---\n"
            f"name: {name}\n"
            f"created: {state.created_at}\n"
            f"current_phase: clarify\n"
            f"status: in_progress\n"
            f"---\n\n"
            f"# Project: {title}\n\n"
            f"{description or 'No description provided.'}\n"
        )

    outcome_md = project_dir / "outcome.md"
    if not outcome_md.exists():
        outcome_md.write_text(
            f"# Outcome: {name.replace('-', ' ').title()}\n\n"
            f"## Desired Outcome\n\n"
            f"{{To be defined during clarify phase}}\n\n"
            f"## Success Criteria\n\n"
            f"1. {{To be defined}}\n\n"
            f"## Scope\n\n"
            f"### In Scope\n- {{To be defined}}\n\n"
            f"### Out of Scope\n- {{To be defined}}\n"
        )

    status_md = phase_dir / "status.md"
    if not status_md.exists():
        status_md.write_text(
            f"---\n"
            f"phase: clarify\n"
            f"status: in_progress\n"
            f"started: {state.created_at}\n"
            f"---\n\n"
            f"# Clarify Phase\n\n"
            f"Defining the outcome and success criteria.\n\n"
            f"## Deliverables\n\n"
            f"- [ ] Outcome statement\n"
            f"- [ ] Success criteria\n"
            f"- [ ] Scope boundaries\n"
        )

    # Emit project creation event
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from _event_store import EventStore
        EventStore.ensure_schema()
        EventStore.append(
            domain="crew",
            action="projects.created",
            source="projects",
            record_id=name,
            project_id=name,
            payload={"name": name, "description": description, "complexity_score": state.complexity_score},
            tags=["project-lifecycle"],
        )
    except Exception:
        pass  # fail open

    # Emit to wicked-bus
    try:
        from _bus import emit_event
        emit_event("wicked.project.created", {
            "project_id": name,
            "complexity_score": state.complexity_score,
        }, chain_id=getattr(state, "chain_id", None))
    except Exception:
        pass  # fail open

    return (state, project_dir)


def update_project(
    state: ProjectState,
    data: Dict[str, Any],
) -> Tuple[ProjectState, List[str]]:
    """Update project state fields from a data dict.

    Merges known fields into ProjectState attributes.
    Unknown fields go into extras.
    Does NOT overwrite phases dict (use start/complete/approve/skip for that).

    Returns:
        (updated_state, list_of_updated_field_names)
    """
    state = _merge_data_into_state(state, data)
    updated = [k for k in data.keys() if k != "phases"]
    save_project_state(state)
    return (state, updated)


def _merge_data_into_state(state: ProjectState, data: Dict[str, Any]) -> ProjectState:
    """Merge a data dict into ProjectState fields."""
    known_fields = {
        "signals_detected", "complexity_score", "specialists_recommended",
        "phase_plan",
        "current_phase", "version", "cp_project_id",
    }

    for key, value in data.items():
        if key == "phases":
            continue  # phases have dedicated state machine methods
        if key in known_fields:
            if key == "phase_plan" and isinstance(value, list):
                value = [resolve_phase(p) for p in value]
            setattr(state, key, value)
        else:
            state.extras[key] = value

    return state


def main():
    """CLI interface for phase management."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase manager for wicked-crew")
    parser.add_argument("project", help="Project name")
    parser.add_argument("action", choices=["status", "start", "complete", "approve", "skip", "can-advance", "validate", "create", "update", "advance"])
    parser.add_argument("--phase", help="Target phase")
    parser.add_argument("--reason", help="Reason for skip or gate override")
    parser.add_argument("--approved-by", default=None, help="Approver identity (default: 'auto' for skip, 'user' for approve)")
    parser.add_argument(
        "--override-gate",
        action="store_true",
        default=False,
        help="Bypass gate enforcement for approve action (requires --reason)"
    )
    parser.add_argument(
        "--override-deliverables",
        action="store_true",
        default=False,
        help="Bypass deliverable enforcement for approve action (requires --reason)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--description", default="", help="Project description (for create)")
    parser.add_argument("--data", default=None, help="JSON string of fields to set/update")

    args = parser.parse_args()

    # Enforce --reason when --override-gate is passed (check before project lookup)
    if getattr(args, "override_gate", False) and args.action in ("approve", "advance"):
        if not (args.reason and args.reason.strip()):
            print(
                "Error: --override-gate requires --reason. "
                "Provide a meaningful explanation, e.g.: "
                "--reason 'Gate ran externally via codex; result: APPROVE'",
                file=sys.stderr,
            )
            sys.exit(1)

    # Enforce --reason when --override-deliverables is passed (check before project lookup)
    if getattr(args, "override_deliverables", False) and args.action in ("approve", "advance"):
        if not (args.reason or "").strip():
            print(
                "Error: --override-deliverables requires --reason. "
                "Provide a reason for bypassing deliverable checks.",
                file=sys.stderr,
            )
            sys.exit(1)

    state = load_project_state(args.project)
    if not state and args.action not in ("status", "create"):
        print(json.dumps({"ok": False, "error": f"Project not found: {args.project}"}) if args.json else f"Project not found: {args.project}")
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
                print(f"Use '/wicked-garden:crew:archive {args.project} --unarchive' to unarchive first.")
                return
        except (json.JSONDecodeError, OSError):
            pass  # fail open: invalid project state skipped

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
        try:
            state, next_phase = approve_phase(
                state,
                phase,
                approver=args.approved_by or "user",
                override_gate=args.override_gate,
                override_reason=args.reason or "",
                override_deliverables=args.override_deliverables,
                override_deliverables_reason=args.reason or "",
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
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

    elif args.action == "create":
        initial_data = None
        if args.data:
            try:
                initial_data = json.loads(args.data)
            except json.JSONDecodeError as e:
                print(json.dumps({"ok": False, "error": f"Invalid --data JSON: {e}"}) if args.json else f"Error: Invalid --data JSON: {e}")
                return

        try:
            state, project_dir = create_project(args.project, args.description, initial_data)
        except ValueError as e:
            print(json.dumps({"ok": False, "error": str(e)}) if args.json else f"Error: {e}")
            return

        if args.json:
            print(json.dumps({
                "ok": True,
                "project": {
                    "name": state.name,
                    "current_phase": state.current_phase,
                    "created_at": state.created_at,
                    "complexity_score": state.complexity_score,
                    "signals_detected": state.signals_detected,
                    "phase_plan": state.phase_plan,
                    "specialists_recommended": state.specialists_recommended,
                    "cp_project_id": state.cp_project_id,
                },
                "project_dir": str(project_dir),
                "phase_started": "clarify",
            }, indent=2))
        else:
            print(f"Created project: {state.name}")
            print(f"Phase: clarify (in_progress)")
            print(f"Dir: {project_dir}")

    elif args.action == "update":
        if not args.data:
            print(json.dumps({"ok": False, "error": "--data required for update"}) if args.json else "Error: --data required for update")
            return
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"Invalid --data JSON: {e}"}) if args.json else f"Error: Invalid --data JSON: {e}")
            return

        state, updated_fields = update_project(state, data)
        if args.json:
            print(json.dumps({
                "ok": True,
                "project": {
                    "name": state.name,
                    "current_phase": state.current_phase,
                    "complexity_score": state.complexity_score,
                    "signals_detected": state.signals_detected,
                    "phase_plan": state.phase_plan,
                    "specialists_recommended": state.specialists_recommended,
                },
                "updated_fields": updated_fields,
            }, indent=2))
        else:
            print(f"Updated project: {state.name}")
            print(f"Fields: {', '.join(updated_fields)}")

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
                if warnings:
                    print("Phase plan validation completed with warnings:")
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

    elif args.action == "advance":
        # Approve current phase, then start the next phase in one step.
        phase = args.phase or state.current_phase
        approved_phase = resolve_phase(phase)
        try:
            state, next_phase = approve_phase(
                state,
                approved_phase,
                approver=args.approved_by or "user",
                override_gate=args.override_gate,
                override_reason=args.reason or "",
                override_deliverables=args.override_deliverables,
                override_deliverables_reason=args.reason or "",
            )
        except ValueError as e:
            if args.json:
                print(json.dumps({"ok": False, "approved_phase": approved_phase, "error": str(e)}))
            else:
                print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if next_phase is None:
            save_project_state(state)
            if args.json:
                print(json.dumps({
                    "ok": True,
                    "approved_phase": approved_phase,
                    "next_phase": None,
                    "message": "Project complete — no next phase",
                }))
            else:
                print(f"Approved phase: {approved_phase}")
                print("Project complete!")
            return

        state = start_phase(state, next_phase)
        save_project_state(state)

        if args.json:
            print(json.dumps({
                "ok": True,
                "approved_phase": approved_phase,
                "next_phase": next_phase,
                "current_phase": state.current_phase,
            }))
        else:
            print(f"Approved phase: {approved_phase}")
            print(f"Started phase: {next_phase}")


if __name__ == "__main__":
    main()
