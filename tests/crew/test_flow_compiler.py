import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import flow_compiler as fc  # noqa: E402


class CompileFlowTests(unittest.TestCase):
    def test_build_flow_shape(self):
        fd = fc.compile_flow("build", flow_id="build-1")
        self.assertEqual(fd["flow_id"], "build-1")
        self.assertEqual([p["name"] for p in fd["phases"]],
                         ["plan", "implement", "test", "review"])
        # build is discrete:review-gate -> no hard:* phase.
        self.assertFalse(any(p["hitl"].startswith("hard:") for p in fd["phases"]))

    def test_migrate_cutover_is_the_hard_phase(self):
        fd = fc.compile_flow("migrate", flow_id="m-1")
        hard = [p for p in fd["phases"] if p["hitl"].startswith("hard:")]
        self.assertEqual(len(hard), 1)
        self.assertEqual(hard[0]["name"], "cutover")
        self.assertEqual(hard[0]["hitl"], "hard:cutover-gate")

    def test_triage_is_fully_gateless(self):
        fd = fc.compile_flow("triage", flow_id="t-1")
        self.assertTrue(all(p["gate"] is None for p in fd["phases"]))
        self.assertTrue(all(p["hitl"] == "none" for p in fd["phases"]))

    def test_gating_archetype_has_a_gate_on_last_phase(self):
        fd = fc.compile_flow("build", flow_id="b-1")
        self.assertIsNotNone(fd["phases"][-1]["gate"])
        self.assertTrue(fd["phases"][-1]["gate"].startswith("produces:"))

    def test_peers_required_includes_testing_when_test_report_produced(self):
        self.assertIn("testing", fc.compile_flow("build", flow_id="b-1")["peers_required"])
        self.assertNotIn("testing", fc.compile_flow("decide", flow_id="d-1")["peers_required"])

    def test_verifier_spec_ref_is_null(self):
        self.assertIsNone(fc.compile_flow("build", flow_id="b-1")["verifier_spec_ref"])

    def test_unknown_archetype_raises(self):
        with self.assertRaises(ValueError):
            fc.compile_flow("frobnicate", flow_id="x-1")

    def test_unsafe_flow_id_raises(self):
        with self.assertRaises(ValueError):
            fc.compile_flow("build", flow_id="../etc/passwd")

    def test_output_is_json_serializable(self):
        import json
        json.dumps(fc.compile_flow("incident", flow_id="i-1"))  # must not raise


if __name__ == "__main__":
    unittest.main()
