"""The strict frontmatter guard (scripts/ci/validate.py::frontmatter_yaml_error) — the EXACT mirror of the
skills publish's parser.

History: garden 12.37.1 shipped INVALID YAML in skills/data-engineer/SKILL.md (batch B8 dropped the
`tool-capabilities:` key but left its value `  - data-query` orphaned) — `yaml.safe_load` refused it and
blocked the whole publish. The first guard was a stdlib structural approximation (garden CI ran the leg
bare); a reviewer's adversarial battery then found 8 cases the real parser REJECTS but the stdlib guard
PASSED — most seriously the same frontmatter-drop class under a nested `metadata:`/`mandates:` key, the block
every wave-2 skill carries. This guard now calls the real `yaml.safe_load` (PyYAML installed on the CI legs)
so nothing the publish rejects goes green, plus a check for the SILENT subclass a plain parse accepts (a
bare-token list value absorbed into a `|` block scalar).
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
ci_yaml_requirement_error = _validate.ci_yaml_requirement_error

pytest.importorskip("yaml", reason="the guard mirrors the publish's yaml.safe_load; CI installs pyyaml")

# --- controls: well-formed frontmatter must PASS ---
_OK = [
    '---\nname: wicked-garden-x\ndescription: "a one-line description"\nmetadata:\n  role: worker\n---\n',
    '---\nname: wicked-garden-x\ndescription: |\n  line one\n  line two\nmetadata:\n  role: worker\n---\n',
    '---\nname: wicked-garden-x\ndescription: d\nmandates:\n  - wicked-garden-core\n  - wicked-garden-qe\nmetadata:\n  role: router\n---\n',
    '---\nname: wicked-garden-x\ndescription: |\n  NOT THIS WHEN:\n  - Reviewing acceptance criteria for SMART+T — use `wicked-garden-qe-requirements-quality-analyst`\nmetadata:\n  role: worker\n---\n',
    '---\n# a leading comment\n# and another\nname: wicked-garden-x\ndescription: |\n  d\nmetadata:\n  role: worker\n---\n',
    '---\nname: wicked-garden-x\ndescription: some plain text\n  continued on the next line\nmetadata:\n  role: worker\n---\n',
]

# --- the reviewer's adversarial battery: the real parser REJECTS these (or the |-block subclass), so the
#     guard MUST now flag every one (regression against the 8 divergences that passed the stdlib guard). ---
_BAD = [
    # 1. frontmatter-drop under a nested metadata: key — the incident class, the block every wave-2 skill carries
    '---\nname: x\ndescription: d\nmetadata:\n  role: worker\n  - orphaned-value\n---\n',
    # 2. frontmatter-drop under a nested mandates: key (a map entry after a seq item)
    '---\nname: x\ndescription: d\nmandates:\n  - wicked-garden-core\n  role: worker\n---\n',
    # 3. tab-indented value under a nested key (YAML forbids tab indentation)
    '---\nname: x\ndescription: d\nmetadata:\n\trole: worker\n---\n',
    # 4. mis-indented nested map (1-space drift)
    '---\nname: x\nmetadata:\n  role: worker\n   phases: x\n---\n',
    # 5. unterminated quoted scalar
    '---\nname: x\ndescription: "unterminated\nmetadata:\n  role: worker\n---\n',
    # 6. colon-in-unquoted-value
    '---\nname: x\ndescription: value: with colon\nmetadata:\n  role: worker\n---\n',
    # 7. col-0 sequence item mixed into the mapping
    '---\nname: x\ndescription: d\n- bare-seq\nmetadata:\n  role: worker\n---\n',
    # 8. SILENT subclass — valid YAML, corrupt: a bare-token list value absorbed into a | block scalar
    '---\nname: x\ndescription: |\n  a real description line.\n  - security-scanning\nmetadata:\n  role: worker\n---\n',
    # + the original 12.37.1 shape (orphan after a quoted scalar) and missing frontmatter
    '---\nname: x\ndescription: "d"\n  - data-query\nmetadata:\n  role: worker\n---\n',
    '# a body with no frontmatter at all\n',
]


@pytest.mark.parametrize("text", _OK, ids=[f"ok{i}" for i in range(len(_OK))])
def test_wellformed_frontmatter_passes(text):
    assert frontmatter_yaml_error(text) is None, frontmatter_yaml_error(text)


@pytest.mark.parametrize("text", _BAD, ids=[f"bad{i}" for i in range(len(_BAD))])
def test_frontmatter_drop_and_yaml_rejects_fail(text):
    assert frontmatter_yaml_error(text) is not None, "guard MISSED a case the publish's yaml.safe_load rejects"


def test_guard_mirrors_yaml_safe_load_on_the_battery():
    """The guard's verdict must match yaml.safe_load on every syntax case (the |-block subclass is the one
    intentional addition, where the guard is STRICTER than the parser — valid YAML, corrupt content)."""
    import yaml
    import re as _re
    silent = '---\nname: x\ndescription: |\n  a real description line.\n  - security-scanning\nmetadata:\n  role: worker\n---\n'
    for text in _OK + _BAD:
        block = _re.match(r"^---\n(.*?\n)---", text, _re.DOTALL)
        parses = True
        if block:
            try:
                yaml.safe_load(block.group(1))
            except yaml.YAMLError:
                parses = False
        else:
            parses = False
        guard_ok = frontmatter_yaml_error(text) is None
        if text == silent:
            assert parses and not guard_ok  # valid YAML the guard deliberately still flags
        else:
            assert guard_ok == parses, (text, guard_ok, parses)


def test_every_shipped_skill_frontmatter_is_valid():
    broken = {}
    for f in sorted((_REPO / "skills").rglob("SKILL.md")):
        err = frontmatter_yaml_error(f.read_text(encoding="utf-8"))
        if err is not None:
            broken[f.relative_to(_REPO).as_posix()] = err
    assert not broken, broken


# --- N1 (#1156 batch): in a CI context the guard MUST run the real yaml.safe_load, never the weaker stdlib
#     fallback, so a future edit dropping `pip install pyyaml` from a workflow can't silently re-weaken it.
#     Locally (no CI env) the graceful fallback stays. ---
@pytest.mark.parametrize(
    "yaml_available,env,expect_error",
    [
        (False, {"CI": "true"}, True),
        (False, {"GITHUB_ACTIONS": "true"}, True),
        (False, {}, False),          # local dev: graceful fallback, no hard-fail
        (True, {"CI": "true"}, False),  # CI with pyyaml installed: the intended state
        (True, {}, False),
    ],
)
def test_ci_yaml_requirement_hard_fails_only_in_ci(yaml_available, env, expect_error):
    err = ci_yaml_requirement_error(yaml_available, env)
    assert (err is not None) is expect_error, (yaml_available, env, err)
