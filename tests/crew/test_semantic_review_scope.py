"""Tests for semantic_review scope fix (issue #530).

Verifies that:
- impl_dir pointing at a real source dir finds AC references in impl_corpus
- A spec-only project_dir no longer causes an empty corpus (and thus bogus REJECT)
- Spec files themselves are still excluded from the scan (self-match prevention)

Deterministic. Stdlib-only.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "qe"))

import semantic_review  # noqa: E402


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestImplDirOverride(unittest.TestCase):
    """AC-1: impl_dir pointing at a dir with AC refs finds them in impl_corpus."""

    def test_ac_found_in_impl_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Spec file
            ac_file = tmp_path / "phases" / "clarify" / "acceptance-criteria.md"
            _write(ac_file, "## AC-1\nThe system must handle retries.\n")

            # Implementation file in a *separate* impl dir
            impl_dir = tmp_path / "src"
            _write(impl_dir / "retry.py", "# AC-1 implemented here\ndef retry(): pass\n")

            report = semantic_review.review_project(
                project_dir=tmp_path,
                project_name="test-impl-dir",
                complexity=3,
                ac_file=ac_file,
                impl_dir=impl_dir,
            )

            ac1_findings = [f for f in report.findings if f.id == "AC-1"]
            self.assertEqual(len(ac1_findings), 1, "AC-1 finding should exist")
            self.assertTrue(
                ac1_findings[0].in_impl,
                "AC-1 should be found in impl_corpus when impl_dir is set correctly",
            )


class TestSpecOnlyProjectDir(unittest.TestCase):
    """AC-2: spec-only project_dir no longer causes empty corpus leading to REJECT."""

    def test_spec_only_project_dir_with_impl_dir_finds_items(self):
        """When project_dir has only phases/, impl_dir provides the real corpus."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # project_dir contains only phases/ (crew project layout)
            ac_file = tmp_path / "project" / "phases" / "clarify" / "acceptance-criteria.md"
            _write(ac_file, "## AC-2\nMust support pagination.\n")

            # Actual implementation lives outside project_dir
            impl_dir = tmp_path / "repo" / "src"
            _write(impl_dir / "api.py", "# AC-2: pagination implemented\ndef paginate(): pass\n")

            project_dir = tmp_path / "project"
            report = semantic_review.review_project(
                project_dir=project_dir,
                project_name="test-spec-only",
                complexity=3,
                ac_file=ac_file,
                impl_dir=impl_dir,
            )

            ac2_findings = [f for f in report.findings if f.id == "AC-2"]
            self.assertEqual(len(ac2_findings), 1, "AC-2 finding should exist")
            # With impl_dir pointing at real src, AC-2 should not be 'missing'
            self.assertNotEqual(
                ac2_findings[0].status,
                "missing",
                "AC-2 must not be 'missing' when impl_dir contains a reference",
            )

    def test_spec_only_project_dir_without_impl_dir_yields_missing(self):
        """Regression: without an impl_dir override a phases-only project_dir
        returns missing for every AC (the old broken behavior, preserved as-is
        to verify the default code path still works correctly for callers who
        do not pass impl_dir)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            ac_file = tmp_path / "phases" / "clarify" / "acceptance-criteria.md"
            _write(ac_file, "## AC-3\nMust support export.\n")

            # Only phases/ exists — no impl files
            (tmp_path / "phases" / "review").mkdir(parents=True, exist_ok=True)

            report = semantic_review.review_project(
                project_dir=tmp_path,
                project_name="test-empty-corpus",
                complexity=3,
                ac_file=ac_file,
            )

            ac3_findings = [f for f in report.findings if f.id == "AC-3"]
            # With no impl files at all, AC-3 is 'missing' — that is correct
            if ac3_findings:
                self.assertEqual(
                    ac3_findings[0].status,
                    "missing",
                    "AC-3 should be 'missing' when corpus is genuinely empty",
                )


class TestSpecFileExclusion(unittest.TestCase):
    """AC-3: spec files are never self-matched even when impl_dir == project_dir."""

    def test_spec_file_not_in_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            ac_file = tmp_path / "acceptance-criteria.md"
            _write(ac_file, "## AC-4\nMust handle errors.\n")

            # implementation also in same dir — but spec must be excluded
            _write(tmp_path / "impl.py", "# AC-4: error handler\ndef handle(): pass\n")

            report = semantic_review.review_project(
                project_dir=tmp_path,
                project_name="test-spec-exclude",
                complexity=3,
                ac_file=ac_file,
                impl_dir=tmp_path,
            )

            # impl.py has AC-4, so it should be found — but the spec itself
            # should never be the *sole* reason a finding is 'aligned'
            ac4_findings = [f for f in report.findings if f.id == "AC-4"]
            self.assertEqual(len(ac4_findings), 1, "AC-4 should appear once")

            # Verify the spec file path is not listed as impl evidence
            ac4 = ac4_findings[0]
            spec_path = str(ac_file)
            for ev in ac4.evidence:
                self.assertNotIn(
                    spec_path, ev,
                    "Spec file must not appear as impl evidence (self-match prevention)",
                )


if __name__ == "__main__":
    unittest.main()
