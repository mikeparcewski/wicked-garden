"""Tests for ``scripts/crew/hitl_judge.py`` (Issue #575).

T1-T6:

* Deterministic -- no sleeps, no randomness, env passed via mapping fixtures.
* Single-focus -- each test asserts one rule branch.
* Descriptive names -- ``test_<callable>_<rule>_<expected>``.
* Provenance -- every docstring cites Issue #575.
"""

from __future__ import annotations

from crew.hitl_judge import (
    CHARTER_BOTH,
    CHARTER_FULL_STEELMAN,
    CHARTER_INTEGRATION_SWEEP,
    JudgeDecision,
    challenge_charter,
    should_pause_clarify,
    should_pause_council,
)


# ---------------------------------------------------------------------------
# Clarify
# ---------------------------------------------------------------------------


def test_clarify_yolo_clean_signals_auto_proceeds() -> None:
    """Issue #575: yolo + high confidence + low complexity + 0 open Qs -> auto-proceed."""
    decision = should_pause_clarify(
        complexity=2,
        facilitator_confidence=0.9,
        open_questions=0,
        yolo=True,
        env={},
    )
    assert decision.pause is False
    assert decision.rule_id == "clarify.auto-proceed"


def test_clarify_low_confidence_pauses_even_under_yolo() -> None:
    """Issue #575: yolo + facilitator confidence 0.5 -> pause (low-confidence)."""
    decision = should_pause_clarify(
        complexity=2,
        facilitator_confidence=0.5,
        open_questions=0,
        yolo=True,
        env={},
    )
    assert decision.pause is True
    assert decision.rule_id == "clarify.low-confidence"


def test_clarify_complexity_threshold_pauses_even_under_yolo() -> None:
    """Issue #575: yolo + complexity 5 -> pause (complexity-threshold)."""
    decision = should_pause_clarify(
        complexity=5,
        facilitator_confidence=0.9,
        open_questions=0,
        yolo=True,
        env={},
    )
    assert decision.pause is True
    assert decision.rule_id == "clarify.complexity-threshold"


def test_clarify_open_questions_pauses_even_under_yolo() -> None:
    """Issue #575: yolo + 2 open questions -> pause (open-questions)."""
    decision = should_pause_clarify(
        complexity=2,
        facilitator_confidence=0.9,
        open_questions=2,
        yolo=True,
        env={},
    )
    assert decision.pause is True
    assert decision.rule_id == "clarify.open-questions"


def test_clarify_non_yolo_always_pauses() -> None:
    """Issue #575: yolo=False always pauses, even on otherwise-clean signals."""
    decision = should_pause_clarify(
        complexity=1,
        facilitator_confidence=0.99,
        open_questions=0,
        yolo=False,
        env={},
    )
    assert decision.pause is True
    assert decision.rule_id == "clarify.non-yolo-baseline"


def test_clarify_env_off_overrides_low_confidence() -> None:
    """Issue #575: WG_HITL_CLARIFY=off forces pause=False even with low confidence."""
    decision = should_pause_clarify(
        complexity=2,
        facilitator_confidence=0.4,
        open_questions=0,
        yolo=True,
        env={"WG_HITL_CLARIFY": "off"},
    )
    assert decision.pause is False
    assert decision.rule_id.endswith(".override-off")
    assert decision.signals["env_override"] == {
        "var": "WG_HITL_CLARIFY",
        "value": "off",
    }
    # Original verdict is preserved in the reason for audit.
    assert "facilitator confidence" in decision.reason


def test_clarify_env_pause_overrides_clean_signals() -> None:
    """Issue #575: WG_HITL_CLARIFY=pause forces pause=True even on clean signals."""
    decision = should_pause_clarify(
        complexity=1,
        facilitator_confidence=0.95,
        open_questions=0,
        yolo=True,
        env={"WG_HITL_CLARIFY": "pause"},
    )
    assert decision.pause is True
    assert decision.rule_id.endswith(".override-pause")
    assert decision.signals["env_override"] == {
        "var": "WG_HITL_CLARIFY",
        "value": "pause",
    }


# ---------------------------------------------------------------------------
# Council
# ---------------------------------------------------------------------------


def _vote(model: str, verdict: str, confidence: float) -> dict:
    return {"model": model, "verdict": verdict, "confidence": confidence}


def test_council_unanimous_high_confidence_auto_proceeds() -> None:
    """Issue #575: 4 unanimous APPROVE @ 0.9 -> auto-proceed."""
    votes = [
        _vote("codex", "APPROVE", 0.9),
        _vote("gemini", "APPROVE", 0.9),
        _vote("opencode", "APPROVE", 0.9),
        _vote("pi", "APPROVE", 0.9),
    ]
    decision = should_pause_council(votes=votes, env={})
    assert decision.pause is False
    assert decision.rule_id == "council.auto-proceed"


