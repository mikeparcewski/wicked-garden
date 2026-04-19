#!/usr/bin/env python3
"""
Unit tests for scripts/crew/amendments.py (issue #478).

Covers:
    - append writes a JSONL record and assigns a monotonic scope_version.
    - Validator rejects bad triggers and missing required fields.
    - list_amendments merges JSONL + legacy design-addendum-N.md.
    - render_markdown produces a non-empty report with section headers.
    - scope_version continues counting past legacy .md addenda.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "crew"))

import amendments  # noqa: E402  (path setup above)


class AppendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.phase_dir = Path(self.tmp.name) / "phases" / "design"

    def test_append_assigns_monotonic_scope_version(self) -> None:
        r1 = amendments.append(
            self.phase_dir,
            trigger="gate-conditional",
            summary="first fix",
        )
        r2 = amendments.append(
            self.phase_dir,
            trigger="re-eval",
            summary="second fix",
        )
        self.assertEqual(r1["scope_version"], 1)
        self.assertEqual(r2["scope_version"], 2)

        # JSONL file has exactly two lines.
        path = self.phase_dir / "amendments.jsonl"
        self.assertTrue(path.exists())
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)

        # Each line is a valid JSON object with the expected keys.
        parsed = [json.loads(ln) for ln in lines]
        for rec in parsed:
            for key in ("amendment_id", "trigger", "scope_version",
                        "timestamp", "summary", "patches", "resolution_refs"):
                self.assertIn(key, rec)

    def test_append_rejects_invalid_trigger(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            amendments.append(
                self.phase_dir,
                trigger="not-a-real-trigger",
                summary="x",
            )
        self.assertIn("trigger", str(ctx.exception).lower())

    def test_append_rejects_missing_summary(self) -> None:
        with self.assertRaises(ValueError):
            amendments.append(
                self.phase_dir,
                trigger="manual",
                summary="",
            )

    def test_append_rejects_non_list_patches(self) -> None:
        with self.assertRaises(ValueError):
            amendments.append(
                self.phase_dir,
                trigger="manual",
                summary="ok",
                patches={"not": "a list"},  # type: ignore[arg-type]
            )

    def test_append_accepts_and_preserves_resolution_refs(self) -> None:
        record = amendments.append(
            self.phase_dir,
            trigger="gate-conditional",
            summary="clarify acceptance criterion",
            patches=[{"target": "design.md#FR-3", "operation": "replace",
                      "rationale": "align with SLO"}],
            resolution_refs=["CONDITION-1", "CONDITION-2"],
        )
        self.assertEqual(
            record["resolution_refs"], ["CONDITION-1", "CONDITION-2"]
        )
        self.assertEqual(len(record["patches"]), 1)


class LegacyCompatTests(unittest.TestCase):
    """Legacy design-addendum-N.md files remain readable and count toward
    the scope_version sequence."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.phase_dir = Path(self.tmp.name) / "phases" / "design"
        self.phase_dir.mkdir(parents=True)

        # Plant two legacy .md addenda (versions 1 and 2).
        (self.phase_dir / "design-addendum-1.md").write_text(
            "# Addendum 1\n\nearly fix.\n"
        )
        (self.phase_dir / "design-addendum-2.md").write_text(
            "# Addendum 2\n\nsecond fix.\n"
        )

    def test_scope_version_continues_past_legacy(self) -> None:
        record = amendments.append(
            self.phase_dir,
            trigger="manual",
            summary="third fix (JSONL)",
        )
        # Legacy 1, legacy 2, new -> scope_version = 3.
        self.assertEqual(record["scope_version"], 3)

    def test_list_amendments_surfaces_legacy(self) -> None:
        amendments.append(
            self.phase_dir,
            trigger="manual",
            summary="jsonl fix",
        )
        records = amendments.list_amendments(self.phase_dir)
        sources = [r.get("source") for r in records]
        self.assertEqual(sources.count("legacy-md"), 2)
        self.assertEqual(sources.count("jsonl"), 1)

        # Ordered by scope_version.
        versions = [r.get("scope_version") for r in records]
        self.assertEqual(versions, sorted(versions))

    def test_list_amendments_excludes_legacy_when_requested(self) -> None:
        amendments.append(
            self.phase_dir,
            trigger="manual",
            summary="jsonl fix",
        )
        records = amendments.list_amendments(
            self.phase_dir, include_legacy=False
        )
        sources = [r.get("source") for r in records]
        self.assertNotIn("legacy-md", sources)


class RenderTests(unittest.TestCase):
    def test_render_empty(self) -> None:
        rendered = amendments.render_markdown([])
        self.assertIn("Amendments", rendered)
        self.assertIn("No amendments", rendered)

    def test_render_includes_patches_and_refs(self) -> None:
        record = {
            "amendment_id": "AMD-test-20260101",
            "trigger": "gate-conditional",
            "scope_version": 1,
            "timestamp": "2026-01-01T00:00:00Z",
            "summary": "fix threshold",
            "patches": [
                {"target": "design.md#FR-3", "operation": "replace",
                 "rationale": "align with SLO"}
            ],
            "resolution_refs": ["CONDITION-1"],
        }
        rendered = amendments.render_markdown([record])
        self.assertIn("v1", rendered)
        self.assertIn("AMD-test", rendered)
        self.assertIn("design.md#FR-3", rendered)
        self.assertIn("CONDITION-1", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
