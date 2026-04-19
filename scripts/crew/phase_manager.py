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
# Gate enforcement mode
# ---------------------------------------------------------------------------
# v6.0 is strict-only. Gate enforcement is unconditionally active.
# The legacy escape hatch was removed in v6.0 (D3 — no backward compat flag).
# Legacy projects should be upgraded with /wicked-garden:adopt-legacy.
GATE_ENFORCEMENT_MODE: str = "strict"

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


# ---------------------------------------------------------------------------
# Gate-policy loader (D1, D4) — codified Gate x Rigor reviewer matrix
# ---------------------------------------------------------------------------

_GATE_POLICY_CACHE: "dict | None" = None


def _load_gate_policy() -> dict:
    """Load gate-policy.json once; cache for the process lifetime.

    Raises FileNotFoundError if the file is missing (fail-closed per architect §9).
    Raises json.JSONDecodeError if the file is malformed.
    """
    global _GATE_POLICY_CACHE
    if _GATE_POLICY_CACHE is not None:
        return _GATE_POLICY_CACHE
    policy_path = _get_plugin_root() / ".claude-plugin" / "gate-policy.json"
    if not policy_path.exists():
        raise FileNotFoundError(
            f"gate-policy.json not found at {policy_path}. "
            "This is a configuration error — restore the file from git."
        )
    _GATE_POLICY_CACHE = json.loads(policy_path.read_text(encoding="utf-8"))
    return _GATE_POLICY_CACHE


def _resolve_gate_reviewer(gate_name: str, rigor_tier: str) -> dict:
    """Return the dispatch block for a (gate_name, rigor_tier) pair (D1, D4).

    Args:
        gate_name:  One of the 6 defined gates (e.g. 'requirements-quality').
        rigor_tier: One of 'minimal', 'standard', 'full'.

    Returns:
        dict with keys: reviewers (list), mode (str), fallback (str).

    Raises:
        ValueError: If gate_name or rigor_tier is unknown.
        FileNotFoundError: If gate-policy.json is missing (configuration error).
    """
    policy = _load_gate_policy()
    gates = policy.get("gates", {})
    if gate_name not in gates:
        raise ValueError(
            f"Unknown gate '{gate_name}' in gate-policy.json. "
            f"Known gates: {sorted(gates.keys())}"
        )
    tier_map = gates[gate_name]
    if rigor_tier not in tier_map:
        raise ValueError(
            f"Unknown rigor_tier '{rigor_tier}' for gate '{gate_name}'. "
            f"Valid tiers: {sorted(tier_map.keys())}"
        )
    return tier_map[rigor_tier]


# ---------------------------------------------------------------------------
# Startup validation (SC-4) — full-rigor gates must declare non-empty reviewers
# ---------------------------------------------------------------------------


class ConfigError(ValueError):
    """Raised on a mis-configured gate-policy.json (e.g. empty full-rigor reviewers).

    Subclass of ValueError so existing callers that catch ValueError continue
    to degrade gracefully, while new callers can discriminate config errors.
    """


_GATE_POLICY_FULL_VALIDATED: bool = False


def _validate_gate_policy_full_rigor() -> None:
    """Raise ConfigError if any gate at 'full' rigor has an empty reviewers list.

    Runs once per process invocation; result cached in module-level flag
    ``_GATE_POLICY_FULL_VALIDATED``. Called lazily from
    ``phase_manager.execute()`` and ``approve_phase()`` entry points.

    Rationale (SC-4 / CHL-04): silent fallback to the fast gate-evaluator at
    full rigor is a correctness bug — the user asked for specialist council
    scrutiny. Hard validation surfaces the misconfiguration immediately.

    Behaviour:
        - Each gate's ``full.reviewers`` list (when ``full`` tier is defined)
          MUST be non-empty.
        - Gates without a ``full`` tier are skipped (they do not advertise
          full-rigor support).
    """
    global _GATE_POLICY_FULL_VALIDATED
    if _GATE_POLICY_FULL_VALIDATED:
        return
    try:
        policy = _load_gate_policy()
    except FileNotFoundError:
        # gate-policy.json missing is handled elsewhere; this validator only
        # inspects a loadable policy.
        return
    for gate_name, tiers in (policy.get("gates") or {}).items():
        if not isinstance(tiers, dict):
            continue
        full = tiers.get("full")
        if not isinstance(full, dict):
            continue
        reviewers = full.get("reviewers")
        if isinstance(reviewers, list) and len(reviewers) == 0:
            raise ConfigError(
                f"Gate policy for '{gate_name}' at full rigor has empty "
                f"reviewers — full rigor requires at least one reviewer, "
                f"found none. Configure reviewers or remove the full tier."
            )
    _GATE_POLICY_FULL_VALIDATED = True


# ---------------------------------------------------------------------------
# Dispatch-mode detection (CR-2 / AC-α11) — in-flight cutover rule
# ---------------------------------------------------------------------------


_DISPATCH_MODE_VALID = ("mode-3", "v6-legacy", "v5")
_DISPATCH_MODE_DEFAULT_LEGACY = "v6-legacy"
_DISPATCH_MODE_DEFAULT_FRESH = "mode-3"


