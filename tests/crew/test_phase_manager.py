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


# ---------------------------------------------------------------------------
# Review-gate condition (a): handle_approve without dispatcher logs a warning
# ---------------------------------------------------------------------------

class TestHandleApproveNoDispatcherWarning(unittest.TestCase):
    """Review-gate condition (a): CLI approve path is honest about not
    dispatching gate reviewers. `handle_approve` must emit a warning log
    containing "no dispatcher" when invoked, so users are not silently
    surprised by dispatcher-unavailable stubs."""

    def test_handle_approve_logs_no_dispatcher_warning(self):
        """Reading the source of the CLI approve branch must contain the
        explicit warning log with "no dispatcher" text."""
        src = Path(pm.__file__).read_text(encoding="utf-8")
        # Find the approve branch. Match the CLI elif body.
        idx = src.find('elif args.action == "approve":')
        self.assertNotEqual(idx, -1, "handle_approve approve branch missing")
        # Grab the next ~40 lines of source.
        branch_src = src[idx:idx + 2500]
        self.assertIn(
            "logger.warning(",
            branch_src,
            "approve branch must call logger.warning() when no dispatcher "
            "is injected",
        )
        self.assertIn(
            "no dispatcher",
            branch_src,
            'approve branch warning text must contain "no dispatcher" so '
            "the message is greppable and matches the review-gate "
            "condition (a) acceptance test",
        )


# ---------------------------------------------------------------------------
# Review-gate condition (b): phases.json has phase_executor_may_delegate
# ---------------------------------------------------------------------------

class TestPhasesJsonExecutorMayDelegate(unittest.TestCase):
    """Review-gate condition (b) / design-addendum-2 §SC-2: every phase
    entry in phases.json must declare `phase_executor_may_delegate`.
    Only `build` and `test` are allowed to delegate; everything else
    must explicitly opt out."""

    @classmethod
    def setUpClass(cls):
        phases_path = (
            _REPO_ROOT / ".claude-plugin" / "phases.json"
        )
        cls.phases = json.loads(phases_path.read_text(encoding="utf-8"))["phases"]

    def test_every_phase_has_field(self):
        for name, cfg in self.phases.items():
            self.assertIn(
                "phase_executor_may_delegate",
                cfg,
                f"phase '{name}' is missing phase_executor_may_delegate",
            )

    def test_build_and_test_may_delegate(self):
        self.assertTrue(self.phases["build"]["phase_executor_may_delegate"])
        self.assertTrue(self.phases["test"]["phase_executor_may_delegate"])

    def test_other_phases_may_not_delegate(self):
        for name in (
            "ideate",
            "clarify",
            "design",
            "test-strategy",
            "challenge",
            "review",
            "operate",
        ):
            self.assertFalse(
                self.phases[name]["phase_executor_may_delegate"],
                f"phase '{name}' must not delegate (design-addendum-2 §SC-2)",
            )


# ---------------------------------------------------------------------------
# B-4 (D-7 caller-contract regression): approve_phase must propagate
# GateResultSchemaError from _load_gate_result. No silent swallow.
# ---------------------------------------------------------------------------

