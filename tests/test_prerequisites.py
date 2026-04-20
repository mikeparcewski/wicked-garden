"""
tests/test_prerequisites.py

Unit tests for scripts/crew/_prerequisites.py.

Coverage:
  - gate passes on ok status
  - gate raises on missing status
  - gate raises on out-of-range status
  - gate raises on probe-absent key (CH-02 fail-closed)
  - gate raises when session_state is None
  - gate raises when extras is None (probe never ran)
  - gate raises when wicked_testing_missing is True (flag set, key absent)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT / "scripts" / "crew") not in sys.path:
    sys.path.append(str(_REPO_ROOT / "scripts" / "crew"))

from crew._prerequisites import PrerequisiteError, crew_command_gate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(probe_result=None, wt_missing=None, extras_override=None):
    """Build a mock SessionState.

    extras_override: if provided, sets state.extras directly (can be None
    to simulate "extras attr is None").
    """
    state = MagicMock()
    if extras_override is not None:
        state.extras = extras_override
    elif probe_result is not None:
        state.extras = {"wicked_testing_probe": probe_result}
    else:
        state.extras = {}
    state.wicked_testing_missing = wt_missing
    return state


# ---------------------------------------------------------------------------
# Gate passes
# ---------------------------------------------------------------------------

class TestGatePasses:
    def test_ok_status_passes(self):
        state = _make_state(probe_result={"status": "ok", "version": "0.1.3", "pin": "^0.1.0", "error": None})
        # Should return None without raising.
        result = crew_command_gate(state)
        assert result is None

    def test_ok_skipped_passes(self):
        """Escape hatch result (version='skipped') also passes."""
        state = _make_state(probe_result={"status": "ok", "version": "skipped", "pin": "skipped", "error": None})
        crew_command_gate(state)  # must not raise


# ---------------------------------------------------------------------------
# Gate raises on missing
# ---------------------------------------------------------------------------

class TestGateRaisesOnMissing:
    def test_missing_status_raises(self):
        state = _make_state(
            probe_result={"status": "missing", "version": None, "pin": "^0.1.0", "error": "npx not found"},
        )
        with pytest.raises(PrerequisiteError, match="wicked-testing required"):
            crew_command_gate(state)

    def test_error_status_raises(self):
        state = _make_state(
            probe_result={"status": "error", "version": None, "pin": "^0.1.0", "error": "probe timeout"},
        )
        with pytest.raises(PrerequisiteError, match="wicked-testing required"):
            crew_command_gate(state)

    def test_error_message_includes_install_pointer(self):
        state = _make_state(
            probe_result={"status": "missing", "version": None, "pin": "^0.1.0", "error": None},
        )
        with pytest.raises(PrerequisiteError) as exc_info:
            crew_command_gate(state)
        assert "npx wicked-testing install" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Gate raises on out-of-range
# ---------------------------------------------------------------------------

class TestGateRaisesOnOutOfRange:
    def test_out_of_range_raises(self):
        state = _make_state(
            probe_result={"status": "out-of-range", "version": "0.0.9", "pin": "^0.1.0", "error": None},
        )
        with pytest.raises(PrerequisiteError):
            crew_command_gate(state)

    def test_out_of_range_message_names_version_and_pin(self):
        state = _make_state(
            probe_result={"status": "out-of-range", "version": "0.0.9", "pin": "^0.1.0", "error": None},
        )
        with pytest.raises(PrerequisiteError) as exc_info:
            crew_command_gate(state)
        msg = str(exc_info.value)
        assert "0.0.9" in msg
        assert "^0.1.0" in msg
        assert "npx wicked-testing install" in msg


# ---------------------------------------------------------------------------
# CH-02 fail-closed: probe-absent key raises (not passes)
# ---------------------------------------------------------------------------

class TestProbeAbsentFailClosed:
    """CH-02 hardening: if the probe key is absent in extras, treat as missing."""

    def test_probe_key_absent_raises(self):
        """Probe key absent (bootstrap exception) → fail-closed."""
        # extras exists but wicked_testing_probe key is not in it
        state = _make_state()  # empty extras, no probe_result
        state.wicked_testing_missing = None  # probe never ran
        with pytest.raises(PrerequisiteError, match="wicked-testing required"):
            crew_command_gate(state)

    def test_probe_key_absent_wt_missing_false_still_raises(self):
        """Even if wicked_testing_missing=False (fail-open path), absent key → raise.

        This is the core CH-02 invariant: fail-open at bootstrap does NOT
        propagate to fail-open at the crew gate.
        """
        state = _make_state()  # empty extras
        state.wicked_testing_missing = False  # bootstrap set False (fail-open)
        with pytest.raises(PrerequisiteError):
            crew_command_gate(state)

    def test_probe_key_absent_wt_missing_true_raises(self):
        state = _make_state()  # empty extras
        state.wicked_testing_missing = True
        with pytest.raises(PrerequisiteError, match="wicked-testing required"):
            crew_command_gate(state)

    def test_extras_is_none_raises(self):
        """extras=None means probe was never run → fail-closed."""
        state = _make_state(extras_override=None)
        state.wicked_testing_missing = None
        with pytest.raises(PrerequisiteError):
            crew_command_gate(state)

    def test_session_state_none_raises(self):
        """session_state=None → fail-closed (cannot determine probe result)."""
        with pytest.raises(PrerequisiteError, match="wicked-testing required"):
            crew_command_gate(None)

    def test_prerequisite_error_is_runtime_error(self):
        """PrerequisiteError is a RuntimeError subclass."""
        assert issubclass(PrerequisiteError, RuntimeError)
