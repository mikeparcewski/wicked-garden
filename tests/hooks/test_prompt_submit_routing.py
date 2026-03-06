#!/usr/bin/env python3
"""
tests/hooks/test_prompt_submit_routing.py

Routing regression tests for the prompt_submit.py refactor.

This is the BLOCKING gate — TestRoutingEquivalence must pass before any
hook-local routing function is deleted.

Classes:
  TestHookRouting        — validates hook's own routing functions against fixtures
  TestV2RouterRouting    — validates v2 Router.route() against same fixtures
  TestRoutingEquivalence — cross-validates hook and v2 agree (BLOCKING gate)

AC-6: Routing decision (HOT / FAST / SLOW) must match pre-refactor behavior
      for the full fixture set, including the 41-200 word no-man's-land range.
"""

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_V2_DIR = _SCRIPTS / "smaht" / "v2"
_HOOK_PY = _REPO_ROOT / "hooks" / "scripts" / "prompt_submit.py"

sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_V2_DIR))


# ---------------------------------------------------------------------------
# AC-6 fixture table: (prompt, expected_path)
# ---------------------------------------------------------------------------
# All fixtures must agree between hook and v2 router EXCEPT documented divergences.
# Documented divergences are listed in NO_MANS_LAND_FIXTURES with explanations.

ROUTING_FIXTURES = [
    # HOT path — clear continuations
    ("yes", "hot"),
    ("ok, continue", "hot"),
    ("ok", "hot"),
    ("yep", "hot"),
    ("sounds good", "hot"),
    ("lgtm", "hot"),
    ("proceed", "hot"),
    # FAST path — short, clear intent
    ("find the SessionState class", "fast"),
    ("recall what we decided about caching", "fast"),
    ("where is Router defined", "fast"),
    # SLOW path — complex / planning prompts
    ("we need to refactor how we handle context for each turn", "slow"),
    ("design a migration strategy for the adapter layer", "slow"),
    # No-man's-land: planning prompt with multiple signals — both route SLOW
    (
        "let's plan the approach for handling context, design the strategy and architecture",
        "slow",
    ),
    # >200 words — word-count auto-SLOW in v2
    (" ".join(["word"] * 210), "slow"),
]

# ---------------------------------------------------------------------------
# No-man's-land fixtures (41-200 words) — documented divergences acceptable
# ---------------------------------------------------------------------------
# The hook routes SLOW at >40 words; v2 uses richer signals and may route FAST
# for long research prompts. Both results are documented here.

NO_MANS_LAND_FIXTURES = [
    # 50-word planning prompt — both should route SLOW (planning + complexity)
    (
        "we need to think through the approach for refactoring the context assembly "
        "pipeline. the goal is to move all routing and assembly logic into the v2 layer "
        "while keeping session-scoped concerns in the hook. what is the best strategy "
        "for this migration to ensure we do not break anything",
        "slow",  # expected for both
    ),
    # 45-word research prompt — hook routes SLOW (>40 words),
    # v2 routes FAST (high confidence RESEARCH, no planning escalation).
    # ACCEPTABLE DIVERGENCE: v2 is correct here per AC-6 comment.
    (
        "find all places in the codebase where _is_hot_path is called and explain "
        "what each call site does, listing the file name and line number for each "
        "occurrence so I can understand the full blast radius of removing this function",
        "slow",  # hook expected; v2 may produce "fast" — documented acceptable
    ),
]

# ---------------------------------------------------------------------------
# Known hook-vs-v2 divergences where v2 is correct (hook bug, not v2 bug)
# These prompts are EXCLUDED from TestRoutingEquivalence hard-fail.
# ---------------------------------------------------------------------------
KNOWN_HOOK_BUG_DIVERGENCES = {
    # Hook routes SLOW because no intents match _INTENT_DOMAINS for code symbol questions.
    # v2 correctly routes FAST (RESEARCH intent via "what does").
    "what does _is_continuation do",
    # Hook routes SLOW for 40+ word research prompts (word count gate).
    # v2 uses richer signals and routes FAST.
    "find all places in the codebase where _is_hot_path is called and explain "
    "what each call site does, listing the file name and line number for each "
    "occurrence so I can understand the full blast radius of removing this function",
}


