#!/usr/bin/env python3
"""
Regression tests for verification_protocol.check_acceptance_criteria fixes (issue #587).

Covers:
  (A) Separator / case normalisation — AC-3 / AC3 / ac_3 / ac-3 all match
  (B) Parent-id fallback — AC-3.1 is satisfied by deliverable referencing AC-3
      (end-to-end via filesystem; extractor now captures dotted IDs)
  (C) Severity downgrade — >=80% coverage yields WARN, not FAIL
  (D) Data-shape distinctness — AC-3 and AC-30 are separate tokens (no false positives)

Run with: pytest tests/crew/test_verification_protocol_ac_linked.py
"""

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — append rather than prepend to avoid shadowing the crew/ package
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CREW_DIR = _SCRIPTS_DIR / "crew"
sys.path.append(str(_SCRIPTS_DIR))
sys.path.append(str(_CREW_DIR))

from verification_protocol import check_acceptance_criteria, CheckResult, VerificationReport  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_phases(tmp: Path, clarify_text: str, deliverable_text: str) -> Path:
    """Create a minimal phases/ tree and return its path."""
    phases = tmp / "phases"
    _write(phases / "clarify" / "ac.md", clarify_text)
    _write(phases / "build" / "impl.md", deliverable_text)
    return phases


# ---------------------------------------------------------------------------
# (A) Separator / case normalisation
# ---------------------------------------------------------------------------

class TestNormalisedMatch(unittest.TestCase):
    """AC-3 in clarify must match cosmetic variants in deliverables."""

    # Use list format: "- **AC-N**: <desc>" (no "criterion" in desc to avoid filter)
    _CLARIFY = "- **AC-3**: User can log in\n"

    def _run(self, deliverable_text: str):
        with tempfile.TemporaryDirectory() as td:
            phases = _make_phases(Path(td), self._CLARIFY, deliverable_text)
            return check_acceptance_criteria("proj", phases)

    def test_exact_match_still_passes(self):
        result = self._run("Implements AC-3 login flow.")
        self.assertEqual(result.status, "PASS")

    def test_no_hyphen_ac3(self):
        """AC3 (no separator) should match AC-3 in clarify."""
        result = self._run("See AC3 for the login requirement.")
        self.assertEqual(result.status, "PASS")

    def test_underscore_ac_3(self):
        """ac_3 (underscore separator) should match AC-3."""
        result = self._run("Ref ac_3 implementation.")
        self.assertEqual(result.status, "PASS")

    def test_lowercase_ac_minus_3(self):
        """ac-3 (lowercase + hyphen) should match AC-3."""
        result = self._run("See ac-3 for details.")
        self.assertEqual(result.status, "PASS")

    def test_uppercase_no_sep(self):
        """AC3 uppercase should match AC-3."""
        result = self._run("Covered by AC3.")
        self.assertEqual(result.status, "PASS")


# ---------------------------------------------------------------------------
# (B) Parent-id fallback — end-to-end filesystem tests
#
# The extractor now captures dotted IDs (AC-3.1) so these run end-to-end
# through check_acceptance_criteria rather than replicating internal logic.
# ---------------------------------------------------------------------------

class TestParentIdFallbackLogic(unittest.TestCase):
    """Parent-id fallback: AC-3.1 in clarify is satisfied by AC-3 in deliverable."""

    def _run(self, clarify_text: str, deliverable_text: str):
        with tempfile.TemporaryDirectory() as td:
            phases = _make_phases(Path(td), clarify_text, deliverable_text)
            return check_acceptance_criteria("proj", phases)

    def test_parent_reference_satisfies_child(self):
        """AC-3 in deliverable satisfies AC-3.1 requirement (end-to-end)."""
        clarify = "- **AC-3.1**: Login timeout handling\n"
        deliverable = "Login timeout covered under AC-3."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS", msg=f"Expected PASS, got {result.status}: {result.evidence}")

    def test_exact_child_still_works(self):
        """AC-3.1 exact reference also matches (end-to-end)."""
        clarify = "- **AC-3.1**: Login timeout handling\n"
        deliverable = "Implemented AC-3.1 timeout logic."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS")

    def test_parent_normalised_ac3_satisfies_child(self):
        """Normalised parent 'AC3' in deliverable satisfies AC-3.1 (end-to-end)."""
        clarify = "- **AC-3.1**: Login timeout handling\n"
        deliverable = "See AC3 for all login criteria."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS")

    def test_unrelated_id_does_not_match(self):
        """AC-5 does NOT satisfy AC-3.1 — only true parent does."""
        clarify = "- **AC-3.1**: Login timeout handling\n"
        deliverable = "Only references AC-5."
        result = self._run(clarify, deliverable)
        # AC-3.1 is unlinked; single AC, coverage = 0/1 = FAIL
        self.assertEqual(result.status, "FAIL")

    def test_deep_nesting_ac_2_1_3_parent_fallback(self):
        """AC-2.1.3 in clarify: immediate parent AC-2.1 in deliverable satisfies it."""
        clarify = "- **AC-2.1.3**: Sub-feature detail\n"
        deliverable = "Implements AC-2.1 feature."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS")


