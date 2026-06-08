"""Unit tests for hooks/scripts/worktree_guard.py (issue #878).

The worktree guard prevents the agent-worktree cwd leak: when a subagent runs
with isolation:worktree, the Bash tool's persistent cwd can drift to the MAIN
repo, so commits land in the wrong checkout. The guard anchors every Bash
command in the agent's worktree (cd <worktree-root> && ...) and denies commands
that explicitly target the main repo from inside a worktree.

The six scenarios enumerated in #878 are the spec:
  1. Not in worktree            → no-op (None)
  2. In worktree + safe command → rewrite with `cd <worktree> &&` prefix
  3. In worktree + main-repo ref → deny with actionable message
  4. Non-Bash tool              → guard never engages (dispatch-level; see pre_tool test)
  5. Idempotency                → already-anchored command is not double-prefixed
  6. Malformed input            → fail open (None)

Stdlib + unittest only. The guard is pure and fail-open by contract.
"""

from __future__ import annotations

import contextlib
import io
import json
import shlex
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# worktree_guard.py + pre_tool.py live at hooks/scripts/, not under scripts/.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
_SCRIPTS = _REPO_ROOT / "scripts"
for _p in (_HOOKS_SCRIPTS, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pre_tool  # noqa: E402
import worktree_guard  # noqa: E402


_MAIN = "/Users/dev/myproj"
_WT = "/Users/dev/myproj/.claude/worktrees/agent-7f3a9b"
_WT_SUBDIR = _WT + "/src/pkg"


def _anchor(cmd: str, root: str = _WT) -> str:
    return f"cd {shlex.quote(root)} && {cmd}"


class WorktreeRootDetection(unittest.TestCase):
    def test_detects_worktree_root_from_cwd(self):
        self.assertEqual(worktree_guard.worktree_root(_WT), _WT)

    def test_detects_root_even_from_a_subdir_of_the_worktree(self):
        # cwd deeper than the worktree root still resolves to the agent root
        self.assertEqual(worktree_guard.worktree_root(_WT_SUBDIR), _WT)

    def test_returns_none_for_normal_repo_path(self):
        self.assertIsNone(worktree_guard.worktree_root(_MAIN))

    def test_returns_none_for_empty_or_none(self):
        self.assertIsNone(worktree_guard.worktree_root(""))
        self.assertIsNone(worktree_guard.worktree_root(None))


class Scenario1_NotInWorktree(unittest.TestCase):
    def test_noop_when_cwd_is_not_a_worktree(self):
        self.assertIsNone(worktree_guard.evaluate("git commit -m x", _MAIN))


class Scenario2_SafeCommandRewrite(unittest.TestCase):
    def test_rewrites_with_cd_prefix(self):
        # git resolution will fail on this fake path → no main-repo ref → rewrite
        decision = worktree_guard.evaluate("git status", _WT)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "rewrite")
        self.assertEqual(decision["command"], _anchor("git status"))

    def test_rewrite_anchors_to_root_even_from_subdir(self):
        decision = worktree_guard.evaluate("ls", _WT_SUBDIR)
        self.assertEqual(decision["action"], "rewrite")
        self.assertEqual(decision["command"], _anchor("ls"))

    def test_rewrite_preserves_complex_command(self):
        cmd = "npm ci && npm test -- --runInBand"
        decision = worktree_guard.evaluate(cmd, _WT)
        self.assertEqual(decision["command"], _anchor(cmd))


class Scenario3_MainRepoReferenceDeny(unittest.TestCase):
    def test_denies_git_dash_C_main_repo(self):
        with patch.object(worktree_guard, "_main_repo_root", return_value=_MAIN):
            decision = worktree_guard.evaluate(f"git -C {_MAIN} commit -m x", _WT)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "deny")
        self.assertIn(_MAIN, decision["reason"])
        self.assertIn(_WT, decision["reason"])

    def test_denies_leading_cd_to_main_repo(self):
        with patch.object(worktree_guard, "_main_repo_root", return_value=_MAIN):
            decision = worktree_guard.evaluate(f"cd {_MAIN} && git status", _WT)
        self.assertEqual(decision["action"], "deny")

    def test_does_not_deny_dash_C_into_the_worktree_itself(self):
        # -C pointing at the worktree (which has the main repo as a path prefix)
        # must NOT be mistaken for a main-repo reference → it rewrites, not denies.
        with patch.object(worktree_guard, "_main_repo_root", return_value=_MAIN):
            decision = worktree_guard.evaluate(f"git -C {_WT} status", _WT)
        self.assertEqual(decision["action"], "rewrite")

    def test_no_deny_when_main_repo_unresolvable(self):
        with patch.object(worktree_guard, "_main_repo_root", return_value=None):
            decision = worktree_guard.evaluate(f"git -C {_MAIN} status", _WT)
        # can't prove it's the main repo → safe default is rewrite, not deny
        self.assertEqual(decision["action"], "rewrite")


