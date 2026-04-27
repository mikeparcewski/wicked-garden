"""Tests for ``scripts/crew/detectors/test_failure_spike.py``.

PR-4 of the steering detector epic (#679). Covers all spec edge cases:

  * ``[0, 1, 1, 1]``       → fires (baseline 0, then 3 failures)
  * ``[1, 1, 1]``          → does NOT fire (no baseline)
  * ``[0, 1, 1]``          → does NOT fire (only 2 failures)
  * ``[0, 1, 0, 1, 1, 1]`` → fires (trailing 3 non-zero, baseline at idx 2)
  * ``[]``                 → no-op
  * Plus: schema validation, custom threshold, input validation, bus emit
    fail-open, CLI smoke.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.detectors import test_failure_spike as detector  # noqa: E402
from crew.detectors import _common as common  # noqa: E402
from crew.steering_event_schema import validate_payload  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _detect(codes, **overrides):
    kwargs = {
        "exit_codes": codes,
        "session_id": "sess-001",
        "project_slug": "demo",
        "now": _FIXED_NOW,
    }
    kwargs.update(overrides)
    return detector.detect_test_failure_spike(**kwargs)


# ---------------------------------------------------------------------------
# Spec edge cases
# ---------------------------------------------------------------------------

class SpecEdgeCases(unittest.TestCase):

    def test_baseline_then_three_failures_fires(self):
        events = _detect([0, 1, 1, 1])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"]["trailing_failures"], 3)
        self.assertEqual(events[0]["evidence"]["baseline_index"], 0)

    def test_three_failures_no_baseline_does_not_fire(self):
        self.assertEqual(_detect([1, 1, 1]), [])

    def test_baseline_then_two_failures_does_not_fire(self):
        self.assertEqual(_detect([0, 1, 1]), [])

    def test_alternating_with_trailing_three_fires(self):
        # [0, 1, 0, 1, 1, 1] — most recent 3 are 1, baseline at idx 2 (zero)
        events = _detect([0, 1, 0, 1, 1, 1])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"]["trailing_failures"], 3)
        self.assertEqual(events[0]["evidence"]["baseline_index"], 2)

    def test_empty_list_is_noop(self):
        self.assertEqual(_detect([]), [])

    def test_all_passes_does_not_fire(self):
        self.assertEqual(_detect([0, 0, 0, 0]), [])

    def test_baseline_then_more_than_threshold_failures_fires(self):
        # 5 trailing failures still fires (threshold met).
        events = _detect([0, 1, 1, 1, 1, 1])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"]["trailing_failures"], 5)


# ---------------------------------------------------------------------------
# Custom threshold
# ---------------------------------------------------------------------------

class CustomThreshold(unittest.TestCase):

    def test_threshold_2_fires_on_two_failures(self):
        events = _detect([0, 1, 1], threshold=2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["threshold"]["consecutive_failure_threshold"], 2)

    def test_threshold_5_does_not_fire_on_three(self):
        self.assertEqual(_detect([0, 1, 1, 1], threshold=5), [])

    def test_threshold_below_1_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, 1, 1, 1], threshold=0)

    def test_threshold_non_int_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, 1, 1, 1], threshold="3")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidation(unittest.TestCase):

    def test_non_int_exit_code_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, "1", 1, 1])  # type: ignore[list-item]

    def test_bool_in_exit_codes_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, True, 1, 1])  # type: ignore[list-item]

    def test_empty_session_id_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, 1, 1, 1], session_id="")

    def test_empty_project_slug_raises(self):
        with self.assertRaises(ValueError):
            _detect([0, 1, 1, 1], project_slug="")


# ---------------------------------------------------------------------------
# Schema integration
# ---------------------------------------------------------------------------

class SchemaIntegration(unittest.TestCase):

    def test_emitted_payload_passes_schema(self):
        ev = _detect([0, 1, 1, 1])[0]
        errors, _warnings = validate_payload(detector.EVENT_TYPE, ev)
        self.assertEqual(errors, [])

    def test_event_type_is_escalated(self):
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.escalated")

    def test_recommended_action_is_regen_test_strategy(self):
        ev = _detect([0, 1, 1, 1])[0]
        self.assertEqual(ev["recommended_action"], "regen-test-strategy")

    def test_subdomain_is_correct(self):
        self.assertEqual(detector.EVENT_SUBDOMAIN, "crew.detector.test-failure-spike")


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class EmitterBehavior(unittest.TestCase):

    def test_bus_unreachable_fails_open(self):
        events = _detect([0, 1, 1, 1])
        with mock.patch.object(common, "resolve_bus_command", return_value=None):
            count = detector.emit_test_failure_spike_events(events)
        self.assertEqual(count, 0)

    def test_successful_emit_uses_correct_subdomain(self):
        events = _detect([0, 1, 1, 1])

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common, "resolve_bus_command", return_value=["wicked-bus"],
        ), mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = detector.emit_test_failure_spike_events(events)
        self.assertEqual(count, 1)
        argv = run_mock.call_args_list[0][0][0]
        self.assertIn("wicked.steer.escalated", argv)
        self.assertIn("crew.detector.test-failure-spike", argv)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class CliSmoke(unittest.TestCase):

    def test_dry_run_does_not_call_bus(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--exit-codes", "0,1,1,1",
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()

    def test_invalid_exit_codes_returns_2(self):
        with mock.patch.object(common.subprocess, "run"):
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--exit-codes", "abc",
                "--dry-run",
            ])
        self.assertEqual(rc, 2)

    def test_cli_parse_handles_whitespace_in_csv(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--exit-codes", " 0 , 1 , 1 , 1 ",
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
