"""tests/crew/test_facilitator_wicked_testing_check.py

Unit tests for the AC-23 defense-in-depth wicked-testing availability check
added to testability_gate_check() in scripts/crew/_prerequisites.py.

Coverage:
  AC-1 — probe present with status="ok" → check passes (returns None)
  AC-2 — probe present with status != "ok" → PrerequisiteError raised with
          structured message naming wicked-testing and install instruction
  AC-2 — probe key absent in extras → PrerequisiteError raised (fail-closed)
  AC-3 — session_state.extras={} (probe never ran) → PrerequisiteError raised

Rules:
  T1: deterministic — no subprocess, no real session state
  T3: isolated — MagicMock only, no filesystem access
  T4: single behaviour per test
  T5: descriptive names
  T6: docstrings cite ACs
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CREW_DIR = _SCRIPTS_DIR / "crew"

for _p in (str(_SCRIPTS_DIR), str(_CREW_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from crew._prerequisites import PrerequisiteError, check_testability_gate  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(probe=None, extras_override=None):
    """Build a minimal mock SessionState.

    extras_override replaces state.extras entirely (use {} to simulate
    a session where the probe key was never written).
    """
    s = MagicMock()
    if extras_override is not None:
        s.extras = extras_override
    elif probe is not None:
        s.extras = {"wicked_testing_probe": probe}
    else:
        s.extras = {}
    return s


# ---------------------------------------------------------------------------
# AC-1: probe ok — check passes
# ---------------------------------------------------------------------------

class TestTestabilityCheckPasses:
    def test_ok_status_returns_none(self):
        """AC-1 — probe status=ok → testability_gate_check returns None."""
        state = _state(probe={"status": "ok", "version": "0.1.3", "pin": "^0.1.0"})
        result = check_testability_gate(state)
        assert result is None

    def test_ok_skipped_returns_none(self):
        """AC-1 — escape-hatch probe (status=ok, version=skipped) also passes."""
        state = _state(probe={"status": "ok", "version": "skipped", "pin": "skipped"})
        check_testability_gate(state)  # must not raise


# ---------------------------------------------------------------------------
# AC-2: probe present with non-ok status → PrerequisiteError
# ---------------------------------------------------------------------------

class TestTestabilityCheckRaisesOnBadStatus:
    def test_missing_status_raises(self):
        """AC-2 — probe status=missing → PrerequisiteError."""
        state = _state(probe={"status": "missing", "version": None})
        with pytest.raises(PrerequisiteError):
            check_testability_gate(state)

    def test_error_status_raises(self):
        """AC-2 — probe status=error → PrerequisiteError."""
        state = _state(probe={"status": "error", "version": None})
        with pytest.raises(PrerequisiteError):
            check_testability_gate(state)

    def test_error_message_names_status_and_install(self):
        """AC-2 — error message includes failing status and install instruction."""
        state = _state(probe={"status": "missing"})
        with pytest.raises(PrerequisiteError) as exc_info:
            check_testability_gate(state)
        msg = str(exc_info.value)
        assert "missing" in msg
        assert "npx wicked-testing install" in msg

    def test_error_message_names_testability_gate(self):
        """AC-2 — error message names the testability-gate dispatch location."""
        state = _state(probe={"status": "missing"})
        with pytest.raises(PrerequisiteError) as exc_info:
            check_testability_gate(state)
        assert "testability-gate" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-2 / AC-3: probe key absent → fail-closed
# ---------------------------------------------------------------------------

class TestTestabilityCheckFailClosed:
    def test_probe_key_absent_raises(self):
        """AC-2/AC-3 — wicked_testing_probe absent in extras → fail-closed."""
        state = _state(extras_override={})  # key not present
        with pytest.raises(PrerequisiteError):
            check_testability_gate(state)

    def test_probe_key_absent_message_names_probe_absent(self):
        """AC-3 — absent probe message names the missing key."""
        state = _state(extras_override={})
        with pytest.raises(PrerequisiteError) as exc_info:
            check_testability_gate(state)
        msg = str(exc_info.value)
        assert "probe absent" in msg
        assert "npx wicked-testing install" in msg

    def test_session_state_none_raises(self):
        """AC-3 — session_state=None → fail-closed (same as crew_command_gate)."""
        with pytest.raises(PrerequisiteError):
            check_testability_gate(None)

    def test_prerequisite_error_is_runtime_error(self):
        """AC-3 — PrerequisiteError is a RuntimeError subclass."""
        assert issubclass(PrerequisiteError, RuntimeError)
