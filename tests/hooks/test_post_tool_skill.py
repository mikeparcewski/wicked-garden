#!/usr/bin/env python3
"""tests/hooks/test_post_tool_skill.py — Issue #608 exact-match guard.

Issue #608: ``hooks/scripts/post_tool.py::_handle_skill`` previously used
substring matching ``if "wicked-brain:memory" not in skill: return`` to decide
when to reset the memory-compliance escalation counter. This false-positives on
any future skill whose name *contains* ``wicked-brain:memory`` as a substring
(e.g. ``wicked-brain:memory-export``, ``wicked-brain:memory-audit``), silently
weakening the ``[ESCALATION]`` directive mechanism.

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
from unittest.mock import patch

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
    """Issue #608: counter resets only on exact ``wicked-brain:memory``."""

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
        """skill='wicked-brain:memory' (exact) zeroes the escalation counter."""
        self._seed_escalations(3)

        result = post_tool._handle_skill({"skill": "wicked-brain:memory"})

        self.assertEqual(result, {"continue": True})
        self.assertEqual(
            SessionState.load().memory_compliance_escalations,
            0,
            "Exact 'wicked-brain:memory' skill must reset the escalation counter "
            "to 0 (Issue #608 contract).",
        )

    def test_substring_match_skill_does_not_reset_counter(self) -> None:
        """skill='wicked-brain:memory-export' must NOT reset the counter (#608 bug)."""
        self._seed_escalations(3)

        result = post_tool._handle_skill({"skill": "wicked-brain:memory-export"})

        self.assertEqual(result, {"continue": True})
        self.assertEqual(
            SessionState.load().memory_compliance_escalations,
            3,
            "Skills whose name *contains* 'wicked-brain:memory' as a substring "
            "(here: 'wicked-brain:memory-export') must NOT reset the escalation "
            "counter — that was the Issue #608 false-positive bug.",
        )


if __name__ == "__main__":
    unittest.main()
