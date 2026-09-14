"""The strict-YAML frontmatter guard (scripts/ci/validate.py::frontmatter_yaml_error).

Regression for the frontmatter-drop class that shipped a broken garden 12.37.1: batch B8 dropped the
`tool-capabilities:` key from `skills/data-engineer/SKILL.md` but left its value line `  - data-query`
orphaned, so the skills publish's `yaml.safe_load` refused the whole publish. A lenient regex frontmatter
reader never saw it. This guard strict-parses every SKILL.md frontmatter as YAML AND flags an orphaned
list value absorbed into a `|` block scalar (valid YAML, corrupt content) — both halves of the class.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("wg_validate", _REPO / "scripts" / "ci" / "validate.py")
_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate)
frontmatter_yaml_error = _validate.frontmatter_yaml_error

_CLEAN = '---\nname: wicked-garden-x\ndescription: "a one-line description"\nmetadata:\n  role: worker\n---\n# body\n'
_CLEAN_BLOCK = '---\nname: wicked-garden-x\ndescription: |\n  line one\n  line two\nmetadata:\n  role: worker\n---\n# body\n'
_MANDATES = '---\nname: wicked-garden-x\ndescription: d\nmandates:\n  - wicked-garden-core\n  - wicked-garden-qe\nmetadata:\n  role: router\n---\n'
# legit prose bullets in a description block (qe-code-analyzer style) — NOT orphans
_LEGIT_BULLETS = '---\nname: wicked-garden-x\ndescription: |\n  NOT THIS WHEN:\n  - Reviewing acceptance criteria for SMART+T — use `wicked-garden-qe-requirements-quality-analyst`\nmetadata:\n  role: worker\n---\n'


@pytest.mark.parametrize(("text", "ok"), [
    (_CLEAN, True),
    (_CLEAN_BLOCK, True),
    (_MANDATES, True),
    (_LEGIT_BULLETS, True),
    # ADVERSARIAL — the frontmatter-drop class must FAIL:
    # (a) orphan after a quoted scalar → YAML syntax error (the exact data-engineer / 12.37.1 shape)
    ('---\nname: wicked-garden-x\ndescription: "a one-line description"\n  - data-query\nmetadata:\n  role: worker\n---\n', False),
    # (b) orphan absorbed into a | block scalar → valid YAML but corrupt (the agentic/platform shape)
    ('---\nname: wicked-garden-x\ndescription: |\n  a real description line.\n  - security-scanning\nmetadata:\n  role: worker\n---\n', False),
    # (c) orphaned nested mapping value after a dropped key → syntax error
    ('---\nname: wicked-garden-x\ndescription: d\n  nested: leaked\nmetadata:\n  role: worker\n---\n', False),
    # (d) no frontmatter at all
    ('# just a body, no frontmatter\n', False),
])
def test_frontmatter_yaml_guard(text, ok):
    assert (frontmatter_yaml_error(text) is None) is ok, frontmatter_yaml_error(text)


def test_every_shipped_skill_frontmatter_is_valid_yaml():
    """The live tree: every SKILL.md frontmatter strict-parses and carries no orphaned value."""
    broken = {}
    for f in sorted((_REPO / "skills").rglob("SKILL.md")):
        err = frontmatter_yaml_error(f.read_text(encoding="utf-8"))
        if err is not None:
            broken[f.relative_to(_REPO).as_posix()] = err
    assert not broken, broken
