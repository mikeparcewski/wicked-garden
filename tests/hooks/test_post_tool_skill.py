#!/usr/bin/env python3
"""tests/hooks/test_post_tool_skill.py — Issue #608 exact-match guard.

Issue #608: ``hooks/scripts/post_tool.py::_handle_skill`` previously used
substring matching to decide when to reset the memory-compliance escalation
counter. This false-positives on any future skill whose name *contains* the
memory skill's name as a substring (e.g. ``wicked-garden-mem-export``),
silently weakening the ``[ESCALATION]`` directive mechanism.

S7: the canonical memory surface is the ``wicked-garden-mem`` skill (over
wicked-estate); the retired ``wicked-brain:memory`` name no longer resets.

This suite locks in exact-match semantics.

Stdlib-only (T-rules: stdlib + deterministic). No sleep-based sync (T2).
Each test asserts a single behaviour (T4) with a descriptive name (T5).
Provenance: Issue #608 (T6) — flagged unanimously by all 6 council voters
on PR #607.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make hooks/scripts importable as a module
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = str(_REPO / "hooks" / "scripts")
_SCRIPTS = str(_REPO / "scripts")

for _p in (_SCRIPTS, _HOOKS_SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import post_tool  # noqa: E402
from _session import SessionState  # noqa: E402


class TestSkillExactMatchGuard(unittest.TestCase):
    """Issue #608: counter resets only on exact ``wicked-garden-mem``."""

    def setUp(self) -> None:
        # Isolate session state to a per-test tempdir so we don't pollute the
        # developer's real session file (T3).
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_tmp = os.environ.get("TMPDIR")
        self._old_session = os.environ.get("CLAUDE_SESSION_ID")
        os.environ["TMPDIR"] = self._tmp.name
        # Unique session id per test guarantees isolation across the class.
        os.environ["CLAUDE_SESSION_ID"] = f"test-608-{id(self)}"

    def tearDown(self) -> None:
        if self._old_tmp is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = self._old_tmp
        if self._old_session is None:
            os.environ.pop("CLAUDE_SESSION_ID", None)
        else:
            os.environ["CLAUDE_SESSION_ID"] = self._old_session

    def _seed_escalations(self, count: int) -> None:
        """Pre-load the session counter to a known non-zero value."""
        state = SessionState.load()
        state.update(memory_compliance_escalations=count)

    def test_exact_skill_name_resets_counter(self) -> None:
        """skill='wicked-garden-mem' (exact) zeroes the escalation counter."""
        self._seed_escalations(3)

        result = post_tool._handle_skill({"skill": "wicked-garden-mem"})

        self.assertEqual(result, {"continue": True})
        self.assertEqual(
            SessionState.load().memory_compliance_escalations,
            0,
            "Exact 'wicked-garden-mem' skill must reset the escalation counter "
            "to 0 (Issue #608 contract).",
        )

    def test_substring_match_skill_does_not_reset_counter(self) -> None:
        """skill='wicked-garden-mem-export' must NOT reset the counter (#608 bug)."""
        self._seed_escalations(3)

        result = post_tool._handle_skill({"skill": "wicked-garden-mem-export"})

        self.assertEqual(result, {"continue": True})
        self.assertEqual(
            SessionState.load().memory_compliance_escalations,
            3,
            "Skills whose name *contains* 'wicked-garden-mem' as a substring "
            "(here: 'wicked-garden-mem-export') must NOT reset the escalation "
            "counter — that was the Issue #608 false-positive bug.",
        )

    def test_retired_brain_memory_skill_does_not_reset_counter(self) -> None:
        """The retired 'wicked-brain:memory' name must NOT reset the counter (S7)."""
        self._seed_escalations(3)

        result = post_tool._handle_skill({"skill": "wicked-brain:memory"})

        self.assertEqual(result, {"continue": True})
        self.assertEqual(
            SessionState.load().memory_compliance_escalations,
            3,
            "wicked-brain:memory was retired at S7 — only the wicked-garden-mem "
            "skill resets the escalation counter.",
        )


if __name__ == "__main__":
    unittest.main()
