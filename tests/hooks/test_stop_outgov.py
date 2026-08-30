"""Tests for hooks/scripts/stop.py::_check_outgov_compliance (AW-16 / arch-R14).

The per-turn output-governance advisory:
  * names `rules.recall` (the estate MCP tool) as THE single per-turn rule
    source — no more "list nodes with kind=Rule" free-form directions;
  * defaults to WG_OUTGOV=warn (default-on advisory, after the AW-13 seed);
  * WG_OUTGOV=off is the per-repo opt-out (P-5 noise budget escape hatch);
  * stays fail-open advisory at every mode — `strict` only strengthens the
    wording, the hook never blocks (two-tier doctrine: hooks advisory,
    crew/core gates fail-closed — never a third enforcement tier).

Hermetic: no live estate, no subprocesses — the function only reads env and
returns message strings.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# stop.py lives at hooks/scripts/, not under scripts/.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
if str(_HOOKS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SCRIPTS))

import stop  # noqa: E402


class DefaultOnAdvisory(unittest.TestCase):
    def test_default_is_warn_and_names_rules_recall(self):
        """WG_OUTGOV unset → the advisory fires and names rules.recall."""
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("WG_OUTGOV", None)
            messages = stop._check_outgov_compliance({})
        self.assertEqual(len(messages), 1)
        self.assertIn("rules.recall", messages[0])
        self.assertIn("[Output Governance]", messages[0])
        # Single-source directive: the old free-form estate listing is gone.
        self.assertNotIn("list nodes with kind=Rule", messages[0])

    def test_warn_mode_no_deny_hint(self):
        with patch.dict("os.environ", {"WG_OUTGOV": "warn"}):
            messages = stop._check_outgov_compliance({})
        self.assertEqual(len(messages), 1)
        self.assertNotIn("CRITICAL severity violations", messages[0])

    def test_strict_mode_adds_hint_but_stays_advisory(self):
        """strict strengthens wording only — still a message, never a block."""
        with patch.dict("os.environ", {"WG_OUTGOV": "strict"}):
            messages = stop._check_outgov_compliance({})
        self.assertEqual(len(messages), 1)
        self.assertIn("rules.recall", messages[0])
        self.assertIn("CRITICAL severity violations", messages[0])
        # The return type is advisory text for the systemMessage — the hook
        # contract has no block/deny channel here.
        self.assertIsInstance(messages[0], str)

    def test_advisory_says_fail_open_on_missing_estate(self):
        with patch.dict("os.environ", {"WG_OUTGOV": "warn"}):
            messages = stop._check_outgov_compliance({})
        self.assertIn("skip silently", messages[0])


class PerRepoOptOut(unittest.TestCase):
    def test_off_opts_out(self):
        """P-5 escape hatch: WG_OUTGOV=off silences the per-turn advisory."""
        with patch.dict("os.environ", {"WG_OUTGOV": "off"}):
            self.assertEqual(stop._check_outgov_compliance({}), [])

    def test_unrecognized_value_treated_as_off(self):
        with patch.dict("os.environ", {"WG_OUTGOV": "banana"}):
            self.assertEqual(stop._check_outgov_compliance({}), [])

    def test_whitespace_and_case_normalized(self):
        with patch.dict("os.environ", {"WG_OUTGOV": "  WARN  "}):
            messages = stop._check_outgov_compliance({})
        self.assertEqual(len(messages), 1)


class FailOpen(unittest.TestCase):
    def test_exception_returns_empty(self):
        """Any internal error yields [] — the Stop hook never breaks on outgov."""
        with patch.object(stop.os.environ, "get", side_effect=RuntimeError("boom")):
            self.assertEqual(stop._check_outgov_compliance({}), [])


if __name__ == "__main__":
    unittest.main()
