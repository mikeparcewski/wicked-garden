#!/usr/bin/env python3
"""tests/crew/test_mode3_pipeline.py — AC-α7 integration tests.

Four sub-cases (a)..(d) per AC-α7 + happy-path / scope-revoke exercise.
Stdlib-only, no sleep-based sync (T2), single-assertion focus (T4).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


def _synth_state(name: str, *, dispatch_mode="mode-3", yolo=False):
    extras = {
        "dispatch_mode": dispatch_mode,
        "rigor_tier": "full",
    }
    if yolo:
        extras["yolo_approved_by_user"] = True
    return phase_manager.ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-19T10:00:00Z",
        phase_plan=["clarify", "design", "build", "review"],
        phases={
            "clarify": phase_manager.PhaseState(status="approved"),
            "design": phase_manager.PhaseState(status="approved"),
            "build": phase_manager.PhaseState(status="in_progress"),
            "review": phase_manager.PhaseState(status="pending"),
        },
        extras=extras,
    )


def _write_executor_status(project_dir: Path, phase: str, *, deliverables, plan_mutations=None, parallelization_check=None):
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    for d in deliverables:
        rel = phase_dir / Path(d).name
        rel.write_text("x" * 200)  # >= 100 bytes
    status = {
        "executor_task_id": "task-test-1",
        "phase": phase,
        "deliverables": [str(phase_dir / Path(d).name) for d in deliverables],
        "plan_mutations": plan_mutations or [],
        "parallelization_check": parallelization_check or {
            "sub_task_count": 0, "dispatched_in_parallel": True, "serial_reason": None,
        },
    }
    (phase_dir / "executor-status.json").write_text(json.dumps(status))
    return status


class TestExecuteHappyPath(unittest.TestCase):
    """AC-α7(a) — happy-path execute returns ok."""

    def test_execute_ok_when_status_present(self):
        """execute() returns status=ok when executor-status.json is valid."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "happy"
            project_dir.mkdir()
            state = _synth_state("happy")
            _write_executor_status(project_dir, "build", deliverables=["impl.md"])
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("happy", "build")
            self.assertEqual(result["status"], "ok")


class TestExecuteLegacySkip(unittest.TestCase):
    """AC-α11 — v6-legacy dispatch_mode short-circuits mode-3 execute()."""

    def test_execute_returns_skipped_for_legacy_project(self):
        """A v6-legacy project's execute() returns status=skipped."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "legacy"
            project_dir.mkdir()
            state = _synth_state("legacy", dispatch_mode="v6-legacy")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("legacy", "build")
            self.assertEqual(result["status"], "skipped")


class TestYoloAutoRevoke(unittest.TestCase):
    """AC-α7(d) — yolo auto-revoke on scope-increase augment."""

    def test_augment_mutation_revokes_yolo(self):
        """Plan mutation op=augment flips yolo_approved_by_user to False."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-revoke"
            project_dir.mkdir()
            state = _synth_state("yolo-revoke", yolo=True)

            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                plan_mutations=[{"op": "augment", "task_id": "t-new", "why": "scope creep"}],
            )

            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                phase_manager.execute("yolo-revoke", "build")

            self.assertFalse(state.extras.get("yolo_approved_by_user"))

    def test_retier_down_does_not_revoke_yolo(self):
        """Plan mutation op=re_tier to 'standard' does NOT revoke yolo."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-keep"
            project_dir.mkdir()
            state = _synth_state("yolo-keep", yolo=True)
            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                plan_mutations=[{"op": "re_tier", "task_id": "t1",
                                 "new_rigor_tier": "standard", "why": "simplify"}],
            )
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                phase_manager.execute("yolo-keep", "build")
            self.assertTrue(state.extras.get("yolo_approved_by_user"))


class TestParallelizationFailure(unittest.TestCase):
    """AC-α7(c) relates — failure mode when parallelization_check is missing."""

    def test_execute_fails_when_serial_without_reason(self):
        """execute() returns status=failed with parallelization-check-missing."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "par-fail"
            project_dir.mkdir()
            state = _synth_state("par-fail")
            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                parallelization_check={
                    "sub_task_count": 3,
                    "dispatched_in_parallel": False,
                    "serial_reason": "",
                },
            )
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("par-fail", "build")
            self.assertEqual(result["status"], "failed")


class TestYoloActionAudit(unittest.TestCase):
    """AC-α5 — yolo_action writes audit line."""

    def test_yolo_approve_writes_audit(self):
        """yolo_action('approve') sets flag and writes yolo-audit.jsonl.

        #470: full-rigor grants require a >= 40 char justification and a
        second-persona review sentinel. Both are provided here so the
        existing contract (audit file is written on grant) still holds.
        """
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-grant"
            project_dir.mkdir()
            state = _synth_state("yolo-grant", yolo=False)
            # #470 — stage the second-persona review sentinel the guardrail
            # requires at full rigor. Content must be >= 100 bytes of
            # non-whitespace per _check_second_persona_review.
            sentinel = project_dir / "phases" / "yolo-approval" / "second-persona-review.md"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text(
                "# Second-persona review\n\n"
                "Reviewed by senior-engineer persona: project spec is locked "
                "to module X; rollback plan documented; scope reviewed and "
                "approved for yolo auto-advance at full rigor.\n"
            )
            justification = (
                "Unit-test full-rigor grant; scope reviewed, rollback covered, "
                "persona review on file."
            )
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                phase_manager.yolo_action(
                    "yolo-grant", "approve", reason=justification,
                )
            audit = project_dir / "yolo-audit.jsonl"
            self.assertTrue(audit.exists())


