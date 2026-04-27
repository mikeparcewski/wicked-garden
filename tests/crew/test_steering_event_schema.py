"""Tests for ``scripts/crew/steering_event_schema.py``.

Covers PR-1 schema validator for the wicked.steer.* event family:
  * valid escalated/advised payloads pass (errors empty, warnings empty)
  * each required field is enforced individually
  * unknown detector / event_type are rejected
  * unknown action produces a warning (loose set), not an error
  * malformed timestamp shape is rejected
  * shape-valid but calendar-invalid timestamps (e.g. 2026-99-99T99:99:99Z)
    are rejected after the datetime parse step
  * empty evidence object is rejected
  * validate_payload returns a (errors, warnings) tuple

Pure stdlib + unittest — no fixtures, no mocks. Deterministic.
"""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.steering_event_schema import (  # noqa: E402
    KNOWN_ACTIONS,
    KNOWN_DETECTORS,
    KNOWN_EVENT_TYPES,
    validate_payload,
)


def _valid_payload() -> dict:
    """Return a minimal, fully valid escalated payload."""
    return {
        "detector": "sensitive-path",
        "signal": "auth/login.py touched",
        "threshold": {"extensions": [".py"]},
        "recommended_action": "force-full-rigor",
        "evidence": {
            "file": "auth/login.py",
            "session_id": "sess-001",
            "project_slug": "test",
        },
        "session_id": "sess-001",
        "project_slug": "test",
        "timestamp": "2026-04-27T10:00:00Z",
    }


class ValidPayloads(unittest.TestCase):
    def test_valid_escalated_payload_passes(self):
        errors, warnings = validate_payload(
            "wicked.steer.escalated", _valid_payload()
        )
        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertEqual(warnings, [], f"unexpected warnings: {warnings}")

    def test_valid_advised_payload_passes(self):
        payload = _valid_payload()
        payload["recommended_action"] = "notify-only"
        errors, warnings = validate_payload("wicked.steer.advised", payload)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertEqual(warnings, [], f"unexpected warnings: {warnings}")

    def test_iso8601_with_offset_passes(self):
        payload = _valid_payload()
        payload["timestamp"] = "2026-04-27T10:00:00+00:00"
        errors, warnings = validate_payload("wicked.steer.escalated", payload)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_iso8601_with_microseconds_passes(self):
        payload = _valid_payload()
        payload["timestamp"] = "2026-04-27T10:00:00.123456+00:00"
        errors, warnings = validate_payload("wicked.steer.escalated", payload)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class RequiredFieldEnforcement(unittest.TestCase):
    """One test per required field — proves none can be silently dropped."""

    def _missing(self, field: str) -> list:
        payload = _valid_payload()
        del payload[field]
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        return errors

    def test_missing_detector_fails(self):
        errors = self._missing("detector")
        self.assertTrue(any("detector" in e for e in errors), errors)

    def test_missing_signal_fails(self):
        errors = self._missing("signal")
        self.assertTrue(any("signal" in e for e in errors), errors)

    def test_missing_threshold_fails(self):
        errors = self._missing("threshold")
        self.assertTrue(any("threshold" in e for e in errors), errors)

    def test_missing_recommended_action_fails(self):
        errors = self._missing("recommended_action")
        self.assertTrue(any("recommended_action" in e for e in errors), errors)

    def test_missing_evidence_fails(self):
        errors = self._missing("evidence")
        self.assertTrue(any("evidence" in e for e in errors), errors)

    def test_missing_session_id_fails(self):
        errors = self._missing("session_id")
        self.assertTrue(any("session_id" in e for e in errors), errors)

    def test_missing_project_slug_fails(self):
        errors = self._missing("project_slug")
        self.assertTrue(any("project_slug" in e for e in errors), errors)

    def test_missing_timestamp_fails(self):
        errors = self._missing("timestamp")
        self.assertTrue(any("timestamp" in e for e in errors), errors)


class AllowlistEnforcement(unittest.TestCase):
    def test_unknown_detector_fails(self):
        payload = _valid_payload()
        payload["detector"] = "some-future-detector-not-yet-allowlisted"
        errors, warnings = validate_payload(
            "wicked.steer.escalated", payload
        )
        self.assertTrue(
            any("unknown detector" in e for e in errors),
            f"expected hard 'unknown detector' error, got errors={errors} "
            f"warnings={warnings}",
        )

    def test_unknown_event_type_fails(self):
        errors, _warnings = validate_payload(
            "wicked.steer.frobnicated", _valid_payload()
        )
        self.assertTrue(
            any("unknown event_type" in e for e in errors),
            f"expected hard 'unknown event_type' error, got: {errors}",
        )

    def test_unknown_action_warns_does_not_reject(self):
        payload = _valid_payload()
        payload["recommended_action"] = "summon-a-cthulhu"
        errors, warnings = validate_payload("wicked.steer.escalated", payload)
        # No HARD errors — the unknown action lives in the warnings list now.
        self.assertEqual(errors, [], f"unexpected hard errors: {errors}")
        self.assertTrue(
            any("unknown recommended_action" in w for w in warnings),
            f"expected warning for unknown action, got: {warnings}",
        )


