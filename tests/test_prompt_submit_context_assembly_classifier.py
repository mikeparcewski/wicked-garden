"""tests/test_prompt_submit_context_assembly_classifier.py — intent variable
and directive emission for the UserPromptSubmit hook.

Provenance:
- Issue #578 (legacy): the original Context Assembly classifier suppressed
  the "Deep context needed" directive on conversational prompts. Tests in
  this file used to assert the multi-classifier `_should_emit_context_assembly`
  contract directly.
- Issue #813 (v10 Phase 1): the five overlapping classifiers
  (`_should_emit_context_assembly`, `_starts_with_leading_confirmation`,
  `_contains_meta_phrase`, the inline `_is_near_hot` guard, and
  `_resolve_pull_phase`) were collapsed into a single explicit `intent`
  variable on SessionState. The wisdom from #578 (conversational vs
  substantive) is preserved inside `_detect_intent` — these tests now
  assert intent classification + directive shape rather than the legacy
  emit/suppress booleans.

T1: deterministic — pure functions, no I/O
T3: isolated — each test builds its own prompt + minimal state
T4: single focus per test (one prompt → one expected intent or directive)
T5: descriptive names spell out input + expected outcome
T6: each docstring cites the relevant issue (#578 spirit + #813 contract)
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Hook scripts and scripts/ both need to be on sys.path for the import chain.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOK_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
_SCRIPTS = _REPO_ROOT / "scripts"
for _p in (_SCRIPTS, _HOOK_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from prompt_submit import (  # noqa: E402
    _CONTEXT_ASSEMBLY_ENV_VAR,
    _AUTO_DETECT_TURN_LIMIT,
    _INTENT_VALUES,
    _build_intent_directive,
    _detect_intent,
    _ensure_intent_set,
    _should_emit_context_assembly,
)


@dataclass
class _FakeState:
    """Minimal SessionState stand-in for tests. Mirrors the fields
    `_ensure_intent_set` and `_build_intent_directive` actually read."""
    intent: str | None = None
    intent_explicit: bool = False
    turn_count: int = 1

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def empty_env():
    return {}


@pytest.fixture
def state():
    return _FakeState()


# ---------------------------------------------------------------------------
# _detect_intent — classification (preserves #578 wisdom in v10 form)
# ---------------------------------------------------------------------------

def test_lets_do_it_classifies_as_simple_edit(state):
    """#578/#813: bare continuation tokens stay simple-edit. The legacy
    suppress-on-conversational rule survives as 'detect simple-edit and
    don't emit a directive.'"""
    intent = _detect_intent("lets do it", complexity=0.0, is_risky=False, state=state)
    assert intent == "simple-edit"


def test_what_do_you_think_classifies_as_simple_edit(state):
    """#578/#813: meta phrases asking for assistant's opinion classify as
    simple-edit so no synthesis directive fires."""
    intent = _detect_intent("what do you think?", complexity=0.0, is_risky=False, state=state)
    assert intent == "simple-edit"


def test_short_status_question_classifies_as_simple_edit(state):
    """#813: 'where are we?' is the canonical example the brainstorm cited
    for the daily papercut. Must not trigger any directive."""
    intent = _detect_intent("where are we?", complexity=0.0, is_risky=False, state=state)
    assert intent == "simple-edit"


def test_explain_how_classifies_as_research(state):
    """#813: explanation prompts route to research intent regardless of
    complexity score, so the synthesis directive fires on conceptual asks."""
    intent = _detect_intent(
        "explain how the phase manager handles transitions",
        complexity=0.2, is_risky=False, state=state,
    )
    assert intent == "research"


def test_why_does_classifies_as_research(state):
    """#813: 'why does X' is a canonical research signal."""
    intent = _detect_intent(
        "why does the validator reject this plan?",
        complexity=0.2, is_risky=False, state=state,
    )
    assert intent == "research"


def test_implement_command_classifies_as_feature(state):
    """#813: imperative technical verb 'implement' triggers feature intent."""
    intent = _detect_intent(
        "implement the auth flow with session tokens",
        complexity=0.3, is_risky=False, state=state,
    )
    assert intent == "feature"


