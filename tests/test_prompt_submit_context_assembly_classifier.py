"""tests/test_prompt_submit_context_assembly_classifier.py — Context Assembly
intent classifier for the UserPromptSubmit hook (Issue #578).

Provenance: Issue #578 — ``hooks/scripts/prompt_submit.py`` used to emit a
"Context Assembly — complexity=X" directive on every prompt whose complexity
crossed the synthesis threshold, including obviously conversational prompts
like "any more feedback?" and "lets do it". Same class of bug as #572: the
hook fired without a signal Claude cannot already see itself.

The new classifier is a pure function that takes a prompt plus an env mapping
and returns ``(should_emit: bool, reason: str)``. Rules:

- env override ``WG_CONTEXT_ASSEMBLY=always``  -> force emit
- env override ``WG_CONTEXT_ASSEMBLY=off``     -> force suppress
- auto mode (default): substantive signals beat conversational signals

T1: deterministic — pure function, no I/O
T3: isolated — each test builds its own prompt + env mapping
T4: single focus per test (one prompt / one override)
T5: descriptive names — each name spells out the input and expected outcome
T6: each docstring cites Issue #578
"""

import sys
from pathlib import Path

import pytest

# The hook script is not on sys.path by default — add it before import.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOK_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
if str(_HOOK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOK_SCRIPTS))

