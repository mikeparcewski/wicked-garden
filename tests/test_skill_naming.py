"""
Regression suite: skill frontmatter names must follow the skills-only
conventions, and worker compat keys must stay resolvable.

History: this suite originally pinned agents/{domain}/{stem}.md →
``subagent_type: wicked-garden:{domain}:{stem}`` (audit finding #535 — 71
agents were missing the field). The v12.25 skills-only conversion moved every
worker to a standalone context-fork skill; the invariants move with them:

  1. Every top-level skills/<dir>/SKILL.md declares
     ``name: wicked-garden-<dir>`` — the dash-form naming the conversion
     standardized on (colons retired with the command namespace). A name that
     drifts from its directory breaks Skill() dispatch and help discovery.
  2. Any SKILL.md that keeps a legacy ``subagent_type:`` compat key (consumed
     by delegation adapters / specialist resolvers that line-scan frontmatter)
     must (a) be a fork-context worker, (b) use the well-formed
     ``wicked-garden:{domain}:{role}`` shape, and (c) live in the directory
     that shape implies (``{role}`` or ``{domain}-{role}``) so a path-based
     resolver and a name-based resolver agree.

Nested skills (skills/<domain>/<sub>/SKILL.md) are namespaced by their parent
domain directory and keep short or fully-qualified names by local precedent;
cross-tree ambiguity is covered by test_skill_name_uniqueness.py.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SKILLS_DIR = REPO / "skills"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
SUBAGENT_KEY_RE = re.compile(r"^subagent_type:\s*(.+)$", re.MULTILINE)
CONTEXT_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)
SUBAGENT_SHAPE_RE = re.compile(
    r"^wicked-garden:([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)$"
)

# Pre-existing skills whose bare frontmatter name predates the conversion's
# wicked-garden-<dir> standard. Keep tight — new skills must not join it.
# ``workflow`` graduated to the standard ``wicked-garden-workflow`` name in the
# v12.25 skills-only cleanup, so the set is now empty; every top-level skill
# must track its directory as ``wicked-garden-<dir>``.
LEGACY_BARE_NAMES: set[str] = set()


def _frontmatter(path: Path) -> str:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.relative_to(REPO)}: SKILL.md has no YAML frontmatter"
    return match.group(1)


def _toplevel_params():
    params = []
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            params.append(pytest.param(skill_md, id=skill_dir.name))
    return params


def _subagent_key_params():
    params = []
    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        st_match = SUBAGENT_KEY_RE.search(_frontmatter(skill_md))
        if st_match:
            params.append(
                pytest.param(
                    skill_md,
                    st_match.group(1).strip(),
                    id=str(skill_md.relative_to(SKILLS_DIR).parent),
                )
            )
    return params


@pytest.mark.parametrize("skill_md", _toplevel_params())
def test_toplevel_skill_name_matches_directory(skill_md: Path):
    """skills/<dir>/SKILL.md must declare name: wicked-garden-<dir>."""
    dir_name = skill_md.parent.name
    name_match = NAME_RE.search(_frontmatter(skill_md))
    assert name_match, (
        f"{skill_md.relative_to(REPO)}: missing 'name:' in frontmatter"
    )
    actual = name_match.group(1).strip()
    if dir_name in LEGACY_BARE_NAMES:
        assert actual == dir_name, (
            f"{skill_md.relative_to(REPO)}: legacy-bare skill renamed to "
            f"'{actual}' — either restore '{dir_name}' or adopt "
            f"'wicked-garden-{dir_name}' and remove it from LEGACY_BARE_NAMES"
        )
        return
    expected = f"wicked-garden-{dir_name}"
    assert actual == expected, (
        f"{skill_md.relative_to(REPO)}: name '{actual}' does not match "
        f"expected '{expected}' (derived from the directory name). Skill "
        "names are dash-form and must track their directory so dispatch and "
        "help discovery agree."
    )


def test_toplevel_skill_set_is_not_vacuous():
    """The tree must contain a plausible number of top-level skills."""
    count = len(_toplevel_params())
    assert count >= 40, (
        f"only {count} top-level skills found — the skills-only tree should "
        "carry the consolidated domains plus the converted fork workers"
    )


@pytest.mark.parametrize("skill_md,subagent_type", _subagent_key_params())
def test_subagent_compat_key_is_wellformed_and_consistent(
    skill_md: Path, subagent_type: str
):
    """A kept subagent_type compat key must be fork-scoped and path-consistent."""
    fm = _frontmatter(skill_md)
    assert CONTEXT_FORK_RE.search(fm), (
        f"{skill_md.relative_to(REPO)}: declares subagent_type "
        f"'{subagent_type}' but is not context: fork — the compat key only "
        "makes sense on a dispatchable worker skill"
    )
    shape = SUBAGENT_SHAPE_RE.match(subagent_type)
    assert shape, (
        f"{skill_md.relative_to(REPO)}: subagent_type '{subagent_type}' does "
        "not match wicked-garden:{domain}:{role}"
    )
    domain, role = shape.group(1), shape.group(2)
    dir_name = skill_md.parent.name
    allowed = {role, f"{domain}-{role}"}
    assert dir_name in allowed, (
        f"{skill_md.relative_to(REPO)}: subagent_type '{subagent_type}' "
        f"implies directory {sorted(allowed)} but the skill lives in "
        f"'{dir_name}' — path-based and key-based resolution would disagree"
    )
    name_match = NAME_RE.search(fm)
    assert name_match and name_match.group(1).strip() == f"wicked-garden-{dir_name}", (
        f"{skill_md.relative_to(REPO)}: worker skill name must be "
        f"'wicked-garden-{dir_name}' so name-based dispatch matches the "
        "subagent_type compat key"
    )


def test_some_workers_keep_compat_keys():
    """Guard against silently dropping every compat key (adapters line-scan them)."""
    assert len(_subagent_key_params()) >= 3, (
        "fewer than 3 skills carry a subagent_type compat key — if the "
        "delegation adapters moved off subagent_type entirely, update this "
        "suite alongside them"
    )
