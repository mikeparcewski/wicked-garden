"""Tests for council raw-vote surfacing (Issue #584).

T1-T6 compliance:

* T1 Determinism -- fixture votes are hard-coded dicts; no external CLIs,
  no randomness, no sleeps.  Env passed via mapping to avoid cross-test leak.
* T2 No sleep-based sync -- pure function calls.
* T3 Isolation -- each test builds its own vote list + env mapping.
* T4 Single-focus assertions -- one behaviour per test.
* T5 Descriptive names -- ``test_<mode>_<expected_shape>``.
* T6 Provenance -- every docstring cites Issue #584.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve scripts/jam on sys.path so ``from jam.consensus import ...`` works.
# conftest already puts scripts/ at sys.path[0]; we just import the module.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from jam.consensus import (  # noqa: E402
    COUNCIL_OUTPUT_BOTH,
    COUNCIL_OUTPUT_RAW,
    COUNCIL_OUTPUT_SYNTH,
    ENV_COUNCIL_OUTPUT,
    _RATIONALE_MAX_CHARS,
    build_council_output,
)


# ---------------------------------------------------------------------------
# Fixture data -- 4 fake model responses so tests do not spawn external CLIs.
# ---------------------------------------------------------------------------


def _fixture_votes() -> list[dict]:
    """Return a hard-coded 4-model council vote list (Issue #584)."""
    return [
        {
            "model": "claude-opus-4-7",
            "verdict": "APPROVE",
            "confidence": 0.9,
            "raw_text": (
                "Recommendation: Option A is the strongest path.\n"
                "The migration risk is manageable if we stage rollout."
            ),
        },
        {
            "model": "codex",
            "verdict": "APPROVE",
            "confidence": 0.85,
            "raw_text": (
                "I recommend Option A with a caveat about backpressure "
                "on the queue consumer. The downstream service may saturate."
            ),
        },
        {
            "model": "gemini",
            "verdict": "APPROVE",
            "confidence": 0.7,
            "raw_text": (
                "TL;DR: Option A, but run a spike on the retry semantics first.\n"
                "Longer analysis follows about idempotency keys and ordering."
            ),
        },
        {
            "model": "pi",
            "verdict": "APPROVE",
            # confidence deliberately absent -- must render as null, not 0.0.
            "raw_text": (
                "Option A looks fine. I would flag test coverage on the "
                "circuit-breaker path as the weakest link in the current plan."
            ),
        },
    ]


def _fixture_synthesized() -> dict:
    """Return a hard-coded synthesised verdict shape (Issue #584)."""
    return {
        "verdict": "APPROVE",
        "agreement_ratio": 1.0,
        "summary": "Council unanimously approves Option A.",
    }


# ---------------------------------------------------------------------------
# Default (both) -- the common case.
# ---------------------------------------------------------------------------


def test_build_council_output_default_contains_both_keys() -> None:
    """Issue #584: default output carries ``synthesized`` AND ``raw_votes``."""
    result = build_council_output(
        _fixture_votes(), _fixture_synthesized(), env={},
    )
    assert "synthesized" in result
    assert "raw_votes" in result


def test_build_council_output_default_raw_votes_has_one_entry_per_model() -> None:
    """Issue #584: raw_votes has one entry per model that voted (4 in fixture)."""
    votes = _fixture_votes()
    result = build_council_output(votes, _fixture_synthesized(), env={})
    assert len(result["raw_votes"]) == len(votes)
    assert [rv["model"] for rv in result["raw_votes"]] == [
        "claude-opus-4-7", "codex", "gemini", "pi",
    ]


def test_build_council_output_default_raw_vote_has_required_fields() -> None:
    """Issue #584: each raw_vote has the 4 required fields."""
    result = build_council_output(
        _fixture_votes(), _fixture_synthesized(), env={},
    )
    required = {"model", "verdict", "confidence", "rationale"}
    for entry in result["raw_votes"]:
        assert required.issubset(entry.keys()), (
            f"entry missing fields: {required - entry.keys()}"
        )


# ---------------------------------------------------------------------------
# Env-flag modes -- the three expected output shapes.
# ---------------------------------------------------------------------------


def test_build_council_output_synth_mode_emits_only_synthesized() -> None:
    """Issue #584: WG_COUNCIL_OUTPUT=synth emits only ``synthesized``."""
    result = build_council_output(
        _fixture_votes(),
        _fixture_synthesized(),
        env={ENV_COUNCIL_OUTPUT: COUNCIL_OUTPUT_SYNTH},
    )
    assert "synthesized" in result
    assert "raw_votes" not in result


def test_build_council_output_raw_mode_emits_only_raw_votes() -> None:
    """Issue #584: WG_COUNCIL_OUTPUT=raw emits only ``raw_votes``."""
    result = build_council_output(
        _fixture_votes(),
        _fixture_synthesized(),
        env={ENV_COUNCIL_OUTPUT: COUNCIL_OUTPUT_RAW},
    )
    assert "raw_votes" in result
    assert "synthesized" not in result


def test_build_council_output_both_mode_emits_both_keys() -> None:
    """Issue #584: WG_COUNCIL_OUTPUT=both (default) emits both keys."""
    result = build_council_output(
        _fixture_votes(),
        _fixture_synthesized(),
        env={ENV_COUNCIL_OUTPUT: COUNCIL_OUTPUT_BOTH},
    )
    assert "synthesized" in result
    assert "raw_votes" in result


def test_build_council_output_unknown_env_value_falls_back_to_both() -> None:
    """Issue #584: unknown WG_COUNCIL_OUTPUT values degrade to ``both`` safely."""
    result = build_council_output(
        _fixture_votes(),
        _fixture_synthesized(),
        env={ENV_COUNCIL_OUTPUT: "gibberish"},
    )
    assert "synthesized" in result
    assert "raw_votes" in result


# ---------------------------------------------------------------------------
# Rationale extraction -- length + deterministic source.
# ---------------------------------------------------------------------------


def test_build_council_output_rationale_at_most_240_chars() -> None:
    """Issue #584: rationale is bounded by _RATIONALE_MAX_CHARS (240)."""
    long_text = "This is a very verbose rationale. " * 50  # ~1700 chars
    votes = [
        {"model": "claude", "verdict": "APPROVE", "raw_text": long_text},
    ]
    result = build_council_output(votes, _fixture_synthesized(), env={})
    rationale = result["raw_votes"][0]["rationale"]
    assert len(rationale) <= _RATIONALE_MAX_CHARS == 240


def test_build_council_output_rationale_prefers_model_summary_label() -> None:
    """Issue #584: a ``TL;DR:`` / ``Summary:`` line wins over the raw prefix."""
    votes = [
        {
            "model": "gemini",
            "verdict": "APPROVE",
            "raw_text": (
                "Here is a long preamble about trade-offs.\n"
                "TL;DR: Option A with a spike on retry semantics.\n"
                "Further paragraphs about testing..."
            ),
        },
    ]
    result = build_council_output(votes, _fixture_synthesized(), env={})
    rationale = result["raw_votes"][0]["rationale"]
    assert rationale.startswith("Option A with a spike on retry semantics")


# ---------------------------------------------------------------------------
# Confidence handling -- missing must render as None, not 0.0.
# ---------------------------------------------------------------------------


def test_build_council_output_missing_confidence_renders_as_null_not_zero() -> None:
    """Issue #584: a vote without ``confidence`` surfaces as ``None``, not 0.0."""
    result = build_council_output(
        _fixture_votes(), _fixture_synthesized(), env={},
    )
    pi_entry = next(rv for rv in result["raw_votes"] if rv["model"] == "pi")
    assert pi_entry["confidence"] is None
    # Guard against the obvious regression -- None != 0.0 in Python.
    assert pi_entry["confidence"] != 0.0


def test_build_council_output_present_confidence_preserved_as_float() -> None:
    """Issue #584: present confidence values pass through as floats in [0, 1]."""
    result = build_council_output(
        _fixture_votes(), _fixture_synthesized(), env={},
    )
    claude_entry = next(
        rv for rv in result["raw_votes"] if rv["model"] == "claude-opus-4-7"
    )
    assert claude_entry["confidence"] == 0.9
    assert isinstance(claude_entry["confidence"], float)


def test_build_council_output_out_of_range_confidence_becomes_null() -> None:
    """Issue #584: out-of-range confidence (e.g. 85 on a 0-100 scale) -> None.

    Rather than silently divide-by-100 and risk masking a real bug, we mark
    such values as missing so the caller can see the model emitted garbage.
    """
    votes = [
        {"model": "claude", "verdict": "APPROVE", "confidence": 85, "raw_text": "ok"},
    ]
    result = build_council_output(votes, _fixture_synthesized(), env={})
    assert result["raw_votes"][0]["confidence"] is None


# ---------------------------------------------------------------------------
# Verdict + model passthrough -- non-goal guard.
# ---------------------------------------------------------------------------


def test_build_council_output_does_not_rewrite_verdicts() -> None:
    """Issue #584 non-goal: do NOT change which models are called or how votes count."""
    votes = [
        {"model": "m1", "verdict": "REJECT", "raw_text": "no"},
        {"model": "m2", "verdict": "CONDITIONAL", "raw_text": "maybe"},
        {"model": "m3", "verdict": "APPROVE", "raw_text": "yes"},
    ]
    result = build_council_output(votes, _fixture_synthesized(), env={})
    verdicts = [rv["verdict"] for rv in result["raw_votes"]]
    assert verdicts == ["REJECT", "CONDITIONAL", "APPROVE"]


def test_build_council_output_synthesized_passthrough_unchanged() -> None:
    """Issue #584: the synthesised payload is passed through without rewriting."""
    synth = {
        "verdict": "APPROVE",
        "agreement_ratio": 1.0,
        "custom_field": "preserved",
    }
    result = build_council_output(_fixture_votes(), synth, env={})
    assert result["synthesized"] == synth
