"""wicked-garden-codemod-first: the mechanical-first gate for upgrade and modernization work (#1334).

Pins the skill's format, its trigger evals (4 activate, 2 skip), the decision-block contract the
wicked-core `mechanical_first` step reads, and its wiring into the archetype playbooks, the
governed-worker floor and the help table.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "skills" / "codemod-first" / "SKILL.md"
BLOCK_REF = REPO / "skills" / "codemod-first" / "refs" / "decision-block.md"
SCRIPT = REPO / "scripts" / "engineering" / "mechanical_first.py"
CASES = Path(__file__).parent / "eval_cases"
NAME = "wicked-garden-codemod-first"


def _mf():
    spec = importlib.util.spec_from_file_location("mechanical_first", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _frontmatter() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md has no frontmatter"
    return yaml.safe_load(m.group(1))


# ── the skill ────────────────────────────────────────────────────────────────────────────────

def test_the_skill_strict_parses_with_the_closed_key_set():
    fm = _frontmatter()
    assert fm["name"] == NAME
    assert set(fm) <= {"name", "description", "license", "compatibility", "metadata", "mandates"}
    assert isinstance(fm["description"], str) and 0 < len(fm["description"]) <= 1024
    assert fm["metadata"]["role"] == "router"
    assert all(isinstance(v, str) for v in fm["metadata"].values())


def test_the_skill_links_the_migration_module_and_copies_none_of_it():
    body = SKILL.read_text(encoding="utf-8")
    assert "wicked-garden-engineering-large-scale-migration" in body
    module = (REPO / "skills" / "engineering" / "large-scale-migration" / "SKILL.md").read_text(encoding="utf-8")
    assert "| # | Technique |" in module          # the table lives there ...
    assert "| # | Technique |" not in body        # ... and only there
    for row in re.findall(r"^\| \d \| \*\*(.+?)\*\*", module, re.M):
        assert f"**{row}**" not in body, row


def test_the_skill_requires_the_block_or_a_written_rejection():
    body = " ".join(SKILL.read_text(encoding="utf-8").split())
    assert "refs/decision-block.md" in body
    assert "`mechanical-first: rejected — <reason>`" in body
    assert "Silence is not a choice" in body
    for key in ("inventory", "count", "recipe_checked", "codemod", "gate", "residue"):
        assert f"`{key}`" in body, key


def test_nothing_depends_on_a_hook():
    body = SKILL.read_text(encoding="utf-8")
    assert "not by a hook" in body
    assert "hooks/" not in body and "PreToolUse" not in body


# ── trigger evals (4 activate, 2 skip) ───────────────────────────────────────────────────────

def _cases() -> list[dict]:
    return json.loads((CASES / "triggers.json").read_text(encoding="utf-8"))["cases"]


def test_the_trigger_cases_are_four_positive_and_two_negative():
    expects = [c["expect"] for c in _cases()]
    assert expects.count("activate") == 4 and expects.count("skip") == 2


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_trigger_eval(case):
    verdict = _mf().applies(case["prompt"])
    assert verdict["applies"] is (case["expect"] == "activate"), verdict
    if case["expect"] == "activate":
        assert case["family"] in verdict["matched"]


@pytest.mark.parametrize("family, words", [
    ("upgrade", "upgrade"), ("bump", "bump"), ("deprecated", "deprecated"),
    ("replace-library", "replacing one library with another"), ("rename", "API rename"),
    ("lint-rollout", "lint or format rule rollout"), ("modernize", "modernization"),
    ("port", "port this module/app"), ("migrate", "migration"),
])
def test_the_description_names_every_trigger_family(family, words):
    """An agent activates on the description, so every family the script knows is in it."""
    assert family in _mf().TRIGGERS
    assert words in " ".join(_frontmatter()["description"].split())


def test_the_description_says_what_it_is_not_for():
    assert "Not for a one-off bug fix or a new feature" in " ".join(_frontmatter()["description"].split())


# ── the decision-block eval ──────────────────────────────────────────────────────────────────

def _check_file(path: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPT), "check", str(path)], capture_output=True,
                          text=True, timeout=60)
    return proc.returncode, json.loads(proc.stdout)


def test_a_plan_with_the_block_passes():
    rc, report = _check_file(CASES / "responses" / "with-block.md")
    assert rc == 0 and report["ok"] and report["form"] == "block"
    assert report["block"]["count"] == "212" and report["block"]["residue"] == "9"


def test_a_plan_that_hand_edits_without_the_block_fails():
    rc, report = _check_file(CASES / "responses" / "hand-edit.md")
    assert rc == 1 and not report["ok"]
    assert any("no mechanical-first decision" in e for e in report["errors"])


def test_a_written_rejection_passes():
    rc, report = _check_file(CASES / "responses" / "rejected.md")
    assert rc == 0 and report["form"] == "rejected"


def test_the_refs_worked_example_passes_and_the_template_is_the_same_shape():
    text = BLOCK_REF.read_text(encoding="utf-8")
    example = text.split("Worked example:", 1)[1]
    assert _mf().check(example)["ok"]
    template = re.search(r"Template.*?```\n(.*?)```", text, re.S).group(1)
    assert [ln.split(":")[0].strip() for ln in template.strip().splitlines()] == ["mechanical-first", *_mf().KEYS]


BLOCK = """```
mechanical-first:
  inventory: rg -c 'foo\\(' src
  count: {count}
  recipe_checked: none exists — checked npm and the framework docs
  codemod: ast-grep --rewrite 'bar($$$)'
  gate: npm test
  residue: {residue}
```"""


@pytest.mark.parametrize("text, needle", [
    (BLOCK.format(count=12, residue=13), "more than `count`"),
    (BLOCK.format(count="about 12", residue=1), "whole number"),
    (BLOCK.format(count=12, residue=1).replace("  gate: npm test\n", ""), "`gate` is missing"),
    (BLOCK.format(count=12, residue=1).replace("gate: npm test", "gate:"), "`gate` is empty"),
    (BLOCK.format(count=12, residue=1).replace("  residue: 1", "  residue: 1\n  residue: 2"), "given twice"),
    (BLOCK.format(count=12, residue=1).replace("  gate: npm test", "  gates: npm test"), "not one of the keys"),
    ("mechanical-first: rejected — ", "no reason"),
    ("mechanical-first: rejected - 3 sites", "no mechanical-first decision"),   # the em dash is the contract
    (BLOCK.format(count=1, residue=0) + "\n\nmechanical-first: rejected — tiny", "exactly one"),
    (BLOCK.format(count=12, residue=1).replace("```\n", "", 1).replace("\n```", ""), "no mechanical-first decision"),
])
def test_a_malformed_decision_fails_and_says_why(text, needle):
    report = _mf().check(text)
    assert not report["ok"] and any(needle in e for e in report["errors"]), report


def test_a_rejection_inside_a_code_block_is_not_a_decision():
    assert not _mf().check("```\nmechanical-first: rejected — quoted, not decided\n```")["ok"]


def test_the_check_reads_stdin_and_reports_a_usage_error():
    ok = subprocess.run([sys.executable, str(SCRIPT), "check", "-"], input="mechanical-first: rejected — one site",
                        capture_output=True, text=True, timeout=60)
    assert ok.returncode == 0 and json.loads(ok.stdout)["form"] == "rejected"
    missing = subprocess.run([sys.executable, str(SCRIPT), "check", str(CASES / "nope.md")],
                             capture_output=True, text=True, timeout=60)
    assert missing.returncode == 2 and json.loads(missing.stdout)["ok"] is False


# ── wiring ───────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ref, phase", [("migrate", "### plan"), ("modernize", "### transform"),
                                        ("build", "### implement")])
def test_the_archetype_playbooks_call_it_before_they_transform(ref, phase):
    text = (REPO / "skills" / "archetype" / "refs" / f"{ref}.md").read_text(encoding="utf-8")
    section = text.split(phase, 1)[1].split("\n### ", 1)[0]
    assert NAME in section, f"{ref}.md {phase} does not call {NAME}"


def test_the_governed_worker_floor_hands_it_to_every_seat():
    floor = (REPO / "skills" / "governed-worker" / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^- \*\*C9 — (.*?)(?=^- \*\*|^\S|\Z)", floor, re.M | re.S)
    assert m and NAME in m.group(1) and "mechanical-first: rejected" in " ".join(m.group(1).split())
    assert re.search(r"^\| C9 \| .*#1334", floor, re.M)


def test_the_help_table_lists_it():
    core = (REPO / "skills" / "core" / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(rf"^\| `{NAME}` \|", core, re.M)


def test_the_changelog_names_it():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert NAME in unreleased
