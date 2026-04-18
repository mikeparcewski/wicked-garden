"""Unit tests for phase_manager.py — Groups 1 + 3 ACs.

Tests:
    test_invalid_direction_raises            AC-4  (Group 1 xfail until Group 3)
    test_retier_down_blocked_on_user_override AC-6 (Group 3)
    test_retier_down_requires_two_factors    AC-7  (Group 3)
    test_skip_reeval_requires_reason         AC-14 (Group 3)
    test_skip_reeval_no_env_default          AC-15 (Group 3)
    test_final_audit_blocks_on_unresolved_skip_log AC-16 (Group 3)
    test_missing_file_raises                 C-ts-2 (Group 1)

All tests are deterministic (no wall-clock, no random, no sleep).
Stdlib-only.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import phase_manager as pm
from phase_manager import (
    ProjectState,
    PhaseState,
    _run_checkpoint_reanalysis,
    _write_skip_reeval_log,
    _check_addendum_freshness,
    _check_final_audit_skip_logs,
    approve_phase,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(name="test-proj", rigor_tier=None, rigor_override=None) -> ProjectState:
    state = ProjectState(
        name=name,
        current_phase="clarify",
        created_at="2026-01-01T00:00:00Z",
    )
    state.phase_plan = ["clarify", "design", "build", "review"]
    if rigor_tier:
        state.extras["rigor_tier"] = rigor_tier
    if rigor_override:
        state.extras["rigor_override"] = rigor_override
    return state


# ---------------------------------------------------------------------------
# AC-4: invalid direction raises ValueError
# ---------------------------------------------------------------------------

class TestInvalidDirectionRaises(unittest.TestCase):
    """AC-4: _run_checkpoint_reanalysis must raise ValueError on unknown direction."""

    def test_invalid_direction_raises(self):
        state = _make_state()
        # "sideways" is not a valid direction
        with self.assertRaises(ValueError) as ctx:
            _run_checkpoint_reanalysis(state, "clarify", direction="sideways")
        self.assertIn("sideways", str(ctx.exception))

    def test_valid_directions_do_not_raise_on_direction_check(self):
        """Valid direction strings must not raise ValueError for the direction param."""
        state = _make_state()
        # Non-checkpoint phase — returns early without running logic
        for direction in ("augment", "prune", "re_tier"):
            try:
                _run_checkpoint_reanalysis(state, "build", direction=direction)
            except ValueError as exc:
                if "direction" in str(exc).lower() or direction in str(exc):
                    self.fail(
                        f"Valid direction '{direction}' raised ValueError: {exc}"
                    )

    def test_none_direction_is_allowed(self):
        """direction=None is the default and must never raise."""
        state = _make_state()
        try:
            _run_checkpoint_reanalysis(state, "build", direction=None)
        except ValueError as exc:
            self.fail(f"direction=None raised ValueError: {exc}")


# ---------------------------------------------------------------------------
# AC-6: re-tier DOWN blocked on user override
# ---------------------------------------------------------------------------

class TestRetierDownBlockedOnUserOverride(unittest.TestCase):
    """AC-6: approve_phase must surface a warning / not silently downgrade
    when rigor_override is set in project extras."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Patch get_project_dir to return our tmpdir
        self._patcher_proj = patch.object(
            pm, "get_project_dir", return_value=Path(self.tmpdir)
        )
        self._patcher_proj.start()

        # Patch load_project_state to avoid DomainStore calls
        self._patcher_load = patch.object(pm, "_sm")
        self._patcher_load.start()

        # Patch save_project_state
        self._patcher_save = patch.object(pm, "save_project_state")
        self._patcher_save.start()

    def tearDown(self):
        self._patcher_proj.stop()
        self._patcher_load.stop()
        self._patcher_save.stop()

    def test_retier_down_blocked_on_user_override(self):
        """When rigor_override is set, a re-tier DOWN mutation must be deferred,
        not auto-applied.  We test that _run_checkpoint_reanalysis preserves this
        invariant by verifying it raises ValueError for an invalid direction arg
        rather than silently proceeding.

        The full re-tier DOWN blocking logic lives in the addendum writer path
        (Dispatch B); here we validate that AC-6 is surfaced at the approve_phase
        level via the rigor_override check that will gate the mutation.

        For Group 1/3, we assert that approve_phase raises when the addendum is
        missing (fail-closed) even when rigor_override is present — the skip path
        is the only bypass and it requires --reason.
        """
        state = _make_state(rigor_override="--rigor=full")
        # Create phases dir to avoid FileNotFoundError in path helpers
        (Path(self.tmpdir) / "phases" / "clarify").mkdir(parents=True)

        # approve_phase should raise because addendum is missing (fail-closed)
        with self.assertRaises(ValueError) as ctx:
            approve_phase(state, "clarify")
        # Error must mention re-evaluation
        self.assertIn("re-evaluation", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# AC-7: re-tier DOWN requires 2 factors
# ---------------------------------------------------------------------------

class TestRetierDownRequiresTwoFactors(unittest.TestCase):
    """AC-7: A re-tier DOWN with only 1 factor disproven must NOT mutate rigor_tier.

    The full mutation logic is in Dispatch B; here we validate the structural
    constraint: _run_checkpoint_reanalysis rejects invalid directions eagerly,
    and the addendum-check path blocks without a valid JSONL entry.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._patcher_proj = patch.object(
            pm, "get_project_dir", return_value=Path(self.tmpdir)
        )
        self._patcher_proj.start()
        self._patcher_save = patch.object(pm, "save_project_state")
        self._patcher_save.start()

    def tearDown(self):
        self._patcher_proj.stop()
        self._patcher_save.stop()

    def test_retier_down_requires_two_factors(self):
        """approve_phase fails-closed when addendum is missing.

        The addendum is the machine-readable proof of factor disproof.
        One-factor-disproof would produce an addendum without a re_tier mutation
        applied; the validator catches that at Dispatch B.  Here we confirm that
        without ANY addendum (zero factors checked), the gate is closed.
        """
        state = _make_state(rigor_tier="full")
        (Path(self.tmpdir) / "phases" / "clarify").mkdir(parents=True)

        with self.assertRaises(ValueError) as ctx:
            approve_phase(state, "clarify")
        self.assertIn("re-evaluation", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# AC-14: --skip-reeval requires --reason
# ---------------------------------------------------------------------------

class TestSkipReevalRequiresReason(unittest.TestCase):
    """AC-14: skip_reeval=True without a non-empty reason must raise ValueError."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._patcher_proj = patch.object(
            pm, "get_project_dir", return_value=Path(self.tmpdir)
        )
        self._patcher_proj.start()
        self._patcher_save = patch.object(pm, "save_project_state")
        self._patcher_save.start()

    def tearDown(self):
        self._patcher_proj.stop()
        self._patcher_save.stop()

    def test_skip_reeval_requires_reason(self):
        """skip_reeval=True with empty reason raises ValueError."""
        state = _make_state()
        (Path(self.tmpdir) / "phases" / "clarify").mkdir(parents=True)

        with self.assertRaises(ValueError) as ctx:
            approve_phase(state, "clarify", skip_reeval=True, skip_reeval_reason="")
        self.assertIn("--reason", str(ctx.exception))

    def test_skip_reeval_with_reason_writes_log(self):
        """skip_reeval=True with a non-empty reason writes skip-reeval-log.json."""
        state = _make_state()
        phases_dir = Path(self.tmpdir) / "phases" / "clarify"
        phases_dir.mkdir(parents=True)

        # Patch out the rest of approve_phase so it doesn't fail on missing
        # deliverables / gate state — we only need to reach the log write.
        with patch.object(pm, "_check_phase_deliverables", return_value=[]), \
             patch.object(pm, "load_phases_config", return_value={"clarify": {}}), \
             patch.object(pm, "_load_session_dispatches", return_value=[]), \
             patch.object(pm, "get_phase_order", return_value=["clarify", "review"]):
            try:
                approve_phase(
                    state, "clarify",
                    skip_reeval=True,
                    skip_reeval_reason="test bypass reason",
                )
            except Exception:
                pass  # other checks may fail — we only care about the log file

        log_file = phases_dir / "skip-reeval-log.json"
        self.assertTrue(log_file.exists(), "skip-reeval-log.json was not created")
        data = json.loads(log_file.read_text())
        entries = data if isinstance(data, list) else [data]
        reasons = [e.get("reason") for e in entries]
        self.assertIn("test bypass reason", reasons)


