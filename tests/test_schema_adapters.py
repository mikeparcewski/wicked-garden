#!/usr/bin/env python3
"""Tier 1 — Pure unit tests for crew schema adapter FK propagation (#155).

Tests cover:
- Forward FK propagation (cp_project_id → project_id) in all 5 crew to_cp adapters
- Reverse FK propagation (project_id → cp_project_id) in all 5 crew from_cp adapters
- Round-trip fidelity for all crew adapters
- crew/projects adapter field renaming
- BC-03: to_cp functions return input unchanged when cp_project_id is absent
"""

import sys
import unittest
from pathlib import Path

# Add scripts/ to path so adapters can be imported
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from _schema_adapters import (
    _crew_decisions_from_cp,
    _crew_decisions_to_cp,
    _crew_feedback_from_cp,
    _crew_feedback_to_cp,
    _crew_metrics_from_cp,
    _crew_metrics_to_cp,
    _crew_projects_from_cp,
    _crew_projects_to_cp,
    _crew_signals_from_cp,
    _crew_signals_to_cp,
    _crew_tool_usage_from_cp,
    _crew_tool_usage_to_cp,
)


class TestCrewProjectsAdapter(unittest.TestCase):
    """#155 — crew/projects adapter pair."""

    def test_to_cp_renames_cp_project_id_to_project_id(self):
        record = {"name": "my-proj", "cp_project_id": "uuid-123"}
        out = _crew_projects_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-123")
        self.assertNotIn("cp_project_id", out)

    def test_from_cp_renames_project_id_to_cp_project_id(self):
        record = {"name": "my-proj", "project_id": "uuid-123", "status": "active"}
        out = _crew_projects_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-123")
        self.assertNotIn("project_id", out)

    def test_to_cp_sets_status_active(self):
        record = {"name": "p"}
        out = _crew_projects_to_cp(record)
        self.assertEqual(out["status"], "active")

    def test_to_cp_sets_status_archived(self):
        record = {"name": "p", "archived": True}
        out = _crew_projects_to_cp(record)
        self.assertEqual(out["status"], "archived")

    def test_from_cp_sets_archived_flag(self):
        out = _crew_projects_from_cp({"status": "archived"})
        self.assertTrue(out["archived"])

    def test_from_cp_sets_not_archived(self):
        out = _crew_projects_from_cp({"status": "active"})
        self.assertFalse(out["archived"])


class TestCrewDecisionsFK(unittest.TestCase):
    """#155 — crew/decisions FK propagation."""

    def test_to_cp_propagates_fk(self):
        record = {"id": "d1", "cp_project_id": "uuid-abc", "project_name": "p"}
        out = _crew_decisions_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-abc")

    def test_to_cp_no_fk_when_absent(self):
        record = {"id": "d1", "project_name": "p"}
        out = _crew_decisions_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_from_cp_reverse_fk(self):
        record = {"id": "d1", "project_id": "uuid-abc", "decision_type": "analysis"}
        out = _crew_decisions_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-abc")
        self.assertNotIn("project_id", out)

    def test_from_cp_no_project_id(self):
        record = {"id": "d1", "decision_type": "analysis"}
        out = _crew_decisions_from_cp(record)
        self.assertNotIn("cp_project_id", out)


class TestCrewFeedbackFK(unittest.TestCase):
    """#155 — crew/feedback FK propagation."""

    def test_to_cp_propagates_fk(self):
        record = {"id": "f1", "cp_project_id": "uuid-def", "project_name": "p"}
        out = _crew_feedback_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-def")

    def test_to_cp_no_fk_when_absent(self):
        record = {"id": "f1", "project_name": "p"}
        out = _crew_feedback_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_from_cp_reverse_fk(self):
        record = {"id": "f1", "project_id": "uuid-def"}
        out = _crew_feedback_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-def")
        self.assertNotIn("project_id", out)


class TestCrewMetricsFK(unittest.TestCase):
    """#155 — crew/metrics FK propagation."""

    def test_to_cp_propagates_fk(self):
        record = {"id": "m1", "cp_project_id": "uuid-ghi"}
        out = _crew_metrics_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-ghi")

    def test_to_cp_no_fk_when_absent(self):
        record = {"id": "m1"}
        out = _crew_metrics_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_from_cp_reverse_fk(self):
        record = {"id": "m1", "project_id": "uuid-ghi", "category": "signal-accuracy"}
        out = _crew_metrics_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-ghi")
        self.assertNotIn("project_id", out)