# ---------------------------------------------------------------------------
# (C) 80% coverage threshold → WARN not FAIL
# ---------------------------------------------------------------------------

class TestCoverageThreshold(unittest.TestCase):
    """>=80% AC coverage should produce WARN; <80% should produce FAIL."""

    def _build_clarify(self, count: int) -> str:
        # Use "User can X" descriptions so "criterion" filter doesn't apply
        return "\n".join(f"- **AC-{i}**: User action {i}" for i in range(1, count + 1))

    def _build_deliverable(self, linked_ids: list) -> str:
        return " ".join(f"AC-{i}" for i in linked_ids)

    def _run(self, total: int, linked: list):
        with tempfile.TemporaryDirectory() as td:
            clarify = self._build_clarify(total)
            deliverable = self._build_deliverable(linked)
            phases = _make_phases(Path(td), clarify, deliverable)
            return check_acceptance_criteria("proj", phases)

    def test_90_percent_coverage_is_warn(self):
        """9/10 ACs linked (90%) -> WARN, not FAIL."""
        result = self._run(10, list(range(1, 10)))  # AC-1..9 linked, AC-10 missing
        self.assertEqual(result.status, "WARN", msg=f"Expected WARN, got {result.status}: {result.evidence}")

    def test_80_percent_exact_is_warn(self):
        """4/5 ACs linked (80%) -> WARN."""
        result = self._run(5, [1, 2, 3, 4])  # AC-5 missing
        self.assertEqual(result.status, "WARN", msg=f"Expected WARN, got {result.status}: {result.evidence}")

    def test_below_80_percent_is_fail(self):
        """3/5 ACs linked (60%) -> FAIL."""
        result = self._run(5, [1, 2, 3])  # AC-4, AC-5 missing
        self.assertEqual(result.status, "FAIL", msg=f"Expected FAIL, got {result.status}: {result.evidence}")

    def test_100_percent_is_pass(self):
        """All ACs linked -> PASS."""
        result = self._run(5, [1, 2, 3, 4, 5])
        self.assertEqual(result.status, "PASS")

    def test_warn_does_not_block_overall_verdict(self):
        """A WARN check should not flip the VerificationReport verdict to FAIL."""
        report = VerificationReport(
            protocol_version="1.0",
            project_id="test",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            checks=[
                CheckResult(
                    name="acceptance_criteria",
                    status="WARN",
                    evidence="9/10 AC linked; high coverage threshold met; treating as advisory; missing: AC-10",
                    details={},
                ),
            ],
        )
        self.assertEqual(report.verdict, "PASS")

    def test_warn_evidence_mentions_coverage_and_advisory(self):
        """WARN evidence string accurately describes the situation — no 'cosmetic' claim."""
        result = self._run(10, list(range(1, 10)))
        self.assertIn("high coverage threshold met", result.evidence)
        self.assertIn("advisory", result.evidence)
        self.assertIn("missing", result.evidence)
        # Old misleading wording must NOT appear
        self.assertNotIn("cosmetic", result.evidence)


# ---------------------------------------------------------------------------
# (D) Data-shape distinctness — canonical-token-set guarantees
# ---------------------------------------------------------------------------

