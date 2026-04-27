"""Tests for ``scripts/crew/rigor_escalator.py``.

PR-3 of the steering detector epic (#679). Covers:

  * Action -> tier mutation: force-full-rigor on minimal/standard projects
    raises tier to full.
  * Never-de-escalate: force-full-rigor on a full project returns redundant.
  * regen-test-strategy: tier unchanged, history appended.
  * require-council-review: tier unchanged, pending_council_upgrade flag set.
  * notify-only: pure no-op, no persistence side-effects.
  * Idempotency: same (project, event_id) processed twice → second is no-op.
  * Invalid payload: returns error decision, audit emit attempted.
  * Unknown project: error decision, no mutation, audit emitted.
  * Dry-run: no project mutation, no audit emit.
  * Audit event emitted on every decision branch (escalated/redundant/no-op/error)
    — verified by counting ``_emit_applied_event`` mock calls.
  * escalation_history is append-only (multi-event projects).
  * Custom action_map override.
  * Bus subscribe-failure handling (resolve returns None).
  * Bare-payload tolerance (test convenience for non-bus callers).
  * advised event_type → no-op (subscriber only acts on escalated).

Pure stdlib + unittest. No live wicked-bus, no live phase_manager — both are
swapped in via ``mock.patch`` against the rigor_escalator module's references.
"""

from __future__ import annotations

import json
import signal
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew import rigor_escalator as escalator  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeProjectState:
    """Minimal stand-in for ``crew.phase_manager.ProjectState``."""

    def __init__(self, name: str, extras: Optional[Dict[str, Any]] = None):
        self.name = name
        self.extras = dict(extras or {})


class FakePhaseManager:
    """In-memory stand-in for the phase_manager module.

    Records every ``update_project`` call so tests can assert on the persisted
    state without exercising DomainStore.
    """

    def __init__(self):
        self.projects: Dict[str, FakeProjectState] = {}
        self.update_calls: List[tuple] = []

    def add_project(self, slug: str, *, rigor_tier: Optional[str] = None) -> FakeProjectState:
        extras: Dict[str, Any] = {}
        if rigor_tier is not None:
            extras["rigor_tier"] = rigor_tier
        state = FakeProjectState(slug, extras=extras)
        self.projects[slug] = state
        return state

    def load_project_state(self, slug: str) -> Optional[FakeProjectState]:
        return self.projects.get(slug)

    def update_project(self, state: FakeProjectState, data: Dict[str, Any]):
        # Mirror real update_project: merges into extras (or top-level for
        # rigor_tier — phase_manager stores it under extras, so do the same).
        for key, value in data.items():
            state.extras[key] = value
        self.update_calls.append((state.name, dict(data)))
        return state, list(data.keys())


