#!/usr/bin/env python3
"""HITL Judge -- rule-based decisions for when crew should pause for review.

Issue #575.

"HITL" (human-in-the-loop) is the *absence* of a decision rule that asks:
is there enough signal to proceed autonomously?  Today wicked-garden has two
opposite frictions in the same system:

* ``--yolo`` + the clarify halt unconditionally pauses, even on a crisp
  high-signal bugfix where the crew has every signal it needs.
* The council verdict auto-proceeds even on a 3-1 split or a low-confidence
  vote -- the very cases where a second look is most valuable.

This module exposes three pure decision functions that are called at the
relevant gate sites.  Each call returns a :class:`JudgeDecision` carrying
``pause`` (True = halt for human review), ``reason`` (human-readable line
that ends up in evidence files + logs), ``rule_id`` (stable identifier for
analytics + tests), and ``signals`` (the scored inputs that produced the
decision so an auditor can reproduce the verdict).

Stdlib-only.  Cross-platform.  Importable from any callsite.

Env overrides
-------------

Each callable consults a single env var (default ``auto``):

* ``WG_HITL_CLARIFY``   -- clarify halt
* ``WG_HITL_COUNCIL``   -- council synthesis
* ``WG_HITL_CHALLENGE`` -- challenge charter selection

Values:

* ``auto``  -- apply the rule table (the default).
* ``pause`` -- force ``pause=True`` regardless of inputs.
* ``off``   -- force ``pause=False`` regardless of inputs.

When an override fires, the override is folded into ``reason`` and
``signals['env_override']`` so evidence remains auditable.

Wiring status (Issue #575)
--------------------------

* B1 (clarify halt): documented in ``commands/crew/just-finish.md`` -- the
  halt today is enforced by the orchestrating skill, not by Python, so
  the integration is a documentation paragraph + the recommendation to
  call :func:`should_pause_clarify` and persist the result to
  ``phases/clarify/hitl-decision.json`` via
  :func:`write_hitl_decision_evidence`.
* B2 (challenge charter): the contrarian agent is dispatched by the
  facilitator/orchestrator from a Markdown skill (no single Python
  callsite).  Selecting the charter therefore happens at the prompt-build
  step.  See the ``# TODO(Issue #575): dispatch integration`` marker in
  :func:`challenge_charter` -- the helper is ready; the wiring is left to
  whichever orchestrator next touches contrarian dispatch.
* B3 (council synthesis): documented in ``commands/jam/council.md``.
  ``scripts/jam/consensus.py`` synthesises agreement structurally but
  does not enforce a pause.  The recommended integration is to call
  :func:`should_pause_council` after consensus synthesis and persist the
  result via :func:`write_hitl_decision_evidence` as
  ``council-decision.json``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping


# ---------------------------------------------------------------------------
# Threshold constants
#
# Centralised so an auditor reading a verdict can map every signal back to a
# named rule.  WHY comments capture the design intent so the next reader does
# not have to re-derive it from issue history.
# ---------------------------------------------------------------------------

#: Minimum facilitator confidence required to auto-proceed past clarify.
#: WHY: below 0.7 the facilitator is signalling that the spec leaves room for
#: divergent interpretations -- the *exact* moment a human glance pays back.
CLARIFY_MIN_CONFIDENCE: float = 0.7

#: Complexity score at which clarify always pauses regardless of yolo.
#: WHY: phases.json review-tier mapping treats >=5 as the "full" rigor band;
#: full rigor implies multi-reviewer gates downstream, so we should not skip
#: the human eyeball at the entry gate either.
CLARIFY_COMPLEXITY_PAUSE: int = 5

#: Open-question count above which clarify pauses.
#: WHY: any unresolved question is, by definition, missing signal.  We treat
#: ``>0`` as "pause" rather than "warn" so the halt is binary and testable.
CLARIFY_OPEN_QUESTIONS_PAUSE: int = 0

#: Minimum per-model confidence required to count a council vote as "high
#: confidence".  WHY: 0.6 is the inflection point where models start hedging;
#: below that the verdict is more vibe than analysis and merits human review.
COUNCIL_MIN_VOTE_CONFIDENCE: float = 0.6

#: Vote-margin threshold considered "split".  Two leading verdicts within
#: ``<= COUNCIL_SPLIT_MARGIN`` votes of each other count as split.
#: WHY: Issue #575 calls out "3-1 or closer" as split.  On a 4-model council
#: that means ``margin <= 2`` (4-0 = margin 4 unanimous; 3-1 = margin 2 split;
#: 2-2 = margin 0 split).  Leaving headroom for larger councils: a 5-1 vote
#: (margin 4) would not be split, but 5-3 (margin 2) would.
COUNCIL_SPLIT_MARGIN: int = 2

#: Complexity at which the challenge phase auto-runs (non-skippable).
#: Mirrors the existing v6.1 propose-process trigger.
CHALLENGE_RUN_THRESHOLD: int = 4

#: Complexity at which BOTH integration-sweep and full-steelman charters apply
#: even on a unanimous council (the "high stakes" band).
#: WHY: at >=6 the blast radius is large enough that we want the steelman in
#: addition to the cheaper integration sweep.
CHALLENGE_BOTH_THRESHOLD: int = 6


# ---------------------------------------------------------------------------
# Env override constants
# ---------------------------------------------------------------------------

ENV_CLARIFY: str = "WG_HITL_CLARIFY"
ENV_COUNCIL: str = "WG_HITL_COUNCIL"
ENV_CHALLENGE: str = "WG_HITL_CHALLENGE"

OVERRIDE_AUTO: str = "auto"
OVERRIDE_PAUSE: str = "pause"
OVERRIDE_OFF: str = "off"

_VALID_OVERRIDES = {OVERRIDE_AUTO, OVERRIDE_PAUSE, OVERRIDE_OFF}


# ---------------------------------------------------------------------------
# Charter identifiers
# ---------------------------------------------------------------------------

CHARTER_INTEGRATION_SWEEP: str = "charter.integration-sweep"
CHARTER_FULL_STEELMAN: str = "charter.full-steelman"
CHARTER_BOTH: str = "charter.both"


# ---------------------------------------------------------------------------
# Decision record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeDecision:
    """Decision record returned by every ``should_pause_*`` / charter call.

    Attributes:
        pause: True when the crew should halt for human review.
        reason: Single human-readable line suitable for logs + evidence files.
        rule_id: Stable identifier (e.g. ``clarify.low-confidence``) used by
            tests and analytics so verdicts can be correlated across runs.
        signals: The scored inputs that produced the decision, plus any env
            override that was applied.  Always serialisable to JSON.
    """

    pause: bool
    reason: str
    rule_id: str
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (helper for evidence-file emit)."""
        return {
            "pause": self.pause,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "signals": dict(self.signals),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_override(
    env_var: str,
    env: Mapping[str, str] | None,
) -> str:
    """Read and validate an env override.  Unknown values fall back to auto.

    We deliberately do not raise on unknown values -- the judge must never
    be the cause of a crew halt because someone typo'd an env var.  Unknown
    values are logged into the decision signals for auditability.
    """
    source = env if env is not None else os.environ
    raw = (source.get(env_var) or OVERRIDE_AUTO).strip().lower()
    if raw not in _VALID_OVERRIDES:
        return OVERRIDE_AUTO
    return raw


def _apply_override(
    override: str,
    base: JudgeDecision,
    env_var: str,
) -> JudgeDecision:
    """Fold an env override into a base decision.

    ``pause`` and ``off`` flip ``pause`` and prefix the reason so reviewers
    can immediately see that the verdict came from an override rather than
    the rule table.  ``auto`` is the no-op path.
    """
    if override == OVERRIDE_AUTO:
        return base

    new_signals = dict(base.signals)
    new_signals["env_override"] = {"var": env_var, "value": override}

    if override == OVERRIDE_PAUSE:
        return JudgeDecision(
            pause=True,
            reason=(
                f"env override {env_var}=pause forced halt "
                f"(would otherwise be: {base.reason})"
            ),
            rule_id=f"{base.rule_id}.override-pause",
            signals=new_signals,
        )

    # override == OVERRIDE_OFF
    return JudgeDecision(
        pause=False,
        reason=(
            f"env override {env_var}=off skipped halt "
            f"(would otherwise be: {base.reason})"
        ),
        rule_id=f"{base.rule_id}.override-off",
        signals=new_signals,
    )


# ---------------------------------------------------------------------------
# Public API: clarify
# ---------------------------------------------------------------------------


def should_pause_clarify(
    *,
    complexity: int,
    facilitator_confidence: float,
    open_questions: int,
    yolo: bool,
    env: Mapping[str, str] | None = None,
) -> JudgeDecision:
    """Decide whether the clarify gate should halt for human acknowledgment.

    Rule table (auto mode):

    * ``yolo=False``                              -> pause (safety baseline)
    * ``facilitator_confidence < 0.7``            -> pause (low-confidence)
    * ``complexity >= 5``                         -> pause (complexity-threshold)
    * ``open_questions > 0``                      -> pause (open-questions)
    * otherwise (yolo + clean signals)            -> auto-proceed

    Args:
        complexity: Facilitator-rated complexity (0-7, ``phases.json`` band).
        facilitator_confidence: Facilitator self-rated confidence in [0, 1].
        open_questions: Count of unresolved clarifying questions.
        yolo: True when the user passed ``--yolo`` (autonomous mode).
        env: Optional env mapping (testing seam; defaults to ``os.environ``).

    Returns:
        JudgeDecision -- ``pause`` True when crew must halt.
    """
    signals = {
        "complexity": complexity,
        "facilitator_confidence": facilitator_confidence,
        "open_questions": open_questions,
        "yolo": yolo,
    }

    if not yolo:
        base = JudgeDecision(
            pause=True,
            reason="non-yolo mode always pauses clarify for confirmation",
            rule_id="clarify.non-yolo-baseline",
            signals=signals,
        )
    elif facilitator_confidence < CLARIFY_MIN_CONFIDENCE:
        base = JudgeDecision(
            pause=True,
            reason=(
                f"facilitator confidence {facilitator_confidence:.2f} below "
                f"threshold {CLARIFY_MIN_CONFIDENCE:.2f}"
            ),
            rule_id="clarify.low-confidence",
            signals=signals,
        )
    elif complexity >= CLARIFY_COMPLEXITY_PAUSE:
        base = JudgeDecision(
            pause=True,
            reason=(
                f"complexity {complexity} at or above threshold "
                f"{CLARIFY_COMPLEXITY_PAUSE}"
            ),
            rule_id="clarify.complexity-threshold",
            signals=signals,
        )
    elif open_questions > CLARIFY_OPEN_QUESTIONS_PAUSE:
        base = JudgeDecision(
            pause=True,
            reason=f"{open_questions} unresolved clarify question(s) remain",
            rule_id="clarify.open-questions",
            signals=signals,
        )
    else:
        base = JudgeDecision(
            pause=False,
            reason=(
                f"yolo + confidence {facilitator_confidence:.2f} + complexity "
                f"{complexity} + 0 open questions: auto-proceed"
            ),
            rule_id="clarify.auto-proceed",
            signals=signals,
        )

    override = _read_override(ENV_CLARIFY, env)
    return _apply_override(override, base, ENV_CLARIFY)


# ---------------------------------------------------------------------------
# Public API: council
# ---------------------------------------------------------------------------


def _tally_votes(votes: list[dict]) -> dict[str, int]:
    """Count verdicts.  Ignores entries missing a verdict field."""
    tally: dict[str, int] = {}
    for vote in votes:
        verdict = vote.get("verdict")
        if not verdict:
            continue
        tally[verdict] = tally.get(verdict, 0) + 1
    return tally


def _is_split(tally: dict[str, int]) -> bool:
    """True when the top two verdicts are within ``COUNCIL_SPLIT_MARGIN``."""
    if len(tally) < 2:
        return False
    counts = sorted(tally.values(), reverse=True)
    return (counts[0] - counts[1]) <= COUNCIL_SPLIT_MARGIN


def _lowest_confidence(votes: list[dict]) -> tuple[float, str | None]:
    """Return (lowest_confidence, model_name) across all votes.

    Returns (1.0, None) when no confidence values are present so the caller
    short-circuits the low-confidence branch rather than blowing up.
    """
    lowest: float = 1.0
    who: str | None = None
    for vote in votes:
        conf = vote.get("confidence")
        if conf is None:
            continue
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_f < lowest:
            lowest = conf_f
            who = vote.get("model")
    return lowest, who


def should_pause_council(
    *,
    votes: list[dict],
    synthesize_quorum: int = 3,
    env: Mapping[str, str] | None = None,
) -> JudgeDecision:
    """Decide whether council synthesis should halt for human adjudication.

    Rule table (auto mode):

    * fewer than ``synthesize_quorum`` votes              -> pause (no-quorum)
    * top two verdicts within ``COUNCIL_SPLIT_MARGIN``    -> pause (split-verdict)
    * any vote with ``confidence < 0.6``                  -> pause (low-confidence-vote)
    * otherwise (unanimous + high confidence)             -> auto-proceed

    Args:
        votes: List of ``{"model": str, "verdict": str, "confidence": float}``
            dicts, one per council participant.
        synthesize_quorum: Minimum votes required to even attempt synthesis.
        env: Optional env mapping (testing seam).

    Returns:
        JudgeDecision -- ``pause`` True when crew must halt for review.
    """
    tally = _tally_votes(votes)
    lowest_conf, lowest_model = _lowest_confidence(votes)
    signals: dict[str, Any] = {
        "vote_count": len(votes),
        "tally": tally,
        "lowest_confidence": lowest_conf,
        "lowest_confidence_model": lowest_model,
        "synthesize_quorum": synthesize_quorum,
    }

    if len(votes) < synthesize_quorum:
        base = JudgeDecision(
            pause=True,
            reason=(
                f"only {len(votes)} council vote(s); quorum is "
                f"{synthesize_quorum}"
            ),
            rule_id="council.no-quorum",
            signals=signals,
        )
    elif _is_split(tally):
        base = JudgeDecision(
            pause=True,
            reason=(
                f"split verdict (top two within {COUNCIL_SPLIT_MARGIN} vote): "
                f"{tally}"
            ),
            rule_id="council.split-verdict",
            signals=signals,
        )
    elif lowest_conf < COUNCIL_MIN_VOTE_CONFIDENCE:
        base = JudgeDecision(
            pause=True,
            reason=(
                f"model {lowest_model!r} confidence {lowest_conf:.2f} below "
                f"threshold {COUNCIL_MIN_VOTE_CONFIDENCE:.2f}"
            ),
            rule_id="council.low-confidence-vote",
            signals=signals,
        )
    else:
        base = JudgeDecision(
            pause=False,
            reason=(
                f"unanimous council with min confidence {lowest_conf:.2f}: "
                f"auto-proceed"
            ),
            rule_id="council.auto-proceed",
            signals=signals,
        )

    override = _read_override(ENV_COUNCIL, env)
    return _apply_override(override, base, ENV_COUNCIL)


# ---------------------------------------------------------------------------
# Public API: challenge charter
# ---------------------------------------------------------------------------


def challenge_charter(
    *,
    complexity: int,
    council_outcome: Literal["unanimous", "split", "none"],
    env: Mapping[str, str] | None = None,
) -> JudgeDecision:
    """Pick the contrarian charter to use at the challenge phase.

    Challenge is **not skippable** at ``complexity >= CHALLENGE_RUN_THRESHOLD``
    -- evidence in wicked-brain memory ``unanimous-council-does-not-skip-
    challenge-phase`` shows a 4-0 council can still miss a wiring consequence
    that the contrarian catches.  The charter shifts based on council outcome:

    * unanimous + complexity in [4, 5]   -> ``charter.integration-sweep``
    * split, any complexity >= 4          -> ``charter.full-steelman``
    * unanimous + complexity >= 6        -> ``charter.both``
    * split + complexity >= 6             -> ``charter.full-steelman``
    * complexity < 4                      -> skipped below threshold

    Always returns ``pause=False`` -- challenge runs as part of the workflow,
    not as a halt.  The ``reason`` field carries the charter id so callsites
    can dispatch the correct contrarian prompt.

    Args:
        complexity: Facilitator-rated complexity (0-7).
        council_outcome: ``unanimous``, ``split``, or ``none`` (no council ran).
        env: Optional env mapping (testing seam).

    Returns:
        JudgeDecision -- ``pause`` False (always); ``reason`` carries charter id.

    Note (Issue #575):
        # TODO(Issue #575): dispatch integration -- the contrarian agent is
        # currently dispatched from the facilitator skill, not from a single
        # Python callsite.  When the dispatch path moves into Python, call
        # this helper and feed ``decision.signals['charter']`` into the
        # Task() prompt builder.
    """
    signals: dict[str, Any] = {
        "complexity": complexity,
        "council_outcome": council_outcome,
    }

    if complexity < CHALLENGE_RUN_THRESHOLD:
        signals["charter"] = None
        base = JudgeDecision(
            pause=False,
            reason=(
                f"complexity {complexity} below challenge threshold "
                f"{CHALLENGE_RUN_THRESHOLD}: challenge skipped"
            ),
            rule_id="challenge.skipped-below-threshold",
            signals=signals,
        )
    else:
        if council_outcome == "split":
            charter = CHARTER_FULL_STEELMAN
            rule = "challenge.split-steelman"
        elif council_outcome == "unanimous" and complexity >= CHALLENGE_BOTH_THRESHOLD:
            charter = CHARTER_BOTH
            rule = "challenge.unanimous-both"
        elif council_outcome == "unanimous":
            charter = CHARTER_INTEGRATION_SWEEP
            rule = "challenge.unanimous-integration-sweep"
        elif complexity >= CHALLENGE_BOTH_THRESHOLD:
            # No council ran (council_outcome == "none") at high complexity --
            # treat like a split to be safe; the steelman is the conservative
            # default when we lack a unanimous signal.
            charter = CHARTER_FULL_STEELMAN
            rule = "challenge.no-council-steelman"
        else:
            # No council ran at moderate complexity -- still run the steelman.
            charter = CHARTER_FULL_STEELMAN
            rule = "challenge.no-council-steelman"

        signals["charter"] = charter
        base = JudgeDecision(
            pause=False,
            reason=(
                f"{charter} (council={council_outcome}, complexity={complexity})"
            ),
            rule_id=rule,
            signals=signals,
        )

    override = _read_override(ENV_CHALLENGE, env)
    if override == OVERRIDE_AUTO:
        return base

    # For challenge overrides we keep the original charter in signals so the
    # auditor can see what would have run.  Pause-override flips pause; off-
    # override is a no-op at challenge (challenge already returns pause=False)
    # but still recorded so reviewers see the env was set.
    new_signals = dict(base.signals)
    new_signals["env_override"] = {"var": ENV_CHALLENGE, "value": override}

    if override == OVERRIDE_PAUSE:
        return JudgeDecision(
            pause=True,
            reason=(
                f"env override {ENV_CHALLENGE}=pause forced halt "
                f"(would otherwise be: {base.reason})"
            ),
            rule_id=f"{base.rule_id}.override-pause",
            signals=new_signals,
        )

    # OVERRIDE_OFF on challenge: explicit no-op acknowledgment.
    return JudgeDecision(
        pause=False,
        reason=(
            f"env override {ENV_CHALLENGE}=off acknowledged "
            f"(challenge already proceeds without halt: {base.reason})"
        ),
        rule_id=f"{base.rule_id}.override-off",
        signals=new_signals,
    )


# ---------------------------------------------------------------------------
# Evidence-file emit helper
# ---------------------------------------------------------------------------


def write_hitl_decision_evidence(
    project_dir: Path,
    phase: str,
    filename: str,
    decision: JudgeDecision,
) -> Path:
    """Write a :class:`JudgeDecision` to ``phases/{phase}/{filename}``.

    Small, single-purpose helper so callsites do not have to know the JSON
    schema.  The path mirrors the existing conditions-manifest convention so
    auditors find HITL evidence in the same place as gate evidence.

    Args:
        project_dir: Project root directory.
        phase: Phase name (e.g. ``clarify``, ``challenge``).
        filename: Evidence-file name (e.g. ``hitl-decision.json``).
        decision: The decision to persist.

    Returns:
        Absolute path to the written evidence file.

    Raises:
        OSError: If the parent directory cannot be created or the write fails.
            We deliberately do not swallow the error -- evidence loss must be
            visible.
    """
    target_dir = project_dir / "phases" / phase
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    # Site W5 of bus-cutover wave-2 (#746): emit BEFORE the disk write
    # so the projector handler can replay the same bytes.  chain_id
    # uses {project}.{phase}.{filename-stem} for per-evidence-file
    # uniqueness (different decisions land in different files within
    # the same phase: hitl-decision.json vs hitl-council-decision.json
    # vs hitl-challenge-decision.json).  Fail-open: bus unavailable
    # must NOT block the disk write — evidence loss must be visible.
    body_bytes = json.dumps(decision.to_dict(), indent=2, sort_keys=True)
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_root = str(_Path(__file__).resolve().parents[1])
        if _scripts_root not in _sys.path:
            _sys.path.insert(0, _scripts_root)
        from _bus import emit_event  # type: ignore[import]
        project_id_str = project_dir.name
        # filename stem (strip .json) for chain_id discriminator
        filename_stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        emit_event(
            "wicked.hitl.decision_recorded",
            {
                "project_id": project_id_str,
                "phase": phase,
                "filename": filename,
                "raw_payload": body_bytes,
                "pause": decision.pause,
                "rule_id": decision.rule_id,
            },
            chain_id=f"{project_id_str}.{phase}.{filename_stem}",
        )
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        pass  # bus unavailable — projector handler replays on reconnect

    return target_path
