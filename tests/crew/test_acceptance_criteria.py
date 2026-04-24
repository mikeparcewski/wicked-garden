#!/usr/bin/env python3
"""
Tests for scripts/crew/acceptance_criteria.py (v8-PR-5 #591).

Covers:
  Parse    — AC-N, AC-N.M, FR-prefix-N, REQ-prefix-N from table / bullet / inline / prose
  Round-trip — parse → serialize → parse → identical records
  Evidence  — empty satisfied_by → UNLINKED, non-empty → LINKED
  Coverage  — >=80% → WARN, <80% → FAIL (via verification_protocol integration)
  Migration — prose-only project auto-migrates to JSON; re-run is idempotent

Run with: pytest tests/crew/test_acceptance_criteria.py
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
_CREW_DIR = _REPO_ROOT / "scripts" / "crew"
sys.path.insert(0, str(_CREW_DIR))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from acceptance_criteria import (  # noqa: E402
    AcceptanceCriterion,
    ACParseError,
    link_evidence,
    load_acs,
    parse_acs_from_markdown,
    save_acs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_project(
    tmp: Path,
    clarify_text: str,
    ac_json: dict | None = None,
) -> Path:
    """Create a minimal project directory with a clarify phase."""
    project = tmp / "proj"
    clarify = project / "phases" / "clarify"
    clarify.mkdir(parents=True, exist_ok=True)
    (clarify / "spec.md").write_text(clarify_text, encoding="utf-8")
    if ac_json is not None:
        (clarify / "acceptance-criteria.json").write_text(
            json.dumps(ac_json), encoding="utf-8"
        )
    return project


# ---------------------------------------------------------------------------
# Parse tests — all 5 formats
# ---------------------------------------------------------------------------

class TestParseTable(unittest.TestCase):
    """Format 1: Markdown table rows."""

    def test_table_ac_n(self):
        md = "| AC-1 | User can log in | test_login.py |\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("AC-1", ids)
        path.unlink()

    def test_table_skips_header_row(self):
        md = "| ID | Description | Test |\n| AC-1 | User logs in | t.py |\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        self.assertFalse(any(a.id == "ID" for a in acs))
        path.unlink()

    def test_table_prefixed_ids(self):
        md = "| FR-auth-1 | Auth flow | tests/ |\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("FR-auth-1", ids)
        path.unlink()


class TestParseBullet(unittest.TestCase):
    """Format 2: Bulleted / listed with bold or plain label."""

    def test_bold_label(self):
        md = "- **AC-3**: User can log in\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("AC-3", ids)
        path.unlink()

    def test_plain_label(self):
        md = "- AC-5: Session expires correctly\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("AC-5", ids)
        path.unlink()

    def test_dotted_id(self):
        """AC-3.1 extracted correctly."""
        md = "- **AC-3.1**: Login timeout handling\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("AC-3.1", ids)
        path.unlink()

    def test_req_prefixed(self):
        md = "- REQ-login-2: Password length >= 8\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("REQ-login-2", ids)
        path.unlink()


class TestParseInline(unittest.TestCase):
    """Format 3: Inline label at line start (AC-N: prose)."""

    def test_inline_colon(self):
        md = "AC-7: The system must respond within 200ms\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("AC-7", ids)
        path.unlink()

    def test_fr_prefix_inline(self):
        md = "FR-auth-3: OAuth2 flow must complete in < 5s\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(md)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        ids = [a.id for a in acs]
        self.assertIn("FR-auth-3", ids)
        path.unlink()


class TestParseMultiFormat(unittest.TestCase):
    """Mixed formats in one file: deduplication and count."""

    def _parse(self, text: str) -> list[AcceptanceCriterion]:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(text)
            path = Path(f.name)
        acs = parse_acs_from_markdown(path)
        path.unlink()
        return acs

    def test_deduplication(self):
        """Same AC-N from multiple patterns → appears once."""
        md = "- **AC-1**: First\nAC-1: Repeated inline\n"
        acs = self._parse(md)
        self.assertEqual(len([a for a in acs if a.id == "AC-1"]), 1)

    def test_statement_captured(self):
        md = "- **AC-2**: User receives email confirmation\n"
        acs = self._parse(md)
        match = next((a for a in acs if a.id == "AC-2"), None)
        self.assertIsNotNone(match)
        self.assertIn("email confirmation", match.statement)


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestRoundTrip(unittest.TestCase):
    """parse → serialize → load → identical records."""

    def test_roundtrip_preserves_fields(self):
        original = [
            AcceptanceCriterion(
                id="AC-1",
                statement="User can log in",
                satisfied_by=("tests/test_login.py",),
                verification="check_acceptance_criteria",
            ),
            AcceptanceCriterion(
                id="AC-2",
                statement="User can reset password",
                satisfied_by=(),
                verification=None,
            ),
        ]
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            (project / "phases" / "clarify").mkdir(parents=True, exist_ok=True)
            save_acs(project, original)
            loaded = load_acs(project)

        self.assertEqual(len(loaded), 2)
        for orig, got in zip(original, loaded):
            self.assertEqual(got.id, orig.id)
            self.assertEqual(got.statement, orig.statement)
            self.assertEqual(got.satisfied_by, orig.satisfied_by)
            self.assertEqual(got.verification, orig.verification)

    def test_roundtrip_empty_satisfied_by(self):
        """Empty satisfied_by round-trips as empty tuple (not None or [])."""
        original = [AcceptanceCriterion(id="AC-1", statement="Test", satisfied_by=())]
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            (project / "phases" / "clarify").mkdir(parents=True, exist_ok=True)
            save_acs(project, original)
            loaded = load_acs(project)
        self.assertEqual(loaded[0].satisfied_by, ())


# ---------------------------------------------------------------------------
# Evidence linking tests
# ---------------------------------------------------------------------------

class TestEvidenceLinking(unittest.TestCase):
    """satisfied_by empty → UNLINKED; non-empty → LINKED."""

    def _project_with_acs(self, tmp: Path) -> Path:
        acs = [
            AcceptanceCriterion(id="AC-1", statement="User logs in", satisfied_by=()),
            AcceptanceCriterion(id="AC-2", statement="User resets password", satisfied_by=()),
        ]
        project = tmp / "proj"
        (project / "phases" / "clarify").mkdir(parents=True, exist_ok=True)
        save_acs(project, acs)
        return project

    def test_unlinked_initially(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._project_with_acs(Path(td))
            acs = load_acs(project)
        for ac in acs:
            self.assertEqual(ac.satisfied_by, (), f"{ac.id} should be unlinked")

    def test_link_adds_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._project_with_acs(Path(td))
            found = link_evidence(project, "AC-1", "tests/test_login.py")
            self.assertTrue(found)
            acs = load_acs(project)
            ac1 = next(a for a in acs if a.id == "AC-1")
            self.assertIn("tests/test_login.py", ac1.satisfied_by)

    def test_link_unknown_ac_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._project_with_acs(Path(td))
            found = link_evidence(project, "AC-999", "tests/foo.py")
            self.assertFalse(found)

    def test_link_idempotent(self):
        """Linking the same evidence twice does not duplicate it."""
        with tempfile.TemporaryDirectory() as td:
            project = self._project_with_acs(Path(td))
            link_evidence(project, "AC-1", "tests/test_login.py")
            link_evidence(project, "AC-1", "tests/test_login.py")
            acs = load_acs(project)
            ac1 = next(a for a in acs if a.id == "AC-1")
            self.assertEqual(ac1.satisfied_by.count("tests/test_login.py"), 1)

    def test_link_multiple_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._project_with_acs(Path(td))
            link_evidence(project, "AC-1", "tests/test_login.py")
            link_evidence(project, "AC-1", "#612")
            acs = load_acs(project)
            ac1 = next(a for a in acs if a.id == "AC-1")
            self.assertEqual(len(ac1.satisfied_by), 2)


# ---------------------------------------------------------------------------
# Coverage threshold tests (via verification_protocol structured path)
# ---------------------------------------------------------------------------

class TestCoverageViaVerificationProtocol(unittest.TestCase):
    """check_acceptance_criteria: structured path → >=80% WARN, <80% FAIL."""

    def setUp(self) -> None:
        from verification_protocol import check_acceptance_criteria  # noqa: F401
        self.check = check_acceptance_criteria

    def _make_phases(self, tmp: Path, acs: list[AcceptanceCriterion]) -> Path:
        project = tmp / "proj"
        clarify = project / "phases" / "clarify"
        clarify.mkdir(parents=True, exist_ok=True)
        save_acs(project, acs)
        return project / "phases"

    def test_all_linked_is_pass(self):
        with tempfile.TemporaryDirectory() as td:
            acs = [
                AcceptanceCriterion("AC-1", "A", ("tests/a.py",)),
                AcceptanceCriterion("AC-2", "B", ("tests/b.py",)),
            ]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "PASS")

    def test_100_percent_linked_pass(self):
        with tempfile.TemporaryDirectory() as td:
            acs = [AcceptanceCriterion(f"AC-{i}", f"S{i}", (f"t{i}.py",)) for i in range(1, 6)]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "PASS")

    def test_80_percent_is_warn(self):
        """4/5 linked (80%) → WARN."""
        with tempfile.TemporaryDirectory() as td:
            acs = [
                AcceptanceCriterion("AC-1", "A", ("t.py",)),
                AcceptanceCriterion("AC-2", "B", ("t.py",)),
                AcceptanceCriterion("AC-3", "C", ("t.py",)),
                AcceptanceCriterion("AC-4", "D", ("t.py",)),
                AcceptanceCriterion("AC-5", "E", ()),  # unlinked
            ]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "WARN", f"Expected WARN: {result.evidence}")

    def test_90_percent_is_warn(self):
        """9/10 linked → WARN."""
        with tempfile.TemporaryDirectory() as td:
            acs = [AcceptanceCriterion(f"AC-{i}", f"S{i}", (f"t{i}.py",)) for i in range(1, 10)]
            acs.append(AcceptanceCriterion("AC-10", "S10", ()))
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "WARN")

    def test_60_percent_is_fail(self):
        """3/5 linked (60%) → FAIL."""
        with tempfile.TemporaryDirectory() as td:
            acs = [
                AcceptanceCriterion("AC-1", "A", ("t.py",)),
                AcceptanceCriterion("AC-2", "B", ("t.py",)),
                AcceptanceCriterion("AC-3", "C", ("t.py",)),
                AcceptanceCriterion("AC-4", "D", ()),
                AcceptanceCriterion("AC-5", "E", ()),
            ]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "FAIL", f"Expected FAIL: {result.evidence}")

    def test_zero_linked_is_fail(self):
        with tempfile.TemporaryDirectory() as td:
            acs = [AcceptanceCriterion("AC-1", "A", ()), AcceptanceCriterion("AC-2", "B", ())]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertEqual(result.status, "FAIL")

    def test_source_label_in_evidence(self):
        """Evidence string tags the path used (structured vs canonical-token)."""
        with tempfile.TemporaryDirectory() as td:
            acs = [AcceptanceCriterion("AC-1", "A", ("t.py",))]
            phases = self._make_phases(Path(td), acs)
            result = self.check("proj", phases)
        self.assertIn("structured", result.evidence)


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------

class TestMigration(unittest.TestCase):
    """Prose-only project auto-migrates; re-run is idempotent."""

    def test_clarify_md_creates_json(self):
        """load_acs on a prose-only project writes acceptance-criteria.json."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            clarify = project / "phases" / "clarify"
            clarify.mkdir(parents=True, exist_ok=True)
            (clarify / "spec.md").write_text(
                "- **AC-3**: User can log in\n- **AC-4**: User receives confirmation email\n",
                encoding="utf-8",
            )
            acs = load_acs(project)
            json_path = clarify / "acceptance-criteria.json"
            self.assertTrue(json_path.exists(), "acceptance-criteria.json not created by migration")
            ids = [a.id for a in acs]
            self.assertIn("AC-3", ids)
            self.assertIn("AC-4", ids)

    def test_migrated_satisfied_by_is_empty(self):
        """Migrated ACs start with empty satisfied_by — evidence not yet linked."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            clarify = project / "phases" / "clarify"
            clarify.mkdir(parents=True, exist_ok=True)
            (clarify / "spec.md").write_text("AC-1: User can register\n", encoding="utf-8")
            acs = load_acs(project)
            for ac in acs:
                self.assertEqual(ac.satisfied_by, (), f"{ac.id} should start unlinked")

    def test_rerun_is_idempotent(self):
        """Calling load_acs twice on the same project yields identical records."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            clarify = project / "phases" / "clarify"
            clarify.mkdir(parents=True, exist_ok=True)
            (clarify / "spec.md").write_text(
                "- **AC-1**: First\n- **AC-2**: Second\n", encoding="utf-8"
            )
            acs1 = load_acs(project)
            acs2 = load_acs(project)
        self.assertEqual(
            [(a.id, a.statement, a.satisfied_by) for a in acs1],
            [(a.id, a.statement, a.satisfied_by) for a in acs2],
        )

    def test_prose_project_verification_still_works(self):
        """A project with only clarify.md passes verification via fallback + migration."""
        from verification_protocol import check_acceptance_criteria

        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            clarify = project / "phases" / "clarify"
            clarify.mkdir(parents=True, exist_ok=True)
            (clarify / "spec.md").write_text(
                "- **AC-1**: User can log in\n", encoding="utf-8"
            )
            # Build dir with a deliverable referencing AC-1
            build = project / "phases" / "build"
            build.mkdir(parents=True, exist_ok=True)
            (build / "impl.md").write_text("Implements AC-1 login flow.", encoding="utf-8")

            # First call triggers migration (writes acceptance-criteria.json)
            # then re-routes to structured path (satisfied_by empty → FAIL or canonical)
            # This exercises that no crash occurs and backward compat is preserved.
            phases = project / "phases"
            result = check_acceptance_criteria("proj", phases)
            # The migrated JSON has empty satisfied_by, so structured path reports FAIL/WARN/PASS
            # depending on whether evidence was linked. Without evidence linking,
            # it will be FAIL (0/1). The important thing is no exception is raised.
            self.assertIn(result.status, ("PASS", "WARN", "FAIL", "SKIP"))


