#!/usr/bin/env python3
"""Tier 1 — Pure unit tests for SessionState cp_project_id / cp_schema_reset_detected (#153).

Tests cover:
- SessionState._from_dict handles cp_project_id and cp_schema_reset_detected
- SessionState._from_dict ignores unknown fields silently
- Default values for new fields
- BC-02: Pre-#153 state files load cleanly with defaults
"""

import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from _session import SessionState


class TestSessionStateCpFields(unittest.TestCase):
    """#153 — SessionState new field handling."""

    def test_default_cp_project_id_is_none(self):
        state = SessionState()
        self.assertIsNone(state.cp_project_id)

    def test_default_cp_schema_reset_detected_is_false(self):
        state = SessionState()
        self.assertFalse(state.cp_schema_reset_detected)

    def test_from_dict_with_cp_project_id(self):
        data = {"cp_project_id": "uuid-123", "cp_schema_reset_detected": True}
        state = SessionState._from_dict(data)
        self.assertEqual(state.cp_project_id, "uuid-123")
        self.assertTrue(state.cp_schema_reset_detected)

    def test_from_dict_without_cp_fields(self):
        """BC-02: Old state files without new fields load cleanly."""
        data = {"cp_available": True, "turn_count": 5}
        state = SessionState._from_dict(data)
        self.assertIsNone(state.cp_project_id)
        self.assertFalse(state.cp_schema_reset_detected)

    def test_from_dict_ignores_unknown_fields(self):
        data = {"cp_project_id": "uuid-123", "some_future_field": "value"}
        state = SessionState._from_dict(data)
        self.assertEqual(state.cp_project_id, "uuid-123")
        self.assertFalse(hasattr(state, "some_future_field"))

    def test_to_dict_includes_cp_fields(self):
        state = SessionState(cp_project_id="uuid-456", cp_schema_reset_detected=True)
        d = state.to_dict()
        self.assertEqual(d["cp_project_id"], "uuid-456")
        self.assertTrue(d["cp_schema_reset_detected"])

    def test_update_cp_project_id(self):
        state = SessionState()
        state.update(cp_project_id="uuid-789")
        self.assertEqual(state.cp_project_id, "uuid-789")

    def test_cp_project_id_type_is_optional_str(self):
        """AC #153: cp_project_id is str | None = None."""
        state = SessionState()
        self.assertIsNone(state.cp_project_id)
        state.cp_project_id = "uuid-test"
        self.assertIsInstance(state.cp_project_id, str)
        state.cp_project_id = None
        self.assertIsNone(state.cp_project_id)


if __name__ == "__main__":
    unittest.main()