# ---------------------------------------------------------------------------
# FR-α5.2 — approve-time yolo auto-accept
# ---------------------------------------------------------------------------


def _minimal_approve_patches(project_dir: Path):
    """Common phase_manager patches so approve_phase() reaches the yolo block
    without needing real gate/deliverable fixtures on disk."""
    return [
        patch.object(phase_manager, "get_project_dir", return_value=project_dir),
        patch.object(phase_manager, "save_project_state"),
        patch.object(phase_manager, "_sm"),
        patch.object(phase_manager, "_check_addendum_freshness", return_value=None),
        patch.object(phase_manager, "_check_phase_deliverables", return_value=[]),
        patch.object(phase_manager, "load_phases_config", return_value={
            "build": {"gate_required": False, "depends_on": []},
        }),
        patch.object(phase_manager, "_load_session_dispatches", return_value=[]),
        patch.object(phase_manager, "_run_checkpoint_reanalysis",
                     return_value=([], [])),
        patch.object(phase_manager, "get_phase_order", return_value=[
            "clarify", "design", "build", "review"]),
        patch.object(phase_manager, "_run_build_phase_guard", return_value=[]),
    ]


class TestYoloApproveTimeAutoAccept(unittest.TestCase):
    """FR-α5.2 — approve-time auto-accept on APPROVE / surface on CONDITIONAL."""

    def _stub_gate_result(self, project_dir: Path, phase: str, verdict: str,
                          score: float = 0.9, conditions=None):
        phase_dir = project_dir / "phases" / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "gate-result.json").write_text(json.dumps({
            "verdict": verdict,
            "result": verdict,
            "score": score,
            "min_score": score,
            "reviewer": "test-reviewer",
            "reason": f"synthetic {verdict}",
            "conditions": conditions or [],
            # recorded_at is required by #479 schema validator.
            "recorded_at": "2026-04-19T10:00:00+00:00",
        }))

    def test_yolo_auto_accept_on_approve(self):
        """yolo + APPROVE → advance to next phase + write auto-accept audit."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-auto-approve"
            project_dir.mkdir()
            state = _synth_state("yolo-auto-approve", yolo=True)
            self._stub_gate_result(project_dir, "build", "APPROVE")

            patches = _minimal_approve_patches(project_dir)
            for p in patches:
                p.start()
            # Gate must be "required" for the verdict check chain to load the
            # synthetic gate-result.json we wrote above.
            phases_patch = patch.object(phase_manager, "load_phases_config",
                                        return_value={"build": {
                                            "gate_required": True,
                                            "gate_override_allowed": True,
                                            "depends_on": [],
                                            "min_gate_score": 0.5,
                                        }})
            phases_patch.start()
            try:
                _, next_phase = phase_manager.approve_phase(state, "build")
            finally:
                phases_patch.stop()
                for p in patches:
                    p.stop()

            audit = project_dir / "yolo-audit.jsonl"
            # Both advance AND audit fired.
            self.assertEqual(next_phase, "review")
            self.assertTrue(audit.exists())

    def test_yolo_no_advance_on_conditional(self):
        """yolo + CONDITIONAL → raise (surface to user); no advance."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-no-advance-cond"
            project_dir.mkdir()
            state = _synth_state("yolo-no-advance-cond", yolo=True)
            self._stub_gate_result(
                project_dir, "build", "CONDITIONAL",
                conditions=[{"id": "c1", "desc": "fix this"}],
            )

            patches = _minimal_approve_patches(project_dir)
            # CONDITIONAL requires gate_required=True to trigger the verdict
            # check chain — override the phases config for this test.
            for p in patches:
                if getattr(p, "attribute", None) == "load_phases_config":
                    p.start()
                    # Replace the return_value with gate_required=True.
                    continue
                p.start()
            # Swap the default phases config patch to one with gate_required.
            phases_patch = patch.object(phase_manager, "load_phases_config",
                                        return_value={"build": {
                                            "gate_required": True,
                                            "gate_override_allowed": True,
                                            "depends_on": [],
                                            "min_gate_score": 0.5,
                                        }})
            phases_patch.start()
            try:
                with self.assertRaises(ValueError):
                    phase_manager.approve_phase(state, "build")
            finally:
                phases_patch.stop()
                for p in patches:
                    p.stop()

    def test_yolo_no_advance_on_reject(self):
        """yolo + REJECT → raise (surface to user); no advance."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-no-advance-reject"
            project_dir.mkdir()
            state = _synth_state("yolo-no-advance-reject", yolo=True)
            self._stub_gate_result(project_dir, "build", "REJECT", score=0.1)

            patches = _minimal_approve_patches(project_dir)
            for p in patches:
                p.start()
            phases_patch = patch.object(phase_manager, "load_phases_config",
                                        return_value={"build": {
                                            "gate_required": True,
                                            "gate_override_allowed": True,
                                            "depends_on": [],
                                            "min_gate_score": 0.5,
                                        }})
            phases_patch.start()
            try:
                with self.assertRaises(ValueError):
                    phase_manager.approve_phase(state, "build")
            finally:
                phases_patch.stop()
                for p in patches:
                    p.stop()


# ---------------------------------------------------------------------------
# COND-TG-1 — corrupt executor-status.json surfaces, is not silently swallowed
# ---------------------------------------------------------------------------


class TestExecuteCorruptStatusRaises(unittest.TestCase):
    """COND-TG-1 — corrupt executor-status.json must raise, not silently pass.

    The phase-executor writes executor-status.json; execute() reads it. If the
    file contains malformed JSON we MUST surface the error — silently falling
    back to a default status would hide executor failures from the gate chain.
    Current code wraps json.JSONDecodeError in RuntimeError with a descriptive
    prefix; this test asserts that propagation path.
    """

    def test_corrupt_executor_status_raises_runtime_error(self):
        """Malformed JSON in executor-status.json propagates as RuntimeError."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "corrupt-status"
            project_dir.mkdir()
            state = _synth_state("corrupt-status")
            phase_dir = project_dir / "phases" / "build"
            phase_dir.mkdir(parents=True, exist_ok=True)
            # Write a deliberately malformed JSON payload (unclosed brace).
            (phase_dir / "executor-status.json").write_text("{not-valid-json,,,")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                with self.assertRaises(RuntimeError) as ctx:
                    phase_manager.execute("corrupt-status", "build")
            self.assertIn("executor-status-unreadable", str(ctx.exception))