class TestDataShapeMatching(unittest.TestCase):
    """Canonical-token-set data shape: AC-3 and AC-30 are distinct tokens."""

    _CLARIFY_AC3 = "- **AC-3**: User can log in\n"
    _CLARIFY_AC30 = "- **AC-30**: User can export data\n"
    _CLARIFY_BOTH = "- **AC-3**: User can log in\n- **AC-30**: User can export data\n"

    def _run(self, clarify_text: str, deliverable_text: str):
        with tempfile.TemporaryDirectory() as td:
            phases = _make_phases(Path(td), clarify_text, deliverable_text)
            return check_acceptance_criteria("proj", phases)

    def test_ac3_does_not_false_match_ac30(self):
        """AC-3 in clarify should be UNLINKED when deliverable only contains AC-30."""
        result = self._run(self._CLARIFY_AC3, "See AC-30 for details.")
        # AC-3 is unlinked; 0/1 coverage -> FAIL
        self.assertEqual(result.status, "FAIL",
                         msg=f"AC-3 falsely matched AC-30: got {result.status}: {result.evidence}")
        self.assertIn("AC-3", result.evidence)

    def test_ac30_distinct_from_ac3(self):
        """Both AC-3 and AC-30 extracted and verified independently."""
        # Deliverable mentions both explicitly
        result = self._run(self._CLARIFY_BOTH, "Implements AC-3 login. See AC-30 export.")
        self.assertEqual(result.status, "PASS",
                         msg=f"Expected both linked, got {result.status}: {result.evidence}")

    def test_ac30_alone_does_not_satisfy_ac3(self):
        """When both defined in clarify, AC-30 alone leaves AC-3 unlinked."""
        result = self._run(self._CLARIFY_BOTH, "Only AC-30 is referenced.")
        self.assertNotEqual(result.status, "PASS")
        # AC-3 should appear as unlinked
        self.assertIn("AC-3", result.evidence)

    def test_dotted_id_extracted_and_matched(self):
        """AC-3.1 in clarify, AC-3.1 in deliverable -> linked directly."""
        clarify = "- **AC-3.1**: Login timeout\n"
        deliverable = "Implements AC-3.1 timeout."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS")

    def test_dotted_id_parent_fallback(self):
        """AC-3.1 in clarify, only AC-3 in deliverable -> linked via parent fallback."""
        clarify = "- **AC-3.1**: Login timeout\n"
        deliverable = "Login behavior covered under AC-3."
        result = self._run(clarify, deliverable)
        self.assertEqual(result.status, "PASS",
                         msg=f"Parent fallback failed: {result.status}: {result.evidence}")

    def test_canonical_form_unifies_variants(self):
        """AC-3, AC3, AC_3, ac 3 in deliverable all match AC-3 in clarify."""
        clarify = "- **AC-3**: User can log in\n"
        for variant in ("AC-3", "AC3", "AC_3", "ac 3"):
            with self.subTest(variant=variant):
                result = self._run(clarify, f"See {variant} for details.")
                self.assertEqual(result.status, "PASS",
                                 msg=f"Variant '{variant}' failed: {result.status}: {result.evidence}")


# ---------------------------------------------------------------------------
# (E) Structured-AC primary path (v8-PR-5 #591)
# ---------------------------------------------------------------------------

