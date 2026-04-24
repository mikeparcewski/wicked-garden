#!/usr/bin/env python3
"""scripts/crew/autonomy.py — Single autonomy flag implementation.

Issue #593 (v8-PR-6).

Replaces five old surfaces with one flag, one axis, three modes::

    --autonomy={ask|balanced|full}

Old surfaces → new mode mapping (deprecation shims in commands retain the old
entry-points but route through this module):

    crew:auto-approve        → full
    --yolo                   → full
    --just-finish            → full  (execution behaviour preserved by the cmd)
    engagementLevel=just-finish → full
    (unset / default)        → ask   (conservative; preserves current behaviour)

Gate behaviour is policy-table-driven (see .claude-plugin/autonomy-policy.json),
not flag-conjugation-driven.  Adding a mode tomorrow is a JSON edit, not a code
change.

``balanced`` mode delegates HITL decisions to :mod:`hitl_judge` — the existing
rule-set from Issue #575.  We do NOT re-implement those rules here.

``full`` mode's AC gate integration queries ``acceptance_criteria.load_acs()``
when that module is available (PR-5).  When it is absent, ``full`` mode falls
back gracefully to ``balanced`` behaviour for the AC gate step.

Stdlib-only.  Cross-platform.

Env overrides
-------------
``WG_AUTONOMY``
    Set the mode without a CLI argument.  Values: ``ask``, ``balanced``,
    ``full``.  Unknown values fall back to ``ask`` (conservative default).

``WG_AUTONOMY_DEPRECATION_WARNED``
    Internal flag — set by :func:`emit_deprecation_warning` so the one-shot
    warning is emitted exactly once per session.

Precedence (high to low)
------------------------
1. CLI argument (``--autonomy=X``)
2. ``WG_AUTONOMY`` env var
3. Project-level config (``autonomy_mode`` field in ``project.json`` extras)
4. Default: ``ask``
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Env var consulted by :func:`get_mode`.
ENV_AUTONOMY: str = "WG_AUTONOMY"

#: Session flag that prevents repeating the deprecation warning.
ENV_WARNED: str = "WG_AUTONOMY_DEPRECATION_WARNED"

#: Path to the policy file, relative to the plugin root.
_POLICY_REL_PATH: str = ".claude-plugin/autonomy-policy.json"

#: Deprecation mapping: old surface name → new AutonomyMode value.
DEPRECATION_MAP: dict[str, str] = {
    "crew:auto-approve": "full",
    "--yolo": "full",
    "--just-finish": "full",
    "engagementLevel:just-finish": "full",
    "engagement_level:just-finish": "full",
}


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------


class AutonomyMode(str, Enum):
    """Three-mode autonomy axis.

    Values are string-valued so ``AutonomyMode.ASK == "ask"`` holds and JSON
    serialisation works without an extra ``.value`` call.
    """

    ASK = "ask"
    BALANCED = "balanced"
    FULL = "full"


# ---------------------------------------------------------------------------
# Gate policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GatePolicy:
    """Policy row for one autonomy mode.

    Attributes:
        clarify_halt: How the clarify gate halt is handled.
        council_verdict: How a council verdict is acted on.
        challenge_phase: How the challenge phase gate is handled.
        destructive_ops: How destructive operations are handled.
            Always ``"confirm"`` — this field exists only for schema
            completeness and audit clarity.
    """

    clarify_halt: str
    council_verdict: str
    challenge_phase: str
    destructive_ops: str

    def to_dict(self) -> dict[str, str]:
        """Return a plain dict (JSON-serialisable)."""
        return {
            "clarify_halt": self.clarify_halt,
            "council_verdict": self.council_verdict,
            "challenge_phase": self.challenge_phase,
            "destructive_ops": self.destructive_ops,
        }


# ---------------------------------------------------------------------------
# Gate decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateDecision:
    """Decision record returned by :func:`apply_policy`.

    Attributes:
        proceed: True when the gate should auto-proceed (no human pause).
        reason: Single human-readable line for logs + evidence.
        mode: The autonomy mode that produced this decision.
        gate_type: The gate type that was evaluated.
        signals: Scored inputs that produced the decision (auditable).
    """

    proceed: bool
    reason: str
    mode: AutonomyMode
    gate_type: str
    signals: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # dataclass frozen=True doesn't allow mutation; use object.__setattr__
        if self.signals is None:
            object.__setattr__(self, "signals", {})

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (helper for evidence files)."""
        return {
            "proceed": self.proceed,
            "reason": self.reason,
            "mode": self.mode.value,
            "gate_type": self.gate_type,
            "signals": dict(self.signals),
        }


# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------


def _locate_plugin_root() -> Optional[Path]:
    """Return the plugin root directory.

    Tries ``CLAUDE_PLUGIN_ROOT`` env var first, then walks up from this file.
    Returns None if neither strategy finds a ``autonomy-policy.json``.
    """
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        candidate = Path(env_root) / _POLICY_REL_PATH
        if candidate.exists():
            return Path(env_root)

    # Walk up from this file (scripts/crew/autonomy.py → repo root)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _POLICY_REL_PATH
        if candidate.exists():
            return parent

    return None


def load_policy(
    policy_path: Optional[Path] = None,
) -> dict[AutonomyMode, GatePolicy]:
    """Load the policy table from ``autonomy-policy.json``.

    Args:
        policy_path: Override path to the JSON file (useful in tests).

    Returns:
        Dict mapping each :class:`AutonomyMode` to its :class:`GatePolicy`.

    Raises:
        FileNotFoundError: When the policy file cannot be located.
        ValueError: When the policy JSON is malformed or missing required modes.
    """
    if policy_path is None:
        root = _locate_plugin_root()
        if root is None:
            raise FileNotFoundError(
                "autonomy-policy.json not found. "
                "Set CLAUDE_PLUGIN_ROOT to the plugin directory."
            )
        policy_path = root / _POLICY_REL_PATH

    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    modes_raw = raw.get("modes")
    if not isinstance(modes_raw, dict):
        raise ValueError(
            f"autonomy-policy.json: expected 'modes' to be a dict, "
            f"got {type(modes_raw).__name__}"
        )

    result: dict[AutonomyMode, GatePolicy] = {}
    for mode_name, mode_cfg in modes_raw.items():
        try:
            mode = AutonomyMode(mode_name)
        except ValueError:
            # Unknown modes in the JSON are ignored — forward compat.
            continue
        try:
            result[mode] = GatePolicy(
                clarify_halt=mode_cfg["clarify_halt"],
                council_verdict=mode_cfg["council_verdict"],
                challenge_phase=mode_cfg["challenge_phase"],
                destructive_ops=mode_cfg["destructive_ops"],
            )
        except KeyError as exc:
            raise ValueError(
                f"autonomy-policy.json: mode '{mode_name}' missing field {exc}"
            ) from exc

    required = {AutonomyMode.ASK, AutonomyMode.BALANCED, AutonomyMode.FULL}
    missing = required - result.keys()
    if missing:
        raise ValueError(
            f"autonomy-policy.json: missing required modes: "
            f"{', '.join(m.value for m in sorted(missing, key=lambda x: x.value))}"
        )

    return result


# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------


