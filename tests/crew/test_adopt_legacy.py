"""Unit tests for scripts/crew/adopt_legacy.py (D5, AC-13 c).

Tests:
    TestDetectMissingPhasePlanMode   — Marker 1 detection + transformation + idempotency
    TestDetectMarkdownReeval         — Marker 2 detection + transformation + idempotency
    TestDetectLegacyBypass           — Marker 3 detection + transformation + idempotency
    TestScanProject                  — scan_project() aggregates all markers
    TestApplyTransformations         — apply_transformations() side-effects + dry-run
    TestV6NativeProjectNoOp          — v6-native project reports zero markers

All tests are deterministic (no wall-clock, no random, no sleep).
Stdlib-only. No external dependencies.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import adopt_legacy as al
from adopt_legacy import (
    _detect_missing_phase_plan_mode,
    _detect_markdown_reeval,
    _detect_legacy_bypass_files,
    scan_project,
    apply_transformations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_dir(tmp_path: Path) -> Path:
    """Return a minimal v6-native project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps({"name": "test-project", "phase_plan_mode": "facilitator"}),
        encoding="utf-8",
    )
    return project_dir


# ---------------------------------------------------------------------------
# Marker 1: missing phase_plan_mode
# ---------------------------------------------------------------------------

class TestDetectMissingPhasePlanMode(unittest.TestCase):

    def test_detects_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "proj"}), encoding="utf-8"
            )
            self.assertTrue(_detect_missing_phase_plan_mode(d))

    def test_no_detection_when_key_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "proj", "phase_plan_mode": "facilitator"}),
                encoding="utf-8",
            )
            self.assertFalse(_detect_missing_phase_plan_mode(d))

    def test_no_detection_when_no_project_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            self.assertFalse(_detect_missing_phase_plan_mode(d))

    def test_transformation_sets_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "proj"}), encoding="utf-8"
            )
            al._transform_phase_plan_mode(d, dry_run=False)
            data = json.loads((d / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(data["phase_plan_mode"], "facilitator")

    def test_transformation_idempotent(self):
        """Re-running after transformation does not change the file again."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "proj"}), encoding="utf-8"
            )
            al._transform_phase_plan_mode(d, dry_run=False)
            al._transform_phase_plan_mode(d, dry_run=False)
            data = json.loads((d / "project.json").read_text(encoding="utf-8"))
            # Should have exactly one phase_plan_mode key
            self.assertEqual(data["phase_plan_mode"], "facilitator")
            self.assertFalse(_detect_missing_phase_plan_mode(d))

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            original = json.dumps({"name": "proj"})
            (d / "project.json").write_text(original, encoding="utf-8")
            al._transform_phase_plan_mode(d, dry_run=True)
            after = (d / "project.json").read_text(encoding="utf-8")
            self.assertEqual(original, after)


# ---------------------------------------------------------------------------
# Marker 2: markdown re-eval addendum
# ---------------------------------------------------------------------------

class TestDetectMarkdownReeval(unittest.TestCase):

    def test_detects_markdown_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "process-plan.md").write_text(
                "## Re-evaluation 2026-04-18\n\nsome content\n",
                encoding="utf-8",
            )
            hits = _detect_markdown_reeval(d)
            self.assertEqual(len(hits), 1)

    def test_no_detection_when_jsonl_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "process-plan.md").write_text(
                "# Plan\n\n## 10. Re-evaluation log\n\nNo entries.\n",
                encoding="utf-8",
            )
            hits = _detect_markdown_reeval(d)
            self.assertEqual(hits, [])

    def test_transformation_strips_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "process-plan.md").write_text(
                "# Plan\n\n## Re-evaluation 2026-04-18\n\nsome content\n",
                encoding="utf-8",
            )
            al._transform_markdown_reeval(
                d, str(d / "process-plan.md"), dry_run=False
            )
            after = (d / "process-plan.md").read_text(encoding="utf-8")
            # Original header replaced
            self.assertNotIn("## Re-evaluation 2026-04-18", after)

    def test_transformation_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "process-plan.md").write_text(
                "## Re-evaluation 2026-04-18T12:00:00Z\n\nsome content\n",
                encoding="utf-8",
            )
            al._transform_markdown_reeval(
                d, str(d / "process-plan.md"), dry_run=False
            )
            # At least one JSONL file was written somewhere under phases/
            jsonl_files = list((d / "phases").rglob("reeval-log.jsonl"))
            self.assertGreater(len(jsonl_files), 0)
            # Each line must be valid JSON
            for jf in jsonl_files:
                for line in jf.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        record = json.loads(line)
                        self.assertIn("chain_id", record)
                        self.assertIn("triggered_at", record)

    def test_transformation_idempotent(self):
        """Second run on the same file detects no more markers."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "process-plan.md").write_text(
                "## Re-evaluation 2026-04-18\n\nsome content\n",
                encoding="utf-8",
            )
            al._transform_markdown_reeval(
                d, str(d / "process-plan.md"), dry_run=False
            )
            hits_after = _detect_markdown_reeval(d)
            self.assertEqual(hits_after, [])

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            content = "## Re-evaluation 2026-04-18\n\nsome content\n"
            (d / "process-plan.md").write_text(content, encoding="utf-8")
            al._transform_markdown_reeval(
                d, str(d / "process-plan.md"), dry_run=True
            )
            after = (d / "process-plan.md").read_text(encoding="utf-8")
            self.assertEqual(content, after)


# ---------------------------------------------------------------------------
# Marker 3: legacy gate-bypass reference
# ---------------------------------------------------------------------------

class TestDetectLegacyBypass(unittest.TestCase):

    _LEGACY_SNIPPET = "Set CREW_GATE_ENFORCEMENT=legacy to bypass checks.\n"

    def test_detects_in_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "status.md").write_text(self._LEGACY_SNIPPET, encoding="utf-8")
            hits = _detect_legacy_bypass_files(d)
            self.assertEqual(len(hits), 1)
            self.assertIn("status.md", hits[0])

    def test_detects_in_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "config.json").write_text(
                '{"note": "CREW_GATE_ENFORCEMENT=legacy was the old bypass"}',
                encoding="utf-8",
            )
            hits = _detect_legacy_bypass_files(d)
            self.assertEqual(len(hits), 1)

    def test_no_detection_in_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "status.md").write_text("All clear.\n", encoding="utf-8")
            hits = _detect_legacy_bypass_files(d)
            self.assertEqual(hits, [])

    def test_transformation_replaces_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "status.md").write_text(self._LEGACY_SNIPPET, encoding="utf-8")
            file_path = str(d / "status.md")
            al._transform_legacy_bypass(d, file_path, dry_run=False)
            after = (d / "status.md").read_text(encoding="utf-8")
            self.assertNotIn("CREW_GATE_ENFORCEMENT", after)
            self.assertIn("removed in v6.0", after)

    def test_transformation_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "status.md").write_text(self._LEGACY_SNIPPET, encoding="utf-8")
            file_path = str(d / "status.md")
            al._transform_legacy_bypass(d, file_path, dry_run=False)
            hits_after = _detect_legacy_bypass_files(d)
            self.assertEqual(hits_after, [])

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "proj"
            d.mkdir()
            (d / "status.md").write_text(self._LEGACY_SNIPPET, encoding="utf-8")
            file_path = str(d / "status.md")
            al._transform_legacy_bypass(d, file_path, dry_run=True)
            after = (d / "status.md").read_text(encoding="utf-8")
            self.assertEqual(self._LEGACY_SNIPPET, after)


