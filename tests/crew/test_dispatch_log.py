"""Tests for ``scripts/crew/dispatch_log.py`` (#471, AC-7).

Covers:
  - ``append()`` + ``read_entries()`` round-trip
  - ``check_orphan()`` graceful-degrade before strict-after
  - ``check_orphan()`` REJECT after strict-after
  - ``WG_GATE_RESULT_DISPATCH_CHECK=off`` scoped bypass
  - Malformed dispatch-log line is skipped (not fatal)

Deterministic. No wall-clock dependency in assertions — tests that
exercise the date flip set the env var explicitly rather than relying
on today's date.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import dispatch_log  # noqa: E402
from dispatch_log import append, check_orphan, read_entries, read_latest  # noqa: E402
from gate_result_schema import GateResultAuthorizationError  # noqa: E402


def _make_project(tmp: str, phase: str = "design") -> Path:
    project = Path(tmp) / "proj"
    (project / "phases" / phase).mkdir(parents=True)
    return project


class AppendAndRead(unittest.TestCase):
    def test_append_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(project, "design", reviewer="security-engineer",
                   gate="design-quality", dispatch_id="d-1",
                   dispatched_at="2026-04-19T10:00:00+00:00")
            entries = read_entries(project, "design")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["reviewer"], "security-engineer")
            self.assertEqual(entries[0]["dispatch_id"], "d-1")

    def test_read_entries_skips_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            log_path.write_text(
                json.dumps({"reviewer": "a", "phase": "design",
                            "gate": "g", "dispatched_at": "2026-04-19T00:00:00+00:00",
                            "dispatch_id": "d-1"}) + "\n"
                + "not-json\n"
                + json.dumps({"reviewer": "b", "phase": "design",
                              "gate": "g", "dispatched_at": "2026-04-19T01:00:00+00:00",
                              "dispatch_id": "d-2"}) + "\n"
            )
            entries = read_entries(project, "design")
            # Malformed line skipped; two valid entries survive.
            self.assertEqual(len(entries), 2)
            self.assertEqual({e["dispatch_id"] for e in entries}, {"d-1", "d-2"})

    def test_read_latest_picks_newest_dispatched_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(project, "design", reviewer="r1", gate="g",
                   dispatch_id="d-old",
                   dispatched_at="2026-04-19T00:00:00+00:00")
            append(project, "design", reviewer="r2", gate="g",
                   dispatch_id="d-new",
                   dispatched_at="2026-04-19T05:00:00+00:00")
            latest = read_latest(project, "design", "g")
            self.assertIsNotNone(latest)
            self.assertEqual(latest["dispatch_id"], "d-new")


class CheckOrphanSoftWindow(unittest.TestCase):
    """Before strict-after: orphan → raise, caller audits + accepts."""

    def test_orphan_raises_authorization_error_pre_flip(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            parsed = {
                "reviewer": "rogue",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            with self.assertRaises(GateResultAuthorizationError) as cm:
                check_orphan(parsed, project, "design")
            self.assertEqual(
                cm.exception.reason,
                "unauthorized-gate-result:no-dispatch-record",
            )
            self.assertEqual(cm.exception.violation_class, "authorization")

    def test_matching_dispatch_entry_accepts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(project, "design",
                   reviewer="security-engineer",
                   gate="design-quality",
                   dispatch_id="d-1",
                   dispatched_at="2026-04-19T09:00:00+00:00")
            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            # No raise — the entry matches.
            check_orphan(parsed, project, "design")

    def test_dispatched_at_after_recorded_at_fails_match(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(project, "design",
                   reviewer="r",
                   gate="g",
                   dispatch_id="d-1",
                   dispatched_at="2026-04-19T12:00:00+00:00")
            parsed = {
                "reviewer": "r",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "g",
            }
            with self.assertRaises(GateResultAuthorizationError):
                check_orphan(parsed, project, "design")


class CheckOrphanStrictWindow(unittest.TestCase):
    def test_orphan_raises_post_flip_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2020-01-01"},
        ):
            project = _make_project(tmp)
            parsed = {"reviewer": "x", "recorded_at":
                      "2026-04-19T10:00:00+00:00", "gate": "g"}
            with self.assertRaises(GateResultAuthorizationError):
                check_orphan(parsed, project, "design")


class DispatchCheckDisabled(unittest.TestCase):
    def test_off_flag_bypasses_orphan_detection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "WG_GATE_RESULT_DISPATCH_CHECK": "off",
                "WG_GATE_RESULT_STRICT_AFTER": "2099-01-01",
            },
        ):
            project = _make_project(tmp)
            parsed = {"reviewer": "nomatch",
                      "recorded_at": "2026-04-19T10:00:00+00:00", "gate": "g"}
            # No raise — disabled.
            check_orphan(parsed, project, "design")


if __name__ == "__main__":
    unittest.main()
