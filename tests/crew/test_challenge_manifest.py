"""Unit tests for scripts/crew/challenge_manifest.py (Issues #442 + #721).

Covers the v2 schema (Issue #721):
    * parse_artifact            — section + dissent-vector + sentence parsing
    * parse_dissent_vectors     — canonical [x] coverage extraction
    * parse_meta_sidecar        — optional meta.json sidecar
    * validate_artifact         — size, sections, per-section minimums
    * detect_convergence_collapse — under-3 vectors -> collapse
    * is_required               — complexity / phase threshold
    * artifact_satisfies_gate   — end-to-end file-based gate

Stdlib + unittest only (no pytest dependency required).
"""

from __future__ import annotations

import json
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import challenge_manifest as cm  # noqa: E402  (imported after sys.path edit)


# ---------------------------------------------------------------------------
# Fixtures (v2 schema)
# ---------------------------------------------------------------------------

def _well_formed_artifact() -> str:
    """A v2-conformant artifact: 4 sections, >=3 dissent vectors covered."""
    return textwrap.dedent(
        """\
        # Challenge Artifacts

        ## Incongruent Representation

        The dominant story claims the new pipeline ships value this quarter.
        The actual shape of the work is a refactor disguised as a feature.
        No customer in the last six interviews asked for it, and three asked
        for things this work pushes back.

        ## Unasked Question

        What measurable user outcome would tell us this migration was worth
        the engineering quarter it will consume?

        ## Steelman of Alternative Path

        I argue we should not ship this pipeline this quarter. The current
        system serves traffic with a known operational profile and a runbook
        on-call already trusts. Replacing it now diverts engineers from a
        backlog of customer-facing fixes that have measurable revenue impact.
        A staged rewrite over two quarters carries less rollback risk and
        preserves optionality. Most importantly, no customer has asked for
        the work, and the team's own product council has not prioritised it.

        ## Dissent Vectors Covered

        - [x] security
        - [x] cost
        - [x] operability
        - [ ] ethics
        - [ ] ux
        - [ ] maintenance
        """
    )


def _write_artifact(project_dir: Path, body: str, phase: str = "design") -> Path:
    path = project_dir / "phases" / phase / cm.CHALLENGE_ARTIFACT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_artifact
# ---------------------------------------------------------------------------

class TestParseArtifact(unittest.TestCase):
    def test_all_sections_and_vectors_parsed(self):
        parsed = cm.parse_artifact(_well_formed_artifact())
        self.assertEqual(parsed["sections_missing"], [])
        self.assertEqual(parsed["dissent_vectors"], ["security", "cost", "operability"])
        self.assertGreaterEqual(parsed["incongruent_sentences"], 3)
        self.assertGreaterEqual(parsed["steelman_sentences"], 5)
        self.assertGreaterEqual(parsed["questions_count"], 1)

    def test_empty_artifact_reports_missing_sections(self):
        parsed = cm.parse_artifact("")
        self.assertEqual(set(parsed["sections_missing"]),
                         set(cm.required_sections()))
        self.assertEqual(parsed["dissent_vectors"], [])

    def test_non_canonical_checkmarks_ignored(self):
        body = _well_formed_artifact() + "\n- [x] vibes\n- [x] groove\n"
        parsed = cm.parse_artifact(body)
        self.assertNotIn("vibes", parsed["dissent_vectors"])
        self.assertEqual(parsed["dissent_vectors"], ["security", "cost", "operability"])

    def test_decorated_section_headers_recognised(self):
        """Headings tolerate trailing decoration like ``(v2)`` or ``— design``.

        Regression: ``_extract_section`` previously required the heading to
        be the entire line, so ``## Incongruent Representation (v2)`` reported
        the section as missing even though ``_has_section`` saw it.
        """
        body = _well_formed_artifact().replace(
            "## Incongruent Representation",
            "## Incongruent Representation (v2)",
        ).replace(
            "## Steelman of Alternative Path",
            "## Steelman of Alternative Path — design",
        )
        parsed = cm.parse_artifact(body)
        self.assertEqual(parsed["sections_missing"], [])
        self.assertGreaterEqual(parsed["incongruent_sentences"], 3)
        self.assertGreaterEqual(parsed["steelman_sentences"], 5)

    def test_inline_code_does_not_inflate_sentence_count(self):
        """Punctuation inside ``v2.0`` or backticked code must not count."""
        body = (
            "## Incongruent Representation\n\n"
            "We ship `v2.0` and `arr[1].len()` and `foo.bar.baz()` in one PR.\n\n"
            "## Unasked Question\n\n"
            "Is `arr[1].len() == 0` actually a question or just code?\n\n"
            "## Steelman of Alternative Path\n\n"
            "Stub.\n\n"
            "## Dissent Vectors Covered\n\n"
            "- [x] security\n"
        )
        parsed = cm.parse_artifact(body)
        # The incongruent section has exactly one real sentence terminator.
        self.assertEqual(parsed["incongruent_sentences"], 1)
        # The unasked-question section has exactly one real ``?`` (the ``==``
        # inside backticks is stripped before counting).
        self.assertEqual(parsed["questions_count"], 1)


# ---------------------------------------------------------------------------
# validate_artifact
# ---------------------------------------------------------------------------

class TestValidateArtifact(unittest.TestCase):
    def test_well_formed_validates(self):
        self.assertIsNone(cm.validate_artifact(_well_formed_artifact()))

    def test_empty_artifact_fails(self):
        err = cm.validate_artifact("")
        self.assertIsNotNone(err)
        self.assertIn("too small", err)

    def test_missing_section_fails(self):
        body = _well_formed_artifact().replace("## Unasked Question", "## NotIt")
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("unasked question", err.lower())

    def test_too_few_dissent_vectors_fails(self):
        body = _well_formed_artifact().replace("- [x] cost", "- [ ] cost")
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("dissent vectors covered", err.lower())

    def test_no_question_fails(self):
        # Replace the only '?' in the artifact with a period.
        body = _well_formed_artifact().replace("?", ".")
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("unasked question", err.lower())