def test_risky_prompt_classifies_as_feature(state):
    """#813: risk signals (auth token, rollback, etc.) bypass complexity
    threshold and route to feature."""
    intent = _detect_intent(
        "rotate the api key in production",
        complexity=0.1, is_risky=True, state=state,
    )
    assert intent == "feature"


def test_high_complexity_classifies_as_feature(state):
    """#813: complexity >= synthesis threshold routes to feature."""
    intent = _detect_intent(
        "design the migration pipeline",
        complexity=0.6, is_risky=False, state=state,
    )
    assert intent == "feature"


def test_crew_command_classifies_as_rigor(state):
    """#813: /wicked-garden:crew:* invocations always route to rigor —
    answers brainstorm Q3 (no per-command self-declare ceremony required)."""
    intent = _detect_intent(
        "/wicked-garden:crew:just-finish",
        complexity=0.0, is_risky=False, state=state,
    )
    assert intent == "rigor"


def test_wg_issue_command_classifies_as_rigor(state):
    """#813: /wg-issue invocations route to rigor."""
    intent = _detect_intent("/wg-issue 42", complexity=0.0, is_risky=False, state=state)
    assert intent == "rigor"


def test_empty_prompt_classifies_as_simple_edit(state):
    """#813: empty/whitespace prompts default to simple-edit (no directive)."""
    assert _detect_intent("", 0.0, False, state) == "simple-edit"
    assert _detect_intent("   ", 0.0, False, state) == "simple-edit"


def test_prompt_with_file_path_classifies_as_feature(state):
    """#813/#578: file path mentions are substantive technical signals."""
    intent = _detect_intent(
        "look at scripts/crew/phase_manager.py",
        complexity=0.1, is_risky=False, state=state,
    )
    assert intent == "feature"


def test_prompt_with_code_fence_classifies_as_feature(state):
    """#813/#578: backtick code blocks signal substantive content."""
    intent = _detect_intent(
        "look at this `def foo():` definition",
        complexity=0.1, is_risky=False, state=state,
    )
    assert intent == "feature"


def test_intent_values_locked_at_four(state):
    """#813: the vocabulary is locked at 4. Any change requires a brainstorm
    revisiting the v10 keystone decisions, so this test guards the constant."""
    assert _INTENT_VALUES == ("simple-edit", "feature", "rigor", "research")


# ---------------------------------------------------------------------------
# _ensure_intent_set — sticky-detection contract
# ---------------------------------------------------------------------------

def test_ensure_intent_runs_detection_on_first_turn(state):
    """#813: turn 1 with no existing intent → detect and persist."""
    state.turn_count = 1
    intent = _ensure_intent_set(
        "implement the feature", state, complexity=0.5, is_risky=False
    )
    assert intent == "feature"
    assert state.intent == "feature"
    assert state.intent_explicit is False  # auto-detected, not explicit


def test_ensure_intent_respects_explicit_override(state):
    """#813: when state.intent is already set (e.g. by /wicked-garden:intent),
    auto-detection is skipped and the existing value is returned."""
    state.intent = "rigor"
    state.intent_explicit = True
    state.turn_count = 1
    intent = _ensure_intent_set(
        "where are we?", state, complexity=0.0, is_risky=False
    )
    # Explicit rigor wins even on a prompt that would auto-detect simple-edit.
    assert intent == "rigor"


def test_ensure_intent_falls_back_to_simple_edit_past_window(state):
    """#813: if intent was never set and we're past _AUTO_DETECT_TURN_LIMIT,
    fall back to simple-edit rather than reclassify mid-session (prevents
    flicker)."""
    state.intent = None
    state.turn_count = _AUTO_DETECT_TURN_LIMIT + 5  # well past the window
    intent = _ensure_intent_set(
        "implement the feature", state, complexity=0.5, is_risky=False
    )
    assert intent == "simple-edit"


# ---------------------------------------------------------------------------
# _build_intent_directive — directive shape
# ---------------------------------------------------------------------------

def test_simple_edit_auto_detect_emits_empty_directive():
    """#813: auto-detected simple-edit produces NO directive — the keystone
    'silence is the signal' improvement. This is THE canonical win."""
    out = _build_intent_directive("simple-edit", turn_count=3, explicit=False)
    assert out == ""


