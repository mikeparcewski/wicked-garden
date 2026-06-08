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


class GateCutoverContract(unittest.TestCase):
    """Strangler safety net: the loom-shelled gate verdict must match the
    in-process cross_check verdict (same overall + satisfied) for PASS,
    REJECT, and the fail-closed-when-vault-absent case."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def _loom_gate_runner(self, overall):
        def fake_run(prefix, args, timeout):
            import json
            verdict = {"satisfied": overall == "PASS", "overall": overall,
                       "gate": "vault-cross-check"}
            return {"exit_code": 0 if overall == "PASS" else 1,
                    "stdout": json.dumps({"gate": verdict}), "stderr": "", "error": None}
        return fake_run

    def test_loom_pass_matches_in_process_pass(self):
        # In-process PASS (stub the vault subprocess).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(vg, "resolve_vault", return_value=["wicked-vault"]), \
             patch.object(vg, "_run", return_value={"exit_code": 0, "error": None,
                          "stdout": '{"overall":"PASS"}', "stderr": ""}):
            in_proc = vg.cross_check("build-1", "test", project_dir=_PROJECT)

        # Loom PASS.
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("PASS")):
            via_loom = vg.cross_check("build-1", "test", project_dir=_PROJECT)

        self.assertEqual(via_loom["overall"], in_proc["overall"])
        self.assertTrue(via_loom["available"])

    def test_loom_reject_matches_in_process_reject(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("REJECT")):
            via_loom = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertEqual(via_loom["overall"], "REJECT")

    def test_gate_fails_closed_when_loom_errors_and_vault_absent(self):
        # auto + loom unresolvable -> in-process gate runs; vault also absent
        # -> fail closed. The loom error never invents a PASS (I2).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(vg, "resolve_vault", return_value=None):
            verdict = vg.gate_satisfied(_PROJECT, "build-1", "test")
        self.assertFalse(verdict["satisfied"])
        self.assertEqual(verdict["gate"], "unavailable")

    def test_loom_with_attestations_forwarded(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        seen = {}

        def fake_run(prefix, args, timeout):
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