from prompt_submit import (  # noqa: E402
    _CONTEXT_ASSEMBLY_ENV_VAR,
    _should_emit_context_assembly,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_env():
    """Env mapping with no WG_CONTEXT_ASSEMBLY override — classifier runs in auto."""
    return {}


# ---------------------------------------------------------------------------
# Conversational prompts — MUST NOT emit the directive
# ---------------------------------------------------------------------------

def test_any_more_feedback_is_conversational_and_suppresses(empty_env):
    """Issue #578 AC: 'any more feedback?' is a meta conversational prompt
    about the conversation itself — must NOT trigger brain grounding."""
    emit, reason = _should_emit_context_assembly("any more feedback?", empty_env)
    assert emit is False
    assert "conversational" in reason


def test_lets_do_it_is_leading_confirmation_and_suppresses(empty_env):
    """Issue #578 AC: 'lets do it' is a bare continuation — classifier must
    recognise the leading-confirmation pattern and suppress."""
    emit, reason = _should_emit_context_assembly("lets do it", empty_env)
    assert emit is False
    assert "conversational" in reason


def test_what_do_you_think_is_meta_phrase_and_suppresses(empty_env):
    """Issue #578 AC: 'what do you think?' asks the assistant's opinion on
    prior context — no new grounding needed."""
    emit, reason = _should_emit_context_assembly("what do you think?", empty_env)
    assert emit is False
    assert "conversational" in reason


def test_ok_proceed_is_leading_confirmation_and_suppresses(empty_env):
    """Issue #578 AC: 'ok proceed' is two continuation tokens back-to-back —
    classifier must catch the leading confirmation."""
    emit, reason = _should_emit_context_assembly("ok proceed", empty_env)
    assert emit is False
    assert "conversational" in reason


def test_single_yes_token_is_continuation_and_suppresses(empty_env):
    """Issue #578 AC: a single 'yes' is the canonical continuation token —
    the hook should never ground the brain on it."""
    emit, reason = _should_emit_context_assembly("yes", empty_env)
    assert emit is False


def test_are_you_sure_is_meta_phrase_and_suppresses(empty_env):
    """Issue #578 AC: 'are you sure?' is a meta phrase addressed at the
    assistant — classifier must suppress."""
    emit, reason = _should_emit_context_assembly("are you sure?", empty_env)
    assert emit is False
    assert "conversational" in reason


def test_thoughts_is_meta_phrase_and_suppresses(empty_env):
    """Issue #578 AC: a bare 'thoughts?' is a request for the assistant's
    opinion — no new work, suppress."""
    emit, reason = _should_emit_context_assembly("thoughts?", empty_env)
    assert emit is False


def test_how_about_this_is_meta_phrase_and_suppresses(empty_env):
    """Issue #578 AC: 'how about this?' is a conversational framing — no
    technical payload, suppress."""
    emit, reason = _should_emit_context_assembly("how about this?", empty_env)
    assert emit is False


# ---------------------------------------------------------------------------
# Substantive prompts — MUST emit the directive
# ---------------------------------------------------------------------------

def test_question_about_validate_plan_file_is_substantive_and_emits(empty_env):
    """Issue #578 AC: 'How does validate_plan.py handle split factor readings?'
    asks a technical question citing a specific file — must ground."""
    emit, reason = _should_emit_context_assembly(
        "How does validate_plan.py handle split factor readings?",
        empty_env,
    )
    assert emit is True
    # File path OR length OR technical verb — any substantive reason wins.
    assert reason.startswith("substantive") or reason == "default_emit"


def test_fix_bug_with_file_path_is_substantive_and_emits(empty_env):
    """Issue #578 AC: 'Fix the bug in hooks/scripts/prompt_submit.py where the
    classifier misfires' has both an imperative verb and a file path."""
    emit, reason = _should_emit_context_assembly(
        "Fix the bug in hooks/scripts/prompt_submit.py where the classifier misfires",
        empty_env,
    )
    assert emit is True
    assert reason.startswith("substantive")


def test_fifty_word_feature_description_is_substantive_and_emits(empty_env):
    """Issue #578 AC: a 50-word prompt describing a feature is well past the
    length threshold — must ground."""
    prompt = (
        "We need to build a new feature that allows users to subscribe to "
        "events published on the bus and replay them later with a cursor. "
        "The subscriber should persist cursor state locally and support "
        "at-least-once delivery semantics with idempotent acknowledgement. "
        "This is the eleventh sentence now describing acceptance tests too."
    )
    assert len(prompt.split()) >= 30
    emit, reason = _should_emit_context_assembly(prompt, empty_env)
    assert emit is True
    assert reason in {"substantive_length", "substantive_file_path",
                      "substantive_code_marker", "substantive_technical_verb"}


def test_prompt_with_file_path_is_substantive_and_emits(empty_env):
    """Issue #578 AC: any prompt with a file path triggers grounding —
    even short ones."""
    emit, reason = _should_emit_context_assembly(
        "look at src/foo/bar.py for me",
        empty_env,
    )
    assert emit is True
    assert reason == "substantive_file_path"


def test_prompt_with_code_fence_is_substantive_and_emits(empty_env):
    """Issue #578 AC: code fences signal real code context — grounding
    should run so the model can align with actual repo structure."""
    emit, reason = _should_emit_context_assembly(
        "```python\nprint('hi')\n```",
        empty_env,
    )
    assert emit is True
    assert reason == "substantive_code_marker"


def test_prompt_with_imperative_refactor_verb_is_substantive_and_emits(empty_env):
    """Issue #578 AC: an imperative technical verb like 'refactor' is a
    strong substantive signal — emit the directive."""
    emit, reason = _should_emit_context_assembly(
        "refactor the router",
        empty_env,
    )
    assert emit is True
    assert reason == "substantive_technical_verb"


# ---------------------------------------------------------------------------
# Env override — WG_CONTEXT_ASSEMBLY=always|off
# ---------------------------------------------------------------------------

def test_env_always_forces_emit_on_conversational_prompt():
    """Issue #578 AC: WG_CONTEXT_ASSEMBLY=always forces emit regardless of
    classifier — operator override for debugging / strict grounding."""
    env = {_CONTEXT_ASSEMBLY_ENV_VAR: "always"}
    emit, reason = _should_emit_context_assembly("yes", env)
    assert emit is True
    assert reason == "env_always"


def test_env_off_forces_suppress_on_substantive_prompt():
    """Issue #578 AC: WG_CONTEXT_ASSEMBLY=off forces suppress regardless of
    classifier — operator override to disable grounding entirely."""
    env = {_CONTEXT_ASSEMBLY_ENV_VAR: "off"}
    emit, reason = _should_emit_context_assembly(
        "Fix the bug in hooks/scripts/prompt_submit.py where the classifier misfires",
        env,
    )
    assert emit is False
    assert reason == "env_off"


def test_env_auto_falls_through_to_classifier():
    """Issue #578 AC: WG_CONTEXT_ASSEMBLY=auto is the documented default —
    must behave identically to an unset variable."""
    env = {_CONTEXT_ASSEMBLY_ENV_VAR: "auto"}
    emit_auto, _ = _should_emit_context_assembly("yes", env)
    emit_unset, _ = _should_emit_context_assembly("yes", {})
    assert emit_auto == emit_unset is False


def test_env_unknown_value_falls_back_to_auto():
    """Issue #578 AC: unknown WG_CONTEXT_ASSEMBLY values must fall back to
    auto — operator typos should not silently flip to always / off."""
    env = {_CONTEXT_ASSEMBLY_ENV_VAR: "banana"}
    emit_unknown, _ = _should_emit_context_assembly("yes", env)
    emit_unset, _ = _should_emit_context_assembly("yes", {})
    assert emit_unknown == emit_unset is False


def test_env_case_insensitive_match():
    """Issue #578 AC: env values are case-insensitive — 'ALWAYS' / 'Off'
    must match the canonical forms."""
    env_always = {_CONTEXT_ASSEMBLY_ENV_VAR: "ALWAYS"}
    env_off = {_CONTEXT_ASSEMBLY_ENV_VAR: "Off"}
    emit_a, reason_a = _should_emit_context_assembly("yes", env_always)
    emit_b, reason_b = _should_emit_context_assembly("refactor code", env_off)
    assert emit_a is True and reason_a == "env_always"
    assert emit_b is False and reason_b == "env_off"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_prompt_suppresses():
    """Issue #578 AC: empty / whitespace-only prompts carry no intent —
    must not emit the directive."""
    emit, reason = _should_emit_context_assembly("   ", {})
    assert emit is False
    assert reason == "empty"


def test_substantive_beats_leading_confirmation():
    """Issue #578 AC: 'substantive wins on conflict' — a 50-word prompt that
    happens to start with 'ok' must still emit, because length overrides
    the leading-confirmation heuristic."""
    prompt = "ok " + ("word " * 40).strip()
    assert len(prompt.split()) >= 30
    emit, reason = _should_emit_context_assembly(prompt, {})
    assert emit is True
    assert reason == "substantive_length"


def test_medium_length_question_without_technical_signal_defaults_emit():
    """Issue #578: 8-29 word prompts with no substantive signal default to
    emit — substantive wins on conflict, so err on the side of grounding."""
    prompt = "I was wondering whether we should pick option A or option B today"
    wc = len(prompt.split())
    assert 8 <= wc < 30
    emit, reason = _should_emit_context_assembly(prompt, {})
    # Either default_emit, or a substantive reason — never conversational.
    assert emit is True
    assert not reason.startswith("conversational")
