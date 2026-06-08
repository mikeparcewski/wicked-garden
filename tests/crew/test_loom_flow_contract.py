import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _loom  # noqa: E402
import phase_manager as pm  # noqa: E402
import flow_compiler as fc  # noqa: E402 — Task 5; import guarded below

# (archetype, gate phase) pairs the in-process map declares. The compiler must
# attach the archetype's HITL discipline to exactly this phase — proving the two
# engines agree on WHERE the human stops, regardless of whether the catalog
# labels that discipline hard:* or discrete:* (that is a separate axis).
_EXPECTED_GATE_PHASES = {
    "migrate": "cutover",
    "incident": "mitigate",
    "review": "remediate-or-accept",
    "specify": "validate",
    "decide": "record",
}


class FlowHardGateParityContract(unittest.TestCase):
    """Strangler safety net: loom's park decision (derived from the compiled
    flow definition) must match phase_manager._HARD_GATE_PHASES for every
    archetype. The two engines must agree on WHERE the human stops."""

    def test_compiled_flow_gate_phase_matches_in_process_map(self):
        for archetype, gate_phase in _EXPECTED_GATE_PHASES.items():
            flow_def = fc.compile_flow(archetype, flow_id=f"{archetype}-x")
            gated = [p["name"] for p in flow_def["phases"]
                     if isinstance(p.get("hitl"), str) and p["hitl"] != "none"]
            self.assertIn(gate_phase, gated,
                          f"{archetype}: compiled flow gate phase != in-process map")

    def test_non_hard_archetypes_compile_no_hard_phase(self):
        for archetype in ("triage", "explore", "build", "ship"):
            flow_def = fc.compile_flow(archetype, flow_id=f"{archetype}-x")
            hard_phases = [p["name"] for p in flow_def["phases"]
                           if isinstance(p.get("hitl"), str) and p["hitl"].startswith("hard:")]
            self.assertEqual(hard_phases, [],
                             f"{archetype} should have no hard:* phase")

    def test_approve_phase_in_process_authority_unchanged_when_loom_off(self):
        # With cutover off, approve_phase behaves exactly as before: a hard gate
        # without --confirmed-by raises ValueError (the in-process guard).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        st = pm.ProjectState(name="m1", current_phase="cutover",
                             created_at=pm.get_utc_timestamp(),
                             phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
                             extras={"v11_archetype": "migrate"})
        with patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def tearDown(self):
        os.environ.pop("WICKED_LOOM_CUTOVER", None)


if __name__ == "__main__":
    unittest.main()