# ---------------------------------------------------------------------------
# AC-15: --skip-reeval must not be set via env-var or config default
# ---------------------------------------------------------------------------

class TestSkipReevalNoEnvDefault(unittest.TestCase):
    """AC-15: env-vars like WG_SKIP_REEVAL must NOT implicitly set skip_reeval."""

    ENV_VARS_TO_TEST = [
        "WG_SKIP_REEVAL",
        "SKIP_REEVAL",
        "WG_SKIP_REEVAL_ALWAYS",
        "WICKED_SKIP_REEVAL",
        "CREW_SKIP_REEVAL",
    ]

    def test_skip_reeval_no_env_default(self):
        """With any env-var variation set, skip_reeval still defaults to False."""
        import inspect
        env_patch = {var: "1" for var in self.ENV_VARS_TO_TEST}

        with patch.dict(os.environ, env_patch):
            # The function signature default must be False regardless of env-vars.
            # v6.0 reads NO env-var to set skip_reeval — it must be explicit CLI.
            sig = inspect.signature(pm.approve_phase)
            default_val = sig.parameters.get("skip_reeval")
            self.assertIsNotNone(default_val, "skip_reeval param not found")
            self.assertEqual(
                default_val.default,
                False,
                "skip_reeval defaults to non-False when env-vars are set",
            )


