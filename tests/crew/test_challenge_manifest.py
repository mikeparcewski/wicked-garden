"""Unit tests for scripts/crew/challenge_manifest.py (Issue #442).

Covers:
    * parse_artifact           — section and challenge-block parsing
    * validate_artifact        — size, sections, steelman-required rule
    * detect_convergence_collapse
    * is_required              — complexity / phase threshold
    * artifact_satisfies_gate  — end-to-end file-based gate

All deterministic (no sleep, no wall-clock, no real paths outside a tmp).
Stdlib + pytest + unittest only.
"""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import challenge_manifest as cm  # noqa: E402  (imported after sys.path edit)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _well_formed_artifact() -> str:
    """A valid challenge artifact with 3 themes and all required sections."""
    return textwrap.dedent(
        """\
        # Challenge Artifacts

        ## Strongest Opposing View

        The proposed architecture trades operational simplicity for a
        novel coordination primitive. The best version of the opposite
        position is that the existing queue-based integration has
        delivered three years of reliable throughput and its failure
        modes are fully understood by on-call.

        ## Challenges

        ### Challenge CH-01: novel-coordination-primitive
        - theme: correctness
        - raised_by: contrarian
        - status: resolved
        - steelman: Current queue semantics are well-understood and
          have stood up to production load for three years. The new
          primitive introduces unknown-unknowns that a rewrite does not.

        ### Challenge CH-02: observability-regression
        - theme: operability
        - raised_by: contrarian
        - status: open
        - steelman: Today on-call can grep one log stream. The new
          design fragments traces across four services and that
          fragmentation is a measurable cost.

        ### Challenge CH-03: rollout-blast-radius
        - theme: security
        - raised_by: contrarian
        - status: resolved
        - steelman: The migration window forces all tenants onto the
          new schema simultaneously. A bug there has a global blast
          radius compared to the current per-tenant isolation.

        ## Convergence Check

        3 challenges across 3 themes (correctness, operability,
        security). No collapse.

        ## Resolution

        CH-01: resolved — chose the new primitive with a rollback
        runbook. CH-03: resolved — added canary. CH-02: open, will be
        revisited after load test.
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
    def test_all_sections_and_challenges_parsed(self):
        parsed = cm.parse_artifact(_well_formed_artifact())
        self.assertEqual(parsed["sections_missing"], [])
        self.assertEqual(len(parsed["challenges"]), 3)
        ids = [c["id"] for c in parsed["challenges"]]
        self.assertEqual(ids, ["CH-01", "CH-02", "CH-03"])
        themes = [c["theme"] for c in parsed["challenges"]]
        self.assertEqual(themes, ["correctness", "operability", "security"])

    def test_empty_artifact_reports_missing_sections(self):
        parsed = cm.parse_artifact("")
        self.assertEqual(set(parsed["sections_missing"]),
                         set(cm.required_sections()))
        self.assertEqual(parsed["challenges"], [])

    def test_challenge_status_and_steelman_captured(self):
        parsed = cm.parse_artifact(_well_formed_artifact())
        ch01 = next(c for c in parsed["challenges"] if c["id"] == "CH-01")
        self.assertEqual(ch01["status"], "resolved")
        self.assertIn("queue semantics", ch01["steelman"])


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
        body = _well_formed_artifact().replace("## Resolution", "## NotResolution")
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("resolution", err.lower())

    def test_resolved_without_steelman_fails(self):
        """The central Issue #442 rule: cannot resolve without a steelman."""
        body = textwrap.dedent(
            """\
            ## Strongest Opposing View
            Some text that makes the artifact large enough to pass byte-size.
            Additional filler to pass the minimum byte threshold for the
            artifact body.  More filler so we clear the 300-byte minimum.
            Even more filler content here for sure.

            ## Challenges

            ### Challenge CH-01: underspecified
            - theme: correctness
            - raised_by: contrarian
            - status: resolved
            - steelman:

            ## Convergence Check
            One challenge.

            ## Resolution
            CH-01 closed without explanation.
            """
        )
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("steelman", err.lower())

    def test_no_challenges_fails(self):
        body = textwrap.dedent(
            """\
            ## Strongest Opposing View
            Lots of text here describing the opposing case in detail to
            make the body exceed the minimum byte size for the artifact.
            Extra filler so we clear the 300-byte minimum threshold for
            the artifact body payload.  Still more filler, getting there.

            ## Challenges

            (none filed yet)

            ## Convergence Check
            No challenges to check.

            ## Resolution
            No open items.
            """
        )
        err = cm.validate_artifact(body)
        self.assertIsNotNone(err)
        self.assertIn("no enumerated", err.lower())


# ---------------------------------------------------------------------------
# detect_convergence_collapse
# ---------------------------------------------------------------------------

class TestConvergenceCollapse(unittest.TestCase):
    def _ch(self, ident: str, theme: str, status: str = "resolved") -> dict:
        return {"id": ident, "theme": theme, "status": status, "steelman": "x" * 80}

    def test_fewer_than_three_challenges_never_collapses(self):
        collapsed, _ = cm.detect_convergence_collapse([
            self._ch("CH-01", "security"),
            self._ch("CH-02", "security"),
        ])
        self.assertFalse(collapsed)

    def test_same_theme_three_plus_collapses(self):
        collapsed, reason = cm.detect_convergence_collapse([
            self._ch("CH-01", "security"),
            self._ch("CH-02", "security"),
            self._ch("CH-03", "security"),
        ])
        self.assertTrue(collapsed)
        self.assertIn("security", reason)

    def test_distinct_themes_do_not_collapse(self):
        collapsed, _ = cm.detect_convergence_collapse([
            self._ch("CH-01", "security"),
            self._ch("CH-02", "correctness"),
            self._ch("CH-03", "operability"),
        ])
        self.assertFalse(collapsed)

    def test_all_empty_themes_collapses(self):
        """Untagged dissent is flagged as collapse so the author enriches it."""
        collapsed, reason = cm.detect_convergence_collapse([
            self._ch("CH-01", ""),
            self._ch("CH-02", ""),
            self._ch("CH-03", ""),
        ])
        self.assertTrue(collapsed)
        self.assertIn("theme", reason.lower())


# ---------------------------------------------------------------------------
# is_required
# ---------------------------------------------------------------------------

class TestIsRequired(unittest.TestCase):
    def test_below_threshold_not_required(self):
        self.assertFalse(cm.is_required(complexity=3, phase="build"))

    def test_at_threshold_required(self):
        self.assertTrue(cm.is_required(complexity=4, phase="build"))

    def test_above_threshold_required(self):
        self.assertTrue(cm.is_required(complexity=7, phase="build"))

    def test_non_build_phase_never_required(self):
        self.assertFalse(cm.is_required(complexity=7, phase="design"))
        self.assertFalse(cm.is_required(complexity=7, phase="test"))


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

    def test_stub_artifact_blocks(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _write_artifact(project_dir, "tiny")
            ok, reason = cm.artifact_satisfies_gate(project_dir, phase="design")
            self.assertFalse(ok)
            self.assertIn("too small", reason)

    def test_collapsed_themes_block_gate(self):
        """End-to-end: three challenges, one theme, all resolved with steelmans."""
        body = textwrap.dedent(
            """\
            ## Strongest Opposing View
            A meaningful narrative summarising the opposing case in full,
            long enough to pass the minimum byte size and give reviewers
            a concrete thing to push back on during the build phase.

            ## Challenges

            ### Challenge CH-01: one
            - theme: security
            - raised_by: contrarian
            - status: resolved
            - steelman: Opposition argues the trust boundary must remain
              where it is today, full stop, for auditor clarity.

            ### Challenge CH-02: two
            - theme: security
            - raised_by: contrarian
            - status: resolved
            - steelman: Opposition argues the secret rotation cost is
              under-estimated by the current design and should block.

            ### Challenge CH-03: three
            - theme: security
            - raised_by: contrarian
            - status: resolved
            - steelman: Opposition argues that co-locating the key
              material violates the compliance boundary we agreed to.

            ## Convergence Check
            All three in one theme — self-reported.

            ## Resolution
            All closed.
            """
        )
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _write_artifact(project_dir, body)
            ok, reason = cm.artifact_satisfies_gate(project_dir, phase="design")
            self.assertFalse(ok)
            self.assertIn("collapse", reason.lower())


if __name__ == "__main__":
    unittest.main()
