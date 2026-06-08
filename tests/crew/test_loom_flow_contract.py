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


class FlowAuthoritativeParkDecision(unittest.TestCase):
    """Flow surface cutover: loom is AUTHORITATIVE for the hard-gate park
    decision. loom-says-hard adds a park; loom-unavailable falls back to the
    in-process map; loom-says-not-hard can NEVER remove a map-asserted park
    (the fail-closed floor). The ValueError + confirmation contract is preserved.
    """

    def setUp(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        os.environ.pop("WICKED_LOOM_CUTOVER", None)

    def _migrate_state(self, phase="cutover"):
        return pm.ProjectState(
            name="m1", current_phase=phase,
            created_at=pm.get_utc_timestamp(),
            phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
            extras={"v11_archetype": "migrate"})

    def _build_state(self, phase="plan"):
        return pm.ProjectState(
            name="b1", current_phase=phase,
            created_at=pm.get_utc_timestamp(),
            phase_plan=["plan", "implement", "test", "review"],
            extras={"v11_archetype": "build"})

    def test_loom_authoritative_hard_gate_requires_confirmation(self):
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_loom_adds_a_park_the_in_process_map_does_not_assert(self):
        st = self._build_state("review")
        self.assertFalse(pm._is_hard_gate(st, "review"))  # floor: not hard
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "review")

    def test_loom_says_not_hard_CANNOT_remove_a_map_asserted_park(self):
        # THE FAIL-CLOSED FLOOR: loom says cutover is NOT hard, but the map
        # asserts it IS. The park MUST still fire — loom can add, never remove.
        st = self._migrate_state("cutover")
        self.assertTrue(pm._is_hard_gate(st, "cutover"))  # floor: hard
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_loom_unavailable_falls_back_to_in_process_map(self):
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=None), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_non_hard_phase_advances_when_both_sources_agree_not_hard(self):
        st = self._build_state("plan")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False), \
             patch.object(pm, "save_project_state", lambda s: None):
            _, next_phase = pm.approve_phase(st, "plan")
        self.assertEqual(next_phase, "implement")

    def test_hard_gate_with_confirmation_advances(self):
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            state, next_phase = pm.approve_phase(
                st, "cutover", confirmed_by="oncall-jane",
                confirmation_evidence="https://dash/rollback-drill-42")
        self.assertEqual(next_phase, "contract")
        self.assertEqual(state.phases["cutover"].status, "approved")

    def test_resolve_hard_gate_returns_floor_when_loom_none(self):
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=None):
            self.assertTrue(pm.resolve_hard_gate(st, "cutover"))
            self.assertFalse(pm.resolve_hard_gate(st, "plan"))

    def test_resolve_hard_gate_is_or_of_both_sources(self):
        st = self._build_state("review")  # not hard in the map
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True):
            self.assertTrue(pm.resolve_hard_gate(st, "review"))  # loom adds it
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False):
            self.assertFalse(pm.resolve_hard_gate(st, "review"))  # neither


if __name__ == "__main__":
    unittest.main()
