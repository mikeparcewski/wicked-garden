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
    def setUp(self):
        self._saved = os.environ.get("WICKED_LOOM_BIN")
        os.environ.pop("WICKED_LOOM_BIN", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("WICKED_LOOM_BIN", None)
        else:
            os.environ["WICKED_LOOM_BIN"] = self._saved

    def test_env_override_wins(self):
        os.environ["WICKED_LOOM_BIN"] = "/opt/custom/loom"
        self.assertEqual(_loom.resolve_loom(), ["/opt/custom/loom"])

    def test_empty_env_is_killswitch(self):
        os.environ["WICKED_LOOM_BIN"] = ""
        self.assertIsNone(_loom.resolve_loom())

    def test_mjs_override_invoked_via_node(self):
        os.environ["WICKED_LOOM_BIN"] = "/some/loom.mjs"
        self.assertEqual(_loom.resolve_loom(), ["node", "/some/loom.mjs"])

    def test_path_lookup_when_no_env(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/local/bin/wicked-loom" if b == "wicked-loom" else None):
            self.assertEqual(_loom.resolve_loom(allow_npx=False), ["/usr/local/bin/wicked-loom"])

    def test_npx_fallback_when_not_on_path(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertEqual(_loom.resolve_loom(), ["npx", "--yes", "wicked-loom"])

    def test_loom_available_excludes_npx(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(_loom.loom_available())


class RunTests(unittest.TestCase):
    def test_run_returns_parsed_json_on_success(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0, "stdout": '{"peer":"vault","command":["npx","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["resolve", "vault"], _run=fake_run)
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(out["json"]["command"], ["npx", "wicked-vault"])

    def test_run_unresolvable_reports_error_not_raise(self):
        with patch.object(_loom, "resolve_loom", return_value=None):
            out = _loom.run_json(["resolve", "vault"])
        self.assertIsNone(out["json"])
        self.assertEqual(out["error"], "wicked-loom not resolvable")

    def test_run_non_json_output_is_error_not_raise(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0, "stdout": "not json", "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["doctor"], _run=fake_run)
        self.assertIsNone(out["json"])
        self.assertIn("non-JSON", out["error"])

    def test_run_passes_project_dir_as_subprocess_cwd(self):
        # Regression guard (#891 loom cutover): loom gate/resolve/flow inspect
        # the *project* dir, not the parent process cwd. run_json MUST run the
        # loom subprocess in project_dir, or the gate re-derives against the
        # wrong repo. Before the fix _default_run got no cwd, and the real-peer
        # gate tests returned ERROR (empty claims) when run from any other cwd.
        seen = {}

        def capturing_default_run(prefix, args, timeout, cwd=None):
            seen["cwd"] = cwd
            return {"exit_code": 0, "stdout": "{}", "stderr": "", "error": None}

        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", capturing_default_run):
            _loom.run_json(["gate", "build"], project_dir=Path("/tmp/some-proj"))
        self.assertEqual(seen["cwd"], "/tmp/some-proj")

    def test_run_without_project_dir_passes_none_cwd(self):
        seen = {}

        def capturing_default_run(prefix, args, timeout, cwd=None):
            seen["cwd"] = cwd
            return {"exit_code": 0, "stdout": "{}", "stderr": "", "error": None}

        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", capturing_default_run):
            _loom.run_json(["doctor"])
        self.assertIsNone(seen["cwd"])


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

    def test_use_loom_auto_true_only_when_resolvable(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None):
            self.assertFalse(_loom.use_loom())
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            self.assertTrue(_loom.use_loom())


if __name__ == "__main__":
    unittest.main()