def test_council_three_to_one_split_pauses() -> None:
    """Issue #575: 3-1 split -> pause (split-verdict)."""
    votes = [
        _vote("codex", "APPROVE", 0.9),
        _vote("gemini", "APPROVE", 0.9),
        _vote("opencode", "APPROVE", 0.9),
        _vote("pi", "REJECT", 0.9),
    ]
    decision = should_pause_council(votes=votes, env={})
    assert decision.pause is True
    assert decision.rule_id == "council.split-verdict"


def test_council_unanimous_one_low_confidence_pauses() -> None:
    """Issue #575: unanimous APPROVE but one model confidence 0.5 -> pause."""
    votes = [
        _vote("codex", "APPROVE", 0.9),
        _vote("gemini", "APPROVE", 0.9),
        _vote("opencode", "APPROVE", 0.9),
        _vote("pi", "APPROVE", 0.5),
    ]
    decision = should_pause_council(votes=votes, env={})
    assert decision.pause is True
    assert decision.rule_id == "council.low-confidence-vote"
    assert decision.signals["lowest_confidence_model"] == "pi"


def test_council_env_off_overrides_split() -> None:
    """Issue #575: WG_HITL_COUNCIL=off forces pause=False on a split verdict."""
    votes = [
        _vote("codex", "APPROVE", 0.9),
        _vote("gemini", "APPROVE", 0.9),
        _vote("opencode", "REJECT", 0.9),
        _vote("pi", "REJECT", 0.9),
    ]
    decision = should_pause_council(
        votes=votes,
        env={"WG_HITL_COUNCIL": "off"},
    )
    assert decision.pause is False
    assert decision.rule_id.endswith(".override-off")
    assert decision.signals["env_override"] == {
        "var": "WG_HITL_COUNCIL",
        "value": "off",
    }


# ---------------------------------------------------------------------------
# Challenge charter
# ---------------------------------------------------------------------------


def test_challenge_below_threshold_skipped() -> None:
    """Issue #575: complexity 3 -> rule_id 'challenge.skipped-below-threshold'."""
    decision = challenge_charter(
        complexity=3,
        council_outcome="unanimous",
        env={},
    )
    assert decision.pause is False
    assert decision.rule_id == "challenge.skipped-below-threshold"
    assert decision.signals["charter"] is None


def test_challenge_complexity_4_unanimous_uses_integration_sweep() -> None:
    """Issue #575: complexity 4 + unanimous -> 'integration-sweep' charter."""
    decision = challenge_charter(
        complexity=4,
        council_outcome="unanimous",
        env={},
    )
    assert decision.pause is False
    assert "integration-sweep" in decision.reason
    assert decision.signals["charter"] == CHARTER_INTEGRATION_SWEEP


def test_challenge_complexity_4_split_uses_full_steelman() -> None:
    """Issue #575: complexity 4 + split -> 'full-steelman' charter."""
    decision = challenge_charter(
        complexity=4,
        council_outcome="split",
        env={},
    )
    assert decision.pause is False
    assert "full-steelman" in decision.reason
    assert decision.signals["charter"] == CHARTER_FULL_STEELMAN


def test_challenge_complexity_6_unanimous_uses_both() -> None:
    """Issue #575: complexity 6 + unanimous -> 'both' charter."""
    decision = challenge_charter(
        complexity=6,
        council_outcome="unanimous",
        env={},
    )
    assert decision.pause is False
    assert "both" in decision.reason
    assert decision.signals["charter"] == CHARTER_BOTH


def test_challenge_complexity_6_split_uses_full_steelman() -> None:
    """Issue #575: complexity 6 + split -> 'full-steelman' charter."""
    decision = challenge_charter(
        complexity=6,
        council_outcome="split",
        env={},
    )
    assert decision.pause is False
    assert "full-steelman" in decision.reason
    assert decision.signals["charter"] == CHARTER_FULL_STEELMAN


def test_challenge_env_pause_overrides_but_records_charter() -> None:
    """Issue #575: WG_HITL_CHALLENGE=pause flips pause but keeps original charter in signals."""
    decision = challenge_charter(
        complexity=4,
        council_outcome="unanimous",
        env={"WG_HITL_CHALLENGE": "pause"},
    )
    assert decision.pause is True
    assert decision.rule_id.endswith(".override-pause")
    # Original charter must remain visible for audit.
    assert decision.signals["charter"] == CHARTER_INTEGRATION_SWEEP
    assert decision.signals["env_override"] == {
        "var": "WG_HITL_CHALLENGE",
        "value": "pause",
    }
