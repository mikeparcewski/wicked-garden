"""
Regression suite: no two SKILL.md files may declare the same frontmatter name.

History: this suite originally guarded agent basename collisions across
agents/{domain}/ directories (audit findings #533/#534 — `facilitator` existed
in both jam/ and crew/, creating routing ambiguity). The v12.25 skills-only
conversion retired agents/; the ambiguity now lives in skill discovery: the
Skill() tool and the fork-skill loader resolve by frontmatter ``name``, so two
SKILL.md files sharing a name would race for the same dispatches.

Every SKILL.md (any depth — consolidated domain skills, nested sub-skills,
fork workers) must therefore parse, declare a name, and that name must be
unique across the whole tree.
"""
import re
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SKILLS_DIR = REPO / "skills"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


def _all_skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def test_every_skill_has_frontmatter_name():
    """Each SKILL.md must carry parsable frontmatter with a name field."""
    files = _all_skill_files()
    assert len(files) >= 80, (
        f"only {len(files)} SKILL.md files found — the skills-only tree "
        "should carry domains + nested sub-skills + fork workers"
    )
    broken = []
    for skill_md in files:
        match = FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
        if not match or not NAME_RE.search(match.group(1)):
            broken.append(str(skill_md.relative_to(REPO)))
    assert not broken, (
        "SKILL.md files missing frontmatter or a name field "
        f"(unloadable by skill discovery): {broken}"
    )


def test_skill_names_are_unique_across_tree():
    """No two SKILL.md files declare the same name (routing ambiguity)."""
    name_to_paths: dict[str, list[Path]] = defaultdict(list)
    for skill_md in _all_skill_files():
        match = FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
        if not match:
            continue  # reported by test_every_skill_has_frontmatter_name
        name_match = NAME_RE.search(match.group(1))
        if not name_match:
            continue
        name_to_paths[name_match.group(1).strip()].append(skill_md)

    duplicates = {
        name: paths for name, paths in name_to_paths.items() if len(paths) > 1
    }
    if duplicates:
        lines = []
        for name, paths in sorted(duplicates.items()):
            rel_paths = [str(p.relative_to(REPO)) for p in paths]
            lines.append(f"  '{name}': {rel_paths}")
        detail = "\n".join(lines)
        pytest.fail(
            "Skill name collisions detected (Skill() dispatch and the "
            f"fork-skill loader resolve by name):\n{detail}"
        )
