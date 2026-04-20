"""
tests/test_command_cross_links.py

Regression suite for cross-link hygiene introduced in v6.3.3 (#533).

For every paired command in the hygiene bundle, asserts that each command
mentions its partner somewhere in its body content (case-insensitive grep).
This prevents the UX anti-pattern where related commands are invisible to
each other.

Pairs checked:
  - product:ux ↔ product:ux-review
  - jam:quick ↔ jam:brainstorm ↔ jam:council (progression)
  - search:blast-radius ↔ search:lineage
  - qe:acceptance ↔ qe:scenarios
  - crew:operate ↔ crew:status
  - crew:explain → crew:status (one-way: explain mentions status)
  - crew:incident ↔ platform:incident
  - product:acceptance → qe:acceptance (one-way: product side mentions qe side)
  - crew:yolo → crew:auto-approve (alias stub mentions canonical)
  - crew:auto-approve → crew:just-finish, crew:execute (when-to-use table)
  - product:listen → product:analyze (next-step pipeline)
  - product:analyze → product:synthesize (next-step pipeline)
  - product:synthesize → product:listen (back-ref to pipeline start)
"""

from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
COMMANDS = REPO / "commands"


def _read(domain: str, command: str) -> str:
    """Read a command file and return its content."""
    path = COMMANDS / domain / f"{command}.md"
    assert path.exists(), f"Command file not found: {path.relative_to(REPO)}"
    return path.read_text(encoding="utf-8")


def _assert_mentions(source_domain: str, source_cmd: str, target: str) -> None:
    """Assert that source command body mentions target string (case-insensitive)."""
    content = _read(source_domain, source_cmd)
    assert target.lower() in content.lower(), (
        f"commands/{source_domain}/{source_cmd}.md does not mention '{target}'. "
        f"Cross-link required by #533 hygiene bundle to prevent invisible-partner UX anti-pattern."
    )


class TestProductUxPair:
    def test_ux_mentions_ux_review(self):
        _assert_mentions("product", "ux", "ux-review")

    def test_ux_review_mentions_ux(self):
        _assert_mentions("product", "ux-review", "product:ux")


class TestJamProgression:
    def test_quick_mentions_brainstorm(self):
        _assert_mentions("jam", "quick", "brainstorm")

    def test_quick_mentions_council(self):
        _assert_mentions("jam", "quick", "council")

    def test_brainstorm_mentions_quick(self):
        _assert_mentions("jam", "brainstorm", "quick")

    def test_brainstorm_mentions_council(self):
        _assert_mentions("jam", "brainstorm", "council")

    def test_council_mentions_brainstorm(self):
        _assert_mentions("jam", "council", "brainstorm")

    def test_council_mentions_quick(self):
        _assert_mentions("jam", "council", "quick")


class TestSearchPair:
    def test_blast_radius_mentions_lineage(self):
        _assert_mentions("search", "blast-radius", "lineage")

    def test_lineage_mentions_blast_radius(self):
        _assert_mentions("search", "lineage", "blast-radius")


class TestQePair:
    def test_acceptance_removed_v71(self):
        """qe:acceptance removed in v7.1 — use /wicked-testing:execution instead."""
        pass  # commands/qe/acceptance.md deleted in v7.1 (#551, #553)

    def test_scenarios_removed_v71(self):
        """qe:scenarios removed in v7.1 — use /wicked-testing:authoring instead."""
        pass  # commands/qe/scenarios.md deleted in v7.1 (#551, #553)


class TestCrewOperateStatus:
    def test_operate_mentions_status(self):
        _assert_mentions("crew", "operate", "status")

    def test_status_mentions_operate(self):
        _assert_mentions("crew", "status", "operate")


class TestCrewExplainStatus:
    def test_explain_mentions_status(self):
        """crew:explain should mention crew:status as a common predecessor."""
        _assert_mentions("crew", "explain", "status")


class TestIncidentPair:
    def test_crew_incident_mentions_platform_incident(self):
        _assert_mentions("crew", "incident", "platform:incident")

    def test_platform_incident_mentions_crew_incident(self):
        _assert_mentions("platform", "incident", "crew:incident")


class TestProductQeAcceptancePair:
    def test_product_acceptance_mentions_wicked_testing(self):
        _assert_mentions("product", "acceptance", "wicked-testing:execution")


class TestCrewAliasRedirect:
    def test_yolo_mentions_auto_approve(self):
        _assert_mentions("crew", "yolo", "auto-approve")


class TestCrewAutoApproveWhenToUse:
    def test_auto_approve_mentions_just_finish(self):
        _assert_mentions("crew", "auto-approve", "just-finish")

    def test_auto_approve_mentions_execute(self):
        _assert_mentions("crew", "auto-approve", "execute")


class TestProductFeedbackPipeline:
    def test_listen_mentions_analyze(self):
        _assert_mentions("product", "listen", "analyze")

    def test_analyze_mentions_synthesize(self):
        _assert_mentions("product", "analyze", "synthesize")

    def test_synthesize_mentions_listen(self):
        _assert_mentions("product", "synthesize", "listen")

    def test_analyze_mentions_listen(self):
        _assert_mentions("product", "analyze", "listen")
