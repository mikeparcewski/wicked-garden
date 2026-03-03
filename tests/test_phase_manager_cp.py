#!/usr/bin/env python3
"""Tier 2 — Integration tests for phase_manager cp_project_id handling (#153).

Tests cover:
- ProjectState.cp_project_id field exists with Optional[str] = None default
- save_project_state serializes cp_project_id via StorageManager
- load_project_state deserializes cp_project_id (backward compatible)
- _merge_data_into_state has cp_project_id in known_fields
- CP status mapping only sends "active" or "archived"
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager as pm

ProjectState = pm.ProjectState
_merge_data_into_state = pm._merge_data_into_state
_update_cp_project_status = pm._update_cp_project_status
save_project_state = pm.save_project_state
load_project_state = pm.load_project_state


def _make_state(**kwargs):
    """Create a ProjectState with required fields filled in."""
    defaults = {
        "name": "test-project",
        "current_phase": "clarify",
        "created_at": "2026-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return ProjectState(**defaults)


class TestProjectStateCpField(unittest.TestCase):
    """#153 — ProjectState.cp_project_id field."""

    def test_default_is_none(self):
        state = _make_state()
        self.assertIsNone(state.cp_project_id)

    def test_can_set_uuid(self):
        state = _make_state(cp_project_id="uuid-123")
        self.assertEqual(state.cp_project_id, "uuid-123")


class TestSaveLoadCpProjectId(unittest.TestCase):
    """#153 — Save and load round-trip with cp_project_id."""

    @patch.object(pm, "_sm")
    def test_save_serializes_cp_project_id(self, mock_sm):
        """save_project_state includes cp_project_id in the data dict."""
        mock_sm.get.return_value = None
        mock_sm.create.return_value = True

        state = _make_state(cp_project_id="uuid-save-test")

        save_project_state(state)

        call_args = mock_sm.create.call_args
        data = call_args[0][1]  # positional: (source, data)
        self.assertEqual(data.get("cp_project_id"), "uuid-save-test")

    @patch.object(pm, "_sm")
    def test_load_deserializes_cp_project_id(self, mock_sm):
        mock_sm.get.return_value = {
            "name": "test-load",
            "cp_project_id": "uuid-load-test",
            "current_phase": "clarify",
            "created_at": "2026-01-01T00:00:00Z",
            "phases": [],
        }

        state = load_project_state("test-load")
        self.assertIsNotNone(state)
        self.assertEqual(state.cp_project_id, "uuid-load-test")

    @patch.object(pm, "_sm")
    def test_load_backward_compatible_without_cp_project_id(self, mock_sm):
        """BC-01: Old project files without cp_project_id load cleanly."""
        mock_sm.get.return_value = {
            "name": "old-project",
            "current_phase": "clarify",
            "created_at": "2026-01-01T00:00:00Z",
            "phases": [],
        }

        state = load_project_state("old-project")
        self.assertIsNotNone(state)
        self.assertIsNone(state.cp_project_id)


class TestMergeDataIntoState(unittest.TestCase):
    """#153 — _merge_data_into_state recognises cp_project_id."""

    def test_merges_cp_project_id(self):
        state = _make_state()
        _merge_data_into_state(state, {"cp_project_id": "uuid-merge"})
        self.assertEqual(state.cp_project_id, "uuid-merge")

    def test_unknown_keys_go_to_extras(self):
        state = _make_state()
        _merge_data_into_state(state, {"unknown_field": "value"})
        self.assertEqual(state.extras.get("unknown_field"), "value")


class TestCpStatusMapping(unittest.TestCase):
    """#153 — _update_cp_project_status only sends valid CP statuses."""

    @patch("_control_plane.get_client")
    @patch("_session.SessionState.load")
    def test_active_status(self, mock_load, mock_get_client):
        """Non-archived statuses map to 'active'."""
        from _session import SessionState
        mock_load.return_value = SessionState(cp_available=True)
        mock_cp = MagicMock()
        mock_get_client.return_value = mock_cp

        state = _make_state(cp_project_id="uuid-1")
        _update_cp_project_status(state, "in_review")
        call_args = mock_cp.request.call_args
        self.assertEqual(call_args[1]["payload"]["status"], "active")

    @patch("_control_plane.get_client")
    @patch("_session.SessionState.load")
    def test_archived_status(self, mock_load, mock_get_client):
        """'archived' maps to 'archived'."""
        from _session import SessionState
        mock_load.return_value = SessionState(cp_available=True)
        mock_cp = MagicMock()
        mock_get_client.return_value = mock_cp

        state = _make_state(cp_project_id="uuid-1")
        _update_cp_project_status(state, "archived")
        call_args = mock_cp.request.call_args
        self.assertEqual(call_args[1]["payload"]["status"], "archived")

    @patch("_control_plane.get_client")
    @patch("_session.SessionState.load")
    def test_completed_maps_to_active(self, mock_load, mock_get_client):
        """'completed' should NOT be sent to CP — maps to 'active'."""
        from _session import SessionState
        mock_load.return_value = SessionState(cp_available=True)
        mock_cp = MagicMock()
        mock_get_client.return_value = mock_cp

        state = _make_state(cp_project_id="uuid-1")
        _update_cp_project_status(state, "completed")
        call_args = mock_cp.request.call_args
        self.assertEqual(call_args[1]["payload"]["status"], "active")

    def test_no_cp_project_id_is_noop(self):
        """Without cp_project_id, the function should not crash."""
        state = _make_state()
        # Should not raise — returns early when cp_project_id is None
        _update_cp_project_status(state, "active")


if __name__ == "__main__":
    unittest.main()