def test_simple_edit_explicit_emits_bare_label_only():
    """#813: explicit simple-edit echoes the label so the model knows the
    user steered the framework, but no synthesis directive."""
    out = _build_intent_directive("simple-edit", turn_count=3, explicit=True)
    assert out == '<wg intent="simple-edit" t=3 />'


def test_feature_auto_detect_emits_synthesis_no_label():
    """#813: feature intent emits synthesis directive without the label
    (auto-detected intent stays invisible to prevent confirmation bias)."""
    out = _build_intent_directive("feature", turn_count=2, explicit=False)
    assert "Context Assembly" in out
    assert "intent=feature" in out
    assert "wicked-brain:query" in out
    assert "<wg intent=" not in out  # no label for auto-detect


def test_feature_explicit_emits_label_plus_synthesis():
    """#813: explicit feature emits both the label and the synthesis directive."""
    out = _build_intent_directive("feature", turn_count=4, explicit=True)
    assert out.startswith('<wg intent="feature" t=4 />')
    assert "Context Assembly" in out


def test_research_auto_detect_emits_synthesis():
    """#813: research intent emits the same synthesis directive shape as
    feature (both fire the wicked-brain pull)."""
    out = _build_intent_directive("research", turn_count=1, explicit=False)
    assert "Context Assembly" in out
    assert "intent=research" in out


def test_rigor_includes_chain_context_directive():
    """#813: rigor intent additionally instructs the model to check the
    active crew project's phase + chain_id — that's the rigor-specific
    extension that distinguishes it from feature."""
    out = _build_intent_directive("rigor", turn_count=5, explicit=False)
    assert "Context Assembly" in out
    assert "intent=rigor" in out
    assert "active_chain_id" in out


def test_rigor_explicit_emits_label_plus_chain_directive():
    """#813: explicit rigor pairs label with chain-aware synthesis."""
    out = _build_intent_directive("rigor", turn_count=5, explicit=True)
    assert out.startswith('<wg intent="rigor" t=5 />')
    assert "active_chain_id" in out


# ---------------------------------------------------------------------------
# _should_emit_context_assembly — env override + intent-based gating
# ---------------------------------------------------------------------------

def test_env_always_overrides_intent(state):
    """#813: WG_CONTEXT_ASSEMBLY=always forces emit regardless of intent."""
    state.intent = "simple-edit"
    emit, reason = _should_emit_context_assembly(
        "anything", {_CONTEXT_ASSEMBLY_ENV_VAR: "always"}, state
    )
    assert emit is True
    assert reason == "env_always"


def test_env_off_overrides_intent(state):
    """#813: WG_CONTEXT_ASSEMBLY=off forces suppress regardless of intent."""
    state.intent = "rigor"
    emit, reason = _should_emit_context_assembly(
        "anything", {_CONTEXT_ASSEMBLY_ENV_VAR: "off"}, state
    )
    assert emit is False
    assert reason == "env_off"


def test_simple_edit_intent_suppresses(state):
    """#813: simple-edit intent → no context-assembly emission."""
    state.intent = "simple-edit"
    emit, reason = _should_emit_context_assembly("anything", {}, state)
    assert emit is False
    assert reason == "simple-edit"


def test_feature_intent_emits(state):
    """#813: feature intent → context-assembly fires."""
    state.intent = "feature"
    emit, reason = _should_emit_context_assembly("anything", {}, state)
    assert emit is True
    assert reason == "feature"


def test_rigor_intent_emits(state):
    """#813: rigor intent → context-assembly fires."""
    state.intent = "rigor"
    emit, reason = _should_emit_context_assembly("anything", {}, state)
    assert emit is True
    assert reason == "rigor"


def test_research_intent_emits(state):
    """#813: research intent → context-assembly fires."""
    state.intent = "research"
    emit, reason = _should_emit_context_assembly("anything", {}, state)
    assert emit is True
    assert reason == "research"


def test_no_state_falls_back_to_no_intent(empty_env):
    """#813: when state is None (e.g. partial test setup), the gate
    returns suppress with reason='no_intent' — fail-closed."""
    emit, reason = _should_emit_context_assembly("anything", empty_env, None)
    assert emit is False
    assert reason == "no_intent"