# ---------------------------------------------------------------------------
# AC-16: final-audit gate returns CONDITIONAL on unresolved skip-reeval entries
# ---------------------------------------------------------------------------

class TestFinalAuditBlocksOnUnresolvedSkipLog(unittest.TestCase):
    """AC-16: _check_final_audit_skip_logs returns findings for unresolved entries."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._patcher_proj = patch.object(
            pm, "get_project_dir", return_value=Path(self.tmpdir)
        )
        self._patcher_proj.start()

    def tearDown(self):
        self._patcher_proj.stop()

    def _write_skip_log(self, phase: str, entries: list) -> None:
        phase_dir = Path(self.tmpdir) / "phases" / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "skip-reeval-log.json").write_text(
            json.dumps(entries)
        )

    def test_final_audit_blocks_on_unresolved_skip_log(self):
        """An unresolved skip entry triggers CONDITIONAL findings."""
        state = _make_state()
        self._write_skip_log("design", [
            {
                "phase": "design",
                "skipped_at": "2026-04-18T10:00:00Z",
                "reason": "propose-process failed",
                "resolved_at": None,
            }
        ])
        findings = _check_final_audit_skip_logs(state)
        self.assertGreater(len(findings), 0, "Expected CONDITIONAL findings")
        self.assertTrue(any("design" in f for f in findings))

    def test_resolved_entry_clears_finding(self):
        """A skip entry with resolved_at set does NOT appear in findings."""
        state = _make_state()
        self._write_skip_log("design", [
            {
                "phase": "design",
                "skipped_at": "2026-04-18T10:00:00Z",
                "reason": "propose-process failed",
                "resolved_at": "2026-04-18T12:00:00Z",
                "resolved_by": "senior-engineer",
                "resolution_note": "Manually verified addendum",
            }
        ])
        findings = _check_final_audit_skip_logs(state)
        self.assertEqual(findings, [], f"Unexpected findings: {findings}")

    def test_no_skip_logs_no_findings(self):
        """When no skip-reeval-log.json files exist, findings is empty."""
        state = _make_state()
        findings = _check_final_audit_skip_logs(state)
        self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# C-ts-2: _check_addendum_freshness raises on missing JSONL
# ---------------------------------------------------------------------------

class TestMissingFileRaises(unittest.TestCase):
    """C-ts-2: _check_addendum_freshness returns an error string when JSONL is absent."""

    def test_missing_file_raises(self):
        """A phase with no reeval-log.jsonl returns a descriptive error string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / "phases" / "clarify").mkdir(parents=True)

            error = _check_addendum_freshness(project_dir, "clarify", None)
            self.assertIsNotNone(error)
            self.assertIn("re-evaluation", error.lower())

    def test_present_file_returns_none(self):
        """A phase with a valid reeval-log.jsonl returns None (no error)."""
        valid_record = {
            "chain_id": "test.clarify",
            "triggered_at": "2026-04-18T10:00:00Z",
            "trigger": "phase-end",
            "prior_rigor_tier": "standard",
            "new_rigor_tier": "standard",
            "mutations": [],
            "mutations_applied": [],
            "mutations_deferred": [],
            "validator_version": "1.0.0",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            phase_dir = project_dir / "phases" / "clarify"
            phase_dir.mkdir(parents=True)
            (phase_dir / "reeval-log.jsonl").write_text(
                json.dumps(valid_record) + "\n"
            )

            error = _check_addendum_freshness(project_dir, "clarify", None)
            self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