def _detect_dispatch_mode(state: "ProjectState") -> str:
    """Return the dispatch mode for a project (reads + backfills).

    Reads ``state.extras['dispatch_mode']`` if present. When absent, inspects
    the project directory for mode-3 evidence (``phases/{phase}/reeval-log.jsonl``
    or ``phases/{phase}/executor-status.json``) and returns ``"mode-3"`` when
    any is found, else ``"v6-legacy"``. Writes the detected value back to
    ``state.extras`` (caller persists via ``save_project_state``).

    Safety: on any unexpected error, returns ``"v6-legacy"`` (preserves
    existing behavior; mode-3 is opt-in).
    """
    try:
        extras = getattr(state, "extras", None) or {}
        stored = extras.get("dispatch_mode")
        if isinstance(stored, str) and stored in _DISPATCH_MODE_VALID:
            return stored

        # Backfill path — inspect project dir for mode-3 evidence.
        project_dir = get_project_dir(state.name)
        phases_dir = project_dir / "phases"
        detected = _DISPATCH_MODE_DEFAULT_LEGACY
        if phases_dir.is_dir():
            for phase_dir in phases_dir.iterdir():
                if not phase_dir.is_dir():
                    continue
                if (phase_dir / "reeval-log.jsonl").exists() or (
                    phase_dir / "executor-status.json"
                ).exists():
                    detected = _DISPATCH_MODE_DEFAULT_FRESH
                    break
        extras["dispatch_mode"] = detected
        state.extras = extras
        return detected
    except Exception:  # noqa: BLE001 — safety: fail-safe default
        return _DISPATCH_MODE_DEFAULT_LEGACY


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
    """
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

    """
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
    """
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


_VALID_REANALYSIS_DIRECTIONS = frozenset({"augment", "prune", "re_tier"})

# AC-9: at most N augment mutations may be applied per phase across the project
# lifetime.  Excess augments are deferred with why="augment-cap-exceeded" and
# surfaced as open questions only — they do NOT spawn new TaskCreate calls.
# The cap guards against runaway plan growth at phase-end checkpoints.
_AUGMENT_CAP_PER_PHASE: int = 2
_AUGMENT_CAP_DEFER_REASON: str = "augment-cap-exceeded"


def _count_prior_augments_for_phase(
    project_dir: "Path | None",
    phase: str,
) -> int:
    """Count previously-applied augment mutations for ``phase``.

    Reads ``process-plan.addendum.jsonl`` via ``reeval_addendum.read`` and
    tallies every ``{"op": "augment", ...}`` entry in ``mutations_applied``
    across records whose ``chain_id`` targets ``phase``.  Missing file /
    unreadable records return 0 (fail-open — the write path will still
    enforce the cap on the new record).
    """
    if project_dir is None:
        return 0
    try:
        from reeval_addendum import read as _read_addendum
    except ImportError:
        return 0
    try:
        records = _read_addendum(project_dir, phase_filter=phase)
    except Exception:  # fail-open on any I/O or parse error
        return 0
    count = 0
    for rec in records:
        applied = rec.get("mutations_applied") or []
        if not isinstance(applied, list):
            continue
        for m in applied:
            if isinstance(m, dict) and m.get("op") == "augment":
                count += 1
    return count


def _apply_augment_cap(
    mutations: "List[Dict[str, Any]]",
    prior_count: int,
    cap: int = _AUGMENT_CAP_PER_PHASE,
) -> "Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]":
    """Split ``mutations`` into (applied, deferred) enforcing the augment cap.

    Non-augment mutations pass through to ``applied`` unchanged.  Augments
    fill the remaining budget (``cap - prior_count``); excess augments are
    cloned into ``deferred`` with ``why`` overwritten to
    ``"augment-cap-exceeded"``.
    """
    applied: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    remaining = max(0, cap - prior_count)
    for m in mutations:
        if not isinstance(m, dict):
            continue
        if m.get("op") != "augment":
            applied.append(m)
            continue
        if remaining > 0:
            applied.append(m)
            remaining -= 1
        else:
            deferred_m = dict(m)
            deferred_m["why"] = _AUGMENT_CAP_DEFER_REASON
            deferred.append(deferred_m)
    return (applied, deferred)


def _run_checkpoint_reanalysis(
    state: "ProjectState",
    phase: str,
    direction: "str | None" = None,
    _reeval_fn=None,
) -> "Tuple[List[str], List[str]]":
    """At checkpoint phases, re-validate the phase plan and inject missing phases.

    Args:
        state:      Current project state.
        phase:      Phase name being approved.
        direction:  Optional mutation direction hint.  When provided, must be one
                    of 'augment', 'prune', 're_tier'.  Unknown values raise
                    ValueError immediately (AC-4 enforcement — silent no-op is
                    NOT acceptable).
        _reeval_fn: Optional dependency-injection shim for acceptance tests.
                    Defaults to None (real facilitator call path); tests can pass
                    a callable ``(state, phase) -> addendum_dict`` returning a
                    fixture addendum.  When provided, the returned record's
                    ``mutations`` list is capped to at most
                    ``_AUGMENT_CAP_PER_PHASE`` augments per phase and the
                    record's ``mutations_applied`` / ``mutations_deferred``
                    fields are rewritten in-place (AC-9).

    Returns:
        (injected_phases, warnings)

    Raises:
        ValueError: If direction is not in the allowed set.
    """
    # AC-4: validate direction eagerly before touching any state
    if direction is not None and direction not in _VALID_REANALYSIS_DIRECTIONS:
        raise ValueError(
            f"Invalid re-analysis direction '{direction}'. "
            f"Valid values: {sorted(_VALID_REANALYSIS_DIRECTIONS)}"
        )

    phases_config = load_phases_config()
    phase_config = phases_config.get(phase, {})

    if not phase_config.get("checkpoint", False):
        return ([], [])

    logger.info(
        "[checkpoint] Phase '%s' is a checkpoint — running phase plan re-validation "
        "(direction=%s)",
        phase, direction,
    )

    # AC-9: augment cap enforcement.  If a re-eval function is injected, run
    # it, then cap the returned mutations to at most _AUGMENT_CAP_PER_PHASE
    # augments per phase.  Excess augments are deferred with
    # why="augment-cap-exceeded" — they do not spawn new TaskCreate calls.
    cap_warnings: List[str] = []
    if _reeval_fn is not None:
        try:
            record = _reeval_fn(state, phase)
        except Exception as exc:  # fail-open: cap logic must not block approve
            logger.warning("[checkpoint] _reeval_fn raised %s — skipping cap", exc)
            record = None
        if isinstance(record, dict):
            mutations = record.get("mutations") or []
            if isinstance(mutations, list) and mutations:
                try:
                    project_dir = get_project_dir(state.name)
                except (ValueError, Exception):
                    project_dir = None  # fail-open on path errors
                prior_count = _count_prior_augments_for_phase(project_dir, phase)
                applied, deferred = _apply_augment_cap(mutations, prior_count)
                # Rewrite the record's applied/deferred fields so downstream
                # writers (e.g., reeval_addendum.append) see the capped state.
                record["mutations_applied"] = applied
                # Preserve any pre-existing deferrals (non-cap reasons) and
                # append the cap-exceeded ones.
                existing_deferred = record.get("mutations_deferred") or []
                if not isinstance(existing_deferred, list):
                    existing_deferred = []
                record["mutations_deferred"] = existing_deferred + deferred
                if deferred:
                    cap_warnings.append(
                        f"augment-cap-exceeded: {len(deferred)} augment mutation(s) "
                        f"deferred for phase '{phase}' "
                        f"(cap={_AUGMENT_CAP_PER_PHASE}, prior={prior_count})"
                    )

    injected, warnings = validate_phase_plan(state)
    return (injected, warnings + cap_warnings)


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

        # Content validation (AC-1.5)
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
    """Load, validate, and orphan-check ``gate-result.json`` for a phase.

    **Contract shift (design-addendum-1 D-7 / #479):** this function
    previously returned ``None`` on ``json.JSONDecodeError``. It now
    **raises** :class:`gate_result_schema.GateResultSchemaError`
    instead. Returning ``None`` silently caused the exact bypass that
    #479 / #471 close — a malformed gate-result would slip through
    ``approve_phase`` as "gate not run". Callers must handle the
    exception explicitly (typically surfacing as a rejection).

    The ``None`` return is preserved when the file does not exist —
    that path still means "no gate run for this phase".

    Layered defenses (all increments of #471 stack here):
      1. Schema validator (AC-1..AC-4, AC-10 env-var bypass)
      2. Content sanitizer (AC-5, AC-6)
      3. Dispatch-log orphan detection (AC-7) — soft-window until
         ``WG_GATE_RESULT_STRICT_AFTER``, then REJECT.
      4. Audit-log write on every reject path (AC-8).
      5. Content-hash memoization cache (AC-11; ``WG_GATE_RESULT_CACHE``
         =off for debug).
    """
    gate_file = project_dir / "phases" / phase / "gate-result.json"
    if not gate_file.exists():
        return None

    # Lazy imports keep hook-path cost low and avoid cycles.
    from gate_result_schema import (
        GateResultAuthorizationError,
        GateResultSchemaError,
        validate_gate_result_from_file,
    )
    from gate_ingest_audit import append_audit_entry
    from dispatch_log import check_orphan

    try:
        raw_bytes = gate_file.read_bytes()
    except OSError as exc:
        logger.warning(
            "[phase-manager] gate-result.json unreadable for phase '%s': %s",
            phase, exc,
        )
        return None

    try:
        parsed = validate_gate_result_from_file(gate_file)
    except GateResultSchemaError as exc:
        # Audit the reject path (AC-8). Failures here are logged to
        # stderr by the audit module — reject still propagates.
        event = (
            "sanitization_violation" if exc.violation_class == "content"
            else (
                "malformed_json"
                if exc.reason.startswith("malformed-json:")
                else "schema_violation"
            )
        )
        append_audit_entry(
            project_dir, phase,
            event=event,
            reason=exc.reason,
            offending_field=exc.offending_field,
            offending_value=exc.offending_value_excerpt,
            raw_bytes=raw_bytes,
        )
        raise

    # Orphan detection (AC-7) — soft-window: warn + allow pre-cutover,
    # REJECT post-cutover. Schema + content violations still REJECT
    # unconditionally (caught above).
    try:
        check_orphan(parsed, project_dir, phase)
    except GateResultAuthorizationError as exc:
        today = datetime.now(timezone.utc).date()
        from dispatch_log import _get_strict_after_date
        if today >= _get_strict_after_date():
            # Strict mode — hard reject, like schema/content violations.
            append_audit_entry(
                project_dir, phase,
                event="unauthorized_dispatch",
                reason=exc.reason,
                offending_field=exc.offending_field,
                offending_value=exc.offending_value_excerpt,
                raw_bytes=raw_bytes,
            )
            raise
        # Soft window — audit as "accepted_legacy" and fall through.
        append_audit_entry(
            project_dir, phase,
            event="unauthorized_dispatch_accepted_legacy",
            reason=exc.reason,
            offending_field=exc.offending_field,
            offending_value=exc.offending_value_excerpt,
            raw_bytes=raw_bytes,
        )

    return parsed


# ---------------------------------------------------------------------------
# BLEND-RULE gate dispatch helpers (design §3, AC-α3 / FR-α3.1..FR-α3.5)
#
# `_dispatch_gate_reviewer()` is the main entry point. It reads the
# `gate-policy.json` entry for `{gate_name, rigor_tier}` and routes to one
# of four sub-helpers based on the policy's `mode`:
#
#   - `_dispatch_fast_evaluator`    (self-check | advisory | empty reviewers)
#   - `_dispatch_sequential`        (mode: sequential — stops on first REJECT)
#   - `_dispatch_parallel_and_merge` (mode: parallel — single-batch dispatch,
#                                     merged via REJECT > CONDITIONAL > APPROVE)
#   - `_dispatch_council`           (mode: council — parallel + plurality)
#
# Since Task/Agent dispatching from within a Python script is
# environment-dependent (not always available in unit tests or CLI subshells),
# every helper accepts an injectable `dispatcher` callable with shape
# `(subagent_type, prompt, context) -> dict`. Callers supply the real
# orchestrator in production; tests supply a mock. When `dispatcher` is None,
# helpers return a conservative CONDITIONAL stub with
# `reason: "dispatcher-unavailable"` so callers can fall back to the existing
# disk-based `gate-result.json` contract without blowing up.
#
# Merge rule (per design §3):
#   - Any banned reviewer identity  -> REJECT "banned-reviewer"
#   - Any REJECT                    -> REJECT (safety bias)
#   - No REJECT, any CONDITIONAL    -> CONDITIONAL (union conditions)
#   - All APPROVE                   -> APPROVE
#   - Score = min of per-reviewer scores (conservative)
# ---------------------------------------------------------------------------


def _banned_reviewer_error(reviewer: str) -> Optional[str]:
    """Return a reason string if `reviewer` is banned; None otherwise.

    Mirrors _validate_gate_reviewer() logic but returns a short tag suitable
    for embedding in a synthesized gate_result.
    """
    if not reviewer:
        return None
    r = reviewer.lower().strip()
    if r in (name.lower() for name in BANNED_REVIEWER_NAMES):
        return f"banned-reviewer:{reviewer}"
    for prefix in BANNED_REVIEWER_PREFIXES:
        if r.startswith(prefix.lower()):
            return f"banned-reviewer:{reviewer}"
    return None


def _empty_verdict_stub(
    gate_name: str, phase: str, reason: str, *, reviewer: str = "phase-manager"
) -> Dict[str, Any]:
    """Return a conservative CONDITIONAL gate_result used when dispatch
    is unavailable. Callers may treat this as "no decision made"."""
    return {
        "verdict": "CONDITIONAL",
        "score": 0.0,
        "min_score": 0.0,
        "reviewer": reviewer,
        "reason": reason,
        "timestamp": get_utc_timestamp(),
        "conditions": [],
        "gate_name": gate_name,
        "phase": phase,
        "per_reviewer_verdicts": [],
        "reviewers_dispatched": [],
        "dispatch_mode": "stub",
        "external_review": False,
    }


def _normalize_reviewer_result(
    raw: Any, *, reviewer: str
) -> Dict[str, Any]:
    """Normalize a reviewer's output into the canonical verdict shape.

    Accepts a dict from the dispatcher with keys like
    `{verdict|result, score, reason, conditions}` and produces:
        {reviewer, verdict, score, reason, conditions}
    Unknown / missing values degrade to CONDITIONAL with score 0.
    """
    if not isinstance(raw, dict):
        return {
            "reviewer": reviewer,
            "verdict": "CONDITIONAL",
            "score": 0.0,
            "reason": "malformed-reviewer-output",
            "conditions": [],
        }
    verdict = str(raw.get("verdict") or raw.get("result") or "CONDITIONAL").upper()
    if verdict not in ("APPROVE", "CONDITIONAL", "REJECT"):
        verdict = "CONDITIONAL"
    try:
        score = float(raw.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    conditions = raw.get("conditions") or []
    if not isinstance(conditions, list):
        conditions = []
    return {
        "reviewer": raw.get("reviewer") or reviewer,
        "verdict": verdict,
        "score": score,
        "reason": raw.get("reason") or "",
        "conditions": conditions,
    }


def _merge_reviewer_verdicts(
    per_reviewer: List[Dict[str, Any]],
    *,
    gate_name: str,
    phase: str,
    dispatch_mode: str,
) -> Dict[str, Any]:
    """Apply the BLEND-RULE merge to a list of normalized reviewer results.

    Rules (design §3):
      - Any banned identity        -> REJECT "banned-reviewer"
      - Any REJECT                 -> REJECT
      - No REJECT, any CONDITIONAL -> CONDITIONAL (union conditions)
      - All APPROVE                -> APPROVE
      - Merged score               -> min of scores (conservative)
    """
    if not per_reviewer:
        return _empty_verdict_stub(
            gate_name, phase, "no-reviewer-results", reviewer="phase-manager"
        )

    # 1. Banned reviewer short-circuit (highest priority).
    for pr in per_reviewer:
        banned = _banned_reviewer_error(pr.get("reviewer", ""))
        if banned:
            return {
                "verdict": "REJECT",
                "score": 0.0,
                "min_score": 0.0,
                "reviewer": pr.get("reviewer", ""),
                "reason": banned,
                "timestamp": get_utc_timestamp(),
                "conditions": [],
                "gate_name": gate_name,
                "phase": phase,
                "per_reviewer_verdicts": per_reviewer,
                "reviewers_dispatched": [p.get("reviewer", "") for p in per_reviewer],
                "dispatch_mode": dispatch_mode,
                "external_review": len(per_reviewer) > 1,
            }

    verdicts = [pr["verdict"] for pr in per_reviewer]
    scores = [pr["score"] for pr in per_reviewer]
    merged_score = min(scores) if scores else 0.0
    reviewers = [pr.get("reviewer", "") for pr in per_reviewer]
    union_conditions: List[Any] = []
    reasons: List[str] = []
    for pr in per_reviewer:
        union_conditions.extend(pr.get("conditions", []))
        if pr.get("reason"):
            reasons.append(f"{pr.get('reviewer', '?')}: {pr['reason']}")

    if "REJECT" in verdicts:
        merged_verdict = "REJECT"
    elif "CONDITIONAL" in verdicts:
        merged_verdict = "CONDITIONAL"
    else:
        merged_verdict = "APPROVE"

    return {
        "verdict": merged_verdict,
        "result": merged_verdict,  # legacy alias consumed by approve_phase
        "score": merged_score,
        "min_score": merged_score,
        "reviewer": reviewers[0] if reviewers else "phase-manager",
        "reason": "; ".join(reasons) if reasons else merged_verdict,
        "timestamp": get_utc_timestamp(),
        "conditions": union_conditions,
        "gate_name": gate_name,
        "phase": phase,
        "per_reviewer_verdicts": per_reviewer,
        "reviewers_dispatched": reviewers,
        "dispatch_mode": dispatch_mode,
        "external_review": len(per_reviewer) > 1,
    }


def _dispatch_fast_evaluator(
    state: Optional["ProjectState"],
    phase: str,
    gate_name: str,
    *,
    dispatcher: Optional[Any] = None,
    fallback_reviewer: str = "gate-evaluator",
) -> Dict[str, Any]:
    """Fast-path dispatcher for self-check / advisory / empty-reviewers gates.

    Dispatches the `gate-evaluator` agent with a deliverable-summary context
    and returns a normalized gate_result. When `dispatcher` is None (unit
    tests / CLI shells without Task tool), returns a CONDITIONAL stub.
    """
    ctx = {
        "gate_name": gate_name,
        "phase": phase,
        "project": getattr(state, "name", None) if state is not None else None,
        "mode": "fast-evaluator",
    }
    if dispatcher is None:
        return _empty_verdict_stub(
            gate_name, phase, "dispatcher-unavailable", reviewer=fallback_reviewer
        )
    try:
        raw = dispatcher(
            "wicked-garden:crew:gate-evaluator",
            (
                f"Evaluate gate '{gate_name}' for phase '{phase}'. "
                "Read gate-policy.json for objective thresholds and the "
                f"deliverables under phases/{phase}/. Emit verdict + score + "
                "reason + conditions."
            ),
            ctx,
        )
    except Exception as exc:  # pragma: no cover — defensive
        return _empty_verdict_stub(
            gate_name, phase, f"dispatch-error:{exc}", reviewer=fallback_reviewer
        )
    norm = _normalize_reviewer_result(raw, reviewer=fallback_reviewer)
    return _merge_reviewer_verdicts(
        [norm],
        gate_name=gate_name,
        phase=phase,
        dispatch_mode="fast-evaluator",
    )


def _dispatch_sequential(
    state: Optional["ProjectState"],
    phase: str,
    gate_name: str,
    reviewers: List[str],
    *,
    dispatcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """Dispatch reviewers in order, stopping on the first REJECT.

    Merged verdict uses BLEND-RULE over the results collected so far.
    """
    if not reviewers:
        return _dispatch_fast_evaluator(
            state, phase, gate_name, dispatcher=dispatcher
        )
    if dispatcher is None:
        return _empty_verdict_stub(gate_name, phase, "dispatcher-unavailable")

    collected: List[Dict[str, Any]] = []
    for reviewer in reviewers:
        try:
            raw = dispatcher(
                f"wicked-garden:crew:{reviewer}",
                (
                    f"Review gate '{gate_name}' for phase '{phase}' as {reviewer}. "
                    "Emit verdict + score + reason + conditions."
                ),
                {"gate_name": gate_name, "phase": phase, "reviewer": reviewer},
            )
        except Exception as exc:  # pragma: no cover — defensive
            raw = {"verdict": "CONDITIONAL", "score": 0.0,
                   "reason": f"dispatch-error:{exc}", "conditions": []}
        norm = _normalize_reviewer_result(raw, reviewer=reviewer)
        collected.append(norm)
        if norm["verdict"] == "REJECT":
            # Short-circuit — do not dispatch remaining reviewers.
            break

    return _merge_reviewer_verdicts(
        collected,
        gate_name=gate_name,
        phase=phase,
        dispatch_mode="sequential",
    )


def _dispatch_parallel_and_merge(
    state: Optional["ProjectState"],
    phase: str,
    gate_name: str,
    reviewers: List[str],
    *,
    dispatcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """Dispatch all reviewers in a single-message parallel Agent batch (SC-6).

    The dispatcher is expected to support a batched call — we pass the
    reviewer list and a per-reviewer context in one invocation. A single-
    reviewer dispatcher is accepted too; we invoke it once per reviewer but
    the intent is that the caller's wrapper preserves the parallel batch
    (see `parallelization_check` in execute() for the SC-6 contract).

    Merge rule: REJECT if any REJECT, CONDITIONAL if any CONDITIONAL, else
    APPROVE. Conditions are unioned; score = min.
    """
    if not reviewers:
        return _dispatch_fast_evaluator(
            state, phase, gate_name, dispatcher=dispatcher
        )
    if dispatcher is None:
        return _empty_verdict_stub(gate_name, phase, "dispatcher-unavailable")

    per_reviewer: List[Dict[str, Any]] = []
    # Attempt batched dispatch first via a sentinel subagent_type. If the
    # dispatcher doesn't recognize the batch shape it returns None / raises;
    # we then fall back to per-reviewer dispatch. The caller supplies
    # whichever style they support.
    batched: Any = None
    try:
        batched = dispatcher(
            "wicked-garden:crew:_parallel_batch",
            (
                f"Dispatch reviewers in parallel for gate '{gate_name}' "
                f"phase '{phase}'. reviewers={reviewers}"
            ),
            {
                "gate_name": gate_name,
                "phase": phase,
                "reviewers": reviewers,
                "mode": "parallel",
            },
        )
    except Exception:
        batched = None

    if isinstance(batched, list) and batched:
        for idx, raw in enumerate(batched):
            name = reviewers[idx] if idx < len(reviewers) else f"reviewer-{idx}"
            per_reviewer.append(
                _normalize_reviewer_result(raw, reviewer=name)
            )
    else:
        # Fallback: call the dispatcher once per reviewer. We still mark
        # dispatch_mode=parallel — the contract is the merge rule.
        for reviewer in reviewers:
            try:
                raw = dispatcher(
                    f"wicked-garden:crew:{reviewer}",
                    (
                        f"Review gate '{gate_name}' for phase '{phase}' as "
                        f"{reviewer}. Emit verdict + score + reason + conditions."
                    ),
                    {
                        "gate_name": gate_name,
                        "phase": phase,
                        "reviewer": reviewer,
                        "mode": "parallel",
                    },
                )
            except Exception as exc:  # pragma: no cover
                raw = {"verdict": "CONDITIONAL", "score": 0.0,
                       "reason": f"dispatch-error:{exc}", "conditions": []}
            per_reviewer.append(
                _normalize_reviewer_result(raw, reviewer=reviewer)
            )

    return _merge_reviewer_verdicts(
        per_reviewer,
        gate_name=gate_name,
        phase=phase,
        dispatch_mode="parallel",
    )


def _dispatch_council(
    state: Optional["ProjectState"],
    phase: str,
    gate_name: str,
    reviewers: List[str],
    *,
    min_concurrence: float = 0.6,
    dispatcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """Council dispatch — parallel plurality vote with concurrence threshold.

    Verdict is the plurality of (APPROVE | CONDITIONAL | REJECT). When the
    plurality share < `min_concurrence`, the verdict is downgraded to
    CONDITIONAL with reason `insufficient-concurrence`. REJECT still
    short-circuits any plurality analysis (one REJECT blocks).
    """
    if not reviewers:
        return _dispatch_fast_evaluator(
            state, phase, gate_name, dispatcher=dispatcher
        )
    if dispatcher is None:
        return _empty_verdict_stub(gate_name, phase, "dispatcher-unavailable")

    merged = _dispatch_parallel_and_merge(
        state, phase, gate_name, reviewers, dispatcher=dispatcher
    )
    merged["dispatch_mode"] = "council"

    per_reviewer = merged.get("per_reviewer_verdicts") or []
    total = len(per_reviewer)
    if not total:
        return merged

    # REJECT short-circuit already applied by the merge helper.
    if merged.get("verdict") == "REJECT":
        return merged

    verdict_counts: Dict[str, int] = {"APPROVE": 0, "CONDITIONAL": 0, "REJECT": 0}
    for pr in per_reviewer:
        v = pr.get("verdict", "CONDITIONAL")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    # Plurality (ties broken in the safer direction: CONDITIONAL > APPROVE).
    plurality_verdict = "APPROVE"
    plurality_count = verdict_counts["APPROVE"]
    if verdict_counts["CONDITIONAL"] >= plurality_count:
        plurality_verdict = "CONDITIONAL"
        plurality_count = verdict_counts["CONDITIONAL"]

    concurrence = plurality_count / total
    merged["concurrence"] = concurrence
    merged["min_concurrence"] = min_concurrence
    merged["plurality_verdict"] = plurality_verdict
    if concurrence < min_concurrence and plurality_verdict == "APPROVE":
        # Downgrade — not enough agreement to approve.
        merged["verdict"] = "CONDITIONAL"
        merged["result"] = "CONDITIONAL"
        prior_reason = merged.get("reason") or ""
        merged["reason"] = (
            "insufficient-concurrence"
            + (f"; {prior_reason}" if prior_reason else "")
        )
    else:
        merged["verdict"] = plurality_verdict
        merged["result"] = plurality_verdict

    return merged


# Phase -> default gate_name mapping. Used by approve_phase() when it needs
# to call _dispatch_gate_reviewer() but the caller didn't pass an explicit
# gate_name. Mirrors skills/propose-process/refs/gate-policy.md. Phases not
# listed fall back to the phase-name (e.g. 'review' -> 'review') which will
# surface as "unknown gate" via _resolve_gate_reviewer.
_PHASE_DEFAULT_GATE: Dict[str, str] = {
    "clarify": "requirements-quality",
    "design": "design-quality",
    "build": "code-quality",
    "review": "evidence-quality",
    "test-strategy": "testability",
    "challenge": "challenge-resolution",
}


def _gate_name_for_phase(phase: str) -> str:
    """Return the default gate_name for a given phase (BLEND dispatch)."""
    return _PHASE_DEFAULT_GATE.get(resolve_phase(phase), resolve_phase(phase))


def _dispatch_gate_reviewer(
    state: Optional["ProjectState"],
    phase: str,
    gate_name: str,
    gate_policy_entry: Dict[str, Any],
    *,
    dispatcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """Main BLEND-RULE entry point.

    Reads the policy entry for `{tier}` and delegates to the right
    sub-helper. Returns a merged gate_result dict with
    `{verdict, score, reason, conditions, per_reviewer_verdicts[]}`.

    Args:
        state:              ProjectState for context (may be None in stubs).
        phase:              Phase being approved.
        gate_name:          One of the configured gates.
        gate_policy_entry:  The rigor-tier block from gate-policy.json
                            (dict with `reviewers`, `mode`, `fallback`).
        dispatcher:         Optional injectable callable
                            `(subagent_type, prompt, context) -> dict`.
                            When None, returns a CONDITIONAL stub.
    """
    if not isinstance(gate_policy_entry, dict):
        return _empty_verdict_stub(
            gate_name, phase, "missing-gate-policy-entry"
        )

    mode = str(gate_policy_entry.get("mode") or "self-check").lower()
    reviewers = list(gate_policy_entry.get("reviewers") or [])
    fallback = gate_policy_entry.get("fallback") or "gate-evaluator"

    # BLEND RULE — fast path when no reviewers or advisory/self-check.
    if not reviewers or mode in ("self-check", "advisory"):
        return _dispatch_fast_evaluator(
            state,
            phase,
            gate_name,
            dispatcher=dispatcher,
            fallback_reviewer=fallback,
        )

    if mode == "sequential":
        return _dispatch_sequential(
            state, phase, gate_name, reviewers, dispatcher=dispatcher
        )
    if mode == "parallel":
        return _dispatch_parallel_and_merge(
            state, phase, gate_name, reviewers, dispatcher=dispatcher
        )
    if mode == "council":
        return _dispatch_council(
            state, phase, gate_name, reviewers, dispatcher=dispatcher
        )

    # Unknown mode — conservative stub (do not raise: this path runs inside
    # approve_phase() where a raise would abort advancement for all callers).
    return _empty_verdict_stub(
        gate_name, phase, f"unknown-dispatch-mode:{mode}", reviewer=fallback
    )


# ---------------------------------------------------------------------------
# Semantic alignment gate (issue #444)
#
# Post-implementation pass that verifies spec-to-code alignment per numbered
# AC / FR. Runs at the review-phase hook point alongside other review-phase
# checks (see call site in ``approve_phase``). Complexity-aware: mandatory at
# complexity >= 3, advisory otherwise.
#
# (v6.0 removed the env-var bypass; strict enforcement is always active.
# Rollback is a ``git revert`` on the PR, not a runtime toggle.)
# ---------------------------------------------------------------------------

# Complexity at/above which semantic alignment is MANDATORY (blocking).
_SEMANTIC_ALIGNMENT_COMPLEXITY_THRESHOLD = 3


def _check_semantic_alignment_gate(
    state: "ProjectState",
    project_dir: Path,
    phase: str,
) -> Tuple[Optional[str], List[str]]:
    """Run the semantic-alignment check at the review-phase hook point.

    Extracts numbered AC / FR from clarify-phase specs and classifies each as
    aligned / divergent / missing against the implementation + test corpora.

    Returns a tuple ``(block_reason, warnings)`` where:
      - ``block_reason`` is non-None when the gate must REJECT phase advance
        (complexity >= 3 AND at least one MISSING finding). Caller should
        raise ValueError with this string.
      - ``warnings`` is a list of non-blocking notes (DIVERGENT or advisory
        findings) to append to the approve-phase warning list.

    Behaviour matrix::

        complexity >= 3 + missing > 0   -> block_reason set (REJECT)
        complexity >= 3 + divergent > 0 -> warning + conditions manifest
                                           appended (CONDITIONAL)
        complexity >= 3 + all aligned   -> single "APPROVE" warning (info)
        complexity <  3                 -> advisory warning only; never blocks
        no spec items found             -> advisory skip

    Fails safe — any exception during analysis becomes a warning, not a block.
    (v6.0 removed the env-var bypass; strict enforcement is always active.)
    """
    # Only runs for the review phase. Caller should pre-check but we
    # defensively verify here too.
    if resolve_phase(phase) != "review":
        return None, []

    complexity = int(getattr(state, "complexity_score", 0) or 0)
    is_mandatory = complexity >= _SEMANTIC_ALIGNMENT_COMPLEXITY_THRESHOLD

    # Resolve project + spec paths defensively — everything must be tolerant
    # to a project dir without a clarify phase (skip cleanly).
    clarify_dir = project_dir / "phases" / "clarify"
    ac_file = clarify_dir / "acceptance-criteria.md"
    obj_file = clarify_dir / "objective.md"

    if not (ac_file.exists() or obj_file.exists()):
        # No specs to check — advisory skip.
        return None, [
            f"[semantic-alignment] skipped — no clarify-phase specs "
            f"(acceptance-criteria.md / objective.md) found at {clarify_dir}."
        ]

    # Import lazily — the script lives under scripts/qe/ and has no
    # cross-module imports that would trigger at module load time.
    try:
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parents[1] / "qe"),
        )
        import semantic_review  # type: ignore
    except Exception as exc:  # noqa: BLE001 — fail-safe on ANY import error
        logger.warning(
            "[semantic-alignment] import failed (%s) — treating as advisory skip.",
            exc,
        )
        return None, [
            f"[semantic-alignment] advisory skip — import error: {exc}"
        ]

    # Run the review, fail-safe on any exception.
    try:
        report = semantic_review.review_project(
            project_dir=project_dir,
            project_name=state.name,
            complexity=complexity,
            ac_file=ac_file if ac_file.exists() else None,
            objective_file=obj_file if obj_file.exists() else None,
        )
    except Exception as exc:  # noqa: BLE001 — see docstring: fail safe.
        logger.warning(
            "[semantic-alignment] review raised %s — advisory skip.", exc,
        )
        return None, [
            f"[semantic-alignment] advisory skip — review error: {exc}"
        ]

    # Persist the report for evidence. Always safe to write even when
    # aligned so downstream tools have a baseline.
    try:
        out_dir = project_dir / "phases" / "review"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "semantic-gap-report.json"
        out_path.write_text(
            json.dumps(semantic_review.report_to_dict(report), indent=2)
        )
    except OSError as exc:
        logger.warning(
            "[semantic-alignment] could not persist gap report: %s", exc,
        )

    # Short-circuit when no numbered spec items were found — nothing to check.
    if report.total == 0:
        return None, [
            "[semantic-alignment] skipped — no numbered AC / FR items found "
            "in clarify-phase specs."
        ]

    warnings: List[str] = []
    summary = (
        f"[semantic-alignment] verdict={report.verdict} "
        f"score={report.score} aligned={report.aligned} "
        f"divergent={report.divergent} missing={report.missing} "
        f"(complexity={complexity}, "
        f"mandatory={'yes' if is_mandatory else 'no'})"
    )
    warnings.append(summary)

    # Add one warning line per non-aligned finding so they surface in approve
    # output without the caller having to read the JSON.
    for finding in report.findings:
        if finding.status == "aligned":
            continue
        warnings.append(
            f"[semantic-alignment] {finding.status.upper()} "
            f"{finding.id} (conf={finding.confidence:.2f}): {finding.reason}"
        )

    # Advisory-only at low complexity.
    if not is_mandatory:
        return None, warnings

    # Mandatory path: missing => hard REJECT.
    if report.missing > 0:
        missing_ids = [f.id for f in report.findings if f.status == "missing"]
        return (
            (
                f"Semantic alignment REJECT: {report.missing} spec item(s) "
                f"missing from implementation ({', '.join(missing_ids)}). "
                f"See {project_dir / 'phases' / 'review' / 'semantic-gap-report.json'}. "
                f"Implement the referenced AC or remove them from the spec "
                f"before approving."
            ),
            warnings,
        )

    # Mandatory path: divergent => CONDITIONAL — write conditions so the
    # existing manifest machinery picks them up on next-phase approve.
    if report.divergent > 0:
        try:
            conditions = [
                {
                    "description": (
                        f"Semantic divergence on {f.id}: {f.reason}"
                    ),
                    "source": "semantic-reviewer",
                    "finding_id": f.id,
                    "severity": "divergent",
                }
                for f in report.findings if f.status == "divergent"
            ]
            _write_conditions_manifest(project_dir, phase, conditions)
            warnings.append(
                f"[semantic-alignment] {len(conditions)} divergent finding(s) "
                f"written to conditions manifest — must be resolved before "
                f"next phase advance."
            )
        except OSError as exc:
            warnings.append(
                f"[semantic-alignment] divergent findings detected but "
                f"conditions manifest write failed: {exc}"
            )

    return None, warnings


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


# ---------------------------------------------------------------------------
# Spec-quality rubric enforcement (clarify phase) — see spec_rubric.py
# ---------------------------------------------------------------------------


def _apply_spec_rubric(
    gate_result: Dict[str, Any],
    phase: str,
    rigor_tier: Optional[str],
) -> Dict[str, Any]:
    """Apply the spec-quality rubric to a clarify-phase gate result.

    Mutates a *copy* of ``gate_result`` so the caller can decide whether to
    persist the adjusted verdict (and conditions) back to disk.

    Only fires when:
      - ``phase == 'clarify'``
      - ``gate_result`` carries a ``rubric_breakdown`` dict (produced by the
        requirements-quality reviewer agent).

    When the rubric breakdown is missing or invalid the original result is
    returned unchanged — the classic ``min_gate_score`` check still runs
    alongside and catches pure-prose gate results. This preserves backward
    compatibility with pre-rubric projects.

    Returns a new dict, never mutates the input.
    """
    if resolve_phase(phase) != "clarify":
        return gate_result

    breakdown = gate_result.get("rubric_breakdown") if isinstance(gate_result, dict) else None
    if not isinstance(breakdown, dict):
        return gate_result

    try:
        # Late import so the module stays optional for non-clarify callers.
        from crew import spec_rubric  # type: ignore
    except ImportError:
        try:
            import spec_rubric  # type: ignore
        except ImportError:
            return gate_result

    ok, err = spec_rubric.validate_breakdown(breakdown)
    if not ok:
        logger.warning(
            "[approve] Ignoring malformed rubric_breakdown on clarify gate: %s",
            err,
        )
        return gate_result

    score = spec_rubric.total_score(breakdown)
    tier = (rigor_tier or "standard").lower()
    base_verdict = str(gate_result.get("result", "APPROVE")).upper()

    verdict, reason, conditions = spec_rubric.evaluate_verdict(
        score=score,
        rigor_tier=tier,
        base_verdict=base_verdict,
        breakdown=breakdown,
    )

    adjusted = dict(gate_result)
    adjusted["rubric_score"] = score
    adjusted["rubric_max_score"] = spec_rubric.MAX_SCORE
    adjusted["rubric_grade"] = spec_rubric.grade_for_score(score)
    adjusted["rubric_rigor_tier"] = tier
    adjusted["rubric_threshold"] = spec_rubric.TIER_THRESHOLDS.get(tier)

    # Persist the score-driven verdict + annotations. When the rubric changed
    # the verdict record a rubric_adjustment block; either way merge any
    # rubric-derived conditions so CONDITIONAL manifests include them.
    if verdict != base_verdict:
        adjusted["result"] = verdict
        adjusted["rubric_adjustment"] = {
            "from": base_verdict,
            "to": verdict,
            "reason": reason,
        }

    if conditions:
        existing_conditions = list(adjusted.get("conditions", []) or [])
        for c in conditions:
            if c not in existing_conditions:
                existing_conditions.append(c)
        adjusted["conditions"] = existing_conditions

    return adjusted


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


# ---------------------------------------------------------------------------
# Skip-reeval helpers (AC-14, AC-15, AC-16)
# ---------------------------------------------------------------------------

def _write_skip_reeval_log(project_dir: Path, phase: str, reason: str) -> None:
    """Write a skip-reeval log entry to phases/{phase}/skip-reeval-log.json.

    The entry intentionally has NO default set by any env-var or config —
    it is only written when the --skip-reeval flag is explicitly passed (AC-15).
    """
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    log_file = phase_dir / "skip-reeval-log.json"

    existing: list = []
    if log_file.exists():
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
            existing = data if isinstance(data, list) else [data]
        except (json.JSONDecodeError, OSError):
            existing = []

    entry = {
        "phase": phase,
        "skipped_at": get_utc_timestamp(),
        "reason": reason,
        "resolved_at": None,
        "resolved_by": None,
        "resolution_note": None,
    }
    existing.append(entry)
    log_file.write_text(json.dumps(existing, indent=2))


def _check_addendum_freshness(
    project_dir: Path, phase: str, phase_started_at: "str | None"
) -> "str | None":
    """Return an error string if the phase-end re-eval addendum is missing or stale.

    Fail-closed: a missing or stale addendum blocks approval (AC-8).

    Args:
        project_dir:      Project root directory.
        phase:            Phase being approved.
        phase_started_at: ISO timestamp when the phase started; None skips check.

    Returns:
        None if the addendum is present and fresh; an error string otherwise.
    """
    reeval_log = project_dir / "phases" / phase / "reeval-log.jsonl"
    if not reeval_log.exists():
        return (
            f"Phase '{phase}' has no re-evaluation addendum "
            f"(phases/{phase}/reeval-log.jsonl missing). "
            "Re-evaluation is required before approval. "
            "Run propose-process in re-evaluate mode, or use "
            "--skip-reeval --reason '<justification>' as an emergency bypass."
        )

    # Read last line to check triggered_at freshness
    try:
        lines = [
            line.strip()
            for line in reeval_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not lines:
            return (
                f"Phase '{phase}' re-evaluation log is empty. "
                "Re-evaluation required before approval."
            )
        last_record = json.loads(lines[-1])
    except (json.JSONDecodeError, OSError):
        return (
            f"Phase '{phase}' re-evaluation log is unreadable or malformed. "
            "Re-run re-evaluation or use --skip-reeval --reason."
        )

    # Optionally check that re-eval occurred after phase start
    if phase_started_at:
        triggered_at = last_record.get("triggered_at", "")
        if triggered_at and phase_started_at:
            if triggered_at < phase_started_at:
                return (
                    f"Phase '{phase}' re-evaluation addendum (triggered_at={triggered_at}) "
                    f"predates phase start ({phase_started_at}). "
                    "Re-run phase-end re-evaluation before approving."
                )

    return None  # addendum is present and fresh


def _check_final_audit_skip_logs(state: "ProjectState") -> List[str]:
    """Collect unresolved skip-reeval entries for the final-audit gate (AC-16).

    Returns a list of CONDITIONAL finding strings.  Empty means no open entries.
    """
    try:
        from audit_skip_log import scan as _scan_skip_log
    except ImportError:
        logger.warning("[final-audit] audit_skip_log module not importable — skipping scan")
        return []

    project_dir = get_project_dir(state.name)
    try:
        unresolved = _scan_skip_log(project_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[final-audit] audit_skip_log.scan failed: %s", exc)
        return []

    findings: List[str] = []
    for entry in unresolved:
        src_phase = entry.get("_source_phase", "unknown")
        reason = entry.get("reason") or "(no reason)"
        findings.append(
            f"Unresolved skip-reeval entry from phase '{src_phase}': {reason!r}. "
            "Retrospective review required before final-audit gate clears."
        )
    return findings


def _check_convergence_gate(state: "ProjectState") -> List[str]:
    """Evaluate the `convergence-verify` gate for the review phase (#445).

    Pulls artifact convergence state from convergence.py and returns a list of
    CONDITIONAL finding strings when any artifact is still in a pre-Integrated
    state or stuck for >= stall-threshold sessions.

    Fails open on:
        - missing module (module not importable)
        - missing log file (no convergence data recorded yet)

    Returns:
        List of human-readable CONDITIONAL finding strings.  Empty means the
        gate passed.  These are warnings, not hard REJECTs — they are
        appended to the approve_phase warnings list so the reviewer sees
        them without the approval itself being blocked by this gate.
    """
    try:
        from convergence import evaluate_review_gate as _eval_cv_gate
    except ImportError:
        logger.warning("[convergence-verify] convergence module not importable — skipping")
        return []

    try:
        project_dir = get_project_dir(state.name)
    except ValueError:
        return []

    try:
        result = _eval_cv_gate(project_dir)
    except Exception as exc:  # noqa: BLE001 — fail-open
        logger.warning("[convergence-verify] evaluate_review_gate failed: %s", exc)
        return []

    if result.get("result") == "APPROVE":
        return []

    findings: List[str] = []
    for finding in result.get("findings", []):
        msg = finding.get("message") or ""
        kind = finding.get("kind", "?")
        if not msg:
            continue
        findings.append(f"[convergence-verify:{kind}] {msg}")
    return findings


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


def _record_last_phase_approved(phase: str) -> None:
    """Write the approved phase onto SessionState (#462).

    Idempotent — re-approving the same phase just rewrites the same value.
    Fail-open — if the session state module is unavailable (e.g. during a
    script run outside the hook environment) we log and move on.  This
    hook must never block or mutate the approve return path.
    """
    try:
        # scripts/ is on sys.path via the module-level insert at the top of
        # this file, so the import is direct (matches other call sites).
        from _session import SessionState  # type: ignore
        sess = SessionState.load()
        if getattr(sess, "last_phase_approved", None) == phase:
            return  # idempotent no-op
        sess.update(last_phase_approved=phase)
    except Exception as exc:
        # Fail open — session wiring should never break approve_phase.
        logger.debug("[approve] last_phase_approved wiring skipped: %s", exc)


def _increment_skip_reeval_count() -> None:
    """Bump SessionState.skip_reeval_count producer for telemetry (#459).

    Fires from approve_phase() whenever the --skip-reeval bypass path is
    actually exercised (addendum present AND bypass flag set AND reason given).
    Read at session close by scripts/delivery/telemetry.py.
    Fail-open — telemetry producers must never block approval.
    """
    try:
        from _session import SessionState  # type: ignore
        sess = SessionState.load()
        current = int(getattr(sess, "skip_reeval_count", 0) or 0)
        sess.update(skip_reeval_count=current + 1)
    except Exception as exc:
        logger.debug("[approve] skip_reeval_count producer skipped: %s", exc)


def _record_complexity_snapshot(complexity: int) -> None:
    """Mirror ProjectState.complexity_score onto SessionState (#459).

    Sets complexity_at_session_open on FIRST observation this session (so the
    telemetry delta is anchored to session start) and always updates
    complexity_score so close-out sees the latest value.  Fail-open.
    """
    try:
        from _session import SessionState  # type: ignore
        sess = SessionState.load()
        updates: Dict[str, Any] = {"complexity_score": int(complexity or 0)}
        if getattr(sess, "complexity_at_session_open", None) is None:
            updates["complexity_at_session_open"] = int(complexity or 0)
        sess.update(**updates)
    except Exception as exc:
        logger.debug("[approve] complexity snapshot producer skipped: %s", exc)


def _run_build_phase_guard(project_dir: Path) -> List[str]:
    """Run the guard pipeline at build-phase approval (#462, Item 2).

    Lazy-imports scripts/platform/guard_pipeline.run_pipeline and returns a
    list of human-readable warning strings to surface in the approve output.
    Fail-open on every axis — ImportError, missing module, exception during
    scan, budget_exceeded — all return an empty list without raising.

    (v6.0 removed the env-var bypass; strict enforcement is always active.
    Rollback is a ``git revert`` on the PR, not a runtime toggle.)

    Mirrors the fail-open pattern used by hooks/scripts/stop.py::_run_guard_pipeline.
    """
    try:
        # scripts/platform/ is a sibling of scripts/crew/.  Add it to
        # sys.path lazily so the import only pays the cost at build-phase
        # approval, not at module import time.
        _platform_path = str(Path(__file__).resolve().parents[1] / "platform")
        if _platform_path not in sys.path:
            sys.path.insert(0, _platform_path)
        from guard_pipeline import run_pipeline, render_summary  # type: ignore
    except ImportError as exc:
        logger.debug("[approve] guard_pipeline unavailable: %s", exc)
        return []
    except Exception as exc:  # pragma: no cover — defense in depth
        logger.debug("[approve] guard_pipeline import error: %s", exc)
        return []

    try:
        report = run_pipeline(
            profile_name="standard",
            project_dir=project_dir if project_dir else None,
        )
    except Exception as exc:
        # MUST NOT let a guard-pipeline error bubble up and block approval.
        print(f"[approve] guard_pipeline error: {exc}", file=sys.stderr)
        logger.warning("[approve] guard_pipeline exception during build approve: %s", exc)
        return []

    if not report or report.total_findings == 0:
        return []

    try:
        summary = render_summary(report)
    except Exception as exc:
        logger.debug("[approve] guard render_summary error: %s", exc)
        # Fall back to a minimal summary — we still want to surface the count.
        summary = (
            f"[Guard] standard pipeline surfaced {report.total_findings} "
            f"finding(s) at build-phase approval."
        )
    return [summary]


def approve_phase(
    state: ProjectState,
    phase: str,
    approver: str = "user",
    override_gate: bool = False,
    override_reason: str = "",
    override_deliverables: bool = False,
    override_deliverables_reason: str = "",
    skip_reeval: bool = False,
    skip_reeval_reason: str = "",
    *,
    dispatcher: Optional[Any] = None,
) -> Tuple[ProjectState, Optional[str]]:
    """Approve a phase and return next phase (or None if done).

    Performs gate checks and deliverable checks.
    Raises ValueError when gate enforcement blocks advancement.
    Caller (CLI handle_approve) catches this and exits non-zero.

    Args:
        skip_reeval:        When True, bypass the addendum-freshness check.
                            Must be used with a non-empty skip_reeval_reason.
                            This is a deliberate, logged, audited bypass — NOT a
                            silent escape (AC-14, AC-15).
        skip_reeval_reason: Mandatory justification string when skip_reeval=True.
        dispatcher:         Optional injectable callable for BLEND-RULE gate
                            dispatch (design §3). When provided, and the gate
                            hasn't been run (no existing gate-result.json),
                            approve_phase() dispatches reviewers per
                            gate-policy.json instead of raising. When None
                            (legacy callers), existing behavior is preserved —
                            "Gate not run" raises as before.

                            IMPORTANT (review-gate condition a): the
                            `handle_approve` CLI entry always passes
                            dispatcher=None because raw CLI invocations
                            cannot dispatch Claude Code subagents. Only
                            Agent-driven callers (e.g. the `crew:approve`
                            slash command running inside claude-code) can
                            inject a real dispatcher. `handle_approve`
                            logs an explicit warning in that case so the
                            behaviour is honest rather than silent.
    """
    phase = resolve_phase(phase)
    warnings: List[str] = []

    # SC-4 startup validation (COND-TG-4): when the project is running at full
    # rigor, assert gate-policy.json declares non-empty reviewers for every
    # full-tier gate. Empty reviewers would silently degrade to the fast
    # evaluator which is a correctness bug at full rigor. Non-full tiers skip
    # this check because an empty reviewer list is legitimate at minimal
    # rigor (advisory-only gates). Matches the docstring claim that the
    # validator is called from both execute() and approve_phase() entry
    # points (see _validate_gate_policy_full_rigor docstring).
    if (state.extras or {}).get("rigor_tier") == "full":
        _validate_gate_policy_full_rigor()

    # Check 0 (AC-8): phase-end re-eval addendum freshness — fail-closed.
    # Must happen before deliverable check so the user sees the most actionable
    # error first.  skip_reeval=True bypasses with a mandatory logged reason.
    project_dir_reeval = get_project_dir(state.name)
    phase_state_for_ts = state.phases.get(phase)
    phase_started_at = (
        phase_state_for_ts.started_at if phase_state_for_ts else None
    )
    addendum_error = _check_addendum_freshness(
        project_dir_reeval, phase, phase_started_at
    )
    if addendum_error:
        if skip_reeval:
            if not (skip_reeval_reason and skip_reeval_reason.strip()):
                raise ValueError(
                    "Error: --skip-reeval requires --reason. "
                    "Provide a justification string, e.g.: "
                    "--reason 'propose-process failed mid-run; manually validated addendum'"
                )
            # Write the bypass to the audit log (AC-14)
            _write_skip_reeval_log(project_dir_reeval, phase, skip_reeval_reason)
            # Producer for telemetry drift (#459): count skip-reeval usage.
            _increment_skip_reeval_count()
            print(
                f"WARNING: [skip-reeval] Phase '{phase}' addendum check bypassed. "
                f"Reason: {skip_reeval_reason}. "
                "Entry written to skip-reeval-log.json.",
                file=sys.stderr,
            )
            warnings.append(
                f"skip-reeval applied for phase '{phase}'. "
                f"Reason: {skip_reeval_reason}"
            )
        else:
            raise ValueError(addendum_error)

    # Check 0.1 (AC-16): final-audit gate must surface unresolved skip-reeval entries.
    if resolve_phase(phase) == "review":
        skip_log_findings = _check_final_audit_skip_logs(state)
        if skip_log_findings:
            # CONDITIONAL — reviewer may mark entries resolved; not a hard REJECT
            for finding in skip_log_findings:
                warnings.append(f"[final-audit CONDITIONAL] {finding}")
            logger.warning(
                "[final-audit] %d unresolved skip-reeval entries detected — "
                "gate verdict is CONDITIONAL until entries are resolved.",
                len(skip_log_findings),
            )

    # Check 0.2 (#445): convergence-verify gate surfaces pre-Integrated and
    # stalled artifacts in the review phase. Additive CONDITIONAL findings —
    # the reviewer sees them without the approval path blocking on them.
    # Fails open on missing log / module import error / legacy enforcement.
    if resolve_phase(phase) == "review":
        convergence_findings = _check_convergence_gate(state)
        if convergence_findings:
            for finding in convergence_findings:
                warnings.append(f"[convergence-verify CONDITIONAL] {finding}")
            logger.warning(
                "[convergence-verify] %d convergence gate finding(s) for review phase.",
                len(convergence_findings),
            )

    # Check 0.3 (issue #444): semantic alignment — spec-to-code verification.
    # Mandatory at complexity >= 3; advisory below. Additive, sits after the
    # convergence-verify hook (#445).
    if resolve_phase(phase) == "review":
        semantic_project_dir = get_project_dir(state.name)
        sem_block_reason, sem_warnings = _check_semantic_alignment_gate(
            state, semantic_project_dir, phase,
        )
        warnings.extend(sem_warnings)
        if sem_block_reason:
            raise ValueError(sem_block_reason)

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

        # BLEND-RULE dispatch hook (design §3, FR-α3.x): when the gate
        # hasn't been run yet and a dispatcher was supplied, synthesize
        # a gate-result.json by invoking reviewers per gate-policy.json
        # BEFORE the legacy "gate not run" branch fires. Writing the
        # artifact lets the existing post-load check chain run unchanged.
        if not gate_run and dispatcher is not None and not override_gate:
            try:
                gate_name = _gate_name_for_phase(phase)
                gate_entry = _resolve_gate_reviewer(
                    gate_name, rigor_tier or "standard"
                )
                synthesized = _dispatch_gate_reviewer(
                    state, phase, gate_name, gate_entry,
                    dispatcher=dispatcher,
                )
                phase_dir = project_dir / "phases" / phase
                phase_dir.mkdir(parents=True, exist_ok=True)
                (phase_dir / "gate-result.json").write_text(
                    json.dumps(synthesized, indent=2, sort_keys=True)
                )
                # Re-run the run-detector now that we've written the file.
                gate_run = _check_gate_run(
                    project_dir, phase, rigor_tier=rigor_tier
                )
            except (ValueError, FileNotFoundError, OSError) as exc:
                # Failed BLEND dispatch — fall through to legacy "gate not
                # run" raise below so the user gets the familiar error.
                logger.warning(
                    "[approve] BLEND dispatch failed for phase '%s': %s; "
                    "falling back to legacy gate-required error.",
                    phase, exc,
                )

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

            # Check 2a.0: spec-quality rubric (clarify phase only). Adjust the
            # verdict up (to CONDITIONAL/REJECT) when the rubric score is below
            # the tier threshold. Safe no-op for non-clarify phases or when the
            # reviewer did not attach a rubric_breakdown.
            if gate_result:
                gate_result = _apply_spec_rubric(
                    gate_result, phase, state.extras.get("rigor_tier")
                )

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

    # FR-α5.2: Approve-time yolo auto-accept.
    #
    # Policy (design §3 + task spec):
    #   - yolo + APPROVE      -> advance normally, append yolo-audit line
    #   - yolo + CONDITIONAL  -> DO NOT auto-advance; surface to user with
    #                            conditions-manifest (raise ValueError)
    #   - yolo + REJECT       -> existing REJECT raise already fired above
    #   - no yolo             -> unchanged
    #
    # The REJECT path is already handled by the "Gate returned REJECT"
    # raise earlier in this function, so only APPROVE + CONDITIONAL need
    # new logic here. Audit lines go to yolo-audit.jsonl; advance logic
    # is otherwise untouched (preserves legacy callers).
    yolo_flag = bool((state.extras or {}).get("yolo_approved_by_user"))
    if yolo_flag and gate_result:
        _verdict_raw = (
            gate_result.get("verdict") or gate_result.get("result") or ""
        )
        _verdict = str(_verdict_raw).upper()
        if _verdict == "APPROVE":
            try:
                _project_dir_yolo = get_project_dir(state.name)
            except Exception:
                _project_dir_yolo = None
            if _project_dir_yolo is not None:
                _append_yolo_audit(
                    _project_dir_yolo,
                    event="auto-accepted",
                    reason=f"phase:{phase} verdict:APPROVE",
                    prior_value=True,
                    new_value=True,
                    extra={
                        "phase": phase,
                        "verdict": "APPROVE",
                        "score": gate_result.get("score"),
                        "reviewer": gate_result.get("reviewer"),
                    },
                )
        elif _verdict == "CONDITIONAL":
            # Surface CONDITIONAL to the user — do not silently advance
            # under yolo. Conditions-manifest has already been written
            # above (Check 2b). Raise so the CLI exits non-zero and the
            # user sees the manifest path in the error text.
            conditions_manifest = (
                get_project_dir(state.name) / "phases" / phase
                / "conditions-manifest.json"
            )
            raise ValueError(
                f"Phase '{phase}' gate verdict is CONDITIONAL under yolo "
                f"— auto-advance blocked. Review "
                f"{conditions_manifest} and re-run approve after "
                f"conditions are resolved, or pass --override-gate "
                f"with a reason to bypass."
            )

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

    # --- #462 wiring: SessionState + build-phase guard hook ---
    # Record the approved phase on SessionState so stop.py can promote
    # the guard pipeline profile (scalpel → standard) next cycle.
    # Idempotent + fail-open: re-approving the same phase is safe.
    _record_last_phase_approved(phase)

    # --- #459 wiring: telemetry producers on SessionState ---
    # Mirror the project's complexity_score onto SessionState so the
    # session-close telemetry capture can compute complexity_delta.  First
    # approve of the session also anchors complexity_at_session_open.
    _record_complexity_snapshot(getattr(state, "complexity_score", 0))

    # Build-phase guard hook — additive, non-blocking.  Surfaces guard
    # findings as warnings in the approve output without gating approval.
    if phase == "build":
        try:
            project_dir = get_project_dir(state.name)
        except Exception:
            project_dir = None  # fail-open: still attempt the scan
        guard_warnings = _run_build_phase_guard(project_dir)
        if guard_warnings:
            warnings.extend(guard_warnings)
            # Mirror the existing pattern — push them to stderr via logger.
            for gw in guard_warnings:
                logger.warning("[approve] %s", gw)
            # Persist the warnings on the project state so structured
            # callers (CLI --json, tests, downstream consumers) can reach
            # them without changing the approve_phase return signature.
            try:
                extras_warnings = list(state.extras.get("last_approve_warnings", []))
                extras_warnings.extend(guard_warnings)
                state.extras["last_approve_warnings"] = extras_warnings
            except Exception:
                pass  # fail open — extras is best-effort surface for CLI consumers

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


# ---------------------------------------------------------------------------
# Mode-3 execute() entry point (AC-α2 / FR-α2.1..FR-α2.5)
# ---------------------------------------------------------------------------


def _append_yolo_audit(
    project_dir: Path,
    *,
    event: str,
    reason: str,
    prior_value: bool,
    new_value: bool,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single yolo-audit.jsonl record at the project root.

    Append-only; never rewrites. Fails open — audit log failures log but
    do not abort the caller (matches plugin's graceful-degradation pattern).
    """
    try:
        audit_path = project_dir / "yolo-audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event": event,
            "timestamp": get_utc_timestamp(),
            "reason": reason,
            "scope": f"project:{project_dir.name}",
            "prior_value": prior_value,
            "new_value": new_value,
        }
        if extra:
            record.update(extra)
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("[yolo-audit] append failed: %s", exc)


def _apply_scope_increase_revoke(
    state: "ProjectState",
    *,
    plan_mutations: List[Dict[str, Any]],
    project_dir: Path,
    trigger: str,
) -> bool:
    """Revoke yolo if any mutation is an augment or re-tier-up to 'full'.

    Returns True when yolo was revoked by this call; False otherwise.
    Idempotent — caller may invoke at both execute() and approve() points.
    """
    scope_increased = any(
        (m.get("op") == "augment")
        or (
            m.get("op") == "re_tier"
            and m.get("new_rigor_tier") == "full"
        )
        for m in (plan_mutations or [])
    )
    if not scope_increased:
        return False
    extras = getattr(state, "extras", None) or {}
    if not extras.get("yolo_approved_by_user"):
        return False
    extras["yolo_approved_by_user"] = False
    extras["yolo_revoked_count"] = int(extras.get("yolo_revoked_count") or 0) + 1
    state.extras = extras
    _append_yolo_audit(
        project_dir,
        event="revoked",
        reason=f"scope-increase@{trigger}",
        prior_value=True,
        new_value=False,
        extra={"triggering_mutations": plan_mutations},
    )
    # Observability: emit bus event so subscribers see the scope-increase
    # revoke without tailing yolo-audit.jsonl. Fail-open on bus absence —
    # emit_event() is a no-op when the bus is unavailable (see _bus.py).
    try:
        from _bus import emit_event
        emit_event(
            "wicked.crew.yolo_revoked",
            {
                "project": project_dir.name,
                "trigger": trigger,
                "mutation_count": len(plan_mutations or []),
                "revoked_count": int(extras.get("yolo_revoked_count") or 0),
            },
        )
    except Exception as exc:  # noqa: BLE001 — observability fail-open
        logger.debug("[yolo-revoke] bus emit failed (fail-open): %s", exc)
    return True


class ExecuteResult(Dict[str, Any]):
    """Result shape for ``execute()``.

    Keys:
        status:                 "ok" | "failed"
        deliverables:           list[str] of absolute paths (>= 100 bytes each)
        executor_task_id:       opaque task identifier
        reeval_start_path:      phases/{phase}/reeval-start.json
        reeval_end_path:        phases/{phase}/reeval-log.jsonl
        parallelization_check:  {sub_task_count, dispatched_in_parallel, serial_reason}
        reason:                 present when status == "failed"
    """


def _check_parallelization(check: Dict[str, Any]) -> Optional[str]:
    """Return a failure reason string when the parallelization_check is invalid.

    Enforces SC-6 / AC-α10: when ``sub_task_count >= 2`` and
    ``dispatched_in_parallel is False``, ``serial_reason`` MUST be non-empty.
    Returns None when the check is satisfied.
    """
    if not isinstance(check, dict):
        return "parallelization-check-missing"
    sub_count = int(check.get("sub_task_count") or 0)
    if sub_count < 2:
        return None
    in_parallel = bool(check.get("dispatched_in_parallel"))
    if in_parallel:
        return None
    serial_reason = (check.get("serial_reason") or "").strip()
    if not serial_reason:
        return "parallelization-check-missing"
    return None


def execute(
    project: str,
    phase: str,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Dispatch the phase-executor, collect deliverables, persist addendum.

    Signature (AC-α2 / FR-α2.1): ``execute(project, phase) -> ExecuteResult``.

    Returns a dict with keys listed in :class:`ExecuteResult`.

    The live dispatch (Task tool invocation) is owned by the orchestrator;
    this function is the server-side persistence / validation / status
    writer. When called by an agent via the CLI, it reads an
    ``executor-status.json`` already produced by the phase-executor and
    performs post-dispatch enforcement (parallelization-check + yolo
    auto-revoke + addendum validation).

    Raises:
        ValueError:  project unknown, archived, wrong phase, unresolved
                     conditions, or ConfigError from gate-policy validator.
        RuntimeError: executor produced empty deliverables, or the
                     parallelization-check failed (AC-α10 failure mode).
    """
    # SC-4 startup validation (first line of every mode-3 entry point).
    _validate_gate_policy_full_rigor()

    state = load_project_state(project)
    if state is None:
        raise ValueError(f"Project not found: {project}")

    # Dispatch-mode routing (CR-2 / AC-α11).
    dispatch_mode = _detect_dispatch_mode(state)
    if dispatch_mode in ("v6-legacy", "v5"):
        return {
            "status": "skipped",
            "reason": f"dispatch_mode={dispatch_mode}; mode-3 execute() is opt-in",
            "dispatch_mode": dispatch_mode,
            "deliverables": [],
        }

    phase = resolve_phase(phase)
    project_dir = get_project_dir(project)
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)

    reeval_start_path = phase_dir / "reeval-start.json"
    reeval_log_path = phase_dir / "reeval-log.jsonl"
    executor_status_path = phase_dir / "executor-status.json"

    # When executor-status.json was already written by the phase-executor
    # agent, apply post-dispatch enforcement to it.
    result: Dict[str, Any] = {
        "status": "ok",
        "deliverables": [],
        "executor_task_id": "",
        "reeval_start_path": str(reeval_start_path),
        "reeval_end_path": str(reeval_log_path),
        "parallelization_check": {
            "sub_task_count": 0,
            "dispatched_in_parallel": True,
            "serial_reason": None,
        },
        "dispatch_mode": dispatch_mode,
    }

    if dry_run:
        return result

    if executor_status_path.exists():
        try:
            status_doc = json.loads(executor_status_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"executor-status-unreadable: {exc}")
        deliverables = status_doc.get("deliverables") or []
        if not deliverables:
            raise RuntimeError("executor-empty-deliverables")
        # Validate deliverables are under phases/{phase}/ — hard path-traversal
        # guard (COND-TG-2). Resolves the declared path and asserts the real
        # on-disk location is scoped inside the phase directory. `..` segments
        # that escape phase_dir or absolute paths outside it are rejected with
        # a ValueError so callers can distinguish "bad input" from runtime
        # failures. Using phase_dir (not project_dir) matches the original
        # intent of the comment and prevents a phase-executor from declaring
        # deliverables under a sibling phase or the project root.
        phase_dir_resolved = phase_dir.resolve()
        for rel in deliverables:
            rel_path = Path(rel)
            if rel_path.is_absolute():
                abs_path = rel_path
            else:
                abs_path = project_dir / rel
            try:
                abs_path.resolve().relative_to(phase_dir_resolved)
            except ValueError:
                raise ValueError(f"deliverable-out-of-scope: {rel}")

        p_check = status_doc.get("parallelization_check") or {}
        fail = _check_parallelization(p_check)
        if fail:
            result["status"] = "failed"
            result["reason"] = fail
            return result

        result["deliverables"] = [str(p) for p in deliverables]
        result["executor_task_id"] = status_doc.get("executor_task_id", "")
        result["parallelization_check"] = p_check

        # Scope-increase revoke hook (Point A — execute-time).
        _apply_scope_increase_revoke(
            state,
            plan_mutations=status_doc.get("plan_mutations") or [],
            project_dir=project_dir,
            trigger="execute",
        )
        save_project_state(state)

    return result


# ---------------------------------------------------------------------------
# Yolo management (AC-α5)
# ---------------------------------------------------------------------------


def yolo_action(project: str, action: str, reason: str = "") -> Dict[str, Any]:
    """Grant / revoke / inspect the yolo flag for a project.

    Actions:
        approve  — set yolo_approved_by_user=True (writes audit line).
        revoke   — set yolo_approved_by_user=False (writes audit line).
        status   — return current flag + last audit record (no write).
    """
    state = load_project_state(project)
    if state is None:
        raise ValueError(f"Project not found: {project}")
    project_dir = get_project_dir(project)
    extras = state.extras or {}
    prior = bool(extras.get("yolo_approved_by_user"))

    if action == "status":
        return {
            "project": project,
            "yolo_approved_by_user": prior,
            "yolo_approved_at": extras.get("yolo_approved_at"),
            "yolo_revoked_count": int(extras.get("yolo_revoked_count") or 0),
            "rigor_tier": extras.get("rigor_tier"),
        }

    if action == "approve":
        new_value = True
        extras["yolo_approved_by_user"] = True
        extras["yolo_approved_at"] = get_utc_timestamp()
        state.extras = extras
        save_project_state(state)
        _append_yolo_audit(
            project_dir,
            event="granted",
            reason=reason or "user-granted",
            prior_value=prior,
            new_value=new_value,
        )
        return {
            "project": project,
            "yolo_approved_by_user": True,
            "prior_value": prior,
        }

    if action == "revoke":
        new_value = False
        extras["yolo_approved_by_user"] = False
        state.extras = extras
        save_project_state(state)
        _append_yolo_audit(
            project_dir,
            event="revoked",
            reason=reason or "user-revoked",
            prior_value=prior,
            new_value=new_value,
        )
        return {
            "project": project,
            "yolo_approved_by_user": False,
            "prior_value": prior,
        }

    raise ValueError(f"Unknown yolo action: {action} (expected approve|revoke|status)")


# ---------------------------------------------------------------------------
# Cutover command (CR-2 / AC-α11)
# ---------------------------------------------------------------------------


def _safe_cutover_window(state: "ProjectState", project_dir: Path) -> Optional[str]:
    """Return an error string when the project is NOT in a safe cutover window.

    Validates:
      - no in-flight phase dispatch (phase-executor task in_progress)
      - no unresolved conditions on the current/prior phase
      - no pending scope-increase re-eval
    """
    # Unresolved conditions check — reuse _verify_conditions heuristics.
    try:
        current = resolve_phase(state.current_phase)
        condition_issues = _verify_conditions(project_dir, current) or []
        if condition_issues:
            return f"unresolved-conditions: {condition_issues[0]}"
    except Exception:  # noqa: BLE001
        pass  # fail open: absence of evidence is not evidence of absence
    # In-flight-dispatch check: phase status == in_progress AND executor-status
    # not yet written indicates an active dispatch.
    cur = state.phases.get(resolve_phase(state.current_phase))
    if cur and cur.status == "in_progress":
        status_path = project_dir / "phases" / state.current_phase / "executor-status.json"
        if not status_path.exists():
            return "in-flight-dispatch: current phase still executing"
    return None


def cutover_action(project: str, target_mode: str) -> Dict[str, Any]:
    """Opt a legacy project into mode-3 dispatch (writes state + audit marker).

    Validates the safe cutover window (no in-flight dispatch, no unresolved
    conditions). Writes ``state.dispatch_mode = "mode-3"`` and emits
    ``{project_dir}/phases/.cutover-to-mode-3.json``.
    """
    if target_mode != "mode-3":
        raise ValueError(f"Unsupported --to value: {target_mode} (only 'mode-3' supported)")

    state = load_project_state(project)
    if state is None:
        raise ValueError(f"Project not found: {project}")

    project_dir = get_project_dir(project)
    prior_mode = _detect_dispatch_mode(state)

    if prior_mode == "mode-3":
        return {
            "project": project,
            "dispatch_mode": "mode-3",
            "already_on_target": True,
            "note": "Project is already on mode-3 dispatch.",
        }

    err = _safe_cutover_window(state, project_dir)
    if err:
        raise ValueError(f"cutover-refused: {err}")

    extras = state.extras or {}
    extras["dispatch_mode"] = "mode-3"
    state.extras = extras
    save_project_state(state)

    phases_dir = project_dir / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    marker_path = phases_dir / ".cutover-to-mode-3.json"
    try:
        marker_path.write_text(json.dumps({
            "timestamp": get_utc_timestamp(),
            "prior_mode": prior_mode,
            "new_mode": "mode-3",
            "prior_phase_pointer": state.current_phase,
            "user_ack": "explicit-cutover-command",
            "note": "Mode-3 semantics apply from the next phase forward.",
        }, indent=2))
    except OSError as exc:
        logger.warning("[cutover] marker write failed: %s", exc)

    return {
        "project": project,
        "dispatch_mode": "mode-3",
        "prior_mode": prior_mode,
        "marker_path": str(marker_path),
    }


def detect_mode_action(project: str) -> Dict[str, Any]:
    """Return the detected dispatch mode (with backfill side-effect)."""
    state = load_project_state(project)
    if state is None:
        raise ValueError(f"Project not found: {project}")
    mode = _detect_dispatch_mode(state)
    # Persist backfill (detect may have mutated extras).
    save_project_state(state)
    return {"project": project, "dispatch_mode": mode}


def main():
    """CLI interface for phase management."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase manager for wicked-crew")
    parser.add_argument("project", help="Project name")
    parser.add_argument("action", choices=["status", "start", "complete", "approve", "skip", "can-advance", "validate", "create", "update", "advance", "execute", "yolo", "cutover", "detect-mode"])
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
    parser.add_argument("--to", default=None, help="Target dispatch mode for cutover (e.g. mode-3)")
    parser.add_argument(
        "--yolo-action", dest="yolo_action",
        default=None, choices=["approve", "revoke", "status"],
        help="Sub-action for the 'yolo' action (approve|revoke|status). Also accepted via --action.",
    )
    parser.add_argument(
        "--action", dest="sub_action", default=None,
        help="Sub-action name (e.g. approve|revoke|status for yolo).",
    )
    parser.add_argument(
        "--skip-reeval",
        action="store_true",
        default=False,
        help=(
            "Bypass phase-end re-eval addendum check (AC-14). "
            "REQUIRES --reason. Writes to phases/{phase}/skip-reeval-log.json. "
            "NEVER set via env-var or config — call-site only (AC-15)."
        ),
    )

    args = parser.parse_args()

    # Enforce --reason when --skip-reeval is passed (AC-14, AC-15)
    # NOTE: NEVER read any env-var or config to default skip_reeval (AC-15).
    if getattr(args, "skip_reeval", False) and args.action in ("approve", "advance"):
        if not (args.reason and args.reason.strip()):
            print(
                "Error: --skip-reeval requires --reason. "
                "Provide a non-empty justification, e.g.: "
                "--reason 'propose-process timed out; addendum manually verified'",
                file=sys.stderr,
            )
            sys.exit(1)

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
        # BLEND-RULE honesty note (review-gate condition a):
        # The CLI `approve` path cannot dispatch subagents — only an
        # Agent-driven caller can inject a real dispatcher. We log an
        # explicit warning so users aren't silently surprised when
        # `_dispatch_gate_reviewer` returns a "dispatcher-unavailable"
        # stub instead of running reviewers. Agent-driven callers should
        # pass `dispatcher=...` to approve_phase() directly.
        logger.warning(
            "CLI approve path: no dispatcher available — gate reviewers "
            "will NOT be auto-dispatched. Use `crew:approve` via the "
            "wicked-garden agent path to invoke reviewers, or pre-stage "
            "a gate-result.json before approval. (BLEND-RULE)"
        )
        try:
            state, next_phase = approve_phase(
                state,
                phase,
                approver=args.approved_by or "user",
                override_gate=args.override_gate,
                override_reason=args.reason or "",
                override_deliverables=args.override_deliverables,
                override_deliverables_reason=args.reason or "",
                skip_reeval=getattr(args, "skip_reeval", False),
                skip_reeval_reason=args.reason or "",
                dispatcher=None,
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

    elif args.action == "execute":
        phase = args.phase or state.current_phase
        try:
            result = execute(args.project, phase)
        except (ValueError, RuntimeError, ConfigError) as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"ok": True, **result}, indent=2))
        else:
            status = result.get("status")
            print(f"execute: status={status} phase={resolve_phase(phase)}")
            if status == "failed":
                print(f"Reason: {result.get('reason')}", file=sys.stderr)
                sys.exit(1)

    elif args.action == "yolo":
        sub = args.yolo_action or args.sub_action or "status"
        try:
            yr = yolo_action(args.project, sub, reason=args.reason or "")
        except ValueError as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"ok": True, **yr}, indent=2))
        else:
            print(json.dumps(yr, indent=2))

    elif args.action == "cutover":
        target = args.to or "mode-3"
        try:
            cr = cutover_action(args.project, target)
        except ValueError as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"ok": True, **cr}, indent=2))
        else:
            print(json.dumps(cr, indent=2))

    elif args.action == "detect-mode":
        try:
            dm = detect_mode_action(args.project)
        except ValueError as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"ok": True, **dm}, indent=2))
        else:
            print(json.dumps(dm, indent=2))


if __name__ == "__main__":
    main()
