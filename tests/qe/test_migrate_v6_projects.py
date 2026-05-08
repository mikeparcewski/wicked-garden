"""Tests for scripts/setup/migrate_v6_projects.py — v6→v11 project migration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "setup"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import migrate_v6_projects as mig  # noqa: E402


class TestPhasePlanClassification(unittest.TestCase):
    """The classifier maps a v6 phase plan to the closest v11 archetype."""

    def test_universal_pipeline_routes_to_build(self):
        plan = ["clarify", "design", "build", "test", "review"]
        self.assertEqual(mig._classify_phase_plan(plan), "build")

    def test_expand_contract_routes_to_migrate(self):
        plan = ["plan", "expand", "backfill", "cutover", "contract"]
        self.assertEqual(mig._classify_phase_plan(plan), "migrate")

    def test_cutover_alone_routes_to_migrate(self):
        plan = ["plan", "cutover"]
        self.assertEqual(mig._classify_phase_plan(plan), "migrate")

    def test_canary_ramp_routes_to_ship(self):
        plan = ["canary", "ramp", "full", "soak"]
        self.assertEqual(mig._classify_phase_plan(plan), "ship")

    def test_triage_investigate_mitigate_routes_to_incident(self):
        plan = ["triage", "investigate", "mitigate", "resolve", "followup"]
        self.assertEqual(mig._classify_phase_plan(plan), "incident")

    def test_review_phases_route_to_review(self):
        plan = ["scope", "assess", "findings", "remediate-or-accept"]
        self.assertEqual(mig._classify_phase_plan(plan), "review")

    def test_specify_phases_route_to_specify(self):
        plan = ["elicit", "structure", "validate"]
        self.assertEqual(mig._classify_phase_plan(plan), "specify")

    def test_decide_phases_route_to_decide(self):
        plan = ["brief", "options", "score", "record"]
        self.assertEqual(mig._classify_phase_plan(plan), "decide")

    def test_explore_phases_route_to_explore(self):
        plan = ["frame", "diverge", "converge"]
        self.assertEqual(mig._classify_phase_plan(plan), "explore")

    def test_unknown_plan_routes_to_build_default(self):
        plan = ["weird", "plan", "shape"]
        self.assertEqual(mig._classify_phase_plan(plan), "build")

    def test_empty_plan_routes_to_build_default(self):
        self.assertEqual(mig._classify_phase_plan([]), "build")


class TestMigrateOne(unittest.TestCase):
    """migrate_one returns a dict describing the proposed migration.

    dry_run=True does not mutate state; dry_run=False applies."""

    def _v6_record(self, name="legacy-proj"):
        return {
            "id": name, "name": name,
            "current_phase": "build",
            "created_at": "2026-04-01T00:00:00Z",
            "version": "v9",
            "phase_plan": ["clarify", "design", "build", "test", "review"],
            "phases": {},
            "extras": {"phase_plan_mode": "facilitator"},
        }

    def test_dry_run_returns_proposed_mapping(self):
        result = mig.migrate_one(self._v6_record(), dry_run=True)
        self.assertEqual(result["chosen_archetype"], "build")
        self.assertEqual(
            result["to_phases"],
            ["plan", "implement", "test", "review"],
        )
        self.assertFalse(result["applied"])

    def test_dry_run_does_not_mutate(self):
        with patch.object(mig, "_utc_now", return_value="2026-05-08T00:00:00Z"):
            with patch("_domain_store.DomainStore") as mock_ds:
                mig.migrate_one(self._v6_record(), dry_run=True)
                mock_ds.assert_not_called()


class TestDetectV6Projects(unittest.TestCase):
    """detect_v6_projects filters DomainStore records that look v6-shaped."""

    def test_skips_v11_archetype_mode(self):
        records = [
            {"name": "legacy", "phase_plan": ["clarify", "design"],
             "extras": {"phase_plan_mode": "facilitator"}},
            {"name": "modern", "phase_plan": ["plan", "implement"],
             "extras": {"phase_plan_mode": "archetype",
                        "v11_archetype": "build"}},
        ]
        with patch("_domain_store.DomainStore") as MockDS:
            MockDS.return_value.list.return_value = records
            legacy = mig.detect_v6_projects()
        names = [r.get("name") for r in legacy]
        self.assertIn("legacy", names)
        self.assertNotIn("modern", names)

    def test_skips_records_without_phase_plan(self):
        records = [
            {"name": "no-plan", "phase_plan": [], "extras": {}},
            {"name": "has-plan",
             "phase_plan": ["clarify", "design"], "extras": {}},
        ]
        with patch("_domain_store.DomainStore") as MockDS:
            MockDS.return_value.list.return_value = records
            legacy = mig.detect_v6_projects()
        names = [r.get("name") for r in legacy]
        self.assertNotIn("no-plan", names)
        self.assertIn("has-plan", names)


if __name__ == "__main__":
    unittest.main()
