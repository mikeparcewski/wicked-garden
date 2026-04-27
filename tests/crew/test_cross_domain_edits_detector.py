"""Tests for ``scripts/crew/detectors/cross_domain_edits.py``.

PR-4 of the steering detector epic (#679). This detector is **advisory**
(emits ``wicked.steer.advised``, NOT ``wicked.steer.escalated``).

Covers:

  * 2 domains → no fire
  * 4+ distinct second-segment domains → fires with `advised`
  * Empty path list → no-op
  * Path normalization (backslashes, leading ./)
  * Custom ``min_distinct_domains``
  * Schema validation on emitted payload
  * Bus emit fail-open
  * The advisory severity contract — emitter targets ``wicked.steer.advised``
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.detectors import cross_domain_edits as detector  # noqa: E402
from crew.detectors import _common as common  # noqa: E402
from crew.steering_event_schema import validate_payload  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _detect(paths, **overrides):
    kwargs = {
        "changed_paths": paths,
        "session_id": "sess-001",
        "project_slug": "demo",
        "now": _FIXED_NOW,
    }
    kwargs.update(overrides)
    return detector.detect_cross_domain_edits(paths, **{
        k: v for k, v in kwargs.items() if k != "changed_paths"
    })


# ---------------------------------------------------------------------------
# Spec edge cases
# ---------------------------------------------------------------------------

class DomainCounting(unittest.TestCase):

    def test_two_domains_does_not_fire(self):
        paths = ["scripts/crew/x.py", "scripts/jam/y.py"]
        self.assertEqual(_detect(paths), [])

    def test_three_domains_does_not_fire_default_threshold(self):
        # Default threshold is 4 — three domains stay quiet.
        paths = ["scripts/crew/x.py", "scripts/jam/y.py", "scripts/qe/z.py"]
        self.assertEqual(_detect(paths), [])

    def test_four_domains_fires(self):
        paths = [
            "scripts/crew/x.py",
            "scripts/jam/y.py",
            "agents/qe/z.md",
            "tests/platform/w.py",
        ]
        events = _detect(paths)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            sorted(events[0]["evidence"]["distinct_domains"]),
            ["crew", "jam", "platform", "qe"],
        )

    def test_five_domains_fires(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",   "tests/platform/d.py",
            "skills/data/e.md",
        ]
        events = _detect(paths)
        self.assertEqual(len(events), 1)

    def test_empty_path_list_is_noop(self):
        self.assertEqual(_detect([]), [])

    def test_blank_paths_are_skipped(self):
        paths = ["", "   ", "scripts/crew/x.py"]
        self.assertEqual(_detect(paths), [])

    def test_unrecognized_root_paths_are_ignored(self):
        # README.md, CHANGELOG.md, src/ — not in DOMAIN_ROOTS.
        paths = [
            "README.md", "CHANGELOG.md",
            "src/foo.py", "lib/bar.py",
            "scripts/crew/a.py",
        ]
        self.assertEqual(_detect(paths), [])


# ---------------------------------------------------------------------------
# Domain extraction edge cases
# ---------------------------------------------------------------------------

class DomainExtraction(unittest.TestCase):

    def test_top_level_only_is_ignored(self):
        # 'scripts' alone has no domain segment.
        paths = ["scripts", "agents", "tests", "commands"]
        self.assertEqual(_detect(paths), [])

    def test_same_domain_across_roots_collapses(self):
        # scripts/crew + tests/crew + agents/crew + skills/crew → ONE domain.
        paths = [
            "scripts/crew/a.py",
            "tests/crew/b.py",
            "agents/crew/c.md",
            "skills/crew/d.md",
        ]
        # All collapse to "crew" — only 1 distinct domain.
        self.assertEqual(_detect(paths), [])

    def test_path_with_backslashes_normalizes(self):
        paths = [
            "scripts\\crew\\a.py", "scripts\\jam\\b.py",
            "agents\\qe\\c.md",    "tests\\platform\\d.py",
        ]
        events = _detect(paths)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            sorted(events[0]["evidence"]["distinct_domains"]),
            ["crew", "jam", "platform", "qe"],
        )

    def test_leading_dot_slash_normalizes(self):
        paths = [
            "./scripts/crew/a.py", "./scripts/jam/b.py",
            "./agents/qe/c.md",    "./tests/platform/d.py",
        ]
        events = _detect(paths)
        self.assertEqual(len(events), 1)


# ---------------------------------------------------------------------------
# Custom min_distinct_domains
# ---------------------------------------------------------------------------

class CustomThreshold(unittest.TestCase):

    def test_threshold_3_fires_on_three_domains(self):
        paths = [
            "scripts/crew/a.py",
            "scripts/jam/b.py",
            "agents/qe/c.md",
        ]
        events = _detect(paths, min_distinct_domains=3)
        self.assertEqual(len(events), 1)

    def test_threshold_below_1_raises(self):
        with self.assertRaises(ValueError):
            _detect(["scripts/crew/x.py"], min_distinct_domains=0)


# ---------------------------------------------------------------------------
# Severity contract — ADVISORY, NOT escalating
# ---------------------------------------------------------------------------

class AdvisorySeverity(unittest.TestCase):

    def test_event_type_is_advised_not_escalated(self):
        # The brainstorm decision: this detector emits `advised`, not `escalated`.
        # Locks in the rigor-escalator contract — advised events do NOT mutate rigor.
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.advised")
        self.assertNotEqual(detector.EVENT_TYPE, "wicked.steer.escalated")

    def test_recommended_action_is_notify_only(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",    "tests/platform/d.py",
        ]
        ev = _detect(paths)[0]
        self.assertEqual(ev["recommended_action"], "notify-only")

    def test_subdomain_is_correct(self):
        self.assertEqual(detector.EVENT_SUBDOMAIN, "crew.detector.cross-domain-edits")


# ---------------------------------------------------------------------------
# Schema integration
# ---------------------------------------------------------------------------

class SchemaIntegration(unittest.TestCase):

    def test_emitted_payload_passes_schema_as_advised(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",    "tests/platform/d.py",
        ]
        ev = _detect(paths)[0]
        # MUST validate against `wicked.steer.advised`.
        errors, _warnings = validate_payload(detector.EVENT_TYPE, ev)
        self.assertEqual(errors, [])

    def test_payload_contains_contributing_paths_and_domains(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",    "tests/platform/d.py",
        ]
        ev = _detect(paths)[0]
        self.assertEqual(len(ev["evidence"]["distinct_domains"]), 4)
        self.assertEqual(len(ev["evidence"]["contributing_paths"]), 4)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidation(unittest.TestCase):

    def test_empty_session_id_raises(self):
        with self.assertRaises(ValueError):
            _detect(["scripts/crew/x.py"], session_id="")

    def test_empty_project_slug_raises(self):
        with self.assertRaises(ValueError):
            _detect(["scripts/crew/x.py"], project_slug="")


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class EmitterBehavior(unittest.TestCase):

    def test_bus_unreachable_fails_open(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",    "tests/platform/d.py",
        ]
        events = _detect(paths)
        with mock.patch.object(common, "resolve_bus_command", return_value=None):
            count = detector.emit_cross_domain_edits_events(events)
        self.assertEqual(count, 0)

    def test_successful_emit_uses_advised_event_type(self):
        paths = [
            "scripts/crew/a.py", "scripts/jam/b.py",
            "agents/qe/c.md",    "tests/platform/d.py",
        ]
        events = _detect(paths)

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common, "resolve_bus_command", return_value=["wicked-bus"],
        ), mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = detector.emit_cross_domain_edits_events(events)
        self.assertEqual(count, 1)
        argv = run_mock.call_args_list[0][0][0]
        # CRITICAL: must be `advised`, not `escalated`.
        self.assertIn("wicked.steer.advised", argv)
        self.assertNotIn("wicked.steer.escalated", argv)
        self.assertIn("crew.detector.cross-domain-edits", argv)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class CliSmoke(unittest.TestCase):

    def test_dry_run_does_not_call_bus(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--paths",
                "scripts/crew/a.py", "scripts/jam/b.py",
                "agents/qe/c.md", "tests/platform/d.py",
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()

    def test_below_threshold_emits_nothing(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            rc = detector.main([
                "--session-id", "s1", "--project-slug", "demo",
                "--paths", "scripts/crew/a.py", "scripts/jam/b.py",
                "--dry-run",
            ])
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
