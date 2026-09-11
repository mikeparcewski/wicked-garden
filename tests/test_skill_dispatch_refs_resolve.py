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

Additionally, every plugin file a skill body reaches through the launcher —
``wicked-garden run|python|path <root-relative path>`` — must exist: the
cross-CLI convention (F-079, 12.33) replaced every ``${CLAUDE_PLUGIN_ROOT}/<path>``
reference with a launcher call, and a pointer at a file that does not exist is
the same silent capability loss the old plugin-root check guarded against.
``${CLAUDE_PLUGIN_ROOT}`` references themselves are asserted ABSENT here (the
full portability lint is ``tests/test_skill_portability.py``).

Template placeholders (paths/refs containing ``{``) are skipped: they are
documentation of a pattern, not a concrete reference.
"""
import json
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
# names are checked; sibling-plugin refs (wicked-bus:*) are other repos'
# surfaces.
SKILL_REF_RE = re.compile(
    r"Skill\(skill=[\"'](wicked-garden-[a-z0-9]+(?:-[a-z0-9]+)*)[\"']"
)
# Literal plugin-root file references (concrete extensions only). Kept so the
# suite can assert there are NONE left under skills/ (12.33 portability).
PLUGIN_PATH_RE = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./{}-]+\.(?:md|py|json|sh|mjs))"
)
# Launcher calls — `wicked-garden run|python|path <root-relative path>` (also the
# CI-template spelling `npx wicked-garden@12 run …`); the target may sit on the
# next line after a trailing `\`, and `python -c …` / `python -` carry no path.
# Every path target must exist. The two template mentions inside the standard
# `## Runtime` block (exact text in tests/portability_rules.json) are not calls.
LAUNCHER_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:npx\s+)?wicked-garden(?:@[A-Za-z0-9_.^~-]+)?\s+"
    r"(run|python|path)(?:[ \t]+(\S+))?"
)
_RUNTIME_BLOCK_LINES = set(
    json.loads((REPO / "tests" / "portability_rules.json").read_text(encoding="utf-8"))
    ["launcher"]["runtime_block"].split("\n")
)


def _launcher_calls() -> list[tuple[Path, int, str, str | None]]:
    """(file, line, verb, target-or-None) for every launcher call site under skills/."""
    calls = []
    for md_file in _skill_md_files():
        lines = md_file.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if line in _RUNTIME_BLOCK_LINES:
                continue
            for match in LAUNCHER_CALL_RE.finditer(line):
                verb, target = match.group(1), match.group(2)
                if target in (None, "\\"):
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    target = lines[j].strip().split()[0] if j < len(lines) and lines[j].strip() else None
                if target is not None:
                    # a call site ends in prose punctuation / closing quotes+parens as often as not
                    target = target.strip("`'\"").rstrip("\\;,)`\"'.:")
                calls.append((md_file, i + 1, verb, target))
    return calls


def _is_path_target(target: str | None) -> bool:
    return bool(target) and not target.startswith(("-", "<", "…")) and "{" not in target and (
        "/" in target or re.search(r"\.(?:py|mjs|js|cjs|sh|md|json|yml|yaml)$", target) is not None
    )

# Dangling paths this suite deliberately tolerates. Emptied by #1111: the five
# pre-existing entries (the imagery provider.py path left behind by the move
# under skills/product/, the two requirements templates cut in v12.21, the
# never-shipped user-story generator script, and the runtime-exec doc
# placeholder) were fixed at the source, so any of them dangling again is a
# real failure. Anything added here hides a broken skill body — fix the body.
KNOWN_DANGLING_PATHS: set[str] = set()


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


def _launcher_path_params():
    seen = set()
    params = []
    for md_file, _lineno, _verb, target in _launcher_calls():
        if not _is_path_target(target):
            continue  # `python -c` / `-` pass-through, template placeholder
        key = (str(md_file), target)
        if key in seen:
            continue
        seen.add(key)
        params.append(
            pytest.param(
                md_file, target, id=f"{md_file.relative_to(REPO)}::{target}"
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


@pytest.mark.parametrize("md_file,rel", _launcher_path_params())
def test_launcher_path_reference_exists(md_file: Path, rel: str):
    """Every `wicked-garden run|python|path <rel>` target must exist at the plugin root."""
    assert (REPO / rel).exists(), (
        f"{md_file.relative_to(REPO)}: runs `wicked-garden … {rel}` but that "
        "file does not exist under the plugin root — a script path did not "
        "survive a move."
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
    # 12.33 (F-079) INVERTED the plugin-root guard: skill text reaches plugin
    # files only through the `wicked-garden` launcher, so the plugin-root count
    # must be ZERO and the launcher-call count implausibly LARGE for a regex
    # drift to pass vacuously (tests/test_skill_portability.py owns the rest).
    assert len(_plugin_path_params()) == 0, (
        "${CLAUDE_PLUGIN_ROOT} references under skills/ — Claude-only; use "
        "`wicked-garden run <path>` / skill-relative paths (see .claude/CLAUDE.md): "
        f"{[p.id for p in _plugin_path_params()][:5]}"
    )
    launcher_calls = len(_launcher_calls())
    assert launcher_calls > 200, (
        f"only {launcher_calls} launcher calls found under skills/ — "
        "extraction broke or the shared-runtime call sites were lost"
    )
    assert len(_launcher_path_params()) > 100, (
        f"only {len(_launcher_path_params())} distinct launcher targets — extraction broke"
    )
    assert len(_FORK_SUBAGENT_TYPES) >= 3, (
        "fewer than 3 fork skills declare a subagent_type compat key — the "
        "frontmatter index the Task-dispatch resolver targets looks broken"
    )
