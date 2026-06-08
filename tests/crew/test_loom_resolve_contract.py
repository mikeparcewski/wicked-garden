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


class ResolveLoomAuthoritative(unittest.TestCase):
    """Contract phase: loom ``resolve vault`` is the SOLE resolution path for
    the run-the-vault case (allow_npx=True). The in-process npx ladder fallback
    is gone. The allow_npx=False concrete-install probe (vault_available) STAYS
    in-process and never consults loom."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN"):
            os.environ.pop(v, None)
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def test_loom_resolve_is_authoritative(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0,
                    "stdout": '{"peer":"vault","command":["npx","--yes","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertEqual(vg.resolve_vault(), ["npx", "--yes", "wicked-vault"])

    def test_loom_command_null_surfaces_as_none(self):
        # loom reports the vault kill-switch / unresolvable -> command=null -> None.
        def fake_run(prefix, args, timeout):
            return {"exit_code": 1, "stdout": '{"peer":"vault","command":null}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertIsNone(vg.resolve_vault())

    def test_loom_unresolvable_returns_none_no_in_process_npx(self):
        # auto + loom unresolvable. There is NO in-process npx ladder on the
        # allow_npx=True path now -> resolve_vault returns None (fail-closed).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertIsNone(vg.resolve_vault())

    def test_loom_error_returns_none_no_in_process_npx(self):
        # loom resolves but the subprocess errors -> None (no fallback).
        def boom(prefix, args, timeout):
            return {"exit_code": None, "stdout": "", "stderr": "",
                    "error": "loom call exceeded 120s"}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", boom), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertIsNone(vg.resolve_vault())

    def test_off_disables_loom_path_returns_none(self):
        # off = emergency disable. allow_npx=True path no longer has an
        # in-process fallback -> None (the gate then fails closed downstream).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertIsNone(vg.resolve_vault())

    def test_vault_available_probe_stays_in_process(self):
        # allow_npx=False is the concrete-install probe: loom is NEVER consulted
        # (loom would report the npx last-resort as resolvable, corrupting the
        # "installed" signal). A concrete PATH install resolves in-process.
        with patch.object(_loom, "resolve_loom",
                          side_effect=AssertionError("loom must not be consulted")), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/local/bin/wicked-vault"
                          if b == "wicked-vault" else None):
            self.assertEqual(vg.resolve_vault(allow_npx=False), ["/usr/local/bin/wicked-vault"])
            self.assertTrue(vg.vault_available())

    def test_vault_available_false_for_npx_only(self):
        with patch.object(_loom, "resolve_loom",
                          side_effect=AssertionError("loom must not be consulted")), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(vg.vault_available())

    def test_vault_available_env_killswitch_in_process(self):
        # WICKED_VAULT_BIN="" kill-switch on the in-process probe path.
        os.environ["WICKED_VAULT_BIN"] = ""
        with patch.object(_loom, "resolve_loom",
                          side_effect=AssertionError("loom must not be consulted")):
            self.assertIsNone(vg.resolve_vault(allow_npx=False))
            self.assertFalse(vg.vault_available())


if __name__ == "__main__":
    unittest.main()