class TestStructuredACPrimaryPath(unittest.TestCase):
    """Primary path: acceptance-criteria.json fully drives coverage; no text scan."""

    def _make_structured_phases(
        self,
        tmp: Path,
        acs: list[dict],
        build_text: str = "",
    ) -> Path:
        """Create phases/ with acceptance-criteria.json and an optional build deliverable."""
        phases = tmp / "phases"
        clarify = phases / "clarify"
        clarify.mkdir(parents=True, exist_ok=True)
        json_path = clarify / "acceptance-criteria.json"
        json_path.write_text(
            __import__("json").dumps({"version": "1", "acs": acs}),
            encoding="utf-8",
        )
        if build_text:
            build = phases / "build"
            build.mkdir(parents=True, exist_ok=True)
            (build / "impl.md").write_text(build_text, encoding="utf-8")
        return phases

    def test_all_linked_is_pass(self):
        """All ACs with non-empty satisfied_by → PASS."""
        with tempfile.TemporaryDirectory() as td:
            acs = [
                {"id": "AC-1", "statement": "Login", "satisfied_by": ["tests/test_login.py"]},
                {"id": "AC-2", "statement": "Logout", "satisfied_by": ["tests/test_logout.py"]},
            ]
            phases = self._make_structured_phases(Path(td), acs)
            result = check_acceptance_criteria("proj", phases)
        self.assertEqual(result.status, "PASS")

    def test_empty_satisfied_by_is_unlinked(self):
        """AC with empty satisfied_by counts as UNLINKED."""
        with tempfile.TemporaryDirectory() as td:
            acs = [
                {"id": "AC-1", "statement": "Login", "satisfied_by": []},
            ]
            phases = self._make_structured_phases(Path(td), acs)
            result = check_acceptance_criteria("proj", phases)
        # 0/1 → below threshold → FAIL
        self.assertEqual(result.status, "FAIL")

    def test_source_label_is_structured(self):
        """Evidence string reports 'structured' path."""
        with tempfile.TemporaryDirectory() as td:
            acs = [{"id": "AC-1", "statement": "S", "satisfied_by": ["t.py"]}]
            phases = self._make_structured_phases(Path(td), acs)
            result = check_acceptance_criteria("proj", phases)
        self.assertIn("structured", result.evidence)

    def test_no_substring_scan_on_prose(self):
        """Deliverable text with AC-1 literal does NOT satisfy unlinked AC-1.

        This is the root-cause fix for #587: satisfied_by is empty → UNLINKED,
        regardless of what appears in the deliverable text.
        """
        with tempfile.TemporaryDirectory() as td:
            acs = [{"id": "AC-1", "statement": "Login", "satisfied_by": []}]
            # Build file explicitly mentions AC-1 — this should NOT satisfy it
            phases = self._make_structured_phases(
                Path(td), acs, build_text="Implements AC-1 login flow."
            )
            result = check_acceptance_criteria("proj", phases)
        # Structured path sees empty satisfied_by → UNLINKED → FAIL
        self.assertEqual(result.status, "FAIL", (
            "BUG: structured path fell through to text scanning. "
            f"Got {result.status}: {result.evidence}"
        ))

    def test_80_percent_warn(self):
        """4/5 structured ACs linked → WARN."""
        with tempfile.TemporaryDirectory() as td:
            acs = [
                {"id": f"AC-{i}", "statement": f"S{i}", "satisfied_by": [f"t{i}.py"]}
                for i in range(1, 5)
            ] + [{"id": "AC-5", "statement": "S5", "satisfied_by": []}]
            phases = self._make_structured_phases(Path(td), acs)
            result = check_acceptance_criteria("proj", phases)
        self.assertEqual(result.status, "WARN")

    def test_empty_acs_array_skips(self):
        """JSON with empty acs array → SKIP (no ACs declared)."""
        with tempfile.TemporaryDirectory() as td:
            phases = self._make_structured_phases(Path(td), [])
            result = check_acceptance_criteria("proj", phases)
        self.assertEqual(result.status, "SKIP")


class TestBackwardCompatFallback(unittest.TestCase):
    """Projects WITHOUT acceptance-criteria.json fall back to canonical-token path."""

    def test_no_json_falls_back_to_canonical(self):
        """Fallback: clarify markdown + deliverable → canonical-token match still works."""
        with tempfile.TemporaryDirectory() as td:
            phases = Path(td) / "phases"
            _write(phases / "clarify" / "ac.md", "- **AC-3**: User can log in\n")
            _write(phases / "build" / "impl.md", "Implements AC-3 login flow.")
            result = check_acceptance_criteria("proj", phases)
        self.assertEqual(result.status, "PASS")

    def test_fallback_source_label_is_canonical_token(self):
        """Fallback evidence string reports 'canonical-token' path."""
        with tempfile.TemporaryDirectory() as td:
            phases = Path(td) / "phases"
            _write(phases / "clarify" / "ac.md", "- **AC-3**: User can log in\n")
            _write(phases / "build" / "impl.md", "Implements AC-3 login flow.")
            result = check_acceptance_criteria("proj", phases)
        self.assertIn("canonical-token", result.evidence)

    def test_fallback_unlinked_still_fails(self):
        """Fallback: AC-3 in clarify, no mention in deliverable → FAIL."""
        with tempfile.TemporaryDirectory() as td:
            phases = Path(td) / "phases"
            _write(phases / "clarify" / "ac.md", "- **AC-3**: User can log in\n")
            _write(phases / "build" / "impl.md", "No references here.")
            result = check_acceptance_criteria("proj", phases)
        self.assertEqual(result.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
