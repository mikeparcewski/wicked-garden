"""
Regression suite: skills/workflow/SKILL.md must describe v6 reality.

Audit finding: #536 — workflow/SKILL.md described v3 architecture (smart_decisioning.py,
v5 rule engine) as current. The file was rewritten in build phase (2026-04-19) to
describe the v6 facilitator-rubric decision engine.

This suite guards against drift back to stale v3/v5 content.
"""
from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
SKILL_PATH = REPO / "skills" / "workflow" / "SKILL.md"

STALE_PHRASES = [
    "smart_decisioning",
    "v3 architecture",
    "v5 rule engine",
    "Workflow Skill (v3)",
    "Smart Decisioning",
]

REQUIRED_PHRASES = [
    "propose-process",
]


@pytest.fixture(scope="module")
def skill_text():
    assert SKILL_PATH.exists(), f"skills/workflow/SKILL.md not found at {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("stale_phrase", STALE_PHRASES)
def test_workflow_skill_does_not_mention_stale_content(skill_text: str, stale_phrase: str):
    """
    SKILL.md must not present v3/v5 concepts as current.
    Historical mentions in refs/ files are allowed; only the entry SKILL.md is checked.
    """
    # Allow mentions only inside code blocks or quoted as historical context
    # Simple check: the phrase should not appear as a current description
    assert stale_phrase not in skill_text, (
        f"skills/workflow/SKILL.md mentions '{stale_phrase}' — this was part of the "
        f"v3/v5 architecture that no longer exists in v6. Update or remove."
    )


@pytest.mark.parametrize("required_phrase", REQUIRED_PHRASES)
def test_workflow_skill_mentions_v6_decision_engine(skill_text: str, required_phrase: str):
    """SKILL.md must reference propose-process as the v6 decision engine."""
    assert required_phrase in skill_text, (
        f"skills/workflow/SKILL.md does not mention '{required_phrase}'. "
        f"The v6 decision engine is wicked-garden:propose-process — "
        f"the SKILL.md must describe it."
    )


def test_workflow_skill_under_200_lines(skill_text: str):
    """SKILL.md must stay under the 200-line plugin validator cap."""
    line_count = len(skill_text.splitlines())
    assert line_count <= 200, (
        f"skills/workflow/SKILL.md has {line_count} lines — exceeds 200-line cap "
        f"enforced by the plugin validator"
    )