def _make_payload(
    project_slug: str,
    *,
    recommended_action: str = "force-full-rigor",
    detector: str = "sensitive-path",
    signal_text: str = "auth path touched",
    timestamp: str = "2026-04-27T10:00:00Z",
    session_id: str = "sess-001",
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a schema-valid steering payload for tests."""
    return {
        "detector": detector,
        "signal": signal_text,
        "threshold": {"glob": "**/auth/**"},
        "recommended_action": recommended_action,
        "evidence": dict(evidence or {"file": "src/auth/login.py"}),
        "session_id": session_id,
        "project_slug": project_slug,
        "timestamp": timestamp,
    }


def _make_event(
    project_slug: str,
    *,
    event_id: str = "evt-1",
    event_type: str = "wicked.steer.escalated",
    **payload_kwargs,
) -> Dict[str, Any]:
    """Wrap a payload in a bus-style envelope."""
    return {
        "id": event_id,
        "event_type": event_type,
        "domain": "wicked-garden",
        "subdomain": "crew.detector.sensitive-path",
        "payload": _make_payload(project_slug, **payload_kwargs),
    }


# ---------------------------------------------------------------------------
# Action -> tier mapping
# ---------------------------------------------------------------------------

class ForceFullRigor(unittest.TestCase):

    def test_minimal_project_is_escalated_to_full(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo"), pm=pm,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(decision["previous_tier"], "minimal")
        self.assertEqual(decision["new_tier"], "full")
        # Project state mutated.
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "full")
        # update_project was called once with both rigor_tier and history.
        self.assertEqual(len(pm.update_calls), 1)
        _, data = pm.update_calls[0]
        self.assertEqual(data["rigor_tier"], "full")
        self.assertIn("rigor_escalation_history", data)
        # Audit event emitted exactly once.
        self.assertEqual(emit.call_count, 1)

    def test_standard_project_is_escalated_to_full(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="standard")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(_make_event("demo"), pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(decision["previous_tier"], "standard")
        self.assertEqual(decision["new_tier"], "full")
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "full")

    def test_default_tier_when_unset_is_standard(self):
        # Project has no rigor_tier in extras — escalator treats it as
        # 'standard' and bumps to full.
        pm = FakePhaseManager()
        pm.add_project("demo")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(_make_event("demo"), pm=pm)

        self.assertEqual(decision["previous_tier"], "standard")
        self.assertEqual(decision["new_tier"], "full")


class NeverDeEscalate(unittest.TestCase):

    def test_full_project_force_full_is_redundant(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="full")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(_make_event("demo"), pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_REDUNDANT)
        self.assertEqual(decision["previous_tier"], "full")
        self.assertEqual(decision["new_tier"], "full", "must not de-escalate")
        # Tier did NOT change, but history WAS appended for false-positive metrics.
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "full")
        self.assertEqual(len(pm.update_calls), 1)
        _, data = pm.update_calls[0]
        self.assertNotIn("rigor_tier", data, "redundant must not write rigor_tier")
        self.assertIn("rigor_escalation_history", data)
        # Audit event still emitted.
        self.assertEqual(emit.call_count, 1)


# ---------------------------------------------------------------------------
# Non-tier actions
# ---------------------------------------------------------------------------

class RegenTestStrategy(unittest.TestCase):

    def test_keeps_tier_records_history(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="standard")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo", recommended_action="regen-test-strategy"),
                pm=pm,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(decision["previous_tier"], "standard")
        self.assertEqual(decision["new_tier"], "standard")
        # update_project was called for history (no rigor_tier change).
        self.assertEqual(len(pm.update_calls), 1)
        _, data = pm.update_calls[0]
        self.assertNotIn("rigor_tier", data)
        self.assertIn("rigor_escalation_history", data)
        # History entry has the right action.
        history = data["rigor_escalation_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["recommended_action"], "regen-test-strategy")
        self.assertEqual(emit.call_count, 1)


class RequireCouncilReview(unittest.TestCase):

    def test_keeps_tier_sets_pending_council_upgrade(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="standard")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo", recommended_action="require-council-review"),
                pm=pm,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "standard")
        # Pending council flag persisted for the next gate dispatch to consume.
        self.assertTrue(pm.projects["demo"].extras.get("pending_council_upgrade"))
        # History also recorded.
        self.assertIn("rigor_escalation_history", pm.projects["demo"].extras)
        self.assertEqual(emit.call_count, 1)


class NotifyOnly(unittest.TestCase):

    def test_no_state_mutation(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="standard")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo", recommended_action="notify-only"),
                pm=pm,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_NO_OP)
        # notify-only: no update_project call AT ALL.
        self.assertEqual(pm.update_calls, [])
        # But audit event still emitted.
        self.assertEqual(emit.call_count, 1)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class IdempotencyInSession(unittest.TestCase):

    def test_second_call_with_same_event_id_is_noop(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        seen: set = set()

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            d1 = escalator.apply_steering_event(
                _make_event("demo", event_id="evt-99"),
                pm=pm, seen_event_ids=seen,
            )
            d2 = escalator.apply_steering_event(
                _make_event("demo", event_id="evt-99"),
                pm=pm, seen_event_ids=seen,
            )

        self.assertEqual(d1["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(d2["action_taken"], escalator.ACTION_NO_OP)
        self.assertIn("idempotency", d2["reason"].lower())
        # Only one mutation — second call short-circuited.
        self.assertEqual(len(pm.update_calls), 1)
        # Only one audit emit — duplicates do not re-emit (avoids feedback loop).
        self.assertEqual(emit.call_count, 1)

    def test_different_events_for_same_project_both_processed(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        seen: set = set()

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            d1 = escalator.apply_steering_event(
                _make_event("demo", event_id="evt-1"),
                pm=pm, seen_event_ids=seen,
            )
            d2 = escalator.apply_steering_event(
                _make_event("demo", event_id="evt-2"),
                pm=pm, seen_event_ids=seen,
            )

        # First escalates minimal -> full; second is redundant (already full).
        self.assertEqual(d1["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(d2["action_taken"], escalator.ACTION_REDUNDANT)


# ---------------------------------------------------------------------------
# Invalid payloads + missing projects
# ---------------------------------------------------------------------------

class InvalidPayload(unittest.TestCase):

    def test_missing_required_field_returns_error(self):
        bad = {
            "id": "evt-1",
            "event_type": "wicked.steer.escalated",
            "payload": {
                # missing detector, threshold, etc.
                "project_slug": "demo",
                "session_id": "sess-001",
                "recommended_action": "force-full-rigor",
                "timestamp": "2026-04-27T10:00:00Z",
            },
        }
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(bad, pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ERROR)
        self.assertEqual(pm.update_calls, [], "errors must not mutate state")
        # Even errors emit an audit so the ledger sees the bad event.
        self.assertEqual(emit.call_count, 1)

    def test_unknown_event_type_returns_error(self):
        bad = {
            "id": "evt-1",
            "event_type": "wicked.steer.unknown",
            "payload": _make_payload("demo"),
        }
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(bad, pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ERROR)


class UnknownProject(unittest.TestCase):

    def test_missing_project_returns_error_decision(self):
        pm = FakePhaseManager()  # No projects added.

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(_make_event("ghost"), pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ERROR)
        self.assertIn("not found", decision["reason"].lower())
        self.assertEqual(pm.update_calls, [])
        # Audit still emitted — required by the per-branch contract.
        self.assertEqual(emit.call_count, 1)


# ---------------------------------------------------------------------------
# Audit emit on every branch (single concentrated test for the contract)
# ---------------------------------------------------------------------------

class AuditEmitContract(unittest.TestCase):

    def test_every_branch_emits_audit(self):
        """Every decision branch must emit a wicked.steer.applied audit event."""
        pm = FakePhaseManager()
        pm.add_project("demo-a", rigor_tier="minimal")  # → escalated
        pm.add_project("demo-b", rigor_tier="full")      # → redundant
        pm.add_project("demo-c", rigor_tier="standard")  # → no-op (notify-only)
        # demo-ghost intentionally missing → error

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            d_esc = escalator.apply_steering_event(
                _make_event("demo-a", event_id="e1"), pm=pm,
            )
            d_red = escalator.apply_steering_event(
                _make_event("demo-b", event_id="e2"), pm=pm,
            )
            d_nop = escalator.apply_steering_event(
                _make_event(
                    "demo-c", event_id="e3", recommended_action="notify-only",
                ),
                pm=pm,
            )
            d_err = escalator.apply_steering_event(
                _make_event("demo-ghost", event_id="e4"), pm=pm,
            )

        self.assertEqual(d_esc["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(d_red["action_taken"], escalator.ACTION_REDUNDANT)
        self.assertEqual(d_nop["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(d_err["action_taken"], escalator.ACTION_ERROR)
        # 4 distinct branches → 4 audit emits.
        self.assertEqual(
            emit.call_count, 4,
            f"expected 4 audit emits across 4 branches, got {emit.call_count}",
        )


# ---------------------------------------------------------------------------
# History append-only behavior
# ---------------------------------------------------------------------------

class EscalationHistoryAppendOnly(unittest.TestCase):

    def test_history_grows_across_events(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        seen: set = set()

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            escalator.apply_steering_event(
                _make_event("demo", event_id="e1"), pm=pm, seen_event_ids=seen,
            )
            escalator.apply_steering_event(
                _make_event(
                    "demo", event_id="e2", recommended_action="regen-test-strategy",
                ),
                pm=pm, seen_event_ids=seen,
            )
            escalator.apply_steering_event(
                _make_event(
                    "demo", event_id="e3", recommended_action="require-council-review",
                ),
                pm=pm, seen_event_ids=seen,
            )

        history = pm.projects["demo"].extras["rigor_escalation_history"]
        # 3 distinct events → 3 history entries.
        self.assertEqual(len(history), 3)
        self.assertEqual(
            [h["event_id"] for h in history],
            ["e1", "e2", "e3"],
        )
        # First entry is the tier change; rest are no-op records.
        self.assertEqual(history[0]["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(history[0]["new_tier"], "full")
        # Events 2 and 3 happen AFTER tier is full, so they're redundant for
        # tier-changing actions but no-op for non-tier actions. regen-test-strategy
        # is a non-tier-action -> no-op (not redundant).
        self.assertEqual(history[1]["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(history[2]["action_taken"], escalator.ACTION_NO_OP)


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

class DryRunMode(unittest.TestCase):

    def test_no_mutation_no_emit(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo"), pm=pm, dry_run=True,
            )

        # Decision is computed correctly...
        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(decision["new_tier"], "full")
        # ...but state is untouched and no audit event fired.
        self.assertEqual(pm.update_calls, [])
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "minimal")
        emit.assert_not_called()


# ---------------------------------------------------------------------------
# Custom action_map override
# ---------------------------------------------------------------------------

class CustomActionMapOverride(unittest.TestCase):

    def test_override_force_full_to_standard_only(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        custom = {"force-full-rigor": "standard"}

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(
                _make_event("demo"), pm=pm, action_map=custom,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)
        self.assertEqual(decision["new_tier"], "standard")
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "standard")

    def test_override_makes_action_a_no_op(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        # Map force-full-rigor to None — should become a no-op.
        custom = {"force-full-rigor": None}

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(
                _make_event("demo"), pm=pm, action_map=custom,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "minimal")


# ---------------------------------------------------------------------------
# Bus subscribe failure path (CLI surface)
# ---------------------------------------------------------------------------

class BusSubscribeFailure(unittest.TestCase):

    def test_main_exits_1_when_bus_unreachable(self):
        with mock.patch.object(escalator, "_resolve_bus_command", return_value=None):
            rc = escalator.main([])
        self.assertEqual(rc, 1)

    def test_main_dry_run_still_exits_1_when_bus_unreachable(self):
        # We require the bus for CLI mode even in --dry-run — there's nothing
        # to subscribe to without it.
        with mock.patch.object(escalator, "_resolve_bus_command", return_value=None):
            rc = escalator.main(["--dry-run"])
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# advised events are not acted on
# ---------------------------------------------------------------------------

class AdvisedEventNoOp(unittest.TestCase):

    def test_advised_event_returns_noop_no_mutation(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True) as emit:
            decision = escalator.apply_steering_event(
                _make_event("demo", event_type="wicked.steer.advised"),
                pm=pm,
            )

        self.assertEqual(decision["action_taken"], escalator.ACTION_NO_OP)
        self.assertEqual(pm.update_calls, [])
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "minimal")
        # Audit still emitted so the trail records that we saw it.
        self.assertEqual(emit.call_count, 1)


# ---------------------------------------------------------------------------
# Bare-payload tolerance (test convenience for non-bus callers)
# ---------------------------------------------------------------------------

class BarePayloadTolerance(unittest.TestCase):

    def test_bare_payload_treated_as_escalated(self):
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")
        bare = _make_payload("demo")

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(bare, pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)


# ---------------------------------------------------------------------------
# Bus wire-format compatibility — wicked-bus subscribe ships payload as a
# JSON-encoded STRING (not a nested object). Verify we parse it correctly.
# ---------------------------------------------------------------------------

class BusEnvelopeWireFormat(unittest.TestCase):

    def test_payload_as_json_string_is_parsed(self):
        """wicked-bus subscribe delivers payload as a JSON-encoded string."""
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        wire_envelope = {
            "event_id": 12345,
            "event_type": "wicked.steer.escalated",
            "domain": "wicked-garden",
            "subdomain": "crew.detector.sensitive-path",
            "payload": json.dumps(_make_payload("demo")),
            "idempotency_key": "uuid-abc-123",
        }

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(wire_envelope, pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ESCALATED)
        # Idempotency key should be the bus's uuid (preferred over event_id).
        self.assertEqual(decision["event_id"], "uuid-abc-123")

    def test_malformed_payload_string_returns_error(self):
        """A non-JSON payload string is treated as an empty payload (schema rejects)."""
        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        broken = {
            "event_id": 99,
            "event_type": "wicked.steer.escalated",
            "payload": "not-valid-json{{{",
        }

        with mock.patch.object(escalator, "_emit_applied_event", return_value=True):
            decision = escalator.apply_steering_event(broken, pm=pm)

        self.assertEqual(decision["action_taken"], escalator.ACTION_ERROR)
        # No mutation despite the malformed wire payload.
        self.assertEqual(pm.update_calls, [])
        self.assertEqual(pm.projects["demo"].extras["rigor_tier"], "minimal")


# ---------------------------------------------------------------------------
# Clean-shutdown signal handling (smoke — verify SIGINT handler is wired)
# ---------------------------------------------------------------------------

class SigintHandling(unittest.TestCase):

    def test_stream_loop_keyboard_interrupt_returns_zero(self):
        """A SIGINT mid-stream returns 0, not a stack trace."""

        # Build a fake Popen whose stdout iterator raises KeyboardInterrupt
        # on the first read — emulating user pressing Ctrl-C immediately.
        class _FakePopen:
            stdout = None
            returncode = 0

            def __init__(self, *_a, **_kw):
                self.stdout = self

            def __iter__(self):
                return self

            def __next__(self):
                raise KeyboardInterrupt

            def poll(self):
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

            def wait(self, timeout=None):
                return 0

        with mock.patch.object(escalator.subprocess, "Popen", _FakePopen):
            rc = escalator._stream_loop(
                ["wicked-bus"], cursor=None, dry_run=True, seen_event_ids=set(),
            )

        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# Audit payload shape — make sure what we emit will pass the schema validator
# ---------------------------------------------------------------------------

class AuditPayloadShape(unittest.TestCase):

    def test_emit_applied_event_payload_passes_schema(self):
        """The audit emit must build a payload that passes validate_payload.

        Mocks the subprocess so we can inspect the argv.
        """
        from crew.steering_event_schema import validate_payload

        pm = FakePhaseManager()
        pm.add_project("demo", rigor_tier="minimal")

        # Capture the subprocess invocation of `wicked-bus emit` by patching
        # subprocess.run and asserting on the JSON payload arg.
        captured: Dict[str, Any] = {}

        class _OkProc:
            returncode = 0
            stderr = ""

        def _capture(cmd, *_a, **_kw):
            # Find --payload arg
            try:
                idx = cmd.index("--payload")
                captured["payload"] = json.loads(cmd[idx + 1])
                captured["type"] = cmd[cmd.index("--type") + 1]
            except (ValueError, KeyError, json.JSONDecodeError):
                pass
            return _OkProc()

        with mock.patch.object(
            escalator, "_resolve_bus_command", return_value=["wicked-bus"],
        ), mock.patch.object(
            escalator.subprocess, "run", side_effect=_capture,
        ):
            escalator.apply_steering_event(_make_event("demo"), pm=pm)

        self.assertIn("payload", captured, "subprocess emit was not called with --payload")
        self.assertEqual(captured["type"], "wicked.steer.applied")
        errors, warnings = validate_payload("wicked.steer.applied", captured["payload"])
        self.assertEqual(
            errors, [],
            f"audit payload failed schema: {errors} payload={captured['payload']}",
        )
        # action_taken stuffed under evidence as documented.
        self.assertEqual(captured["payload"]["evidence"]["action_taken"], escalator.ACTION_ESCALATED)


if __name__ == "__main__":
    unittest.main()
