"""
Regression suite: every agent file must have subagent_type matching its path.

Audit finding: #535 — 71 agents were missing subagent_type frontmatter.
Fix: bulk injection via Python script in build phase (2026-04-19).
This suite ensures no agent is added in the future without the field.

Expected pattern: agents/{domain}/{stem}.md → subagent_type: wicked-garden:{domain}:{stem}
"""
import re
from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
AGENTS_DIR = REPO / "agents"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
SUBAGENT_TYPE_RE = re.compile(r"^subagent_type:\s*(.+)$", re.MULTILINE)


def _parse_subagent_type(text: str):
    """Return subagent_type value from frontmatter, or None if absent."""
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    st_match = SUBAGENT_TYPE_RE.search(fm_match.group(1))
    if not st_match:
        return None
    return st_match.group(1).strip()


def _agent_params():
    """Collect (path, expected_subagent_type) for all agent .md files."""
    params = []
    for md_file in sorted(AGENTS_DIR.rglob("*.md")):
        domain = md_file.parent.name
        stem = md_file.stem
        expected = f"wicked-garden:{domain}:{stem}"
        params.append(pytest.param(md_file, expected, id=f"{domain}/{stem}"))
    return params


@pytest.mark.parametrize("agent_path,expected_subagent_type", _agent_params())
def test_agent_has_correct_subagent_type(agent_path: Path, expected_subagent_type: str):
    """Agent file must declare subagent_type matching its file path convention."""
    text = agent_path.read_text(encoding="utf-8")
    actual = _parse_subagent_type(text)
    assert actual is not None, (
        f"{agent_path.relative_to(REPO)}: missing subagent_type in frontmatter"
    )
    assert actual == expected_subagent_type, (
        f"{agent_path.relative_to(REPO)}: subagent_type '{actual}' does not match "
        f"expected '{expected_subagent_type}' (derived from file path)"
    )