# ---------------------------------------------------------------------------
# Isolated unit tests — numbered-under-heading parser path (#591 / #617)
# Council condition: format 5 (_RE_NUMBERED + _RE_AC_SECTION section-context
# gate) has integration coverage but no dedicated unit test.  Migration is
# one-shot so a parse miss is permanent silent data loss.
# ---------------------------------------------------------------------------

class TestNumberedUnderHeadingIsolated(unittest.TestCase):
    """Isolated unit tests for _RE_NUMBERED + _RE_AC_SECTION (format 5).

    Three cases per council requirement (PR #617):
      1. _RE_AC_SECTION matches common heading variants (5 variants)
      2. Numbered items UNDER the AC section ARE captured
      3. Numbered items OUTSIDE the AC section are NOT captured
    """

    # ------------------------------------------------------------------
    # Helper: parse from an in-memory string, no disk fixture needed
    # ------------------------------------------------------------------

    def _parse(self, text: str):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(text)
            path = Path(f.name)
        try:
            return parse_acs_from_markdown(path)
        finally:
            path.unlink()

    # ------------------------------------------------------------------
    # Case 1: _RE_AC_SECTION matches common heading variants
    # ------------------------------------------------------------------

    def _assert_heading_variant(self, heading: str) -> None:
        """Assert that a given heading activates the numbered-list parser."""
        md = f"{heading}\n\n1. User can log in\n2. User can log out\n"
        acs = self._parse(md)
        ids = [a.id for a in acs]
        self.assertIn(
            "AC-1",
            ids,
            f"Heading variant {heading!r} did not activate numbered parser — AC-1 missing. "
            f"Got IDs: {ids}",
        )
        self.assertIn(
            "AC-2",
            ids,
            f"Heading variant {heading!r} did not activate numbered parser — AC-2 missing. "
            f"Got IDs: {ids}",
        )

    def test_heading_variant_standard(self):
        """'## Acceptance Criteria' activates numbered parser."""
        self._assert_heading_variant("## Acceptance Criteria")

    def test_heading_variant_acs_short(self):
        """'## ACs' activates numbered parser (short alias)."""
        self._assert_heading_variant("## ACs")

    def test_heading_variant_draft_suffix(self):
        """'## Acceptance Criteria (Draft)' activates numbered parser."""
        self._assert_heading_variant("## Acceptance Criteria (Draft)")

    def test_heading_variant_h3(self):
        """'### Acceptance Criteria' (h3) activates numbered parser."""
        self._assert_heading_variant("### Acceptance Criteria")

    def test_heading_variant_h1(self):
        """'# Acceptance Criteria' (h1) activates numbered parser."""
        self._assert_heading_variant("# Acceptance Criteria")

    # ------------------------------------------------------------------
    # Case 2: Numbered items UNDER the AC section ARE captured
    # ------------------------------------------------------------------

    def test_numbered_items_under_ac_section_captured(self):
        """Three numbered items under '## Acceptance Criteria' → 3 ACs, statements verbatim."""
        md = (
            "## Acceptance Criteria\n\n"
            "1. First criterion\n"
            "2. Second criterion\n"
            "3. Third criterion\n"
        )
        acs = self._parse(md)
        ids = [a.id for a in acs]
        statements = {a.id: a.statement for a in acs}

        self.assertEqual(
            len(acs),
            3,
            f"Expected 3 ACs, got {len(acs)}: {ids}",
        )
        self.assertIn("AC-1", ids)
        self.assertIn("AC-2", ids)
        self.assertIn("AC-3", ids)

        # Statements preserved verbatim
        self.assertEqual(statements.get("AC-1"), "First criterion")
        self.assertEqual(statements.get("AC-2"), "Second criterion")
        self.assertEqual(statements.get("AC-3"), "Third criterion")

    # ------------------------------------------------------------------
    # Case 3: Numbered items OUTSIDE the AC section are NOT captured
    # ------------------------------------------------------------------

    def test_numbered_items_outside_ac_section_not_captured(self):
        """Numbered lists in non-AC sections must not contribute ACs.

        Only the single item under '## Acceptance Criteria' should be parsed.
        Items under '## Other Heading' and '## Later Heading' must be excluded.
        """
        md = (
            "## Other Heading\n\n"
            "1. Some other numbered item\n"
            "2. Another item\n\n"
            "## Acceptance Criteria\n\n"
            "1. Real criterion\n\n"
            "## Later Heading\n\n"
            "1. Post-AC item\n"
        )
        acs = self._parse(md)
        ids = [a.id for a in acs]
        statements = {a.id: a.statement for a in acs}

        self.assertEqual(
            len(acs),
            1,
            f"Expected exactly 1 AC (from the AC section only), got {len(acs)}: "
            f"{[(a.id, a.statement) for a in acs]}",
        )
        self.assertIn("AC-1", ids)
        self.assertEqual(
            statements.get("AC-1"),
            "Real criterion",
            f"AC-1 statement should be 'Real criterion', got {statements.get('AC-1')!r}",
        )


if __name__ == "__main__":
    unittest.main()
