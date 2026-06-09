import os
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

_PROJECT = Path("/tmp/proj-loom-gate")


class GateLoomAuthoritative(unittest.TestCase):
    """Contract phase: loom ``gate`` is the SOLE re-derivation path. The
    in-process cross_check body is gone. loom unresolvable/errors → the gate
    is unavailable and FAILS CLOSED — never a vacuous pass (I2)."""

    def setUp(self):
        # Default each test to the loom path on; the autouse off default was
        # removed in the contract phase (tests own their own flag — T3).
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN"):
            os.environ.pop(v, None)
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def _loom_gate_runner(self, overall):
        def fake_run(prefix, args, timeout, cwd=None):
            import json
            verdict = {"satisfied": overall == "PASS", "overall": overall,
                       "gate": "vault-cross-check", "claims": [{"id": "tests-pass"}]}
            return {"exit_code": 0 if overall == "PASS" else 1,
                    "stdout": json.dumps({"gate": verdict}), "stderr": "", "error": None}
        return fake_run

    def test_loom_pass_is_the_only_path(self):
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("PASS")):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertTrue(cc["available"])
        self.assertEqual(cc["overall"], "PASS")
        self.assertEqual(cc["claims"], [{"id": "tests-pass"}])

    def test_loom_reject_surfaced(self):
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("REJECT")):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertTrue(cc["available"])
        self.assertEqual(cc["overall"], "REJECT")

    def test_loom_gate_unavailable_maps_to_fail_closed(self):
        # loom reached, but vault unresolvable behind it -> gate: unavailable.
        def fake_run(prefix, args, timeout, cwd=None):
            import json
            return {"exit_code": 1, "stdout": json.dumps(
                {"gate": {"gate": "unavailable", "error": "no vault"}}),
                "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_loom_error_fails_closed_no_in_process_pass(self):
        # loom resolves but the subprocess errors (timeout/not-found). There is
        # NO in-process fallback now -> cross_check must report unavailable.
        def boom(prefix, args, timeout, cwd=None):
            return {"exit_code": None, "stdout": "", "stderr": "",
                    "error": "loom call exceeded 120s"}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", boom):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_loom_unresolvable_fails_closed(self):
        # auto + loom unresolvable -> the loom path is not taken; with no
        # in-process body, cross_check reports unavailable (fail-closed).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_off_disables_loom_fails_closed(self):
        # off = emergency disable. No in-process fallback -> unavailable.
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_gate_satisfied_fails_closed_when_loom_absent(self):
        # The load-bearing fail-closed invariant end-to-end: loom unresolvable
        # AND vault unresolvable -> gate_satisfied is unavailable, NOT a pass.
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        os.environ["WICKED_VAULT_BIN"] = ""  # vault kill-switch too
        with patch.object(_loom, "resolve_loom", return_value=None):
            verdict = vg.gate_satisfied(_PROJECT, "build-1", "test")
        self.assertFalse(verdict["satisfied"])
        self.assertEqual(verdict["gate"], "unavailable")
        self.assertFalse(verdict["re_derived"])

    def test_with_attestations_forwarded_to_loom(self):
        seen = {}

        def fake_run(prefix, args, timeout, cwd=None):
            import json
            seen["args"] = args
            return {"exit_code": 0, "stdout": json.dumps(
                {"gate": {"satisfied": True, "overall": "PASS"}}), "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            vg.cross_check("build-1", "review", project_dir=_PROJECT, with_attestations=True)
        self.assertIn("--with-attestations", seen["args"])


if __name__ == "__main__":
    unittest.main()
