#!/usr/bin/env python3
"""Tests for the semantic reviewer (issue #444).

Covers the P0 acceptance requirement explicitly (TestAc1DivergentAcceptance)
plus aligned / missing detection, gate-result integration, complexity
threshold honouring, and legacy bypass.

Run with::

    python3 -m pytest tests/qe/test_semantic_review.py -v
    # or
    python3 -m unittest tests.qe.test_semantic_review -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_QE = _SCRIPTS / "qe"
_CREW = _SCRIPTS / "crew"

sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_QE))
sys.path.insert(0, str(_CREW))


import semantic_review  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — synthetic project factories
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _make_project(root: Path, ac_text: str, impl_map: dict, test_map: dict) -> Path:
    """Create a synthetic project layout under root.

    impl_map / test_map are {relative_path: body}.
    """
    project = root / "proj"
    _write(project / "phases" / "clarify" / "acceptance-criteria.md", ac_text)
    _write(project / "phases" / "clarify" / "objective.md",
           "# Objective\nImplement the feature described by AC-1 and friends.\n")

    for rel, body in impl_map.items():
        _write(project / rel, body)
    for rel, body in test_map.items():
        _write(project / "tests" / rel, body)

    return project


# ---------------------------------------------------------------------------
# Acceptance test required by issue #444 — AC-1 Divergent finding
# ---------------------------------------------------------------------------


class TestAc1DivergentAcceptance(unittest.TestCase):
    """Issue #444 acceptance: an AC-1 spec + implementation that partially
    satisfies it produces a DIVERGENT finding naming AC-1.

    Spec: "Given 3 failed login attempts per session, When user tries again,
           Then account locked".
    Impl: enforces rate limit PER REQUEST instead of PER SESSION — classic
          scope drift.
    """

    def test_ac1_per_session_impl_per_request_is_divergent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ac_text = (
                "# Acceptance Criteria\n"
                "\n"
                "- AC-1: Given 3 failed login attempts per session, When user "
                "tries again, Then account is locked for 15 minutes [P0]\n"
            )
            impl_map = {
                "src/auth.py": (
                    "# Handles login rate limiting.\n"
                    "# See AC-1 — we enforce a 3-attempt cap per request.\n"
                    "def login(user, password, request):\n"
                    "    attempts = request.headers.get('X-Attempts', 0)\n"
                    "    if attempts >= 3:\n"
                    "        return 'locked'\n"
                    "    return 'ok'\n"
                ),
            }
            test_map = {
                "test_auth.py": (
                    "# AC-1 coverage\n"
                    "def test_login_locks_after_three_attempts():\n"
                    "    # asserts lock after 3 attempts\n"
                    "    assert True\n"
                ),
            }
            project = _make_project(Path(td), ac_text, impl_map, test_map)

            report = semantic_review.review_project(
                project_dir=project,
                project_name="proj",
                complexity=4,
            )

            self.assertEqual(report.total, 1, f"Expected 1 spec item, got {report.total}")

            ac1_finding = next(
                (f for f in report.findings if f.id.upper() == "AC-1"),
                None,
            )
            self.assertIsNotNone(ac1_finding, "AC-1 finding missing")
            self.assertEqual(
                ac1_finding.status, "divergent",
                f"Expected AC-1 divergent, got {ac1_finding.status}. Reason: {ac1_finding.reason}",
            )
            # Explicit check that the DIVERGENT finding names AC-1 (per #444 AC).
            self.assertIn("AC-1", ac1_finding.id)
            # The scope drift must surface as an unmatched 'per session'
            # constraint.
            self.assertIn("per session", [c.lower() for c in ac1_finding.unmatched_constraints],
                          f"Expected 'per session' in unmatched; got {ac1_finding.unmatched_constraints}")
            # Verdict at complexity 4 with 0 missing + 1 divergent -> CONDITIONAL.
            self.assertEqual(report.verdict, "CONDITIONAL",
                             f"Got verdict={report.verdict}; reason={report.summary}")
            print(f"PASS AC-1 Divergent acceptance (confidence={ac1_finding.confidence:.2f})")


# ---------------------------------------------------------------------------
# Aligned detection
# ---------------------------------------------------------------------------


class TestAlignedDetection(unittest.TestCase):
    def test_all_aligned_when_impl_and_tests_cover_ac(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ac_text = (
                "# Acceptance Criteria\n\n"
                "- AC-1: User can greet the world and receive a response [P0]\n"
            )
            impl_map = {
                "src/greet.py": (
                    "# AC-1 — greet the world\n"
                    "def greet(user):\n"
                    "    # returns response when user greets the world\n"
                    "    return f'hello {user}, welcome to the world'\n"
                ),
            }
            test_map = {
                "test_greet.py": (
                    "# AC-1 coverage — user can greet the world, receive response\n"
                    "def test_greet_returns_welcome():\n"
                    "    from src.greet import greet\n"
                    "    assert 'welcome' in greet('alice')\n"
                ),
            }
            project = _make_project(Path(td), ac_text, impl_map, test_map)
            report = semantic_review.review_project(project, "proj", complexity=4)

            self.assertEqual(report.total, 1)
            self.assertEqual(report.aligned, 1)
            self.assertEqual(report.missing, 0)
            self.assertEqual(report.divergent, 0)
            self.assertEqual(report.verdict, "APPROVE")
            print(f"PASS aligned detection (score={report.score})")


# ---------------------------------------------------------------------------
# Missing detection
# ---------------------------------------------------------------------------


class TestMissingDetection(unittest.TestCase):
    def test_ac2_not_referenced_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ac_text = (
                "# Acceptance Criteria\n\n"
                "- AC-1: User can greet [P0]\n"
                "- AC-2: System logs the greeting for audit [P0]\n"
            )
            impl_map = {
                "src/greet.py": (
                    "# AC-1 — greet only\n"
                    "def greet(user):\n"
                    "    return f'hello {user}'\n"
                ),
            }
            test_map = {
                "test_greet.py": (
                    "# AC-1 coverage\n"
                    "def test_greet():\n"
                    "    assert True\n"
                ),
            }
            project = _make_project(Path(td), ac_text, impl_map, test_map)
            report = semantic_review.review_project(project, "proj", complexity=4)

            self.assertEqual(report.total, 2)
            missing_ids = [f.id for f in report.findings if f.status == "missing"]
            self.assertIn("AC-2", missing_ids, f"Expected AC-2 missing, got missing={missing_ids}")
            self.assertEqual(report.verdict, "REJECT")
            print(f"PASS missing detection (missing={missing_ids})")


# ---------------------------------------------------------------------------
# Gate-result integration via phase_manager._check_semantic_alignment_gate
# ---------------------------------------------------------------------------


class TestGateIntegration(unittest.TestCase):
    def setUp(self) -> None:
        # Fresh-import phase_manager to pick up any test-specific state.
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager  # noqa: E402
        self.pm = phase_manager

    def _make_state(self, complexity: int) -> "self.pm.ProjectState":
        return self.pm.ProjectState(
            name="semtest",
            current_phase="review",
            created_at="2026-01-01T00:00:00Z",
            complexity_score=complexity,
        )

    def test_missing_blocks_at_complexity_5(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            _write(project / "phases" / "clarify" / "acceptance-criteria.md",
                   "- AC-9: Widget explodes on overload [P0]\n")
            # Empty impl — AC-9 not referenced anywhere.
            _write(project / "src" / "main.py", "# unrelated code\n")

            state = self._make_state(complexity=5)
            block, warnings = self.pm._check_semantic_alignment_gate(
                state, project, "review",
            )
            self.assertIsNotNone(block, f"Expected block reason; warnings={warnings}")
            self.assertIn("REJECT", block)
            self.assertIn("AC-9", block)
            print("PASS gate-integration: missing blocks at complexity 5")

    def test_divergent_emits_warning_at_complexity_4(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            _write(project / "phases" / "clarify" / "acceptance-criteria.md",
                   "- AC-1: Lock after 3 failed attempts per session [P0]\n")
            _write(project / "src" / "auth.py",
                   "# AC-1\n# attempts per request logic\n"
                   "def check(r):\n    return r.attempts < 3\n")
            _write(project / "tests" / "test_auth.py",
                   "# AC-1 test\n"
                   "def test_lock():\n    assert True\n")

            state = self._make_state(complexity=4)
            block, warnings = self.pm._check_semantic_alignment_gate(
                state, project, "review",
            )
            self.assertIsNone(block, f"Expected no block; got {block}")
            # Warnings must name AC-1 and divergent.
            joined = "\n".join(warnings)
            self.assertIn("AC-1", joined)
            self.assertIn("DIVERGENT", joined)

            # Verify conditions manifest was written.
            manifest = project / "phases" / "review" / "conditions-manifest.json"
            self.assertTrue(manifest.exists(),
                            "Conditions manifest should be written for divergent findings")
            body = json.loads(manifest.read_text())
            descriptions = [c.get("description", "") for c in body.get("conditions", [])]
            self.assertTrue(any("AC-1" in d for d in descriptions),
                            f"Expected AC-1 in conditions manifest; got {descriptions}")

            # Verify report artifact written.
            report_path = project / "phases" / "review" / "semantic-gap-report.json"
            self.assertTrue(report_path.exists())
            report_data = json.loads(report_path.read_text())
            self.assertEqual(report_data["verdict"], "CONDITIONAL")
            print("PASS gate-integration: divergent yields conditions at complexity 4")


# ---------------------------------------------------------------------------
# Complexity threshold honouring (advisory vs blocking)
# ---------------------------------------------------------------------------


class TestComplexityThreshold(unittest.TestCase):
    def setUp(self) -> None:
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager  # noqa: E402
        self.pm = phase_manager

    def _setup_missing_project(self, td: Path) -> Path:
        project = td / "proj"
        _write(project / "phases" / "clarify" / "acceptance-criteria.md",
               "- AC-99: missing feature [P0]\n")
        _write(project / "src" / "foo.py", "# unrelated\n")
        return project

    def test_complexity_2_is_advisory_not_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = self._setup_missing_project(Path(td))
            state = self.pm.ProjectState(
                name="semtest", current_phase="review",
                created_at="2026-01-01T00:00:00Z", complexity_score=2,
            )
            block, warnings = self.pm._check_semantic_alignment_gate(
                state, project, "review",
            )
            self.assertIsNone(block,
                              f"Complexity 2 must not block; got {block}")
            self.assertTrue(
                any("MISSING" in w for w in warnings),
                f"Expected MISSING warning to still surface; got {warnings}",
            )
            print("PASS complexity threshold: complexity 2 is advisory")

    def test_complexity_3_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = self._setup_missing_project(Path(td))
            state = self.pm.ProjectState(
                name="semtest", current_phase="review",
                created_at="2026-01-01T00:00:00Z", complexity_score=3,
            )
            block, _ = self.pm._check_semantic_alignment_gate(
                state, project, "review",
            )
            self.assertIsNotNone(block, "Complexity 3 must block on missing")
            print("PASS complexity threshold: complexity 3 blocks on missing")


# ---------------------------------------------------------------------------
# ADR constraint extraction (MVP)
# ---------------------------------------------------------------------------


class TestAdrConstraints(unittest.TestCase):
    def test_must_and_shall_directives_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adr_dir = Path(td) / "adrs"
            _write(adr_dir / "001-encryption.md",
                   "# ADR-001: Encryption\n\n"
                   "The system MUST encrypt all PII at rest.\n"
                   "Passwords SHALL NOT be logged in plaintext.\n"
                   "Developers SHOULD rotate keys quarterly.\n"
                   "## Context\nbackground prose\n")
            directives = semantic_review.extract_adr_constraints(adr_dir)
            # At least 3 directives found (MUST, SHALL NOT, SHOULD).
            self.assertGreaterEqual(len(directives), 3,
                                    f"Expected >=3 directives; got {directives}")
            kinds = {d["directive"] for d in directives}
            self.assertIn("MUST", kinds)
            self.assertIn("SHALL NOT", kinds)
            print(f"PASS ADR constraint extraction ({len(directives)} directives)")

    def test_missing_adr_dir_returns_empty_list(self) -> None:
        result = semantic_review.extract_adr_constraints(Path("/nonexistent/adr/path"))
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Extraction edge cases
# ---------------------------------------------------------------------------


class TestSpecExtraction(unittest.TestCase):
    def test_table_row_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ac = Path(td) / "ac.md"
            ac.write_text(
                "| ID | Criterion | Test |\n"
                "|----|-----------|------|\n"
                "| AC-1 | User logs in | test_login |\n"
                "| AC-2 | User logs out | test_logout |\n",
            )
            items = semantic_review.extract_spec_items(ac_file=ac)
            ids = [it.id for it in items]
            self.assertIn("AC-1", ids)
            self.assertIn("AC-2", ids)

    def test_bullet_list_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ac = Path(td) / "ac.md"
            ac.write_text(
                "- AC-1: Given X When Y Then Z\n"
                "- **AC-2**: Given A When B Then C\n",
            )
            items = semantic_review.extract_spec_items(ac_file=ac)
            ids = [it.id for it in items]
            self.assertIn("AC-1", ids)
            self.assertIn("AC-2", ids)

    def test_no_ac_file_returns_empty(self) -> None:
        items = semantic_review.extract_spec_items(
            ac_file=Path("/nonexistent"), objective_file=Path("/also-nope"),
        )
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
