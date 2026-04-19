"""Integration tests for the #462 approve-phase wiring.

Covers:
    AC-1: approve_phase(phase="build") writes SessionState.last_phase_approved
    AC-2: guard_pipeline warnings surface in the approve output (state.extras)
    AC-3: guard_pipeline raising during build-approve does NOT raise from approve

All tests are deterministic and stdlib-only. Session state is isolated via
TMPDIR + a per-test CLAUDE_SESSION_ID.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup — keep in sync with tests/crew/test_phase_manager.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "platform"))

import phase_manager as pm  # noqa: E402
from phase_manager import ProjectState, PhaseState, approve_phase  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_build_ready_state(name: str = "issue-462-test") -> ProjectState:
    state = ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-18T00:00:00Z",
    )
    state.phase_plan = ["clarify", "design", "build", "review"]
    state.phases["clarify"] = PhaseState(status="approved")
    state.phases["design"] = PhaseState(status="approved")
    state.phases["build"] = PhaseState(
        status="in_progress",
        started_at="2026-04-18T01:00:00Z",
    )
    return state


class _SessionTempTestCase(unittest.TestCase):
    """Base class: isolate SessionState to a temp dir and patch phase_manager
    helpers so approve_phase can reach the tail-end wiring without hitting
    real deliverable / gate / addendum checks.
    """

    def setUp(self):
        # Isolate SessionState by pointing TMPDIR at a per-test temp dir and
        # setting a unique session id so no other test can see our state.
        self._tempdir_obj = tempfile.TemporaryDirectory()
        self._tempdir = Path(self._tempdir_obj.name)
        self._env = patch.dict(os.environ, {
            "TMPDIR": str(self._tempdir),
            "CLAUDE_SESSION_ID": f"test-462-{id(self)}",
        })
        self._env.start()

        self._proj_dir = Path(self._tempdir_obj.name) / "projects" / "issue-462-test"
        self._proj_dir.mkdir(parents=True, exist_ok=True)
        (self._proj_dir / "phases" / "build").mkdir(parents=True, exist_ok=True)

        # Patch phase_manager to bypass real storage + deliverable checks.
        self._patches = [
            patch.object(pm, "get_project_dir", return_value=self._proj_dir),
            patch.object(pm, "save_project_state"),
            patch.object(pm, "_sm"),
            patch.object(pm, "_check_addendum_freshness", return_value=None),
            patch.object(pm, "_check_phase_deliverables", return_value=[]),
            patch.object(pm, "load_phases_config", return_value={
                "build": {"gate_required": False, "depends_on": []},
            }),
            patch.object(pm, "_load_session_dispatches", return_value=[]),
            patch.object(pm, "_run_checkpoint_reanalysis", return_value=(
                [], [])),
            patch.object(pm, "get_phase_order", return_value=[
                "clarify", "design", "build", "review"]),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._env.stop()
        self._tempdir_obj.cleanup()

    # ------------------------------------------------------------------
    # SessionState helpers — must import freshly each call so asdict()
    # serialization respects the current field schema.
    # ------------------------------------------------------------------
    def _load_session_state(self):
        # The session module caches path resolution per-call, so env
        # changes between tests are respected automatically.
        if "_session" in sys.modules:
            del sys.modules["_session"]
        from _session import SessionState  # type: ignore
        return SessionState.load()


# ---------------------------------------------------------------------------
# AC-1: last_phase_approved is set on successful build-phase approval
# ---------------------------------------------------------------------------


class TestLastPhaseApprovedWiring(_SessionTempTestCase):

    def test_build_approve_sets_last_phase_approved(self):
        """AC-1: after approving build, SessionState.last_phase_approved == 'build'."""
        state = _make_build_ready_state()
        # Guard pipeline is irrelevant to AC-1 — stub it to return nothing.
        with patch.object(pm, "_run_build_phase_guard", return_value=[]):
            result_state, next_phase = approve_phase(state, "build")

        self.assertEqual(next_phase, "review")
        sess = self._load_session_state()
        self.assertEqual(sess.last_phase_approved, "build")

    def test_re_approving_same_phase_is_idempotent(self):
        """AC-1: re-running approve for the same phase is safe (no crash, value stable)."""
        state = _make_build_ready_state()
        with patch.object(pm, "_run_build_phase_guard", return_value=[]):
            approve_phase(state, "build")
        # Reset phase state to simulate a re-approval.
        state.phases["build"] = PhaseState(
            status="in_progress",
            started_at="2026-04-18T01:00:00Z",
        )
        state.current_phase = "build"
        with patch.object(pm, "_run_build_phase_guard", return_value=[]):
            approve_phase(state, "build")

        sess = self._load_session_state()
        self.assertEqual(sess.last_phase_approved, "build")


# ---------------------------------------------------------------------------
# AC-2: guard-pipeline findings surface in approve output
# ---------------------------------------------------------------------------


class TestGuardWarningsSurface(_SessionTempTestCase):

    def test_guard_findings_appended_to_state_extras(self):
        """AC-2: when the guard emits findings at build-approve, they appear
        in state.extras['last_approve_warnings']."""
        state = _make_build_ready_state()

        synthetic_warning = (
            "[Guard] standard pipeline surfaced 3 finding(s) (120ms) — "
            "block=0 warn=2 info=1. Review next-session briefing."
        )
        with patch.object(pm, "_run_build_phase_guard", return_value=[synthetic_warning]):
            result_state, _ = approve_phase(state, "build")

        warnings = result_state.extras.get("last_approve_warnings", [])
        self.assertTrue(warnings, "expected approve warnings to be populated")
        self.assertIn(synthetic_warning, warnings)

    def test_no_findings_no_warnings(self):
        """Empty guard result leaves state.extras untouched."""
        state = _make_build_ready_state()
        with patch.object(pm, "_run_build_phase_guard", return_value=[]):
            result_state, _ = approve_phase(state, "build")

        self.assertEqual(
            result_state.extras.get("last_approve_warnings", []), [],
        )


# ---------------------------------------------------------------------------
# AC-3: guard-pipeline exception does NOT block approve
# ---------------------------------------------------------------------------


class TestGuardFailOpen(_SessionTempTestCase):

    def test_guard_exception_does_not_raise(self):
        """AC-3: even if guard_pipeline raises, approve still succeeds."""
        state = _make_build_ready_state()

        def _boom(*_a, **_kw):
            raise RuntimeError("synthetic guard crash")

        # Patch the underlying run_pipeline so _run_build_phase_guard's
        # try/except is exercised (not _run_build_phase_guard itself).
        import guard_pipeline as gp  # noqa: WPS433 (local import by design)
        with patch.object(gp, "run_pipeline", side_effect=_boom):
            try:
                result_state, next_phase = approve_phase(state, "build")
            except Exception as exc:
                self.fail(f"approve_phase must not raise on guard failure: {exc}")

        # Sanity: approve still advanced to the next phase.
        self.assertEqual(next_phase, "review")
        # No warnings surface (guard errored silently).
        self.assertEqual(result_state.extras.get("last_approve_warnings", []), [])

    def test_guard_import_error_does_not_raise(self):
        """Missing guard_pipeline module is a no-op (fail-open)."""
        state = _make_build_ready_state()

        # Poison the import so the lazy import path in _run_build_phase_guard
        # hits ImportError.
        with patch.dict(sys.modules, {"guard_pipeline": None}):
            try:
                result_state, _ = approve_phase(state, "build")
            except Exception as exc:
                self.fail(f"approve_phase must not raise on guard ImportError: {exc}")

        self.assertEqual(result_state.extras.get("last_approve_warnings", []), [])


# ---------------------------------------------------------------------------
# CREW_GATE_ENFORCEMENT=legacy rollback — the build-phase guard is a no-op
# ---------------------------------------------------------------------------


class TestLegacyBypass(_SessionTempTestCase):

    def test_legacy_enforcement_skips_guard(self):
        """When CREW_GATE_ENFORCEMENT=legacy, the build-phase guard returns
        an empty list without attempting to import guard_pipeline."""
        state = _make_build_ready_state()

        # If the guard ran, this patched run_pipeline would be called; we
        # assert it's NOT called, proving the early-return in legacy mode.
        import guard_pipeline as gp  # noqa: WPS433
        called = {"count": 0}

        def _counting(*_a, **_kw):
            called["count"] += 1
            return gp.PipelineReport(
                pipeline_version="1.0", profile="standard",
                budget_seconds=5.0, duration_ms=1, status="ok",
            )

        with patch.dict(os.environ, {"CREW_GATE_ENFORCEMENT": "legacy"}):
            with patch.object(gp, "run_pipeline", side_effect=_counting):
                approve_phase(state, "build")

        self.assertEqual(called["count"], 0,
                         "guard pipeline must not run under CREW_GATE_ENFORCEMENT=legacy")


if __name__ == "__main__":
    unittest.main()
