"""
Regression suite: the core skill's help surface must describe the ACTUAL skill tree.

History: this suite originally diffed commands/help.md against the commands/
directory (garden-docs review, 2026-06 — help.md had drifted to a retired v6
architecture and nothing caught it). The v12.25 skills-only conversion retired
commands/ and agents/ entirely: user entry points are consolidated per-domain
skills (skills/<domain>/SKILL.md), former agents are context-fork worker skills
(skills/<domain>-<role>/SKILL.md), and the help overview is the `help` action
of the core skill (skills/core/SKILL.md). The failure mode is unchanged — an
advertised surface that drifts from the real one — so the suite now diffs the
help overview against the skills/ tree:

  - FAIL if help advertises a ``wicked-garden-<x>`` skill that no SKILL.md
    declares in its frontmatter ``name:``.
  - FAIL if a real user-entry skill (top-level skills/<dir>/SKILL.md without
    ``context: fork``) is not mentioned in the help overview.
  - FAIL if the core action router drops one of the utility actions that
    absorbed the former top-level commands (help/setup/install/reset/
    where-am-i/report-issue).
  - FAIL if the archetype entry skill drops an archetype the catalog declares
    (the former commands/archetype/{name}.md surface).

Extraction is deliberately tolerant (token-level), so help can phrase prose
freely as long as every advertised skill is real and every real entry skill is
mentioned.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SKILLS_DIR = REPO / "skills"
CORE_SKILL = SKILLS_DIR / "core" / "SKILL.md"
ARCHETYPE_SKILL = SKILLS_DIR / "archetype" / "SKILL.md"
ARCHETYPES_JSON = REPO / ".claude-plugin" / "archetypes.json"

# Match a plugin-skill token: wicked-garden-<kebab-name>. Sibling plugins
# (wicked-brain, wicked-testing, wicked-bus, ...) never carry the
# `wicked-garden-` prefix, so they are excluded by construction.
SKILL_TOKEN_RE = re.compile(r"\bwicked-garden-[a-z0-9]+(?:-[a-z0-9]+)*")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
CONTEXT_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)

# The utility actions the core skill absorbed from the former top-level
# commands/{help,setup,install,reset,where-am-i,report-issue}.md. Dropping one
# from the action router silently loses a user surface.
CORE_UTILITY_ACTIONS = {
    "help",
    "setup",
    "install",
    "reset",
    "where-am-i",
    "report-issue",
}


def _frontmatter(path: Path) -> str:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.relative_to(REPO)}: SKILL.md has no YAML frontmatter"
    return match.group(1)


def _declared_skill_names() -> set[str]:
    """Every ``name:`` declared by any SKILL.md under skills/ (all depths)."""
    names = set()
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        name_match = NAME_RE.search(_frontmatter(skill_md))
        if name_match:
            names.add(name_match.group(1).strip())
    return names


def _entry_skills() -> dict[str, str]:
    """Top-level user-entry skills: skills/<dir>/SKILL.md without context: fork.

    Fork-context skills are workers reached by dispatch, not entry points the
    operator would look for in help — the same scoping the old suite applied by
    reading commands/ (entry points) and not agents/ (workers).
    """
    entries = {}
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = _frontmatter(skill_md)
        if CONTEXT_FORK_RE.search(fm):
            continue
        name_match = NAME_RE.search(fm)
        assert name_match, f"{skill_md.relative_to(REPO)}: missing name"
        entries[skill_dir.name] = name_match.group(1).strip()
    return entries


def _help_text() -> str:
    return CORE_SKILL.read_text(encoding="utf-8")


def test_help_advertises_only_real_skills():
    """Every wicked-garden-<x> token in the help overview must be a real skill."""
    advertised = set(SKILL_TOKEN_RE.findall(_help_text()))
    declared = _declared_skill_names()
    phantom = sorted(advertised - declared)
    assert not phantom, (
        "skills/core/SKILL.md advertises skill name(s) no SKILL.md declares: "
        f"{phantom}. Declared names: {sorted(n for n in declared if n.startswith('wicked-garden-'))}. "
        "Update the help overview to match the actual skill tree."
    )


@pytest.mark.parametrize(
    "skill_dir,skill_name", sorted(_entry_skills().items())
)
def test_every_entry_skill_is_advertised(skill_dir: str, skill_name: str):
    """Every real user-entry skill must appear in the help overview."""
    assert skill_name in _help_text(), (
        f"skills/core/SKILL.md does not mention the entry skill '{skill_name}' "
        f"(skills/{skill_dir}/SKILL.md, not context:fork). Add it to the help "
        "overview so operators can discover it."
    )


@pytest.mark.parametrize("action", sorted(CORE_UTILITY_ACTIONS))
def test_core_action_router_covers_utility_surface(action: str):
    """The core skill must still route every absorbed top-level utility action."""
    assert f"`{action}`" in _help_text(), (
        f"skills/core/SKILL.md no longer lists the '{action}' action. That "
        "action absorbed a former top-level command surface — dropping it "
        "loses user-reachable functionality."
    )


def test_archetype_skill_covers_catalog():
    """Every catalog archetype must be reachable from the archetype entry skill.

    The former commands/archetype/{name}.md files (one per archetype) are gone;
    skills/archetype/SKILL.md is now the single dispatch surface. If the
    catalog declares an archetype the skill never mentions, that work-shape is
    unreachable by name.
    """
    catalog = json.loads(ARCHETYPES_JSON.read_text(encoding="utf-8"))
    archetypes = catalog["archetypes"]
    # The catalog is a name-keyed object; tolerate a list-of-objects layout too.
    if isinstance(archetypes, dict):
        catalog_names = sorted(archetypes.keys())
    else:
        catalog_names = sorted(a["name"] for a in archetypes)
    assert catalog_names, ".claude-plugin/archetypes.json declares no archetypes"

    skill_text = ARCHETYPE_SKILL.read_text(encoding="utf-8")
    missing = sorted(n for n in catalog_names if n not in skill_text)
    assert not missing, (
        "skills/archetype/SKILL.md does not mention catalog archetype(s) "
        f"{missing} — every archetype in .claude-plugin/archetypes.json must "
        "be dispatchable from the archetype entry skill."
    )
