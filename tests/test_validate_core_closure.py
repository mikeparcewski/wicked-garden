"""The core-closure guard (scripts/ci/validate.py::dangling_skill_refs) — garden's mirror of the skills
publish's core-by-reference closure (wicked-crew packages/crew/src/skills/core-closure.ts).

History: garden 12.38.0 shipped skills/governed-worker/SKILL.md naming three skills batch B18 (#1169)
had DELETED — `wicked-garden-crew-implementer`, `-crew-reviewer`, `-crew-researcher`. B18 shielded the
prose mentions with `<!-- not-a-skill -->`, which satisfies garden's own linters
(tests/test_skill_portability.py `unresolved-skill-name` honors that marker). But the daemon's
skills-publish core-closure scans the SKILL.md body regardless of HTML comments, so it saw three
references to skills that are not in the catalog and REFUSED the publish (fail-closed) — the crew 0.7.38
smoke S02 blocker (both legs; it passed on garden 12.37.2, which still carried the stub skills). This is
the SECOND garden cut to ship a skills-publish-breaker garden CI missed (12.37.1 was invalid frontmatter
YAML); this guard closes the class.

The decisive divergence, asserted below: the guard does NOT honor `<!-- not-a-skill -->`, exactly as the
publish's closure does not. A shielded prose mention of a DELETED skill is a dangling reference to the
guard — that is the whole bug, so treating the shield as an exemption would reproduce it.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("wg_validate", _REPO / "scripts" / "ci" / "validate.py")
_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate)
dangling_skill_refs = _validate.dangling_skill_refs
catalog_skill_names = _validate.catalog_skill_names

# A small catalog for the unit cases; the real catalog is used by the shipped-skills regression below.
_CATALOG = {"wicked-garden-governed-worker", "wicked-garden-core", "wicked-garden-qe", "wicked-garden-x"}


def _names(text: str, self_name: str = "wicked-garden-x") -> set[str]:
    return {n for n, _ in dangling_skill_refs(text, self_name, _CATALOG)}


# --- CLEAN: references only real catalog skills / non-name tokens → NO dangling ref ---
_CLEAN = [
    # a prose mention of a real catalog skill
    "---\nname: wicked-garden-x\ndescription: d\n---\nUse the `wicked-garden-core` skill, then `wicked-garden-qe`.\n",
    # a self-reference is never a dangling ref
    "---\nname: wicked-garden-governed-worker\ndescription: d\n---\nFollow `wicked-garden-governed-worker` (A2).\n",
    # a glob/prefix token (trailing `-`) is not a name
    "---\nname: wicked-garden-x\ndescription: d\n---\nEnable `wicked-garden-qe-acceptance-test-*` for the phase.\n",
    # a `:`-continued token is a Claude subagent type, not a skill
    "---\nname: wicked-garden-x\ndescription: d\n---\nDispatch `wicked-garden:crew:implementer` as a subagent.\n",
    # a token glued to a preceding name character is not a mention
    "---\nname: wicked-garden-x\ndescription: d\n---\nThe path foo-wicked-garden-gone is unrelated.\n",
    # a wicked-garden-<x> token that ONLY ever appears in the blanked frontmatter is not prose
    "---\nname: wicked-garden-x\ndescription: see wicked-garden-gone\n---\nNo prose mention here.\n",
]

# --- DANGLING: names a skill absent from the catalog → MUST be flagged ---
_DANGLING = [
    # the exact 12.38.0 blocker, shield included — the shield MUST NOT exempt it (the whole bug)
    ("---\nname: wicked-garden-governed-worker\ndescription: d\n---\n"
     "History: `wicked-garden-crew-implementer` <!-- not-a-skill --> and `wicked-garden-crew-reviewer` were folded in.\n",
     "wicked-garden-governed-worker", {"wicked-garden-crew-implementer", "wicked-garden-crew-reviewer"}),
    # an unshielded prose mention of a deleted skill
    ("---\nname: wicked-garden-x\ndescription: d\n---\nSee `wicked-garden-gone` for details.\n",
     "wicked-garden-x", {"wicked-garden-gone"}),
    # the Claude plugin colon form `wicked-garden:<x>` is a reference too
    ("---\nname: wicked-garden-x\ndescription: d\n---\n## Engine — `wicked-garden:propose-process`\n",
     "wicked-garden-x", {"wicked-garden-propose-process"}),
    # a DECLARED frontmatter mandate naming an absent skill
    ("---\nname: wicked-garden-x\ndescription: d\nmandates:\n  - wicked-garden-gone\n---\nbody\n",
     "wicked-garden-x", {"wicked-garden-gone"}),
]


@pytest.mark.parametrize("text", _CLEAN, ids=[f"clean{i}" for i in range(len(_CLEAN))])
def test_clean_skill_has_no_dangling_refs(text):
    assert _names(text) == set(), _names(text)


@pytest.mark.parametrize("text,self_name,expected", _DANGLING, ids=[f"dangling{i}" for i in range(len(_DANGLING))])
def test_dangling_ref_is_flagged(text, self_name, expected):
    got = {n for n, _ in dangling_skill_refs(text, self_name, _CATALOG)}
    assert got == expected, got


def test_not_a_skill_shield_is_not_honored():
    """The core divergence: `<!-- not-a-skill -->` satisfies garden's test_skill_portability, but the
    skills-publish core-closure ignores it — so this guard must too, or it reproduces the 12.38.0 blocker."""
    shielded = (
        "---\nname: wicked-garden-governed-worker\ndescription: d\n---\n"
        "History: `wicked-garden-crew-implementer` <!-- not-a-skill -->, "
        "`wicked-garden-crew-reviewer` <!-- not-a-skill --> and "
        "`wicked-garden-crew-researcher` <!-- not-a-skill --> were folded in.\n"
    )
    got = {n for n, _ in dangling_skill_refs(shielded, "wicked-garden-governed-worker", _CATALOG)}
    assert got == {
        "wicked-garden-crew-implementer",
        "wicked-garden-crew-reviewer",
        "wicked-garden-crew-researcher",
    }, got


def test_every_shipped_skill_has_no_dangling_refs():
    """Regression over the real catalog: NO SKILL.md may name a skill absent from the catalog — the
    publish's core-closure refuses the whole publish on the first one (garden 12.38.0 / crew 0.7.38)."""
    skills_root = _REPO / "skills"
    catalog = catalog_skill_names(skills_root)
    broken: dict[str, list[str]] = {}
    for skill_md in sorted(skills_root.glob("**/SKILL.md")):
        dir_rel = skill_md.parent.relative_to(skills_root).as_posix()
        self_name = "wicked-garden-" + dir_rel.replace("/", "-")
        refs = dangling_skill_refs(skill_md.read_text(encoding="utf-8"), self_name, catalog)
        if refs:
            broken[skill_md.relative_to(_REPO).as_posix()] = [f"{n}:{ln}" for n, ln in refs]
    assert not broken, broken
