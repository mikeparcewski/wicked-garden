#!/usr/bin/env python3
"""tests/crew/test_reeval_addendum.py — unit tests for reeval_addendum.py (AC-α4).

Covers:
    - append round-trip (single + multiple records)
    - phase filter slicing via chain_id
    - read_latest returns the last-appended record for a phase
    - validation rejects structurally-invalid records

Stdlib-only. No external fixtures.
"""

import json
import tempfile
import unittest
from pathlib import Path

import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import reeval_addendum  # noqa: E402


def _valid_record(*, chain_suffix: str = "design") -> dict:
    """Return a structurally-valid addendum record."""
    return {
        "chain_id": f"test-project.{chain_suffix}",
        "triggered_at": "2026-04-19T14:00:00Z",
        "trigger": "phase-end",
        "prior_rigor_tier": "full",
        "new_rigor_tier": "full",
        "mutations": [],
        "mutations_applied": [],
        "mutations_deferred": [],
        "validator_version": "1.0.0",
    }


class TestAppendRoundTrip(unittest.TestCase):
    """AC-α4 + NFR-α5 — append validates, writes both targets, round-trips."""

    def test_append_writes_to_both_targets(self):
        """After append, both per-phase and project-root logs contain the record."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            rec = _valid_record(chain_suffix="design")
            reeval_addendum.append(project_dir, phase="design", record=rec)

            per_phase = project_dir / "phases" / "design" / "reeval-log.jsonl"
            project_log = project_dir / "process-plan.addendum.jsonl"
            self.assertTrue(per_phase.exists(), "per-phase JSONL missing")
            self.assertTrue(project_log.exists(), "project-root JSONL missing")

    def test_append_rejects_invalid_record(self):
        """Records missing required keys raise ValueError without writing."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            bad_record = {"chain_id": "x.design"}  # missing all other required keys
            with self.assertRaises(ValueError):
                reeval_addendum.append(project_dir, phase="design", record=bad_record)
            # Nothing written.
            self.assertFalse((project_dir / "process-plan.addendum.jsonl").exists())


class TestReadPhaseFilter(unittest.TestCase):
    """AC-α4 — phase_filter slices by chain_id suffix."""

    def test_read_returns_all_records_when_no_filter(self):
        """read() with no filter returns every appended record."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            for phase in ("clarify", "design", "build"):
                reeval_addendum.append(
                    project_dir, phase=phase, record=_valid_record(chain_suffix=phase),
                )
            recs = reeval_addendum.read(project_dir)
            self.assertEqual(len(recs), 3)

    def test_read_phase_slice_filters_correctly(self):
        """read(..., phase_filter='design') returns only design-chain records."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            for phase in ("clarify", "design", "build"):
                reeval_addendum.append(
                    project_dir, phase=phase, record=_valid_record(chain_suffix=phase),
                )
            design_recs = reeval_addendum.read(project_dir, phase_filter="design")
            self.assertEqual(len(design_recs), 1)
            self.assertIn("design", design_recs[0]["chain_id"])


class TestReadLatest(unittest.TestCase):
    """AC-α4 — read_latest returns the last-appended record for a phase."""

    def test_read_latest_returns_last_record(self):
        """When multiple design records exist, read_latest returns the last one."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            first = _valid_record(chain_suffix="design")
            first["triggered_at"] = "2026-04-19T10:00:00Z"
            second = _valid_record(chain_suffix="design")
            second["triggered_at"] = "2026-04-19T11:00:00Z"
            reeval_addendum.append(project_dir, phase="design", record=first)
            reeval_addendum.append(project_dir, phase="design", record=second)
            latest = reeval_addendum.read_latest(project_dir, phase="design")
            self.assertIsNotNone(latest)
            self.assertEqual(latest["triggered_at"], "2026-04-19T11:00:00Z")

    def test_read_latest_missing_returns_none(self):
        """read_latest on empty project returns None."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            self.assertIsNone(reeval_addendum.read_latest(project_dir, phase="design"))


if __name__ == "__main__":
    unittest.main()
