"""Tests for ``scripts/crew/detectors/blast_radius.py``.

PR-4 of the steering detector epic (#679). Covers:

  * Threshold (``observed > 2x estimated AND observed > 8``).
  * Edge cases from the PR-4 spec:
      - observed=10, estimated=2 → fires
      - observed=8,  estimated=2 → does NOT fire (8 not > 8)
      - observed=9,  estimated=10 → does NOT fire (9 not > 20)
      - estimated=0 → log warning + use floor=1, may fire
  * Schema validation on every emitted payload.
  * Input validation (negative, non-int, bool).
  * Bus emit fail-open behavior.
  * CLI smoke (--dry-run; no bus interaction).

Pure stdlib + unittest.
"""

from __future__ import annotations

import io
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.detectors import blast_radius as detector  # noqa: E402
from crew.detectors import _common as common  # noqa: E402
from crew.steering_event_schema import validate_payload  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _detect(observed: int, estimated: int, **overrides):
    kwargs = {
        "observed_files": observed,
        "estimated_files": estimated,
        "session_id": "sess-001",
        "project_slug": "demo",
        "now": _FIXED_NOW,
    }
    kwargs.update(overrides)
    return detector.detect_blast_radius_explosion(**kwargs)


# ---------------------------------------------------------------------------
# Threshold logic — the spec edge cases
# ---------------------------------------------------------------------------

class ThresholdSpec(unittest.TestCase):

    def test_observed_10_estimated_2_fires(self):
        # 10 > 2*2=4 AND 10 > 8 → fires
        events = _detect(10, 2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"]["observed_files"], 10)
        self.assertEqual(events[0]["evidence"]["estimated_files"], 2)

    def test_observed_8_estimated_2_does_not_fire(self):
        # 8 > 4 BUT 8 not > 8 → does not fire (the absolute floor)
        events = _detect(8, 2)
        self.assertEqual(events, [])

    def test_observed_9_estimated_10_does_not_fire(self):
        # 9 > 8 BUT 9 not > 20 → does not fire (the ratio floor)
        events = _detect(9, 10)
        self.assertEqual(events, [])

    def test_observed_just_over_both_thresholds_fires(self):
        # 9 > 8 AND 9 > 2*4=8 → fires
        events = _detect(9, 4)
        self.assertEqual(len(events), 1)

    def test_observed_zero_estimated_zero_does_not_fire(self):
        # estimated=0 → effective_estimate=1, 2*1=2; 0 not > 2 AND 0 not > 8.
        # Suppress the expected warning to keep test output clean.
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            events = _detect(0, 0)
        self.assertEqual(events, [])

    def test_observed_high_estimated_zero_fires_with_floor(self):
        # estimated=0 → effective_estimate=1, 2*1=2. observed=15 > 2 AND > 8 → fires.
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            events = _detect(15, 0)
        self.assertEqual(len(events), 1)
        self.assertIn("estimated_files=0", err.getvalue())
        self.assertEqual(events[0]["threshold"]["effective_estimate"], 1)
        self.assertEqual(events[0]["threshold"]["estimated_files"], 0)


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

class PayloadShape(unittest.TestCase):

    def test_recommended_action_is_force_full_rigor(self):
        ev = _detect(20, 2)[0]
        self.assertEqual(ev["recommended_action"], "force-full-rigor")

    def test_threshold_carries_constants_and_inputs(self):
        ev = _detect(20, 5)[0]
        self.assertEqual(ev["threshold"]["ratio_multiplier"], 2)
        self.assertEqual(ev["threshold"]["absolute_floor"], 8)
        self.assertEqual(ev["threshold"]["estimated_files"], 5)
        self.assertEqual(ev["threshold"]["effective_estimate"], 5)

    def test_evidence_includes_ratio(self):
        ev = _detect(20, 5)[0]
        self.assertEqual(ev["evidence"]["ratio"], 4.0)

    def test_detector_name_and_event_type(self):
        ev = _detect(20, 2)[0]
        self.assertEqual(ev["detector"], "blast-radius")
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.escalated")
        self.assertEqual(detector.EVENT_SUBDOMAIN, "crew.detector.blast-radius")

    def test_timestamp_is_fixed_when_now_supplied(self):
        ev = _detect(20, 2)[0]
        self.assertEqual(ev["timestamp"], "2026-04-27T10:00:00Z")


# ---------------------------------------------------------------------------
# Schema integration
# ---------------------------------------------------------------------------

class SchemaIntegration(unittest.TestCase):

    def test_emitted_payload_passes_schema(self):
        ev = _detect(50, 1)[0]
        errors, _warnings = validate_payload(detector.EVENT_TYPE, ev)
        self.assertEqual(errors, [])

    def test_payload_event_type_is_escalated(self):
        # Blast-radius is a force-rigor signal — must be `escalated`, not `advised`.
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.escalated")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidation(unittest.TestCase):

    def test_negative_observed_raises(self):
        with self.assertRaises(ValueError):
            _detect(-1, 2)

    def test_negative_estimated_raises(self):
        with self.assertRaises(ValueError):
            _detect(10, -1)

    def test_non_int_observed_raises(self):
        with self.assertRaises(ValueError):
            detector.detect_blast_radius_explosion(
                observed_files="10",  # type: ignore[arg-type]
                estimated_files=2,
                session_id="s1",
                project_slug="demo",
            )

    def test_bool_observed_rejected_even_though_int_subclass(self):
        with self.assertRaises(ValueError):
            detector.detect_blast_radius_explosion(
                observed_files=True,  # type: ignore[arg-type]
                estimated_files=2,
                session_id="s1",
                project_slug="demo",
            )

    def test_empty_session_id_raises(self):
        with self.assertRaises(ValueError):
            _detect(10, 2, session_id="")

    def test_empty_project_slug_raises(self):
        with self.assertRaises(ValueError):
            _detect(10, 2, project_slug="")


# ---------------------------------------------------------------------------
# Emitter — bus interaction (delegates to common)
# ---------------------------------------------------------------------------

class EmitterBehavior(unittest.TestCase):

    def test_empty_payloads_returns_zero(self):
        self.assertEqual(detector.emit_blast_radius_events([]), 0)

    def test_bus_unreachable_fails_open(self):
        events = _detect(20, 2)
        with mock.patch.object(common, "resolve_bus_command", return_value=None):
            count = detector.emit_blast_radius_events(events)
        self.assertEqual(count, 0)

    def test_successful_emit_uses_correct_subdomain(self):
        events = _detect(20, 2)

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common, "resolve_bus_command", return_value=["wicked-bus"],
        ), mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = detector.emit_blast_radius_events(events)
        self.assertEqual(count, 1)
        argv = run_mock.call_args_list[0][0][0]
        self.assertIn("wicked.steer.escalated", argv)
        self.assertIn("crew.detector.blast-radius", argv)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class CliSmoke(unittest.TestCase):

    def test_dry_run_does_not_call_bus(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--observed", "20", "--estimated", "2",
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()

    def test_invalid_input_returns_2(self):
        with mock.patch.object(common.subprocess, "run"):
            rc = detector.main([
                "--session-id", "", "--project-slug", "demo",
                "--observed", "20", "--estimated", "2",
                "--dry-run",
            ])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
