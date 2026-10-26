"""Tests for hooks/scripts/stop.py::_check_outgov_compliance (AW-16 / arch-R14, garden#1333).

The output-governance audit:
  * runs `rules.recall` ITSELF, through the read-only shim, on the first Stop of
    a session, and never again in that session;
  * is silent when the store has zero policy rules, when estate is unreachable,
    and on any internal error;
  * never tells the model to call an MCP tool (no estate MCP is registered on a
    seat, by design: the old per-turn line could never run);
  * defaults to WG_OUTGOV=warn; WG_OUTGOV=off is the per-repo opt-out;
  * stays fail-open advisory at every mode (`strict` only strengthens wording).

Hermetic: the recall seam and the session state are injected; no live estate.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
if str(_HOOKS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SCRIPTS))

import stop  # noqa: E402

_RULES = {
    "total": 7,
    "returned": 5,
    "rules": [
        {"id": "POL-1", "severity": "critical", "statement": "Never log secrets."},
        {"id": "POL-2", "severity": "error", "statement": "Hooks fail open."},
        {"id": "POL-3", "severity": "warn", "statement": "One mechanism per concern."},
        {"id": "POL-4", "severity": "info", "statement": "fourth"},
    ],
}


class _Claim:
    """One-shot claim double: True the first time, False after."""

    def __init__(self):
        self.claimed = False
        self.calls = 0

    def __call__(self, _input):
        self.calls += 1
        if self.claimed:
            return False
        self.claimed = True
        return True


def _run(env=None, *, recall=lambda: _RULES, state=None):
    env = dict(env or {})
    with patch.dict(os.environ, env, clear=False):
        if "WG_OUTGOV" not in env:
            os.environ.pop("WG_OUTGOV", None)
        if "WICKED_CONTEXT_BACKEND" not in env:
            os.environ.pop("WICKED_CONTEXT_BACKEND", None)
        st = state if state is not None else _Claim()
        return stop._check_outgov_compliance({}, recall=recall, claim=st), st


class SessionAudit(unittest.TestCase):
    def test_default_warn_names_rules_once_and_the_shim_command(self):
        messages, st = _run()
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertIn("[Output Governance] 7 policy rule(s)", msg)
        self.assertIn("POL-1 (critical): Never log secrets.", msg)
        self.assertIn("POL-3", msg)
        self.assertNotIn("POL-4", msg)  # top three only
        self.assertIn("_estate_client.py --readonly call", msg)
        self.assertIn('"tool":"rules.recall"', msg)
        self.assertTrue(st.claimed)

    def test_never_points_at_an_mcp_tool(self):
        messages, _ = _run()
        self.assertNotIn("MCP", messages[0])
        self.assertNotIn("If the estate", messages[0])

    def test_second_stop_in_a_session_is_silent(self):
        calls = []

        def recall():
            calls.append(1)
            return _RULES

        st = _Claim()
        first, _ = _run(recall=recall, state=st)
        second, _ = _run(recall=recall, state=st)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(calls), 1, "rules.recall runs at most once per session")

    def test_zero_rules_is_silent(self):
        messages, st = _run(recall=lambda: {"rules": [], "total": 0, "returned": 0})
        self.assertEqual(messages, [])
        self.assertTrue(st.claimed)

    def test_unreachable_estate_is_silent_and_latched(self):
        calls = []

        def recall():
            calls.append(1)
            return None

        st = _Claim()
        self.assertEqual(_run(recall=recall, state=st)[0], [])
        self.assertEqual(_run(recall=recall, state=st)[0], [])
        self.assertEqual(len(calls), 1, "a failing estate costs one attempt per session")

    def test_recall_error_is_silent(self):
        def boom():
            raise RuntimeError("boom")

        self.assertEqual(_run(recall=boom)[0], [])

    def test_strict_adds_hint_but_stays_advisory(self):
        messages, _ = _run({"WG_OUTGOV": "strict"})
        self.assertEqual(len(messages), 1)
        self.assertIn("CRITICAL severity violations", messages[0])
        self.assertIsInstance(messages[0], str)

    def test_warn_has_no_deny_hint(self):
        messages, _ = _run({"WG_OUTGOV": "warn"})
        self.assertNotIn("CRITICAL severity violations", messages[0])


class OptOut(unittest.TestCase):
    def test_off_opts_out_without_calling_estate(self):
        messages, st = _run({"WG_OUTGOV": "off"},
                            recall=lambda: self.fail("must not call estate"))
        self.assertEqual(messages, [])
        self.assertEqual(st.calls, 0)

    def test_unrecognized_value_treated_as_off(self):
        self.assertEqual(_run({"WG_OUTGOV": "banana"})[0], [])

    def test_whitespace_and_case_normalized(self):
        self.assertEqual(len(_run({"WG_OUTGOV": "  WARN  "})[0]), 1)

    def test_context_backend_off_is_silent(self):
        messages, _ = _run({"WICKED_CONTEXT_BACKEND": "off"},
                           recall=lambda: self.fail("must not call estate"))
        self.assertEqual(messages, [])


class MarkerClaim(unittest.TestCase):
    """The real claim: an O_EXCL marker per session, independent of SessionState
    (whose whole-file saves from an overlapping prompt hook could reset a flag)."""

    def test_claims_once_per_session_and_per_session_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"TMPDIR": tmp}):
            self.assertTrue(stop._claim_outgov_audit({"session_id": "s-1"}))
            self.assertFalse(stop._claim_outgov_audit({"session_id": "s-1"}))
            self.assertTrue(stop._claim_outgov_audit({"session_id": "s-2"}))

    def test_session_state_save_cannot_rearm_the_audit(self):
        """A stale SessionState snapshot saved after the claim leaves it claimed."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {"TMPDIR": tmp, "CLAUDE_SESSION_ID": "s-3"}):
            from _session import SessionState
            stale = SessionState.load()           # a prompt hook loads first
            self.assertTrue(stop._claim_outgov_audit({"session_id": "s-3"}))
            stale.update(turn_count=5)            # ...and saves after the claim
            self.assertFalse(stop._claim_outgov_audit({"session_id": "s-3"}))

    def test_path_unsafe_session_id_is_sanitized(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"TMPDIR": tmp}):
            self.assertTrue(stop._claim_outgov_audit({"session_id": "../../x"}))
            created = list((Path(tmp) / "wicked-garden-outgov").iterdir())
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0].parent, Path(tmp) / "wicked-garden-outgov")


class ShimSeam(unittest.TestCase):
    def test_recall_goes_through_the_readonly_shim(self):
        seen = {}

        class _Proc:
            returncode = 0
            stdout = json.dumps({"result": _RULES, "diagnostics": []}) + "\n"

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return _Proc()

        with patch("subprocess.run", fake_run):
            result = stop._recall_policy_rules()
        self.assertEqual(result, _RULES)
        argv = seen["argv"]
        self.assertTrue(argv[1].endswith("_estate_client.py"))
        self.assertEqual(argv[2:4], ["--readonly", "call"])
        req = json.loads(argv[4])
        self.assertEqual(req["tool"], "rules.recall")
        self.assertEqual(req["arguments"]["rule_type"], "policy")

    def test_shim_failure_yields_none(self):
        class _Proc:
            returncode = 0
            stdout = json.dumps({"ok": False, "reason": "refused"}) + "\n"

        with patch("subprocess.run", lambda *a, **k: _Proc()):
            self.assertIsNone(stop._recall_policy_rules())


if __name__ == "__main__":
    unittest.main()
