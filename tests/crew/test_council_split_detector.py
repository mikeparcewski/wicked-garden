"""Tests for ``scripts/crew/detectors/council_split.py``.

PR-4 of the steering detector epic (#679). Covers:

  * 4-voter 2-2 split → fires
  * 4-voter 3-1 majority → does NOT fire
  * 4-voter 2-1-1 split → fires (no quorum)
  * Empty input → no-op
  * Single voter → no-op
  * Schema validation on emitted payload
  * Custom quorum_threshold (e.g. 5-voter panel needing 4)
  * Malformed records (no verdict, non-dict) — skipped with warning
  * Bus emit fail-open
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

from crew.detectors import council_split as detector  # noqa: E402
from crew.detectors import _common as common  # noqa: E402
from crew.steering_event_schema import validate_payload  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _v(verdict: str, reviewer: str = "r") -> dict:
    return {"verdict": verdict, "reviewer": reviewer}


def _detect(findings, **overrides):
    kwargs = {
        "gate_findings": findings,
        "session_id": "sess-001",
        "project_slug": "demo",
        "now": _FIXED_NOW,
    }
    kwargs.update(overrides)
    return detector.detect_council_split(**kwargs)


# ---------------------------------------------------------------------------
# Spec edge cases
# ---------------------------------------------------------------------------

class SplitDetection(unittest.TestCase):

    def test_4_voter_2_2_split_fires(self):
        findings = [
            _v("APPROVE", "a"), _v("APPROVE", "b"),
            _v("REJECT",  "c"), _v("REJECT",  "d"),
        ]
        events = _detect(findings)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"]["voter_count"], 4)
        self.assertEqual(events[0]["evidence"]["leading_count"], 2)

    def test_4_voter_3_1_majority_does_not_fire(self):
        findings = [
            _v("APPROVE", "a"), _v("APPROVE", "b"), _v("APPROVE", "c"),
            _v("REJECT",  "d"),
        ]
        self.assertEqual(_detect(findings), [])

    def test_4_voter_2_1_1_split_fires(self):
        findings = [
            _v("APPROVE",     "a"), _v("APPROVE",     "b"),
            _v("REJECT",      "c"), _v("CONDITIONAL", "d"),
        ]
        events = _detect(findings)
        self.assertEqual(len(events), 1)
        # Leading count is 2 (APPROVE), three distinct verdicts present.
        self.assertEqual(events[0]["evidence"]["leading_count"], 2)
        self.assertEqual(
            sorted(events[0]["evidence"]["vote_tally"].keys()),
            ["APPROVE", "CONDITIONAL", "REJECT"],
        )

    def test_empty_input_is_noop(self):
        self.assertEqual(_detect([]), [])

    def test_single_voter_is_noop(self):
        # Can't have a split with one vote, regardless of verdict.
        self.assertEqual(_detect([_v("APPROVE")]), [])

    def test_unanimous_does_not_fire(self):
        findings = [_v("APPROVE", "a"), _v("APPROVE", "b"), _v("APPROVE", "c")]
        self.assertEqual(_detect(findings), [])


# ---------------------------------------------------------------------------
# Custom quorum threshold
# ---------------------------------------------------------------------------

class QuorumThresholds(unittest.TestCase):

    def test_5_voter_panel_3_2_split_does_not_fire_default_quorum(self):
        # Default quorum=3, leading=3 → no split.
        findings = [_v("APPROVE")] * 3 + [_v("REJECT")] * 2
        self.assertEqual(_detect(findings), [])

    def test_5_voter_panel_3_2_split_fires_with_custom_quorum_4(self):
        findings = [_v("APPROVE")] * 3 + [_v("REJECT")] * 2
        events = _detect(findings, quorum_threshold=4)
        self.assertEqual(len(events), 1)

    def test_quorum_threshold_below_2_raises(self):
        with self.assertRaises(ValueError):
            _detect([_v("APPROVE"), _v("REJECT")], quorum_threshold=1)

    def test_quorum_threshold_non_int_raises(self):
        with self.assertRaises(ValueError):
            _detect([_v("APPROVE"), _v("REJECT")], quorum_threshold="3")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Malformed input handling
# ---------------------------------------------------------------------------

class MalformedInput(unittest.TestCase):

    def test_record_without_verdict_is_skipped(self):
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            findings = [
                _v("APPROVE"), _v("APPROVE"), _v("APPROVE"),
                {"reviewer": "broken"},  # no verdict — skipped
                _v("REJECT"),
            ]
            events = _detect(findings)
        # 4 valid voters (the broken one is dropped), 3-1 → clear quorum, no fire.
        self.assertEqual(events, [])
        self.assertIn("verdict", err.getvalue().lower())

    def test_non_dict_record_is_skipped(self):
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            findings = [
                _v("APPROVE"), _v("APPROVE"),
                "not a dict",  # type: ignore[list-item]
                _v("REJECT"),  _v("REJECT"),
            ]
            events = _detect(findings)
        # 4 valid → 2-2 split → fires.
        self.assertEqual(len(events), 1)

    def test_non_string_verdict_is_skipped(self):
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            findings = [
                _v("APPROVE"), _v("APPROVE"), _v("APPROVE"),
                {"verdict": 1},  # invalid type — skipped
                _v("REJECT"),
            ]
            events = _detect(findings)
        # 4 valid voters (the broken one is dropped), 3-1 → clear quorum, no fire.
        self.assertEqual(events, [])

    def test_evidence_gate_findings_excludes_skipped_records(self):
        """Audit-trail accuracy: ``evidence['gate_findings']`` MUST contain
        ONLY records that actually contributed to the vote tally — never
        records skipped for missing/invalid verdict (Copilot finding F1)."""
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            findings = [
                _v("APPROVE", "alice"),
                _v("APPROVE", "bob"),
                {"reviewer": "no-verdict-here"},          # skipped (no verdict)
                {"verdict": 42, "reviewer": "wrong-type"},  # skipped (non-string verdict)
                "not-a-dict",                             # type: ignore[list-item]
                _v("REJECT", "carol"),
                _v("REJECT", "dave"),
            ]
            events = _detect(findings)
        # 4 valid voters → 2-2 split → fires.
        self.assertEqual(len(events), 1)
        audit = events[0]["evidence"]["gate_findings"]
        # Exactly four records — one per contributing voter.
        self.assertEqual(len(audit), 4)
        reviewers = {entry.get("reviewer") for entry in audit}
        self.assertEqual(reviewers, {"alice", "bob", "carol", "dave"})
        # Skipped records (and their distinguishing fields) MUST NOT appear.
        for entry in audit:
            self.assertNotEqual(entry.get("reviewer"), "no-verdict-here")
            self.assertNotEqual(entry.get("reviewer"), "wrong-type")
        # voter_count and audit-list length agree — the contract.
        self.assertEqual(events[0]["evidence"]["voter_count"], len(audit))


# ---------------------------------------------------------------------------
# Schema integration
# ---------------------------------------------------------------------------

class SchemaIntegration(unittest.TestCase):

    def test_emitted_payload_passes_schema(self):
        findings = [_v("APPROVE")] * 2 + [_v("REJECT")] * 2
        ev = _detect(findings)[0]
        errors, _warnings = validate_payload(detector.EVENT_TYPE, ev)
        self.assertEqual(errors, [])

    def test_event_type_is_escalated_with_council_action(self):
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.escalated")
        findings = [_v("APPROVE")] * 2 + [_v("REJECT")] * 2
        ev = _detect(findings)[0]
        self.assertEqual(ev["recommended_action"], "require-council-review")

    def test_subdomain_is_correct(self):
        self.assertEqual(detector.EVENT_SUBDOMAIN, "crew.detector.council-split")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidation(unittest.TestCase):

    def test_empty_session_id_raises(self):
        with self.assertRaises(ValueError):
            _detect([_v("APPROVE"), _v("REJECT")], session_id="")

    def test_empty_project_slug_raises(self):
        with self.assertRaises(ValueError):
            _detect([_v("APPROVE"), _v("REJECT")], project_slug="")


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class EmitterBehavior(unittest.TestCase):

    def test_bus_unreachable_fails_open(self):
        findings = [_v("APPROVE")] * 2 + [_v("REJECT")] * 2
        events = _detect(findings)
        with mock.patch.object(common, "resolve_bus_command", return_value=None):
            count = detector.emit_council_split_events(events)
        self.assertEqual(count, 0)

    def test_successful_emit(self):
        findings = [_v("APPROVE")] * 2 + [_v("REJECT")] * 2
        events = _detect(findings)

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common, "resolve_bus_command", return_value=["wicked-bus"],
        ), mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = detector.emit_council_split_events(events)
        self.assertEqual(count, 1)
        argv = run_mock.call_args_list[0][0][0]
        self.assertIn("wicked.steer.escalated", argv)
        self.assertIn("crew.detector.council-split", argv)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class CliSmoke(unittest.TestCase):

    def test_dry_run_does_not_call_bus(self):
        findings_json = (
            '[{"verdict":"APPROVE"},{"verdict":"APPROVE"},'
            '{"verdict":"REJECT"},{"verdict":"REJECT"}]'
        )
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--gate-findings", findings_json,
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()

    def test_malformed_json_returns_2(self):
        with mock.patch.object(common.subprocess, "run"):
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--gate-findings", "not-json",
                "--dry-run",
            ])
        self.assertEqual(rc, 2)

    def test_non_list_json_returns_2(self):
        with mock.patch.object(common.subprocess, "run"):
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--gate-findings", '{"verdict":"APPROVE"}',
                "--dry-run",
            ])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