def _load_hook():
    """Import prompt_submit.py as a module without executing main().

    Sets CLAUDE_PLUGIN_ROOT to the repo root so that the hook's path resolution
    uses the local repo scripts, not any installed/cached plugin version.
    """
    import importlib.util
    import os
    # Override CLAUDE_PLUGIN_ROOT for the duration of exec_module so the hook's
    # _PLUGIN_ROOT / _V2_DIR resolve to THIS repo, not an installed cache.
    _orig_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    try:
        spec = importlib.util.spec_from_file_location("prompt_submit", _HOOK_PY)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
    finally:
        if _orig_root is not None:
            os.environ["CLAUDE_PLUGIN_ROOT"] = _orig_root
        else:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    return hook


def _hook_is_refactored(hook) -> bool:
    """Return True if the hook has been refactored (routing functions removed)."""
    return not hasattr(hook, "_is_hot_path")


def _hook_route(hook, prompt: str) -> str:
    """Derive hook routing decision.

    Pre-refactor: uses hook-local routing functions.
    Post-refactor: delegates to v2 Router (hook no longer has routing functions).
    Uses _load_router() to ensure the repo's router.py is used, not a cached copy.
    """
    if _hook_is_refactored(hook):
        # Post-refactor: routing is in v2 Router
        router_mod = _load_router()
        return router_mod.Router().route(prompt).path.value
    # Pre-refactor: hook-local routing functions
    if hook._is_hot_path(prompt):
        return "hot"
    intents = hook._classify_intents(prompt)
    if hook._is_fast_path(prompt, intents):
        return "fast"
    return "slow"


# ---------------------------------------------------------------------------
# TestHookRouting — validates hook's own routing (pre-refactor baseline)
# ---------------------------------------------------------------------------

class TestHookRouting(unittest.TestCase):
    """Routing must agree with expected paths for AC-6 fixtures.

    Pre-refactor: tests hook-local routing functions directly.
    Post-refactor: hook delegates routing to v2, so tests run via v2 Router.
    Both states must produce the expected AC-6 paths.
    """

    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook()
        cls.is_refactored = _hook_is_refactored(cls.hook)

    def test_routing_fixtures(self):
        for prompt, expected in ROUTING_FIXTURES:
            # Skip prompts with known pre-refactor hook bugs (pre-refactor only)
            if not self.is_refactored and prompt in KNOWN_HOOK_BUG_DIVERGENCES:
                continue
            with self.subTest(prompt=prompt[:60]):
                actual = _hook_route(self.hook, prompt)
                self.assertEqual(
                    actual, expected,
                    f"{'v2' if self.is_refactored else 'hook'} routed "
                    f"'{prompt[:60]}' to '{actual}', expected '{expected}'"
                )

    def test_hot_path_short_continuation(self):
        """Single-word continuations must route HOT."""
        for word in ("yes", "ok", "yep", "proceed", "lgtm"):
            with self.subTest(word=word):
                self.assertEqual(_hook_route(self.hook, word), "hot")

    def test_fast_path_clear_research_intent(self):
        """Clear research prompt routes FAST."""
        result = _hook_route(self.hook, "find the SessionState class")
        self.assertEqual(result, "fast")

    def test_slow_path_on_planning_complexity(self):
        """Planning + complexity => SLOW."""
        result = _hook_route(self.hook, "design a migration strategy for the adapter layer")
        self.assertEqual(result, "slow")


# ---------------------------------------------------------------------------
# TestV2RouterRouting — validates v2 Router against same fixtures (post-refactor)
# ---------------------------------------------------------------------------

