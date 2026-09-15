#!/usr/bin/env python3
"""tests/hooks/test_prompt_submit_intent.py — the smaht-retirement gate (2026-09-15).

The `smaht` domain was retired whole. Its `smaht-intent` skill was the ONLY writer
of the explicit intent override (`state.intent_explicit=True`); the intent *primitive*
that drives archetype routing — auto-detection + `state.intent` — lives in this hook and
in `_session.py`, NOT in smaht. Retiring smaht therefore removes the manual override path
but MUST NOT degrade routing, and the UserPromptSubmit hook (which runs on EVERY prompt)
MUST still import cleanly and classify to an archetype with smaht gone.

This suite is the gate: it proves the hook's intent + archetype path works without the
retired skill or any `scripts/smaht` import, and that the override plumbing is gone.

Stdlib-only, deterministic (no sleeps, no network, no state-home writes — a fake state).
Provenance: smaht domain retirement (user-approved 2026-09-15).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
# Pin the plugin root to THIS clone BEFORE importing the hook — otherwise the hook
# resolves CLAUDE_PLUGIN_ROOT to a locally-installed wicked-garden and shadows this
# clone's `scripts/` on sys.path (a dev-machine-only hazard; CI leaves the env unset).
os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
for _p in (str(_REPO / "scripts"), str(_REPO / "hooks" / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util  # noqa: E402

import prompt_submit  # noqa: E402  — must import with smaht gone


def _session_from_clone():
    """Load `_session` from THIS clone by explicit path — robust against a
    sys.modules entry another (earlier-collected) test cached from an installed
    wicked-garden before CLAUDE_PLUGIN_ROOT was pinned above."""
    spec = importlib.util.spec_from_file_location("_session_clone", _REPO / "scripts" / "_session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SessionState = _session_from_clone().SessionState


class _FakeState:
    """Minimal session-state stand-in: attribute reads + an update() setter.

    No SessionState.load() so the test never touches the operator's state home.
    """

    def __init__(self, **kw):
        self.intent = None
        self.turn_count = 1
        self.archetypes_v11 = None
        self.classified_at = None
        self.active_project_id = None
        for k, v in kw.items():
            setattr(self, k, v)

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class TestIntentPrimitiveSurvivesSmahtRetirement(unittest.TestCase):
    def test_session_state_no_longer_carries_the_override_field(self):
        # `intent_explicit` was the smaht-intent override flag — retired with the domain.
        self.assertNotIn("intent_explicit", SessionState.__dataclass_fields__)
        # the routing primitive stays.
        self.assertIn("intent", SessionState.__dataclass_fields__)

    def test_intent_auto_detects_for_a_non_trivial_prompt(self):
        state = _FakeState(turn_count=1)
        intent = prompt_submit._ensure_intent_set(
            "refactor the auth module and add rate limiting", state,
            complexity=0.8, is_risky=True,
        )
        self.assertIn(intent, prompt_submit._INTENT_VALUES)
        self.assertNotEqual(intent, "simple-edit")  # a real feature/rigor turn
        self.assertEqual(state.intent, intent)  # persisted without intent_explicit

    def test_intent_auto_detects_simple_edit_for_a_trivial_prompt(self):
        state = _FakeState(turn_count=1)
        intent = prompt_submit._ensure_intent_set("thanks, looks good", state, complexity=0.0, is_risky=False)
        self.assertEqual(intent, "simple-edit")

    def test_intent_directive_carries_no_override_label(self):
        state = _FakeState()
        # new 3-arg signature (the `explicit` param is retired)
        self.assertEqual(prompt_submit._build_intent_directive("simple-edit", 3, state), "")
        feat = prompt_submit._build_intent_directive("feature", 3, state)
        self.assertTrue(feat)  # synthesis directive present
        self.assertNotIn("<wg intent=", feat)  # the override label is gone for good

    def test_archetype_routing_still_classifies_with_smaht_gone(self):
        # Tier 1: a persisted classification routes to a concrete archetype directive.
        state = _FakeState(archetypes_v11=[{"name": "build", "score": 0.9}])
        directive = prompt_submit._build_archetype_directive(
            "add a new endpoint and wire it up", "feature", state,
        )
        self.assertIsNotNone(directive)
        self.assertIn("build", directive)
        # simple-edit is intentionally silent.
        self.assertIsNone(
            prompt_submit._build_archetype_directive("fix typo", "simple-edit", _FakeState())
        )

    def test_archetype_regex_fallback_runs_cleanly_no_traceback(self):
        # No persisted classification → the regex fallback path must run without raising
        # and return a directive or None (fail-open) — never a missing-smaht error.
        result = prompt_submit._build_archetype_directive(
            "debug the failing login test and fix the crash", "feature", _FakeState(),
        )
        self.assertIsInstance(result, (str, type(None)))


if __name__ == "__main__":
    unittest.main()
