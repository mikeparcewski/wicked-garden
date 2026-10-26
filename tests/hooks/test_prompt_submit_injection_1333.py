"""garden#1333 — which prompts get a per-turn injection from prompt_submit.

The UserPromptSubmit hook runs on every prompt of every session on every seat
that loads garden. An injection that does not fit the turn costs context and
trains agents to skim past reminders. These tests pin the decisions:

  * Context Assembly fires only when the prompt names code, files, symbols,
    repos or past decisions AND is long enough (> 12 words) or asks about
    them. Never on acknowledgements, status checks or one-word replies, even
    after an earlier prompt made the session's (sticky) intent research.
  * Its text names no MCP tool (none is registered on a seat by design).
  * A regex fall-through emits nothing (no `<wg classify-due />`).
  * `prove:` lines ride only a high-confidence archetype.

Two layers: the pure gate functions, and the real hook run as a subprocess
in an isolated HOME / TMPDIR (so the developer's state never leaks in).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_HOOKS = _REPO / "hooks" / "scripts"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

import prompt_submit as ps  # noqa: E402

CODE_QUESTION = "why does repo_checks.rs refuse a symlinked cwd?"
CHATTER = ["agree", "go", "still waiting", "how is it going?"]


class _State:
    archetypes_v11 = None


class GroundingGate(unittest.TestCase):
    def test_fixture_chatter_never_needs_grounding(self):
        for p in CHATTER + ["thanks, looks good", "ok", "how is the test going?",
                            "what is the status of the outage", "any update?"]:
            with self.subTest(prompt=p):
                self.assertFalse(ps._prompt_needs_grounding(p))

    def test_code_question_needs_grounding(self):
        self.assertTrue(ps._prompt_needs_grounding(CODE_QUESTION))

    def test_other_grounding_shapes(self):
        for p in [
            "how does the hook decide what to inject?",          # question + code noun
            "why did we pick sqlite?",                            # past decision
            "what calls parse_cli_flags?",                        # symbol
            "please carefully refactor the authentication module so that "
            "the session tokens rotate on every login",           # > 12 words + code noun
        ]:
            with self.subTest(prompt=p):
                self.assertTrue(ps._prompt_needs_grounding(p))

    def test_short_imperative_or_non_code_prompt_does_not(self):
        for p in [
            "fix repo_checks.rs",                                 # names code, 2 words, no question
            "can you summarize the meeting notes for me and send them "
            "to the team by the end of the day",                   # long, names no code
        ]:
            with self.subTest(prompt=p):
                self.assertFalse(ps._prompt_needs_grounding(p))

    def test_directive_names_no_mcp_tool(self):
        text = ps._build_intent_directive("research", 1, None)
        self.assertNotIn("SearchEntity", text)
        self.assertNotIn("MCP", text)
        self.assertIn("wicked-garden-mem", text)


class ArchetypeDirective(unittest.TestCase):
    def test_regex_fall_through_emits_nothing(self):
        # Only triage matches: the classify-due nag is gone.
        self.assertIsNone(ps._build_archetype_directive(CODE_QUESTION, "research", _State()))

    def test_chatter_emits_nothing_even_with_a_persisted_classification(self):
        st = _State()
        st.archetypes_v11 = [{"name": "build", "score": 0.9}]
        for p in CHATTER:
            with self.subTest(prompt=p):
                self.assertIsNone(ps._build_archetype_directive(p, "feature", st))

    def test_medium_regex_match_emits_nothing(self):
        # "outage" alone scores incident at 0.55: a misroute risk, so silent.
        self.assertIsNone(ps._build_archetype_directive(
            "what changed in the outage handler code path", "feature", _State()))

    def test_prove_only_on_high_confidence(self):
        d = ps._build_archetype_directive("add a CSV export feature", "feature", _State())
        self.assertIn('<wg archetype="build"', d)
        self.assertIn("prove:", d)

    def test_persisted_card_carries_prove_only_for_confident_archetypes(self):
        st = _State()
        st.archetypes_v11 = [{"name": "build", "score": 0.6}, {"name": "review", "score": 0.8}]
        d = ps._build_archetype_directive("review and build the new export path", "feature", st)
        self.assertIn("build (0.60)", d)
        self.assertIn("--scope review", d)
        self.assertNotIn("--scope build", d)

    def test_threshold_matches_the_catalog_constant(self):
        sys.path.insert(0, str(_REPO / "scripts" / "crew"))
        import archetypes_v11
        self.assertEqual(ps._PROVE_MIN_SCORE, archetypes_v11.HIGH_CONFIDENCE)


def _hook_env():
    home = tempfile.mkdtemp(prefix="wg-1333-home-")
    tmp = tempfile.mkdtemp(prefix="wg-1333-tmp-")
    cfg = Path(home) / ".something-wicked" / "wicked-garden"
    cfg.mkdir(parents=True)
    (cfg / "config.json").write_text(json.dumps({"setup_complete": True}), encoding="utf-8")
    env = dict(os.environ, HOME=home, USERPROFILE=home, TMPDIR=tmp, TEMP=tmp, TMP=tmp,
               CLAUDE_SESSION_ID=f"t1333-{uuid.uuid4().hex}", CLAUDE_PLUGIN_ROOT=str(_REPO),
               WICKED_CONTEXT_BACKEND="off", WG_DAEMON_ENABLED="false")
    return env


def _submit(prompt, env):
    r = subprocess.run([sys.executable, str(_HOOKS / "prompt_submit.py")],
                       input=json.dumps({"prompt": prompt, "session_id": env["CLAUDE_SESSION_ID"]}),
                       capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


class HookEndToEnd(unittest.TestCase):
    """The real hook, one session: the code question first (it makes the
    session's sticky intent `research`), then the fixtures."""

    @classmethod
    def setUpClass(cls):
        env = _hook_env()
        cls.results = [(p, _submit(p, env)) for p in [CODE_QUESTION, *CHATTER, CODE_QUESTION]]

    def test_code_question_injects_context_assembly(self):
        for p, ctx in (self.results[0], self.results[-1]):
            self.assertIn("[Context Assembly", ctx)
            self.assertNotIn("SearchEntity", ctx)

    def test_chatter_injects_nothing(self):
        for p, ctx in self.results[1:-1]:
            with self.subTest(prompt=p):
                self.assertEqual(ctx, "", f"{p!r} must inject nothing, got: {ctx!r}")

    def test_no_classify_due_anywhere(self):
        for p, ctx in self.results:
            with self.subTest(prompt=p):
                self.assertNotIn("classify-due", ctx)
                self.assertNotIn("prove:", ctx)


class MemoryWriteGuard(unittest.TestCase):
    """The native-memory write guard hands over the exact one-line command."""

    def test_deny_prints_the_propose_command(self):
        import pre_tool
        sys.path.insert(0, str(_REPO / "scripts"))
        from _context_backend import MEMORY_PROPOSE_COMMAND
        for path in ["/x/.claude/projects/-p/memory/note.md", "/x/MEMORY.md"]:
            with self.subTest(path=path):
                out = json.loads(pre_tool._handle_write_guard({"file_path": path}))
                reason = out["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertIn(MEMORY_PROPOSE_COMMAND, reason)
        self.assertIn("estate_memory.py --readonly propose '", MEMORY_PROPOSE_COMMAND)


if __name__ == "__main__":
    unittest.main()