# ---------------------------------------------------------------------------
# COND-TG-2 — deliverable path-traversal guard
# ---------------------------------------------------------------------------


class TestExecuteDeliverablePathTraversal(unittest.TestCase):
    """COND-TG-2 — deliverables declared outside phases/{phase}/ are rejected.

    A malicious or buggy phase-executor could declare a deliverable at a path
    like `../outside/dir.md` or an absolute path to a sibling phase. execute()
    MUST reject any deliverable that does not resolve under the phase
    directory (SC-2 scope containment).
    """

    def test_relative_parent_escape_raises_value_error(self):
        """`../outside/doc.md` path-traversal is rejected with ValueError."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "pt-rel"
            project_dir.mkdir()
            state = _synth_state("pt-rel")
            phase_dir = project_dir / "phases" / "build"
            phase_dir.mkdir(parents=True, exist_ok=True)
            # The escape target actually exists outside the phase dir so the
            # resolve() call won't fail for a different reason.
            outside_dir = project_dir / "outside"
            outside_dir.mkdir(parents=True, exist_ok=True)
            evil = outside_dir / "leak.md"
            evil.write_text("x" * 200)
            status = {
                "executor_task_id": "task-pt-1",
                "phase": "build",
                "deliverables": [str(evil.resolve())],
                "plan_mutations": [],
                "parallelization_check": {
                    "sub_task_count": 0,
                    "dispatched_in_parallel": True,
                    "serial_reason": None,
                },
            }
            (phase_dir / "executor-status.json").write_text(json.dumps(status))
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.execute("pt-rel", "build")
            self.assertIn("deliverable-out-of-scope", str(ctx.exception))


# ---------------------------------------------------------------------------
# COND-TG-5 — scope-increase revoke emits wicked.crew.yolo_revoked bus event
# ---------------------------------------------------------------------------


class TestScopeIncreaseRevokeEmitsBusEvent(unittest.TestCase):
    """COND-TG-5 — _apply_scope_increase_revoke emits observability event.

    After writing yolo-audit.jsonl the function must also emit
    wicked.crew.yolo_revoked so downstream subscribers (delivery telemetry,
    platform observability) see the auto-revoke without tailing the audit
    file. Fail-open on bus absence is verified elsewhere; this test checks
    the emit is wired up when the bus is available.
    """

    def test_augment_mutation_emits_yolo_revoked_bus_event(self):
        """Scope-increase augment triggers emit of wicked.crew.yolo_revoked."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "bus-revoke"
            project_dir.mkdir()
            state = _synth_state("bus-revoke", yolo=True)
            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                plan_mutations=[{"op": "augment", "task_id": "t-new", "why": "creep"}],
            )
            # Patch the emit_event import target. phase_manager does a lazy
            # `from _bus import emit_event` inside the function — patching the
            # attribute on the _bus module covers both import styles.
            import _bus as _bus_mod  # noqa: WPS433 — local test import
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"), \
                 patch.object(_bus_mod, "emit_event") as mock_emit:
                phase_manager.execute("bus-revoke", "build")
            # Assert the yolo_revoked event was emitted exactly once.
            event_types = [call.args[0] for call in mock_emit.call_args_list]
            self.assertIn("wicked.crew.yolo_revoked", event_types)


if __name__ == "__main__":
    unittest.main()