class FieldShapeChecks(unittest.TestCase):
    def test_bad_timestamp_format_fails(self):
        payload = _valid_payload()
        payload["timestamp"] = "yesterday at noon"
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("timestamp" in e and "ISO8601" in e for e in errors),
            f"expected ISO8601 error, got: {errors}",
        )

    def test_naive_timestamp_no_zone_fails(self):
        payload = _valid_payload()
        payload["timestamp"] = "2026-04-27T10:00:00"  # missing zone
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("timestamp" in e for e in errors),
            f"expected timestamp error for naive ts, got: {errors}",
        )

    def test_calendar_invalid_timestamp_fails(self):
        # Regex shape passes (4-2-2 T 2:2:2 Z) but the components are nonsense.
        # The datetime.fromisoformat() check after the regex must catch this.
        payload = _valid_payload()
        payload["timestamp"] = "2026-99-99T99:99:99Z"
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("timestamp" in e for e in errors),
            f"expected timestamp error for calendar-invalid ts, got: {errors}",
        )

    def test_calendar_invalid_timestamp_with_offset_fails(self):
        payload = _valid_payload()
        payload["timestamp"] = "2026-13-40T25:61:99+00:00"
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("timestamp" in e for e in errors),
            f"expected timestamp error for calendar-invalid ts, got: {errors}",
        )

    def test_empty_evidence_fails(self):
        payload = _valid_payload()
        payload["evidence"] = {}
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("evidence" in e and "at least one" in e for e in errors),
            f"expected empty-evidence error, got: {errors}",
        )

    def test_evidence_must_be_dict(self):
        payload = _valid_payload()
        payload["evidence"] = "a string is not a dict"
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("evidence" in e and "dict" in e for e in errors),
            f"expected evidence-type error, got: {errors}",
        )

    def test_threshold_must_be_dict(self):
        payload = _valid_payload()
        payload["threshold"] = ["a", "list"]
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("threshold" in e and "dict" in e for e in errors),
            f"expected threshold-type error, got: {errors}",
        )

    def test_payload_not_a_dict_short_circuits(self):
        errors, _ = validate_payload("wicked.steer.escalated", "not a dict")
        self.assertTrue(any("payload must be a dict" in e for e in errors))

    def test_blank_session_id_fails(self):
        payload = _valid_payload()
        payload["session_id"] = "   "
        errors, _ = validate_payload("wicked.steer.escalated", payload)
        self.assertTrue(
            any("session_id" in e for e in errors),
            f"expected session_id error, got: {errors}",
        )


class ReturnShape(unittest.TestCase):
    """Validator must always return a (errors, warnings) tuple."""

    def test_returns_tuple_of_two_lists(self):
        result = validate_payload("wicked.steer.escalated", _valid_payload())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        errors, warnings = result
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warnings, list)

    def test_returns_tuple_even_on_non_dict_payload(self):
        # Short-circuit path must still return the tuple shape.
        result = validate_payload("wicked.steer.escalated", 42)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        errors, warnings = result
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warnings, list)
        self.assertTrue(errors, "expected hard error for non-dict payload")


class AllowlistContents(unittest.TestCase):
    """Lock the v1 allowlist contents — additions need explicit PR review."""

    def test_known_detectors_v1_set(self):
        self.assertEqual(
            KNOWN_DETECTORS,
            frozenset({
                "sensitive-path",
                "blast-radius",
                "council-split",
                "test-failure-spike",
                "cross-domain-edits",
            }),
        )

    def test_known_event_types_v1_set(self):
        self.assertEqual(
            KNOWN_EVENT_TYPES,
            frozenset({"wicked.steer.escalated", "wicked.steer.advised"}),
        )

    def test_known_actions_v1_set(self):
        self.assertEqual(
            KNOWN_ACTIONS,
            frozenset({
                "force-full-rigor",
                "regen-test-strategy",
                "require-council-review",
                "notify-only",
            }),
        )


class DeepCopyImmunity(unittest.TestCase):
    """Validator must not mutate the caller's payload."""

    def test_payload_is_not_mutated(self):
        original = _valid_payload()
        snapshot = deepcopy(original)
        validate_payload("wicked.steer.escalated", original)
        self.assertEqual(original, snapshot)


class NonDictPayloadTypes(unittest.TestCase):
    """validate_payload accepts Any — non-dicts must short-circuit cleanly."""

    def test_none_payload(self):
        errors, _ = validate_payload("wicked.steer.escalated", None)
        self.assertTrue(any("payload must be a dict" in e for e in errors))

    def test_list_payload(self):
        errors, _ = validate_payload("wicked.steer.escalated", [1, 2, 3])
        self.assertTrue(any("payload must be a dict" in e for e in errors))

    def test_int_payload(self):
        errors, _ = validate_payload("wicked.steer.escalated", 42)
        self.assertTrue(any("payload must be a dict" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