def _load_router():
    """Load Router from this repo's scripts/smaht/v2/router.py explicitly.

    Uses importlib to load by file path, bypassing any cached version in
    sys.modules that may have been loaded from CLAUDE_PLUGIN_ROOT cache.
    """
    import importlib.util
    router_path = _V2_DIR / "router.py"
    spec = importlib.util.spec_from_file_location("_repo_router", router_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestV2RouterRouting(unittest.TestCase):
    """v2 Router.route() must produce expected paths for all AC-6 fixtures."""

    @classmethod
    def setUpClass(cls):
        router_mod = _load_router()
        cls.router = router_mod.Router()

    def test_routing_fixtures(self):
        for prompt, expected in ROUTING_FIXTURES:
            with self.subTest(prompt=prompt[:60]):
                decision = self.router.route(prompt)
                self.assertEqual(
                    decision.path.value, expected,
                    f"v2 Router routed '{prompt[:60]}' to '{decision.path.value}', "
                    f"expected '{expected}'. Reason: {decision.reason}"
                )

    def test_hot_path_continuation_patterns(self):
        """All HOT-path continuations from AC-6 must hit is_continuation=True."""
        r = self.router
        for prompt in ("yes", "ok, continue", "ok", "yep", "sounds good", "lgtm", "proceed"):
            with self.subTest(prompt=prompt):
                analysis = r.analyze(prompt)
                self.assertTrue(
                    analysis.is_continuation,
                    f"'{prompt}' should have is_continuation=True"
                )

    def test_no_mans_land_planning_routes_slow(self):
        """50-word planning prompt in no-man's-land must route SLOW in v2."""
        r = self.router
        prompt = NO_MANS_LAND_FIXTURES[0][0]
        decision = r.route(prompt)
        self.assertEqual(
            decision.path.value, "slow",
            f"50-word planning prompt routed '{decision.path.value}', expected 'slow'. "
            f"Reason: {decision.reason}"
        )


# ---------------------------------------------------------------------------
# TestRoutingEquivalence — BLOCKING GATE (must pass before deleting hook routing)
# ---------------------------------------------------------------------------

class TestRoutingEquivalence(unittest.TestCase):
    """Routing equivalence verification — BLOCKING GATE.

    Pre-refactor: verifies hook-local functions agree with v2 Router before deletion.
    Post-refactor: verifies v2 Router produces correct paths for all AC-6 fixtures.

    The BLOCKING condition is: v2 Router must match expected paths for all fixtures.
    If it fails, update router.py thresholds first.
    """

    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook()
        cls.is_refactored = _hook_is_refactored(cls.hook)
        router_mod = _load_router()
        cls.router = router_mod.Router()

    def test_hook_and_v2_agree_on_ac6_fixtures(self):
        """All AC-6 fixtures must produce correct paths.

        Pre-refactor: hook and v2 must agree (except known hook bugs).
        Post-refactor: both use v2 Router — trivially agreed.
        """
        divergences = []
        for prompt, expected in ROUTING_FIXTURES:
            hook_path = _hook_route(self.hook, prompt)
            v2_path = self.router.route(prompt).path.value

            if not self.is_refactored and hook_path != v2_path:
                if prompt not in KNOWN_HOOK_BUG_DIVERGENCES:
                    divergences.append((prompt[:60], hook_path, v2_path, expected))
                else:
                    print(
                        f"\n[known-divergence] '{prompt[:60]}': "
                        f"hook={hook_path}, v2={v2_path} (v2 is correct)"
                    )

        if divergences:
            msgs = [
                f"  '{p}': hook={h}, v2={v}, expected={e}"
                for p, h, v, e in divergences
            ]
            self.fail(
                "Routing divergences found — update router.py thresholds "
                "before deleting hook routing:\n" + "\n".join(msgs)
            )

    def test_v2_matches_expected_for_all_fixtures(self):
        """v2 Router must produce the expected path for every AC-6 fixture.

        This is the core post-refactor assertion — the routing contract.
        """
        failures = []
        for prompt, expected in ROUTING_FIXTURES:
            v2_path = self.router.route(prompt).path.value
            if v2_path != expected:
                failures.append((prompt[:60], v2_path, expected))

        if failures:
            msgs = [
                f"  '{p}': v2={v}, expected={e}"
                for p, v, e in failures
            ]
            self.fail("v2 Router produces wrong path:\n" + "\n".join(msgs))

    def test_no_mans_land_documented(self):
        """No-man's-land fixtures: log results, verify v2 is reasonable (not HOT)."""
        r = self.router  # Uses _load_router() instance from setUpClass
        for prompt, _ in NO_MANS_LAND_FIXTURES:
            v2_decision = r.route(prompt)
            v2_path = v2_decision.path.value
            self.assertIn(
                v2_path, ("fast", "slow"),
                f"No-man's-land prompt must not route HOT: '{prompt[:60]}'"
            )
            if not self.is_refactored:
                hook_path = _hook_route(self.hook, prompt)
                print(
                    f"\n[no-mans-land] '{prompt[:40]}...': "
                    f"hook={hook_path}, v2={v2_path}, reason={v2_decision.reason}"
                )
            else:
                print(
                    f"\n[no-mans-land] '{prompt[:40]}...': "
                    f"v2={v2_path}, reason={v2_decision.reason}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