def get_mode(
    cli_arg: Optional[str] = None,
    project_extras: Optional[Mapping[str, Any]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> AutonomyMode:
    """Resolve the active autonomy mode.

    Precedence (high to low):
    1. ``cli_arg`` — value from ``--autonomy=X`` CLI flag.
    2. ``WG_AUTONOMY`` env var.
    3. ``autonomy_mode`` field in ``project_extras`` (project.json extras).
    4. Default: ``ask`` (conservative; preserves pre-v8 behaviour).

    Unknown values at any layer fall back to the next layer, then ``ask``.

    Args:
        cli_arg: String value from the CLI flag, or None.
        project_extras: Dict of project.json ``extras`` field.
        env: Optional env mapping (testing seam; defaults to ``os.environ``).

    Returns:
        Resolved :class:`AutonomyMode`.
    """
    source = env if env is not None else os.environ

    for candidate in [
        cli_arg,
        source.get(ENV_AUTONOMY),
        (project_extras or {}).get("autonomy_mode"),
    ]:
        if candidate is None:
            continue
        try:
            return AutonomyMode(str(candidate).strip().lower())
        except ValueError:
            continue  # unknown value — fall to next layer

    return AutonomyMode.ASK  # conservative default


# ---------------------------------------------------------------------------
# Policy application
# ---------------------------------------------------------------------------

# Gate type constants — used both here and in tests
GATE_CLARIFY = "clarify"
GATE_COUNCIL = "council"
GATE_CHALLENGE = "challenge"
GATE_DESTRUCTIVE = "destructive"


def apply_policy(
    mode: AutonomyMode,
    gate_type: str,
    context: dict[str, Any],
    policy: Optional[dict[AutonomyMode, GatePolicy]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> GateDecision:
    """Apply the policy table for ``mode`` × ``gate_type``.

    For ``balanced`` mode, delegates HITL decisions to ``hitl_judge`` (the
    existing rule-set from Issue #575).  We import it lazily so the module
    stays usable when hitl_judge is unavailable.

    For ``full`` mode + ``clarify`` gate, queries structured ACs via
    ``acceptance_criteria.load_acs()`` when available (PR-5).  Falls back to
    ``balanced`` behaviour when the module is absent.

    Args:
        mode: The resolved :class:`AutonomyMode`.
        gate_type: One of ``clarify``, ``council``, ``challenge``,
            ``destructive``.
        context: Gate-specific context dict.  Keys vary by gate type.  See
            inline documentation for each gate below.
        policy: Pre-loaded policy dict (caches across calls; loaded from file
            if None).
        env: Optional env mapping (testing seam).

    Returns:
        :class:`GateDecision` with ``proceed=True`` to auto-advance, or
        ``proceed=False`` to pause for human review.
    """
    if policy is None:
        policy = load_policy()

    gate_policy = policy[mode]

    if gate_type == GATE_DESTRUCTIVE:
        # Destructive ops always confirm regardless of mode.
        return GateDecision(
            proceed=False,
            reason="destructive_ops always requires confirmation (all modes)",
            mode=mode,
            gate_type=gate_type,
            signals={"policy_value": gate_policy.destructive_ops},
        )

    if gate_type == GATE_CLARIFY:
        return _apply_clarify_policy(mode, gate_policy, context, env)

    if gate_type == GATE_COUNCIL:
        return _apply_council_policy(mode, gate_policy, context, env)

    if gate_type == GATE_CHALLENGE:
        return _apply_challenge_policy(mode, gate_policy, context, env)

    # Unknown gate type — conservative default: require human review.
    return GateDecision(
        proceed=False,
        reason=f"unknown gate_type {gate_type!r}: defaulting to pause",
        mode=mode,
        gate_type=gate_type,
        signals={"gate_type": gate_type},
    )


# ---------------------------------------------------------------------------
# Per-gate policy helpers
# ---------------------------------------------------------------------------


def _apply_clarify_policy(
    mode: AutonomyMode,
    gate_policy: GatePolicy,
    context: dict[str, Any],
    env: Optional[Mapping[str, str]],
) -> GateDecision:
    """Apply clarify gate policy.

    Context keys consumed:
        complexity (int): Facilitator-rated complexity 0-7.
        facilitator_confidence (float): Confidence in [0, 1].
        open_questions (int): Count of unresolved clarifying questions.
        project_dir (str|Path, optional): Project root for AC lookup.
        ac_satisfied (bool, optional): Pre-computed AC status (skip lookup).
    """
    policy_value = gate_policy.clarify_halt

    if policy_value == "always_pause":
        return GateDecision(
            proceed=False,
            reason="ask mode: clarify always pauses for confirmation",
            mode=mode,
            gate_type=GATE_CLARIFY,
            signals={"policy_value": policy_value},
        )

    if policy_value == "hitl_judge":
        return _clarify_via_hitl_judge(mode, context, env, policy_value)

    # auto_unless_judge_pauses (full mode)
    # First: check structured ACs if available
    ac_gate = _check_ac_gate(context)
    if ac_gate is not None:
        # ac_gate is (all_satisfied: bool, detail: str)
        all_satisfied, detail = ac_gate
        if not all_satisfied:
            # Fall back to balanced / hitl_judge when ACs are not all satisfied
            judge_decision = _clarify_via_hitl_judge(mode, context, env, policy_value)
            return GateDecision(
                proceed=judge_decision.proceed,
                reason=(
                    f"full mode: ACs not all satisfied ({detail}); "
                    f"falling back to HITL judge: {judge_decision.reason}"
                ),
                mode=mode,
                gate_type=GATE_CLARIFY,
                signals={
                    "policy_value": policy_value,
                    "ac_all_satisfied": False,
                    "ac_detail": detail,
                    "hitl_judge_proceed": judge_decision.proceed,
                },
            )
        # All ACs satisfied — still check HITL judge as a safety net
        judge_decision = _clarify_via_hitl_judge(mode, context, env, policy_value)
        if not judge_decision.proceed:
            return GateDecision(
                proceed=False,
                reason=(
                    f"full mode: ACs satisfied but HITL judge paused: "
                    f"{judge_decision.reason}"
                ),
                mode=mode,
                gate_type=GATE_CLARIFY,
                signals={
                    "policy_value": policy_value,
                    "ac_all_satisfied": True,
                    "hitl_judge_proceed": False,
                    "hitl_judge_reason": judge_decision.reason,
                },
            )
        return GateDecision(
            proceed=True,
            reason=f"full mode: all ACs satisfied + HITL judge auto-proceed ({detail})",
            mode=mode,
            gate_type=GATE_CLARIFY,
            signals={
                "policy_value": policy_value,
                "ac_all_satisfied": True,
                "ac_detail": detail,
            },
        )

    # No AC module — fall through to HITL judge
    judge_decision = _clarify_via_hitl_judge(mode, context, env, policy_value)
    return GateDecision(
        proceed=judge_decision.proceed,
        reason=(
            f"full mode (no AC module): HITL judge: {judge_decision.reason}"
        ),
        mode=mode,
        gate_type=GATE_CLARIFY,
        signals={
            "policy_value": policy_value,
            "ac_module_available": False,
            "hitl_judge_proceed": judge_decision.proceed,
        },
    )


def _clarify_via_hitl_judge(
    mode: AutonomyMode,
    context: dict[str, Any],
    env: Optional[Mapping[str, str]],
    policy_value: str,
) -> GateDecision:
    """Delegate the clarify decision to hitl_judge.should_pause_clarify.

    ``yolo`` is set to True in both ``balanced`` and ``full`` modes since
    the user has opted for some level of autonomy.  The rule table in
    hitl_judge maps: yolo=True + clean signals → auto-proceed.
    """
    try:
        try:
            from crew.hitl_judge import should_pause_clarify
        except ImportError:
            from hitl_judge import should_pause_clarify  # type: ignore[no-redef]

        decision = should_pause_clarify(
            complexity=int(context.get("complexity", 0)),
            facilitator_confidence=float(context.get("facilitator_confidence", 1.0)),
            open_questions=int(context.get("open_questions", 0)),
            # NOTE: yolo=True here means "user has granted some level of autonomy" (balanced or full
            # mode), NOT "user passed the deprecated --yolo CLI flag". The hitl_judge internal
            # parameter predates v8-PR-6. See autonomy-policy.json for the canonical mode axis.
            yolo=True,
            env=env,
        )
        return GateDecision(
            proceed=not decision.pause,
            reason=decision.reason,
            mode=mode,
            gate_type=GATE_CLARIFY,
            signals={
                "policy_value": policy_value,
                "judge_rule_id": decision.rule_id,
                **decision.signals,
            },
        )
    except ImportError:
        # hitl_judge unavailable — conservative: pause
        return GateDecision(
            proceed=False,
            reason="hitl_judge unavailable: defaulting to pause (conservative)",
            mode=mode,
            gate_type=GATE_CLARIFY,
            signals={"policy_value": policy_value, "hitl_judge_available": False},
        )


def _apply_council_policy(
    mode: AutonomyMode,
    gate_policy: GatePolicy,
    context: dict[str, Any],
    env: Optional[Mapping[str, str]],
) -> GateDecision:
    """Apply council verdict policy.

    Context keys consumed:
        votes (list[dict]): Council vote list (see hitl_judge.should_pause_council).
        synthesize_quorum (int, optional): Minimum votes for quorum (default 3).
    """
    policy_value = gate_policy.council_verdict

    if policy_value == "show_and_pause":
        return GateDecision(
            proceed=False,
            reason="ask mode: council verdict always shown and paused for human review",
            mode=mode,
            gate_type=GATE_COUNCIL,
            signals={"policy_value": policy_value},
        )

    # pause_on_split (balanced) and auto_if_unanimous (full) both delegate to
    # hitl_judge.should_pause_council — the split-detection logic is identical.
    # The difference is that ``full`` only pauses when the judge says split;
    # ``balanced`` also pauses when the judge says split (same rule, different framing).
    try:
        try:
            from crew.hitl_judge import should_pause_council
        except ImportError:
            from hitl_judge import should_pause_council  # type: ignore[no-redef]

        votes = context.get("votes", [])
        quorum = int(context.get("synthesize_quorum", 3))
        decision = should_pause_council(votes=votes, synthesize_quorum=quorum, env=env)

        if policy_value == "auto_if_unanimous":
            # full mode: auto-proceed when council is unanimous (judge says no pause)
            return GateDecision(
                proceed=not decision.pause,
                reason=(
                    f"full mode: council {'auto-proceed' if not decision.pause else 'pause'}: "
                    f"{decision.reason}"
                ),
                mode=mode,
                gate_type=GATE_COUNCIL,
                signals={
                    "policy_value": policy_value,
                    "judge_rule_id": decision.rule_id,
                    **decision.signals,
                },
            )

        # pause_on_split (balanced): same logic — judge determines if split
        return GateDecision(
            proceed=not decision.pause,
            reason=f"balanced mode: council {decision.reason}",
            mode=mode,
            gate_type=GATE_COUNCIL,
            signals={
                "policy_value": policy_value,
                "judge_rule_id": decision.rule_id,
                **decision.signals,
            },
        )

    except ImportError:
        return GateDecision(
            proceed=False,
            reason="hitl_judge unavailable: defaulting to pause (conservative)",
            mode=mode,
            gate_type=GATE_COUNCIL,
            signals={"policy_value": policy_value, "hitl_judge_available": False},
        )


def _apply_challenge_policy(
    mode: AutonomyMode,
    gate_policy: GatePolicy,
    context: dict[str, Any],
    env: Optional[Mapping[str, str]],
) -> GateDecision:
    """Apply challenge phase gate policy.

    Context keys consumed:
        complexity (int): Facilitator-rated complexity 0-7.
        council_outcome (str): "unanimous", "split", or "none".
    """
    policy_value = gate_policy.challenge_phase

    if policy_value == "require_approval":
        return GateDecision(
            proceed=False,
            reason="ask mode: challenge phase requires explicit approval",
            mode=mode,
            gate_type=GATE_CHALLENGE,
            signals={"policy_value": policy_value},
        )

    if policy_value == "auto":
        return GateDecision(
            proceed=True,
            reason="full mode: challenge phase auto-proceeds",
            mode=mode,
            gate_type=GATE_CHALLENGE,
            signals={"policy_value": policy_value},
        )

    # hitl_judge (balanced mode) — delegate to challenge_charter
    try:
        try:
            from crew.hitl_judge import challenge_charter
        except ImportError:
            from hitl_judge import challenge_charter  # type: ignore[no-redef]

        complexity = int(context.get("complexity", 0))
        council_outcome = str(context.get("council_outcome", "none"))
        decision = challenge_charter(
            complexity=complexity,
            council_outcome=council_outcome,  # type: ignore[arg-type]
            env=env,
        )
        return GateDecision(
            proceed=not decision.pause,
            reason=f"balanced mode: challenge_charter: {decision.reason}",
            mode=mode,
            gate_type=GATE_CHALLENGE,
            signals={
                "policy_value": policy_value,
                "judge_rule_id": decision.rule_id,
                **decision.signals,
            },
        )
    except ImportError:
        return GateDecision(
            proceed=False,
            reason="hitl_judge unavailable: defaulting to pause (conservative)",
            mode=mode,
            gate_type=GATE_CHALLENGE,
            signals={"policy_value": policy_value, "hitl_judge_available": False},
        )


# ---------------------------------------------------------------------------
# AC gate integration (Stream 4)
# ---------------------------------------------------------------------------


def _check_ac_gate(
    context: dict[str, Any],
) -> Optional[tuple[bool, str]]:
    """Query structured ACs from acceptance_criteria module (PR-5).

    Returns:
        ``(all_satisfied, detail_string)`` when the module is available and
        a project directory is provided in context.  Returns ``None`` when
        the module is absent or no project directory is provided — callers
        must treat None as "AC check unavailable" and fall back to HITL judge.

    Context keys consumed:
        project_dir (str|Path, optional): Project root for AC lookup.
        ac_satisfied (bool, optional): If provided, skip module lookup and
            use this pre-computed result directly.  Useful in tests.
    """
    # Fast path: pre-computed result passed explicitly
    if "ac_satisfied" in context:
        satisfied = bool(context["ac_satisfied"])
        detail = "pre-computed ac_satisfied={}".format(satisfied)
        return satisfied, detail

    project_dir = context.get("project_dir")
    if project_dir is None:
        return None

    project_dir = Path(project_dir)

    try:
        try:
            from crew.acceptance_criteria import load_acs
        except ImportError:
            try:
                from acceptance_criteria import load_acs  # type: ignore[no-redef]
            except ImportError:
                return None  # PR-5 module not yet available — degrade gracefully

        acs = load_acs(project_dir)
        if not acs:
            # No ACs defined — treat as "satisfied" to avoid blocking
            return True, "no ACs defined"

        # Determine satisfaction: PR-5 AcceptanceCriterion uses `satisfied_by: tuple[str, ...]`.
        # An AC is satisfied when satisfied_by is non-empty (at least one evidence ref linked).
        total = len(acs)
        satisfied_count = 0
        unsatisfied_ids: list[str] = []
        for ac in acs:
            ac_id = getattr(ac, "id", str(ac))
            # PR-5 canonical shape: AcceptanceCriterion.satisfied_by is a tuple[str, ...]
            # Non-empty tuple means at least one evidence reference has been linked.
            # Dict fallback retained for any legacy serialised forms.
            if hasattr(ac, "satisfied_by"):
                is_sat = bool(getattr(ac, "satisfied_by", ()))
            elif isinstance(ac, dict):
                is_sat = bool(ac.get("satisfied_by") or ac.get("satisfied"))
            else:
                is_sat = False

            if is_sat:
                satisfied_count += 1
            else:
                unsatisfied_ids.append(str(ac_id))

        all_done = satisfied_count == total
        detail = (
            f"{satisfied_count}/{total} ACs satisfied"
            if all_done
            else (
                f"{satisfied_count}/{total} ACs satisfied; "
                f"unsatisfied: {', '.join(unsatisfied_ids[:5])}"
                + (" ..." if len(unsatisfied_ids) > 5 else "")
            )
        )
        return all_done, detail

    except Exception:  # noqa: BLE001 — degrade gracefully; never crash a gate
        return None


# ---------------------------------------------------------------------------
# Deprecation shim helpers
# ---------------------------------------------------------------------------


def map_deprecated_surface(surface_name: str) -> AutonomyMode:
    """Return the new :class:`AutonomyMode` for a deprecated surface name.

    Args:
        surface_name: One of the keys in :data:`DEPRECATION_MAP`.

    Returns:
        The mapped :class:`AutonomyMode`, or :attr:`AutonomyMode.FULL` if the
        surface is not in the table (unknown old surfaces default to full since
        all old surfaces were "more autonomous" variants).
    """
    mapped = DEPRECATION_MAP.get(surface_name, "full")
    try:
        return AutonomyMode(mapped)
    except ValueError:
        return AutonomyMode.FULL


def emit_deprecation_warning(
    surface_name: str,
    new_flag: str = "--autonomy=full",
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Emit a one-shot deprecation warning to stderr.

    The warning is emitted at most once per session (guarded by
    ``WG_AUTONOMY_DEPRECATION_WARNED`` env var set on the process).

    Args:
        surface_name: The old surface being invoked (for the message).
        new_flag: The replacement flag to advertise (e.g. ``--autonomy=full``).
        env: Optional env mapping (testing seam; defaults to os.environ).

    Returns:
        True when the warning was emitted; False when already warned.
    """
    source = env if env is not None else os.environ

    # Check already-warned flag in the real environment (not just the seam)
    if os.environ.get(ENV_WARNED):
        return False

    msg = (
        f"[wicked-garden] DEPRECATION: '{surface_name}' is deprecated. "
        f"Use '{new_flag}' instead. "
        f"Old surface remains functional but will be removed in a future version."
    )
    print(msg, file=sys.stderr)

    # Set the flag so subsequent calls in the same process are suppressed.
    os.environ[ENV_WARNED] = "1"
    return True


# ---------------------------------------------------------------------------
# CLI entry-point (minimal — for smoke testing)
# ---------------------------------------------------------------------------


def _cli() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomy mode resolver (smoke test entry point)."
    )
    parser.add_argument(
        "--autonomy",
        choices=["ask", "balanced", "full"],
        default=None,
        help="Autonomy mode override.",
    )
    parser.add_argument(
        "--gate",
        choices=["clarify", "council", "challenge", "destructive"],
        default="clarify",
        help="Gate type to evaluate.",
    )
    args = parser.parse_args()

    mode = get_mode(cli_arg=args.autonomy)
    policy = load_policy()
    decision = apply_policy(mode, args.gate, {}, policy=policy)
    json.dump(decision.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":  # pragma: no cover
    _cli()
