"""v11 slim phase_manager tests.

The v6-v10 universal-pipeline phase_manager.py was replaced in v11 with a
slim project-state manager (~370 lines) that does CRUD + state transitions
only. No gate machinery, no addendum freshness, no deliverable schema, no
conditions-manifest enforcement, no banned-reviewer enforcement, no
dispatch-log HMAC. Those concerns moved into per-archetype playbooks.

These tests cover the slim API surface: project creation (legacy + v11
archetype-mode), load/save round-trip, phase state transitions, the
is_complete predicate, and the CLI shim.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# scripts/ + scripts/crew/ on sys.path (append, do not insert — match the
# repo conftest convention)
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import phase_manager as pm  # noqa: E402


class TestProjectStateRoundtrip(unittest.TestCase):
    """ProjectState load/save roundtrip via DomainStore."""

    def test_load_returns_none_for_missing_project(self):
        with patch.object(pm._sm, "get", return_value=None):
            state = pm.load_project_state("does-not-exist")
        self.assertIsNone(state)

    def test_load_normalizes_phases_dict(self):
        stored = {
            "name": "p", "current_phase": "build",
            "created_at": "2026-05-07T00:00:00Z",
            "phases": {
                "build": {"status": "in_progress",
                          "started_at": "2026-05-07T01:00:00Z"},
            },
            "phase_plan": ["plan", "implement", "test", "review"],
            "extras": {"v11_archetype": "build"},
        }
        with patch.object(pm._sm, "get", return_value=stored):
            state = pm.load_project_state("p")
        self.assertEqual(state.name, "p")
        self.assertEqual(state.current_phase, "build")
        self.assertEqual(state.phase_plan,
                         ["plan", "implement", "test", "review"])
        self.assertIsInstance(state.phases["build"], pm.PhaseState)
        self.assertEqual(state.phases["build"].status, "in_progress")
        self.assertEqual(state.extras["v11_archetype"], "build")


class TestSafeProjectName(unittest.TestCase):
    def test_alphanumeric_kebab_snake_ok(self):
        self.assertTrue(pm.is_safe_project_name("my-project"))
        self.assertTrue(pm.is_safe_project_name("my_project_2"))
        self.assertTrue(pm.is_safe_project_name("Foo123"))

    def test_path_traversal_rejected(self):
        for bad in ("..", "../foo", "foo/../bar", "foo bar", "x" * 65, ""):
            self.assertFalse(pm.is_safe_project_name(bad),
                             f"name should be rejected: {bad!r}")


class TestCreateProjectArchetypeMode(unittest.TestCase):
    """create_project --archetype-mode hydrates phase_plan from
    .claude-plugin/archetypes.json."""

    def test_archetype_mode_hydrates_phase_plan(self):
        with patch.object(pm, "save_project_state"):
            state, _ = pm.create_project(
                "v11-build-proj", description="x",
                archetype_mode="build",
            )
        self.assertEqual(state.phase_plan,
                         ["plan", "implement", "test", "review"])
        self.assertEqual(state.current_phase, "plan")
        self.assertEqual(state.extras["phase_plan_mode"], "archetype")
        self.assertEqual(state.extras["v11_archetype"], "build")
        self.assertIn("archetype_produces", state.extras)

    def test_archetype_mode_migrate_uses_expand_contract(self):
        with patch.object(pm, "save_project_state"):
            state, _ = pm.create_project(
                "v11-mig", archetype_mode="migrate",
            )
        self.assertEqual(state.phase_plan,
                         ["plan", "expand", "backfill", "cutover", "contract"])

    def test_unknown_archetype_raises(self):
        with patch.object(pm, "save_project_state"):
            with self.assertRaises(ValueError) as cm:
                pm.create_project("p", archetype_mode="not-real")  # type: ignore
        # NB: argparse choices catches this at the CLI; the function
        # still validates because callers can bypass argparse.
        # The catalog raises through the function path when an unknown
        # archetype name is passed.
        self.assertIn("Unknown archetype", str(cm.exception))

    def test_legacy_create_no_archetype_mode(self):
        with patch.object(pm, "save_project_state"):
            state, _ = pm.create_project("legacy-proj")
        self.assertEqual(state.phase_plan, [])
        self.assertEqual(state.current_phase, "")
        self.assertNotIn("v11_archetype", state.extras)


class TestStateTransitions(unittest.TestCase):
    def _state(self):
        s = pm.ProjectState(
            name="t", current_phase="plan",
            created_at="2026-05-07T00:00:00Z",
            phase_plan=["plan", "implement", "test", "review"],
        )
        return s

    def test_start_phase_marks_in_progress(self):
        with patch.object(pm, "save_project_state"):
            state = pm.start_phase(self._state(), "implement")
        self.assertEqual(state.current_phase, "implement")
        self.assertEqual(state.phases["implement"].status, "in_progress")
        self.assertIsNotNone(state.phases["implement"].started_at)

    def test_complete_phase_marks_completed(self):
        with patch.object(pm, "save_project_state"):
            state = pm.start_phase(self._state(), "implement")
            state = pm.complete_phase(state, "implement")
        self.assertEqual(state.phases["implement"].status, "completed")
        self.assertIsNotNone(state.phases["implement"].completed_at)

    def test_approve_phase_advances_current(self):
        with patch.object(pm, "save_project_state"):
            state, next_phase = pm.approve_phase(self._state(), "plan")
        self.assertEqual(next_phase, "implement")
        self.assertEqual(state.current_phase, "implement")
        self.assertEqual(state.phases["plan"].status, "approved")

    def test_approve_last_phase_returns_no_next(self):
        s = self._state()
        s.current_phase = "review"
        with patch.object(pm, "save_project_state"):
            state, next_phase = pm.approve_phase(s, "review")
        self.assertIsNone(next_phase)
        self.assertEqual(state.phases["review"].status, "approved")

    def test_skip_phase_records_reason(self):
        with patch.object(pm, "save_project_state"):
            state = pm.skip_phase(self._state(), "test", reason="docs-only")
        self.assertEqual(state.phases["test"].status, "skipped")
        skips = state.extras["skips"]
        self.assertEqual(len(skips), 1)
        self.assertEqual(skips[0]["reason"], "docs-only")


class TestIsComplete(unittest.TestCase):
    def test_empty_plan_is_not_complete(self):
        s = pm.ProjectState(name="e", current_phase="",
                            created_at="2026-05-07T00:00:00Z")
        self.assertFalse(pm.is_complete(s))

    def test_all_approved_or_skipped_is_complete(self):
        s = pm.ProjectState(
            name="c", current_phase="review",
            created_at="2026-05-07T00:00:00Z",
            phase_plan=["plan", "test", "review"],
            phases={
                "plan": pm.PhaseState(status="approved"),
                "test": pm.PhaseState(status="skipped"),
                "review": pm.PhaseState(status="approved"),
            },
        )
        self.assertTrue(pm.is_complete(s))

    def test_one_pending_blocks_complete(self):
        s = pm.ProjectState(
            name="c", current_phase="review",
            created_at="2026-05-07T00:00:00Z",
            phase_plan=["plan", "test", "review"],
            phases={
                "plan": pm.PhaseState(status="approved"),
                "test": pm.PhaseState(status="completed"),
                "review": pm.PhaseState(status="approved"),
            },
        )
        self.assertFalse(pm.is_complete(s))


class TestCLI(unittest.TestCase):
    """Smoke the CLI shim — create + status round trip."""

    def _run(self, *args, expect_returncode=0):
        path = _REPO_ROOT / "scripts" / "crew" / "phase_manager.py"
        result = subprocess.run(
            [sys.executable, str(path), *args],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, expect_returncode,
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        return result

    def test_cli_help_runs(self):
        result = subprocess.run(
            [sys.executable,
             str(_REPO_ROOT / "scripts" / "crew" / "phase_manager.py"),
             "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--archetype-mode", result.stdout)
        self.assertIn("--confirmed-by", result.stdout)


class TestHardGateEnforcement(unittest.TestCase):
    """v11 hard-gate enforcement at the runtime layer.

    The doctrine of `hard:cutover`, `hard:mitigate`, etc. used to live
    only in playbook prose. v11 mirrors it in code: approve_phase
    refuses to advance past a hard gate without explicit
    `--confirmed-by` AND `--confirmation-evidence`. The audit trail
    records both.
    """

    def _migrate_state_at_cutover(self):
        s = pm.ProjectState(
            name="mig-proj", current_phase="cutover",
            created_at="2026-05-08T00:00:00Z",
            phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
            extras={
                "phase_plan_mode": "archetype",
                "v11_archetype": "migrate",
            },
        )
        return s

    def _build_state_at_test(self):
        s = pm.ProjectState(
            name="build-proj", current_phase="test",
            created_at="2026-05-08T00:00:00Z",
            phase_plan=["plan", "implement", "test", "review"],
            extras={
                "phase_plan_mode": "archetype",
                "v11_archetype": "build",
            },
        )
        return s

    def test_is_hard_gate_for_migrate_cutover(self):
        s = self._migrate_state_at_cutover()
        self.assertTrue(pm._is_hard_gate(s, "cutover"))
        self.assertFalse(pm._is_hard_gate(s, "plan"))

    def test_is_hard_gate_for_incident_mitigate(self):
        s = pm.ProjectState(
            name="inc", current_phase="mitigate",
            created_at="2026-05-08T00:00:00Z",
            extras={"v11_archetype": "incident"},
        )
        self.assertTrue(pm._is_hard_gate(s, "mitigate"))
        self.assertFalse(pm._is_hard_gate(s, "investigate"))

    def test_is_hard_gate_false_for_legacy_no_archetype(self):
        s = pm.ProjectState(name="x", current_phase="cutover",
                            created_at="2026-05-08T00:00:00Z")
        self.assertFalse(pm._is_hard_gate(s, "cutover"))

    def test_cutover_refuses_without_confirmed_by(self):
        with patch.object(pm, "save_project_state"):
            with self.assertRaises(ValueError) as cm:
                pm.approve_phase(self._migrate_state_at_cutover(), "cutover")
        msg = str(cm.exception)
        self.assertIn("requires --confirmed-by", msg)
        self.assertIn("v11 enforced HITL gate", msg)

    def test_cutover_refuses_without_evidence(self):
        with patch.object(pm, "save_project_state"):
            with self.assertRaises(ValueError) as cm:
                pm.approve_phase(
                    self._migrate_state_at_cutover(), "cutover",
                    confirmed_by="oncall-mike",
                )
        self.assertIn("requires --confirmation-evidence", str(cm.exception))

    def test_cutover_refuses_blank_confirmed_by(self):
        with patch.object(pm, "save_project_state"):
            with self.assertRaises(ValueError):
                pm.approve_phase(
                    self._migrate_state_at_cutover(), "cutover",
                    confirmed_by="   ",
                    confirmation_evidence="x",
                )

    def test_cutover_advances_when_both_provided(self):
        with patch.object(pm, "save_project_state"):
            state, next_phase = pm.approve_phase(
                self._migrate_state_at_cutover(), "cutover",
                confirmed_by="oncall-mike",
                confirmation_evidence="dashboard:reads-switched-clean",
            )
        self.assertEqual(state.phases["cutover"].status, "approved")
        self.assertEqual(next_phase, "contract")
        approvals = state.extras["approvals"]
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["confirmed_by"], "oncall-mike")
        self.assertEqual(approvals[0]["confirmation_evidence"],
                         "dashboard:reads-switched-clean")
        self.assertTrue(approvals[0]["hard_gate"])

    def test_non_hard_phase_does_not_require_confirmation(self):
        # build:test is NOT a hard gate; approve without --confirmed-by
        # must succeed and not include hard_gate=True in the audit row.
        with patch.object(pm, "save_project_state"):
            state, next_phase = pm.approve_phase(
                self._build_state_at_test(), "test",
            )
        self.assertEqual(state.phases["test"].status, "approved")
        self.assertEqual(next_phase, "review")
        approvals = state.extras["approvals"]
        self.assertEqual(len(approvals), 1)
        self.assertNotIn("hard_gate", approvals[0])
        self.assertNotIn("confirmed_by", approvals[0])


class TestBusEmits(unittest.TestCase):
    """v11.1.1 — phase_manager state transitions emit bus events.

    Each emit goes through _bus_emit_safe which is fail-open. We patch
    the underlying emit_event to assert the right event types fire with
    the right payloads, without hitting the actual subprocess.
    """

    def _state(self, archetype=None):
        s = pm.ProjectState(
            name="emit-proj", current_phase="plan",
            created_at="2026-05-08T00:00:00Z",
            phase_plan=["plan", "implement", "test", "review"],
            extras={"v11_archetype": archetype} if archetype else {},
        )
        return s

    def test_create_archetype_emits_archetype_created(self):
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.create_project("emit-proj", archetype_mode="build")
        events = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn("wicked.archetype.created", events)

    def test_create_legacy_emits_project_created(self):
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.create_project("emit-proj-legacy")
        events = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn("wicked.project.created", events)
        self.assertNotIn("wicked.archetype.created", events)

    def test_approve_emits_archetype_advanced(self):
        state = self._state(archetype="build")
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.approve_phase(state, "plan")
        events = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn("wicked.archetype.advanced", events)
        # Payload contains archetype + phase + next_phase
        advance_call = next(
            c for c in mock_emit.call_args_list
            if c.args[0] == "wicked.archetype.advanced"
        )
        self.assertEqual(advance_call.args[1]["archetype"], "build")
        self.assertEqual(advance_call.args[1]["phase"], "plan")
        self.assertEqual(advance_call.args[1]["next_phase"], "implement")

    def test_approve_legacy_does_not_emit_archetype_events(self):
        # No v11_archetype on the state → no archetype.* events
        state = self._state(archetype=None)
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.approve_phase(state, "plan")
        events = [c.args[0] for c in mock_emit.call_args_list]
        for ev in events:
            self.assertFalse(
                ev.startswith("wicked.archetype."),
                f"legacy approve emitted archetype event: {ev}",
            )

    def test_hard_gate_pass_emits_dedicated_event(self):
        state = pm.ProjectState(
            name="emit-mig", current_phase="cutover",
            created_at="2026-05-08T00:00:00Z",
            phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
            extras={"v11_archetype": "migrate"},
        )
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.approve_phase(
                state, "cutover",
                confirmed_by="oncall-mike",
                confirmation_evidence="rollback-drill:staging",
            )
        events = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn("wicked.archetype.hard_gate_passed", events)
        self.assertIn("wicked.archetype.advanced", events)
        # hard_gate_passed payload carries confirmed_by + evidence
        hg_call = next(
            c for c in mock_emit.call_args_list
            if c.args[0] == "wicked.archetype.hard_gate_passed"
        )
        self.assertEqual(hg_call.args[1]["confirmed_by"], "oncall-mike")
        self.assertEqual(hg_call.args[1]["confirmation_evidence"],
                         "rollback-drill:staging")

    def test_completion_emits_archetype_completed(self):
        # Build state: pre-mark plan/implement/test approved so review
        # is the last remaining phase.
        state = pm.ProjectState(
            name="emit-final", current_phase="review",
            created_at="2026-05-08T00:00:00Z",
            phase_plan=["plan", "implement", "test", "review"],
            phases={
                "plan": pm.PhaseState(status="approved"),
                "implement": pm.PhaseState(status="approved"),
                "test": pm.PhaseState(status="approved"),
            },
            extras={"v11_archetype": "build"},
        )
        with patch.object(pm, "save_project_state"), \
             patch.object(pm, "_bus_emit_safe") as mock_emit:
            pm.approve_phase(state, "review")
        events = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn("wicked.archetype.completed", events)


class TestEndToEndArchetypeFlow(unittest.TestCase):
    """Integration test: full archetype flow from creation through final
    approval, exercising:
      - archetype-mode project creation
      - phase_plan hydrated from catalog
      - state transitions per phase
      - hard-gate enforcement at cutover
      - is_complete predicate
      - audit trail captured in extras
    """

    def test_full_migrate_lifecycle(self):
        """A migrate project: plan -> expand -> backfill -> cutover -> contract.

        The cutover phase requires hard-gate confirmation; everything else
        is a discrete-gate auto-pass."""
        with patch.object(pm, "save_project_state"):
            state, _ = pm.create_project(
                "migrate-int-test",
                description="drop legacy_id with backfill",
                archetype_mode="migrate",
            )
            self.assertEqual(
                state.phase_plan,
                ["plan", "expand", "backfill", "cutover", "contract"],
            )
            self.assertEqual(state.current_phase, "plan")

            # plan -> expand
            state = pm.start_phase(state, "plan")
            state = pm.complete_phase(state, "plan")
            state, nxt = pm.approve_phase(state, "plan")
            self.assertEqual(nxt, "expand")

            # expand -> backfill
            state = pm.start_phase(state, "expand")
            state = pm.complete_phase(state, "expand")
            state, nxt = pm.approve_phase(state, "expand")
            self.assertEqual(nxt, "backfill")

            # backfill -> cutover
            state = pm.start_phase(state, "backfill")
            state = pm.complete_phase(state, "backfill")
            state, nxt = pm.approve_phase(state, "backfill")
            self.assertEqual(nxt, "cutover")

            # cutover REFUSES without confirmation
            state = pm.start_phase(state, "cutover")
            state = pm.complete_phase(state, "cutover")
            with self.assertRaises(ValueError):
                pm.approve_phase(state, "cutover")

            # cutover advances WITH confirmation
            state, nxt = pm.approve_phase(
                state, "cutover",
                confirmed_by="release-eng-lead",
                confirmation_evidence="rollback-drill-log:staging-2026-05-08",
            )
            self.assertEqual(nxt, "contract")

            # contract -> done
            state = pm.start_phase(state, "contract")
            state = pm.complete_phase(state, "contract")
            state, nxt = pm.approve_phase(state, "contract")
            self.assertIsNone(nxt)
            self.assertTrue(pm.is_complete(state))

            # Audit trail: 5 approvals, exactly one with hard_gate=True
            approvals = state.extras["approvals"]
            self.assertEqual(len(approvals), 5)
            hard_gate_approvals = [a for a in approvals
                                    if a.get("hard_gate")]
            self.assertEqual(len(hard_gate_approvals), 1)
            self.assertEqual(hard_gate_approvals[0]["phase"], "cutover")


if __name__ == "__main__":
    unittest.main()