class Scenario5_Idempotency(unittest.TestCase):
    def test_already_anchored_command_is_noop(self):
        already = _anchor("git status")
        self.assertIsNone(worktree_guard.evaluate(already, _WT))

    def test_anchored_with_leading_whitespace_is_noop(self):
        already = "   " + _anchor("ls")
        self.assertIsNone(worktree_guard.evaluate(already, _WT))


class Scenario6_FailOpen(unittest.TestCase):
    def test_none_command_is_noop(self):
        self.assertIsNone(worktree_guard.evaluate(None, _WT))

    def test_empty_command_is_noop(self):
        self.assertIsNone(worktree_guard.evaluate("   ", _WT))

    def test_none_cwd_is_noop(self):
        self.assertIsNone(worktree_guard.evaluate("ls", None))

    def test_internal_error_fails_open(self):
        # Force an internal explosion → must swallow and return None
        with patch.object(worktree_guard, "worktree_root", side_effect=RuntimeError("boom")):
            self.assertIsNone(worktree_guard.evaluate("ls", _WT))


class ReferencesMainRepoPure(unittest.TestCase):
    """Direct tests of the pure path-comparison helper."""

    def test_true_for_exact_main_root_via_dash_C(self):
        self.assertTrue(
            worktree_guard._references_main_repo(f"git -C {_MAIN} log", _MAIN, _WT)
        )

    def test_false_for_worktree_path(self):
        self.assertFalse(
            worktree_guard._references_main_repo(f"git -C {_WT} log", _MAIN, _WT)
        )

    def test_false_when_main_root_missing(self):
        self.assertFalse(
            worktree_guard._references_main_repo(f"git -C {_MAIN} log", None, _WT)
        )

    def test_false_when_no_path_args(self):
        self.assertFalse(
            worktree_guard._references_main_repo("git status", _MAIN, _WT)
        )


class PreToolBashWiring(unittest.TestCase):
    """Integration: the guard is wired into pre_tool._handle_bash + main()."""

    def _hso(self, raw: str) -> dict:
        return json.loads(raw)["hookSpecificOutput"]

    def test_rewrite_in_worktree(self):
        hso = self._hso(pre_tool._handle_bash({"command": "git status"}, _WT))
        self.assertEqual(hso["permissionDecision"], "allow")
        self.assertEqual(hso["updatedInput"]["command"], _anchor("git status"))

    def test_deny_main_repo_reference(self):
        with patch.object(worktree_guard, "_main_repo_root", return_value=_MAIN):
            hso = self._hso(pre_tool._handle_bash({"command": f"git -C {_MAIN} push"}, _WT))
        self.assertEqual(hso["permissionDecision"], "deny")

    def test_plain_allow_outside_worktree(self):
        hso = self._hso(pre_tool._handle_bash({"command": "git status"}, _MAIN))
        self.assertEqual(hso["permissionDecision"], "allow")
        self.assertNotIn("updatedInput", hso)

    def test_main_threads_cwd_into_guard(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": _WT}
        )
        buf = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(payload)), \
                contextlib.redirect_stdout(buf):
            pre_tool.main()
        hso = self._hso(buf.getvalue())
        self.assertEqual(hso["updatedInput"]["command"], _anchor("ls"))

    def test_non_bash_tool_never_engages_guard(self):
        # Scenario 4: a non-Bash tool is not rewritten even with a worktree cwd.
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "cwd": _WT}
        )
        buf = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(payload)), \
                contextlib.redirect_stdout(buf):
            pre_tool.main()
        self.assertNotIn("updatedInput", self._hso(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