# ---------------------------------------------------------------------------
# scan_project aggregation
# ---------------------------------------------------------------------------

class TestScanProject(unittest.TestCase):

    def test_all_three_markers_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "legacy-proj"
            d.mkdir()
            # Marker 1: project.json without phase_plan_mode
            (d / "project.json").write_text(
                json.dumps({"name": "legacy-proj"}), encoding="utf-8"
            )
            # Marker 2: markdown re-eval in process-plan.md
            (d / "process-plan.md").write_text(
                "## Re-evaluation 2026-01-01\n\nold content\n",
                encoding="utf-8",
            )
            # Marker 3: legacy bypass in status.md
            (d / "status.md").write_text(
                "CREW_GATE_ENFORCEMENT=legacy was used here\n",
                encoding="utf-8",
            )
            markers, warnings = scan_project(d)
            self.assertEqual(len(warnings), 0)
            self.assertEqual(len(markers), 3)
            marker_types = {m.split(":")[0] for m in markers}
            self.assertIn("missing-phase_plan_mode", marker_types)
            self.assertIn("markdown-reeval", marker_types)
            self.assertIn("legacy-bypass", marker_types)

    def test_nonexistent_dir_returns_warning(self):
        markers, warnings = scan_project(Path("/nonexistent/path/that/does/not/exist"))
        self.assertEqual(markers, [])
        self.assertEqual(len(warnings), 1)


# ---------------------------------------------------------------------------
# apply_transformations full integration
# ---------------------------------------------------------------------------

class TestApplyTransformations(unittest.TestCase):

    def test_apply_all_three_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "full-legacy"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "full-legacy"}), encoding="utf-8"
            )
            (d / "process-plan.md").write_text(
                "## Re-evaluation 2026-02-01\nsome text\n",
                encoding="utf-8",
            )
            (d / "status.md").write_text(
                "CREW_GATE_ENFORCEMENT=legacy was here\n",
                encoding="utf-8",
            )
            markers, _ = scan_project(d)
            self.assertEqual(len(markers), 3)
            apply_transformations(d, markers, dry_run=False)
            # After apply: no markers remain
            markers_after, _ = scan_project(d)
            self.assertEqual(markers_after, [])

    def test_dry_run_leaves_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "dry-run-proj"
            d.mkdir()
            pj_content = json.dumps({"name": "dry-run-proj"})
            pp_content = "## Re-evaluation 2026-03-01\ntext\n"
            (d / "project.json").write_text(pj_content, encoding="utf-8")
            (d / "process-plan.md").write_text(pp_content, encoding="utf-8")
            markers, _ = scan_project(d)
            apply_transformations(d, markers, dry_run=True)
            # Files unchanged
            self.assertEqual(
                (d / "project.json").read_text(encoding="utf-8"), pj_content
            )
            self.assertEqual(
                (d / "process-plan.md").read_text(encoding="utf-8"), pp_content
            )


# ---------------------------------------------------------------------------
# v6-native project is a no-op
# ---------------------------------------------------------------------------

class TestV6NativeProjectNoOp(unittest.TestCase):

    def test_v6_native_zero_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "v6-native"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "v6-native", "phase_plan_mode": "facilitator"}),
                encoding="utf-8",
            )
            (d / "process-plan.md").write_text(
                "# Plan\n\n## 10. Re-evaluation log\n\nNo entries.\n",
                encoding="utf-8",
            )
            markers, warnings = scan_project(d)
            self.assertEqual(markers, [])
            self.assertEqual(warnings, [])

    def test_apply_on_empty_markers_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "v6-native"
            d.mkdir()
            (d / "project.json").write_text(
                json.dumps({"name": "v6-native", "phase_plan_mode": "facilitator"}),
                encoding="utf-8",
            )
            outcomes = apply_transformations(d, [], dry_run=False)
            self.assertEqual(outcomes, [])


if __name__ == "__main__":
    unittest.main()