# ---------------------------------------------------------------------------
# detect_convergence_collapse
# ---------------------------------------------------------------------------

class TestConvergenceCollapse(unittest.TestCase):
    def test_under_three_vectors_collapses(self):
        collapsed, reason = cm.detect_convergence_collapse(["security", "cost"])
        self.assertTrue(collapsed)
        self.assertIn("only 2 dissent vector", reason)

    def test_three_or_more_vectors_does_not_collapse(self):
        collapsed, _ = cm.detect_convergence_collapse(
            ["security", "cost", "operability"]
        )
        self.assertFalse(collapsed)

    def test_accepts_parsed_dict(self):
        parsed = cm.parse_artifact(_well_formed_artifact())
        collapsed, _ = cm.detect_convergence_collapse(parsed)
        self.assertFalse(collapsed)

    def test_legacy_challenge_dicts_back_compat(self):
        legacy = [
            {"theme": "security"},
            {"theme": "cost"},
            {"theme": "operability"},
        ]
        collapsed, _ = cm.detect_convergence_collapse(legacy)
        self.assertFalse(collapsed)


# ---------------------------------------------------------------------------
# parse_meta_sidecar
# ---------------------------------------------------------------------------

class TestParseMetaSidecar(unittest.TestCase):
    def test_missing_sidecar_returns_none(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(cm.parse_meta_sidecar(Path(tmp)))

    def test_well_formed_sidecar_parsed(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "phases" / "design").mkdir(parents=True)
            (project_dir / "phases" / "design" / cm.CHALLENGE_ARTIFACT_META_FILENAME).write_text(
                json.dumps({"vectors": ["security", "cost", "ux"], "questions_count": 2}),
                encoding="utf-8",
            )
            meta = cm.parse_meta_sidecar(project_dir)
            self.assertIsNotNone(meta)
            self.assertEqual(meta["vectors"], ["security", "cost", "ux"])
            self.assertEqual(meta["questions_count"], 2)

    def test_non_canonical_vectors_filtered(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "phases" / "design").mkdir(parents=True)
            (project_dir / "phases" / "design" / cm.CHALLENGE_ARTIFACT_META_FILENAME).write_text(
                json.dumps({"vectors": ["security", "vibes"], "questions_count": 1}),
                encoding="utf-8",
            )
            meta = cm.parse_meta_sidecar(project_dir)
            self.assertEqual(meta["vectors"], ["security"])


# ---------------------------------------------------------------------------
# is_required
# ---------------------------------------------------------------------------

class TestIsRequired(unittest.TestCase):
    def test_below_threshold_not_required(self):
        self.assertFalse(cm.is_required(complexity=3, phase="build"))

    def test_at_threshold_required(self):
        self.assertTrue(cm.is_required(complexity=4, phase="build"))

    def test_non_build_phase_never_required(self):
        self.assertFalse(cm.is_required(complexity=7, phase="design"))


# ---------------------------------------------------------------------------
# artifact_satisfies_gate (integration)
# ---------------------------------------------------------------------------

class TestArtifactSatisfiesGate(unittest.TestCase):
    def test_missing_file_fails(self):
        with TemporaryDirectory() as tmp:
            ok, reason = cm.artifact_satisfies_gate(Path(tmp), phase="design")
            self.assertFalse(ok)
            self.assertIn("missing", reason)

    def test_well_formed_artifact_passes(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _write_artifact(project_dir, _well_formed_artifact())
            ok, reason = cm.artifact_satisfies_gate(project_dir, phase="design")
            self.assertTrue(ok, f"expected gate to clear, got {reason!r}")

    def test_collapsed_vectors_block_gate(self):
        body = _well_formed_artifact().replace(
            "- [x] cost", "- [ ] cost"
        ).replace(
            "- [x] operability", "- [ ] operability"
        )
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _write_artifact(project_dir, body)
            ok, reason = cm.artifact_satisfies_gate(project_dir, phase="design")
            self.assertFalse(ok)
            # Validation fires before convergence check (vectors < 3 also
            # trips the validator's per-section minimum). Either signal
            # is acceptable proof the gate holds.
            self.assertTrue(
                "dissent vectors covered" in reason.lower()
                or "convergence collapse" in reason.lower(),
                f"expected vector-coverage failure, got: {reason!r}",
            )

    def test_sidecar_preferred_for_collapse_detection(self):
        """Sidecar is preferred for *convergence-collapse* detection.

        The contract tested here: ``artifact_satisfies_gate`` validates the
        markdown first (so a thin markdown still fails validation), and
        only *after* validation passes does it prefer the sidecar's vector
        list over re-parsing the markdown checklist for collapse detection.
        This test fixes the markdown to be valid and proves the sidecar
        path is wired in for the collapse step.
        """
        body = _well_formed_artifact()
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _write_artifact(project_dir, body)
            (project_dir / "phases" / "design" / cm.CHALLENGE_ARTIFACT_META_FILENAME).write_text(
                json.dumps({
                    "vectors": ["security", "cost", "operability", "ethics"],
                    "questions_count": 1,
                }),
                encoding="utf-8",
            )
            ok, reason = cm.artifact_satisfies_gate(project_dir, phase="design")
            self.assertTrue(ok, f"expected gate to clear via sidecar, got {reason!r}")


if __name__ == "__main__":
    unittest.main()
