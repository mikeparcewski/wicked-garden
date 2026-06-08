import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _loom  # noqa: E402
import vault_gate as vg  # noqa: E402


class ResolveCutoverContract(unittest.TestCase):
    """Strangler safety net: the loom-shelled resolve path must return the
    SAME argv the in-process resolve_vault returns for the same inputs."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def test_loom_resolve_matches_in_process_for_npx_case(self):
        # In-process: no env, not on PATH -> npx --yes wicked-vault.
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            in_proc = vg.resolve_vault()
        self.assertEqual(in_proc, ["npx", "--yes", "wicked-vault"])

        # Loom path: force loom on; loom resolve vault returns the SAME argv.
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

        def fake_run(prefix, args, timeout):
            return {"exit_code": 0,
                    "stdout": '{"peer":"vault","command":["npx","--yes","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            via_loom = vg.resolve_vault()
        self.assertEqual(via_loom, in_proc)

    def test_loom_unresolvable_falls_back_to_in_process(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            via = vg.resolve_vault()
        # auto + loom unresolvable -> in-process path used (fail-soft).
        self.assertEqual(via, ["npx", "--yes", "wicked-vault"])

    def test_loom_killswitch_env_still_honored_through_loom(self):
        # WICKED_VAULT_BIN="" is the vault kill-switch; the loom resolve path
        # must surface the same None (loom resolve returns command=null).
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        os.environ["WICKED_VAULT_BIN"] = ""

        def fake_run(prefix, args, timeout):
            return {"exit_code": 1, "stdout": '{"peer":"vault","command":null}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertIsNone(vg.resolve_vault())


if __name__ == "__main__":
    unittest.main()
