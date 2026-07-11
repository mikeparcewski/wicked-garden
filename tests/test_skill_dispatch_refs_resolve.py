"""
Regression suite: every dispatch reference in skills/ must resolve to a real
skill, and every ``${CLAUDE_PLUGIN_ROOT}`` file reference must exist on disk.

History: this suite originally resolved Task(subagent_type="wicked-garden:*:*")
references in commands/ against agents/{domain}/{name}.md (audit finding #533 —
15 command files referenced agents that did not exist). The v12.25 skills-only
conversion retired both directories: workers are now context-fork skills and
dispatch happens two ways —

  1. ``Task(subagent_type="wicked-garden:{domain}:{role}")`` — legacy-shaped
     dispatch preserved for delegation adapters. It must resolve to a SKILL.md
     whose frontmatter declares that exact ``subagent_type:`` compat key AND
     ``context: fork``.
  2. ``Skill(skill="wicked-garden-<name>")`` — skill-to-skill dispatch. It must
     resolve to a SKILL.md whose frontmatter declares that ``name:``.

Additionally, every literal ``${CLAUDE_PLUGIN_ROOT}/<path>`` file reference in
a skill body must exist — the conversion moved a lot of content into refs/ and
a pointer at a file that didn't move with it is a silent capability loss.

Template placeholders (paths/refs containing ``{``) are skipped: they are
documentation of a pattern, not a concrete reference.
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

# Task-dispatch references in skill bodies (quoted, in Task() calls).
TASK_REF_RE = re.compile(
    r'subagent_type\s*=\s*"(wicked-garden:[a-z][a-z0-9-]*:[a-z][a-z0-9-]*)"'
)
# Skill-dispatch references in skill bodies. Only the plugin's own dash-form
# names are checked; sibling-plugin refs (wicked-brain:*, wicked-testing:*)
# are other repos' surfaces.
SKILL_REF_RE = re.compile(
    r"Skill\(skill=[\"'](wicked-garden-[a-z0-9]+(?:-[a-z0-9]+)*)[\"']"
)
# Literal plugin-root file references (concrete extensions only).
PLUGIN_PATH_RE = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./{}-]+\.(?:md|py|json|sh|mjs))"
)

# Pre-existing dangling paths that predate the skills-only conversion — they
# are documentation placeholders or already-filed staleness, not conversion
# regressions. Keep this list tight; anything new here is a real failure.
KNOWN_DANGLING_PATHS = {
    # Doc example placeholder ("some/script.py") in the runtime-exec skill.
    "scripts/some/script.py",
    # Pre-existing stale pointer in the user-story guide (predates v12.25).
    "scripts/user-story-template.sh",
    # Pre-existing stale pointer: imagery moved under skills/product/ but its
    # sub-skills still reference the old skills/imagery/ location.
    "skills/imagery/scripts/provider.py",
    # Pre-existing stale pointers (v12.21 cleanup): the requirements templates
    # directory was cut but the output-format ref still documents it.
    "templates/requirements-minimal.md",
    "templates/requirements-full.md",
}


def _skill_md_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("*.md"))


def _frontmatter_index() -> tuple[set[str], dict[str, Path]]:
    """(declared skill names, subagent_type -> fork SKILL.md path)."""
    names: set[str] = set()
    subagent_types: dict[str, Path] = {}
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        match = FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
        if not match:
            continue
        fm = match.group(1)
        name_match = NAME_RE.search(fm)
        if name_match:
            names.add(name_match.group(1).strip())
        st_match = SUBAGENT_KEY_RE.search(fm)
        if st_match and CONTEXT_FORK_RE.search(fm):
            subagent_types[st_match.group(1).strip()] = skill_md
    return names, subagent_types


_DECLARED_NAMES, _FORK_SUBAGENT_TYPES = _frontmatter_index()


def _task_ref_params():
    params = []
    for md_file in _skill_md_files():
        text = md_file.read_text(encoding="utf-8")
        for match in TASK_REF_RE.finditer(text):
            ref = match.group(1)
            if "{" in ref:
                continue  # template placeholder, not a concrete ref
            params.append(
                pytest.param(
                    md_file, ref, id=f"{md_file.relative_to(REPO)}::{ref}"
                )
            )
    return params


def _skill_ref_params():
    params = []
    for md_file in _skill_md_files():
        text = md_file.read_text(encoding="utf-8")
        for match in SKILL_REF_RE.finditer(text):
            ref = match.group(1)
            if "{" in ref:
                continue
            params.append(
                pytest.param(
                    md_file, ref, id=f"{md_file.relative_to(REPO)}::{ref}"
                )
            )
    return params


def _plugin_path_params():
    seen = set()
    params = []
    for md_file in _skill_md_files():
        text = md_file.read_text(encoding="utf-8")
        for match in PLUGIN_PATH_RE.finditer(text):
            rel = match.group(1)
            if "{" in rel or rel in KNOWN_DANGLING_PATHS:
                continue
            key = (str(md_file), rel)
            if key in seen:
                continue
            seen.add(key)
            params.append(
                pytest.param(
                    md_file, rel, id=f"{md_file.relative_to(REPO)}::{rel}"
                )
            )
    return params


@pytest.mark.parametrize("md_file,ref", _task_ref_params())
def test_task_subagent_ref_resolves_to_fork_skill(md_file: Path, ref: str):
    """Every Task(subagent_type=...) must map to a context:fork skill that
    declares the same subagent_type compat key in its frontmatter."""
    assert ref in _FORK_SUBAGENT_TYPES, (
        f"{md_file.relative_to(REPO)}: dispatches '{ref}' but no context:fork "
        "SKILL.md declares that subagent_type. Known fork subagent_types: "
        f"{sorted(_FORK_SUBAGENT_TYPES)}"
    )


@pytest.mark.parametrize("md_file,ref", _skill_ref_params())
def test_skill_dispatch_ref_resolves(md_file: Path, ref: str):
    """Every Skill(skill="wicked-garden-...") must name a declared skill."""
    assert ref in _DECLARED_NAMES, (
        f"{md_file.relative_to(REPO)}: dispatches skill '{ref}' but no "
        "SKILL.md declares that name in its frontmatter."
    )


@pytest.mark.parametrize("md_file,rel", _plugin_path_params())
def test_plugin_root_file_reference_exists(md_file: Path, rel: str):
    """Every concrete ${CLAUDE_PLUGIN_ROOT}/<path> reference must exist."""
    assert (REPO / rel).exists(), (
        f"{md_file.relative_to(REPO)}: references "
        f"${{CLAUDE_PLUGIN_ROOT}}/{rel} but that file does not exist — a "
        "refs/ pointer or script path did not survive the skills-only move."
    )


def test_reference_extraction_is_not_vacuous():
    """Guard against a silent regex/layout drift making the suite pass empty.

    The v12.25 skills-only conversion retired concrete
    ``Task(subagent_type="wicked-garden:...")`` *call-forms* from skill bodies:
    skill-to-skill dispatch is now ``Skill(skill="wicked-garden-...")`` and the
    legacy Task shape survives only as a ``subagent_type:`` compat key in
    fork-skill *frontmatter* (line-scanned by the delegation adapter,
    ``scripts/smaht/adapters/delegation_adapter.py``). So ``_task_ref_params()``
    is legitimately empty now — ``test_task_subagent_ref_resolves_to_fork_skill``
    still validates any body call-form that reappears, and the Task-dispatch
    machinery's real non-vacuity signal is its frontmatter resolution index,
    asserted here by count (matching ``test_some_workers_keep_compat_keys`` in
    the naming suite: adapters line-scan these, so dropping them all is the drift
    we actually guard against).
    """
    assert _skill_ref_params(), "no Skill dispatch refs found in skills/ — extraction broke"
    assert len(_plugin_path_params()) > 20, (
        "implausibly few ${CLAUDE_PLUGIN_ROOT} references found — extraction broke"
    )
    assert len(_FORK_SUBAGENT_TYPES) >= 3, (
        "fewer than 3 fork skills declare a subagent_type compat key — the "
        "frontmatter index the Task-dispatch resolver targets looks broken"
    )
