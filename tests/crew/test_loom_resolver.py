"""Tests for _loom.py — the absorbed peer-resolution shim.

After the Phase B absorption (ECOSYSTEM-RATIONALIZATION.md §5a):
  - _HAVE_INTERNAL is True in any environment that has scripts/loom/
  - use_loom() auto mode returns True when _HAVE_INTERNAL (always in garden)
  - run_json() dispatches to internal modules in-process (no subprocess)
  - The external subprocess path is still exercised when _run is injected
    (test seam) or when _HAVE_INTERNAL is patched to False
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import _loom  # noqa: E402


class ResolveLadderTests(unittest.TestCase):
    """resolve_loom() ladder — env override and external CLI fallback.

    The ladder: WICKED_LOOM_BIN env > internal > config > PATH > node_modules > npx.
    The env override and kill-switch still work exactly as before absorption.
    """

    def setUp(self):
        self._saved_bin = os.environ.get("WICKED_LOOM_BIN")
        os.environ.pop("WICKED_LOOM_BIN", None)

    def tearDown(self):
        if self._saved_bin is None:
            os.environ.pop("WICKED_LOOM_BIN", None)
        else:
            os.environ["WICKED_LOOM_BIN"] = self._saved_bin

    def test_env_override_beats_internal(self):
        """Explicit WICKED_LOOM_BIN beats the internal absorbed module."""
        os.environ["WICKED_LOOM_BIN"] = "/opt/custom/loom"
        self.assertEqual(_loom.resolve_loom(), ["/opt/custom/loom"])

    def test_empty_env_is_killswitch(self):
        """Empty WICKED_LOOM_BIN is the deliberate kill-switch."""
        os.environ["WICKED_LOOM_BIN"] = ""
        self.assertIsNone(_loom.resolve_loom())

    def test_mjs_override_invoked_via_node(self):
        """A .mjs env override is wrapped in ['node', path]."""
        os.environ["WICKED_LOOM_BIN"] = "/some/loom.mjs"
        self.assertEqual(_loom.resolve_loom(), ["node", "/some/loom.mjs"])

    def test_internal_module_returns_sentinel_when_have_internal(self):
        """When _HAVE_INTERNAL is True, resolve_loom returns ['_internal']."""
        with patch.object(_loom, "_HAVE_INTERNAL", True):
            result = _loom.resolve_loom(allow_npx=False)
        self.assertEqual(result, ["_internal"])

    def test_path_lookup_when_no_env_and_no_internal(self):
        """PATH lookup runs when internal is absent and env is not set."""
        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/local/bin/wicked-loom"
                          if b == "wicked-loom" else None):
            self.assertEqual(_loom.resolve_loom(allow_npx=False),
                             ["/usr/local/bin/wicked-loom"])

    def test_npx_fallback_when_not_on_path_and_no_internal(self):
        """npx fallback fires when PATH has nothing and internal is absent."""
        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertEqual(_loom.resolve_loom(), ["npx", "--yes", "wicked-loom"])

    def test_loom_available_true_when_have_internal(self):
        """loom_available is True when the internal module is present."""
        with patch.object(_loom, "_HAVE_INTERNAL", True):
            self.assertTrue(_loom.loom_available())

    def test_loom_available_excludes_npx_for_external(self):
        """loom_available excludes the npx last-resort for external installs."""
        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(_loom.loom_available())


class InternalDispatchTests(unittest.TestCase):
    """run_json() internal dispatch — in-process calls to absorbed loom modules.

    When _HAVE_INTERNAL is True and no _run is injected, run_json dispatches
    to the absorbed Python modules directly (no subprocess for loom).
    """

    def test_resolve_dispatches_internally(self):
        """run_json(['resolve', 'vault']) calls internal resolve module."""
        out = _loom.run_json(["resolve", "vault"])
        self.assertIsNone(out["error"])
        self.assertIsInstance(out["json"], dict)
        self.assertEqual(out["json"]["peer"], "vault")
        # command is a list (even if vault not installed = npx fallback)
        self.assertIn("command", out["json"])

    def test_doctor_dispatches_internally(self):
        """run_json(['doctor']) calls internal compose module."""
        out = _loom.run_json(["doctor"])
        self.assertIsNone(out["error"])
        payload = out["json"]
        self.assertIn("peers", payload)
        self.assertIn("all_reachable", payload)
        self.assertIn("all_capable", payload)

    def test_compose_install_dispatches_internally(self):
        """run_json(['compose', 'install']) calls internal compose module."""
        # We're not actually installing; just verify it dispatches in-process
        # and returns the right shape.
        with patch("loom.compose._default_run") as mock_run:
            from loom.compose import RunResult
            mock_run.return_value = RunResult(returncode=0, stdout="", stderr="")
            out = _loom.run_json(["compose", "install", "--peer", "bus"])
        self.assertIsNone(out["error"])
        self.assertIn("results", out["json"])

    def test_gate_dispatches_internally(self):
        """run_json(['gate', 'test-report', '--scope', 'proj-1']) goes in-process.

        Patch _loom._loom_gate_mod.run_gate directly — the internal gate module
        is imported by name into _loom, so this is the correct seam. Patching
        loom.gate._default_run would not work because the default parameter is
        bound at function-definition time, not at call time.
        """
        gate_verdict = {
            "satisfied": True, "re_derived": True,
            "gate": "vault-cross-check", "overall": "PASS",
            "claims": [], "error": None,
        }
        with patch.object(_loom, "_loom_gate_mod") as mock_gate_mod:
            mock_gate_mod.run_gate.return_value = gate_verdict
            out = _loom.run_json(["gate", "test-report", "--scope", "proj-1"])
        self.assertIsNone(out["error"])
        self.assertIn("gate", out["json"])
        self.assertEqual(out["json"]["gate"]["overall"], "PASS")
        mock_gate_mod.run_gate.assert_called_once_with(
            "test-report", scope="proj-1", verifier_spec=None,
            with_attestations=False,
        )

    def test_flow_command_returns_retired_error(self):
        """run_json(['flow', 'run', ...]) surfaces the retirement message."""
        out = _loom.run_json(["flow", "run", "some-flow.json"])
        self.assertIsNotNone(out["error"])
        self.assertIn("retired", out["error"])
        self.assertEqual(out["exit_code"], 2)

    def test_unknown_command_returns_error(self):
        """run_json(['frobnicate']) returns structured error."""
        out = _loom.run_json(["frobnicate"])
        self.assertIsNotNone(out["error"])
        self.assertEqual(out["exit_code"], 2)


class ExternalSubprocessTests(unittest.TestCase):
    """run_json() external subprocess path — still works via _run injection.

    Tests that inject _run bypass the internal path, exercising the subprocess
    code path. This preserves the test seam for callers that already mock
    _loom._default_run or inject _run.
    """

    def test_run_returns_parsed_json_on_success(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0,
                    "stdout": '{"peer":"vault","command":["npx","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["resolve", "vault"], _run=fake_run)
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(out["json"]["command"], ["npx", "wicked-vault"])

    def test_run_non_json_output_is_error_not_raise(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0, "stdout": "not json", "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["doctor"], _run=fake_run)
        self.assertIsNone(out["json"])
        self.assertIn("non-JSON", out["error"])

    def test_run_passes_project_dir_as_subprocess_cwd(self):
        """Regression guard (#891 loom cutover): project_dir must be the cwd.

        This test exercises the external subprocess path, so _HAVE_INTERNAL must
        be patched to False to bypass the internal dispatch and reach _default_run.
        """
        seen = {}

        def capturing_default_run(prefix, args, timeout, cwd=None):
            seen["cwd"] = cwd
            return {"exit_code": 0, "stdout": "{}", "stderr": "", "error": None}

        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", capturing_default_run):
            _loom.run_json(["gate", "build"], project_dir=Path("/tmp/some-proj"))
        self.assertEqual(seen["cwd"], "/tmp/some-proj")

    def test_run_without_project_dir_passes_none_cwd(self):
        """_default_run gets cwd=None when no project_dir is passed.

        Patches _HAVE_INTERNAL=False to exercise the external subprocess path.
        """
        seen = {}

        def capturing_default_run(prefix, args, timeout, cwd=None):
            seen["cwd"] = cwd
            return {"exit_code": 0, "stdout": "{}", "stderr": "", "error": None}

        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", capturing_default_run):
            _loom.run_json(["doctor"])
        self.assertIsNone(seen["cwd"])

    def test_run_unresolvable_when_internal_absent_reports_error(self):
        """When internal is absent and external CLI is unresolvable: error dict."""
        with patch.object(_loom, "_HAVE_INTERNAL", False), \
             patch.object(_loom, "resolve_loom", return_value=None):
            out = _loom.run_json(["resolve", "vault"])
        self.assertIsNone(out["json"])
        self.assertEqual(out["error"], "wicked-loom not resolvable")


class CutoverModeTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("WICKED_LOOM_CUTOVER")
        os.environ.pop("WICKED_LOOM_CUTOVER", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("WICKED_LOOM_CUTOVER", None)
        else:
            os.environ["WICKED_LOOM_CUTOVER"] = self._saved

    def test_default_is_auto(self):
        self.assertEqual(_loom.cutover_mode(), "auto")

    def test_explicit_off(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        self.assertEqual(_loom.cutover_mode(), "off")

    def test_unknown_value_falls_back_to_auto(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "frobnicate"
        self.assertEqual(_loom.cutover_mode(), "auto")

    def test_use_loom_off_is_false(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        self.assertFalse(_loom.use_loom())

    def test_use_loom_auto_true_when_internal_available(self):
        """After absorption: auto mode is True when the internal module is present."""
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "_HAVE_INTERNAL", True):
            self.assertTrue(_loom.use_loom())

    def test_use_loom_auto_falls_back_to_resolve_when_no_internal(self):
        """When internal is absent, auto mode falls back to the external CLI check."""
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "_HAVE_INTERNAL", False):
            with patch.object(_loom, "resolve_loom", return_value=None):
                self.assertFalse(_loom.use_loom())
            with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
                self.assertTrue(_loom.use_loom())

    def test_use_loom_on_is_true_regardless_of_internal(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "_HAVE_INTERNAL", False):
            self.assertTrue(_loom.use_loom())


if __name__ == "__main__":
    unittest.main()