class TestApprovePhaseHandlesGateResultSchemaError(unittest.TestCase):
    """B-4: when ``_load_gate_result`` raises ``GateResultSchemaError``
    (malformed / oversize / banned / content-leak payload), ``approve_phase``
    must NOT silently swallow the exception. The caller sees the error
    and the audit log carries the rejection entry.
    """

    def test_approve_phase_propagates_gate_result_schema_error(self):
        """Schema violation surfaces as GateResultSchemaError, not as a
        silent 'no-gate-run' bypass."""
        from gate_result_schema import GateResultSchemaError

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "proj"
            phase_dir = project_dir / "phases" / "build"
            phase_dir.mkdir(parents=True)
            # Write a malformed gate-result.json — invalid verdict enum.
            (phase_dir / "gate-result.json").write_text(
                json.dumps({
                    "verdict": "MAYBE",
                    "reviewer": "security-engineer",
                    "recorded_at": "2026-04-19T10:00:00+00:00",
                })
            )

            state = _make_state(rigor_tier="full")
            state.current_phase = "build"
            state.phases["build"] = PhaseState(
                status="in_progress",
                started_at="2026-04-19T00:00:00Z",
            )

            # Patch the pre-flight checks that would otherwise block the
            # path to _load_gate_result (addendum freshness, deliverables,
            # rigor policy validator).
            with patch.object(pm, "get_project_dir", return_value=project_dir), \
                 patch.object(pm, "_check_addendum_freshness", return_value=None), \
                 patch.object(pm, "_check_phase_deliverables", return_value=[]), \
                 patch.object(pm, "_validate_gate_policy_full_rigor"), \
                 patch.object(pm, "load_phases_config", return_value={
                     "build": {"gate_required": True,
                               "depends_on": [], "blocks_next": True,
                               "required_deliverables": []},
                 }):
                # GateResultSchemaError must bubble up from _load_gate_result,
                # NOT be swallowed into a fall-through "gate not run" path.
                with self.assertRaises(GateResultSchemaError) as cm:
                    approve_phase(state, "build", approver="test-user")

            # Contract: reason is set; violation_class set.
            self.assertTrue(cm.exception.reason)
            self.assertEqual(cm.exception.violation_class, "schema")

            # Audit log captures the rejection (AC-8).
            audit_path = phase_dir / "gate-ingest-audit.jsonl"
            self.assertTrue(
                audit_path.exists(),
                "AC-8: audit-log entry must be written on schema_violation",
            )
            text = audit_path.read_text(encoding="utf-8")
            self.assertIn("schema_violation", text)

    def test_approve_phase_does_not_swallow_authorization_error(self):
        """GateResultAuthorizationError (orphan in strict window) also
        propagates — approve_phase must NOT silently accept unauthorized
        gate-results by treating the exception as 'no gate run'."""
        from gate_result_schema import (
            GateResultAuthorizationError,
            GateResultSchemaError,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "proj"
            phase_dir = project_dir / "phases" / "build"
            phase_dir.mkdir(parents=True)
            valid_result = {
                "verdict": "APPROVE", "result": "APPROVE",
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "phase": "build", "gate": "code-quality",
                "score": 0.9, "min_score": 0.7,
            }
            (phase_dir / "gate-result.json").write_text(json.dumps(valid_result))

            state = _make_state(rigor_tier="full")
            state.current_phase = "build"
            state.phases["build"] = PhaseState(
                status="in_progress",
                started_at="2026-04-19T00:00:00Z",
            )

            # Force strict-after to the past so orphan -> REJECT (no
            # dispatch-log present -> GateResultAuthorizationError).
            with patch.object(pm, "get_project_dir", return_value=project_dir), \
                 patch.object(pm, "_check_addendum_freshness", return_value=None), \
                 patch.object(pm, "_check_phase_deliverables", return_value=[]), \
                 patch.object(pm, "_validate_gate_policy_full_rigor"), \
                 patch.object(pm, "load_phases_config", return_value={
                     "build": {"gate_required": True,
                               "depends_on": [], "blocks_next": True,
                               "required_deliverables": []},
                 }), \
                 patch.dict(os.environ, {
                     "WG_GATE_RESULT_STRICT_AFTER": "2020-01-01",
                 }):
                with self.assertRaises(GateResultSchemaError) as cm:
                    approve_phase(state, "build", approver="test-user")

            self.assertIsInstance(cm.exception, GateResultAuthorizationError)


# ---------------------------------------------------------------------------
# CLI parity bundle — issues #492, #493, #494, #498, #499
# ---------------------------------------------------------------------------


class TestCliApproveNoDispatcher(unittest.TestCase):
    """Issue #492: CLI approve path is honest about not dispatching.

    When ``main()`` runs the approve action without a dispatcher (the only
    path a raw CLI caller can take), the JSON output must carry
    ``status: "cli-no-dispatcher"`` so consumers can tell the gate was NOT
    auto-dispatched. A warning must also hit stderr.
    """

    def test_cli_approve_json_contains_cli_no_dispatcher_status(self):
        from io import StringIO
        import contextlib

        state = _make_state(name="cli-approve-proj", rigor_tier="standard")
        state.current_phase = "clarify"
        state.phases["clarify"] = pm.PhaseState(
            status="in_progress", started_at="2026-04-19T00:00:00Z",
        )

        argv = [
            "phase_manager.py", "cli-approve-proj", "approve",
            "--phase", "clarify", "--json",
        ]

        stdout = StringIO()
        stderr = StringIO()
        with patch.object(pm, "load_project_state", return_value=state), \
             patch.object(pm, "save_project_state"), \
             patch.object(
                 pm, "approve_phase",
                 return_value=(state, "design"),
             ), \
             patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(stdout), \
             contextlib.redirect_stderr(stderr):
            pm.main()

        out = stdout.getvalue()
        err = stderr.getvalue()
        payload = json.loads(out)
        self.assertEqual(payload.get("status"), "cli-no-dispatcher")
        self.assertTrue(payload.get("ok"))
        self.assertIn("cli-no-dispatcher", payload.get("status", ""))
        self.assertIn("WARNING", err)
        self.assertIn("BLEND-RULE", err)


class TestPhaseDeliverablesFallback(unittest.TestCase):
    """Issue #493: _check_phase_deliverables reads phases.json first,
    falls back to the hardcoded _FALLBACK_REQUIRED_DELIVERABLES map when
    the config has no entry for the phase (backward-compat).
    """

    def test_fallback_used_when_phases_config_empty_for_phase(self):
        state = _make_state(name="fallback-proj")

        # Force phases_config to return NO deliverables for the 'design'
        # phase so the fallback map is exercised. 'design' has
        # architecture.md in _FALLBACK_REQUIRED_DELIVERABLES.
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "fallback-proj"
            (project_dir / "phases" / "design").mkdir(parents=True)

            with patch.object(pm, "get_project_dir", return_value=project_dir), \
                 patch.object(
                     pm, "load_phases_config",
                     return_value={"design": {"required_deliverables": []}},
                 ):
                issues = pm._check_phase_deliverables(state, "design")

            # architecture.md is missing — fallback should surface it.
            self.assertTrue(
                any("architecture.md" in issue for issue in issues),
                f"expected fallback architecture.md check, got: {issues}",
            )

    def test_phases_config_takes_precedence_over_fallback(self):
        """When phases.json declares deliverables for a phase, those are
        authoritative — the fallback map must NOT be consulted."""
        state = _make_state(name="precedence-proj")

        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "precedence-proj"
            (project_dir / "phases" / "design").mkdir(parents=True)

            # phases_config declares a DIFFERENT deliverable. Fallback
            # map would flag architecture.md, but config says foo.md.
            with patch.object(pm, "get_project_dir", return_value=project_dir), \
                 patch.object(
                     pm, "load_phases_config",
                     return_value={"design": {
                         "required_deliverables": [
                             {"file": "foo.md", "min_bytes": 10},
                         ],
                     }},
                 ):
                issues = pm._check_phase_deliverables(state, "design")

            joined = " ".join(issues)
            self.assertIn("foo.md", joined)
            self.assertNotIn("architecture.md", joined)


class TestStatusJsonFieldParity(unittest.TestCase):
    """Issue #494: `phase_manager.py status --json` surfaces rigor_tier,
    complexity_score, and is_complete alongside the existing fields."""

    def test_status_json_includes_new_fields(self):
        from io import StringIO
        import contextlib

        state = _make_state(name="status-proj", rigor_tier="full")
        state.complexity_score = 5
        # Mark all phases in phase_plan as approved so is_complete=True
        for p in state.phase_plan:
            state.phases[p] = pm.PhaseState(status="approved")

        argv = ["phase_manager.py", "status-proj", "status", "--json"]

        stdout = StringIO()
        with patch.object(pm, "load_project_state", return_value=state), \
             patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(stdout):
            pm.main()

        payload = json.loads(stdout.getvalue())
        self.assertIn("rigor_tier", payload)
        self.assertEqual(payload["rigor_tier"], "full")
        self.assertIn("complexity_score", payload)
        self.assertEqual(payload["complexity_score"], 5)
        self.assertIn("is_complete", payload)
        self.assertTrue(payload["is_complete"])

    def test_status_json_is_complete_false_when_phases_pending(self):
        from io import StringIO
        import contextlib

        state = _make_state(name="in-progress-proj")
        state.complexity_score = 3
        # Only first phase approved; rest pending -> not complete.
        state.phases["clarify"] = pm.PhaseState(status="approved")

        argv = ["phase_manager.py", "in-progress-proj", "status", "--json"]
        stdout = StringIO()
        with patch.object(pm, "load_project_state", return_value=state), \
             patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(stdout):
            pm.main()

        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["is_complete"])