class TestCrewSignalsFK(unittest.TestCase):
    """#155 — crew/signals FK propagation."""

    def test_to_cp_propagates_fk(self):
        record = {"id": "s1", "cp_project_id": "uuid-jkl"}
        out = _crew_signals_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-jkl")

    def test_to_cp_no_fk_when_absent(self):
        record = {"id": "s1"}
        out = _crew_signals_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_from_cp_reverse_fk(self):
        record = {"id": "s1", "project_id": "uuid-jkl", "signal_type": "security"}
        out = _crew_signals_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-jkl")
        self.assertNotIn("project_id", out)


class TestCrewToolUsageFK(unittest.TestCase):
    """#155 — crew/tool-usage FK propagation."""

    def test_to_cp_propagates_fk(self):
        record = {"id": "t1", "tool": "grep", "cp_project_id": "uuid-mno"}
        out = _crew_tool_usage_to_cp(record)
        self.assertEqual(out["project_id"], "uuid-mno")

    def test_to_cp_no_fk_when_absent(self):
        record = {"id": "t1", "tool": "grep"}
        out = _crew_tool_usage_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_from_cp_reverse_fk(self):
        record = {"id": "t1", "project_id": "uuid-mno", "tool_name": "grep"}
        out = _crew_tool_usage_from_cp(record)
        self.assertEqual(out["cp_project_id"], "uuid-mno")
        self.assertNotIn("project_id", out)


class TestRoundTrip(unittest.TestCase):
    """#155 — Round-trip fidelity: to_cp then from_cp preserves cp_project_id."""

    def test_decisions_round_trip(self):
        original = {"id": "d1", "cp_project_id": "uuid-rt", "project_name": "p"}
        cp = _crew_decisions_to_cp(original)
        back = _crew_decisions_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")

    def test_feedback_round_trip(self):
        original = {"id": "f1", "cp_project_id": "uuid-rt", "project_name": "p"}
        cp = _crew_feedback_to_cp(original)
        back = _crew_feedback_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")

    def test_metrics_round_trip(self):
        original = {"id": "m1", "cp_project_id": "uuid-rt"}
        cp = _crew_metrics_to_cp(original)
        back = _crew_metrics_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")

    def test_signals_round_trip(self):
        original = {"id": "s1", "cp_project_id": "uuid-rt", "category": "security",
                     "text": "Uses auth", "weight": 0.8}
        cp = _crew_signals_to_cp(original)
        back = _crew_signals_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")

    def test_tool_usage_round_trip(self):
        original = {"id": "t1", "cp_project_id": "uuid-rt", "tool": "grep"}
        cp = _crew_tool_usage_to_cp(original)
        back = _crew_tool_usage_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")

    def test_projects_round_trip(self):
        original = {"name": "proj", "cp_project_id": "uuid-rt"}
        cp = _crew_projects_to_cp(original)
        back = _crew_projects_from_cp(cp)
        self.assertEqual(back.get("cp_project_id"), "uuid-rt")


class TestBC03NoFKWhenAbsent(unittest.TestCase):
    """BC-03: to_cp functions leave output unchanged when cp_project_id is absent."""

    def test_decisions_no_fk(self):
        record = {"id": "d1", "project_name": "p"}
        out = _crew_decisions_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_feedback_no_fk(self):
        record = {"id": "f1", "project_name": "p"}
        out = _crew_feedback_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_metrics_no_fk(self):
        record = {"id": "m1"}
        out = _crew_metrics_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_signals_no_fk(self):
        record = {"id": "s1"}
        out = _crew_signals_to_cp(record)
        self.assertNotIn("project_id", out)

    def test_tool_usage_no_fk(self):
        record = {"id": "t1", "tool": "grep"}
        out = _crew_tool_usage_to_cp(record)
        self.assertNotIn("project_id", out)


if __name__ == "__main__":
    unittest.main()