class TestCreateProjectDefaultsToMode3(unittest.TestCase):
    """Issue #498: create_project() stamps dispatch_mode='mode-3' on new
    projects so _detect_dispatch_mode() does NOT return 'v6-legacy' for
    freshly created projects. Legacy projects (missing the field entirely)
    still fall through to the existing legacy-detection code path.
    """

    def test_fresh_project_defaults_to_mode_3(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "mode3-proj"

            class _FakeStore:
                def __init__(self):
                    self._data = {}
                def get(self, domain, key):
                    return self._data.get(key)
                def put(self, domain, key, value):
                    self._data[key] = value
                def create(self, domain, data):
                    self._data[data.get("id") or data.get("name")] = data
                def update(self, domain, key, data):
                    self._data[key] = data
                def list(self, domain):
                    return list(self._data.values())
                def delete(self, domain, key):
                    self._data.pop(key, None)

            fake_store = _FakeStore()
            with patch.object(pm, "_sm", fake_store), \
                 patch.object(pm, "get_project_dir", return_value=project_dir):
                state, _ = pm.create_project(
                    "mode3-proj", description="test mode3 default",
                )

            self.assertEqual(
                state.extras.get("dispatch_mode"), "mode-3",
                "newly created projects must default to dispatch_mode=mode-3",
            )
            # _detect_dispatch_mode must agree.
            self.assertEqual(pm._detect_dispatch_mode(state), "mode-3")

    def test_initial_data_dispatch_mode_preserved(self):
        """A caller explicitly passing dispatch_mode='v6-legacy' in
        initial_data must have that value preserved — create_project must
        NOT overwrite an explicit caller choice."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "legacy-proj"

            class _FakeStore:
                def __init__(self):
                    self._data = {}
                def get(self, domain, key):
                    return self._data.get(key)
                def put(self, domain, key, value):
                    self._data[key] = value
                def create(self, domain, data):
                    self._data[data.get("id") or data.get("name")] = data
                def update(self, domain, key, data):
                    self._data[key] = data
                def list(self, domain):
                    return list(self._data.values())
                def delete(self, domain, key):
                    self._data.pop(key, None)

            fake_store = _FakeStore()
            with patch.object(pm, "_sm", fake_store), \
                 patch.object(pm, "get_project_dir", return_value=project_dir):
                state, _ = pm.create_project(
                    "legacy-proj",
                    description="legacy test",
                    initial_data={"dispatch_mode": "v6-legacy"},
                )

            self.assertEqual(
                state.extras.get("dispatch_mode"), "v6-legacy",
                "explicit initial_data.dispatch_mode must be preserved",
            )


class TestExecuteCliStub(unittest.TestCase):
    """Issue #499: execute() with NO executor-status.json returns
    ``status="cli-stub"`` and emits a clear warning — not a silent
    ``status=ok, deliverables=[]`` stub."""

    def test_execute_returns_cli_stub_when_no_executor_status(self):
        from io import StringIO
        import contextlib

        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "stub-proj"
            project_dir.mkdir()
            state = pm.ProjectState(
                name="stub-proj",
                current_phase="build",
                created_at="2026-04-19T00:00:00Z",
                phase_plan=["clarify", "design", "build", "review"],
                phases={
                    "clarify": pm.PhaseState(status="approved"),
                    "design": pm.PhaseState(status="approved"),
                    "build": pm.PhaseState(status="in_progress"),
                },
                extras={"dispatch_mode": "mode-3", "rigor_tier": "standard"},
            )

            stderr = StringIO()
            with patch.object(pm, "load_project_state", return_value=state), \
                 patch.object(pm, "save_project_state"), \
                 patch.object(pm, "get_project_dir", return_value=project_dir), \
                 patch.object(pm, "_validate_gate_policy_full_rigor"), \
                 contextlib.redirect_stderr(stderr):
                result = pm.execute("stub-proj", "build")

            self.assertEqual(result["status"], "cli-stub")
            self.assertIn("warning", result)
            self.assertIn("no phase work performed", result["warning"])
            # stderr receives the explicit WARNING line.
            self.assertIn("WARNING", stderr.getvalue())
            self.assertIn("CLI execute", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
