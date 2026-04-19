"""tests/crew/test_archetype_detect.py — Unit tests for archetype_detect.py (D1).

Provenance: AC-1, AC-8, AC-8.1
T1: deterministic — no randomness, no sleep, no external I/O beyond tempfile
T2: no sleep-based sync
T3: isolated — each test uses its own temp directory
T4: single focus per test function
T5: descriptive names
T6: each docstring cites its AC
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts/ to sys.path for direct import.
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from crew.archetype_detect import (  # noqa: E402
    DOMINANCE_RATIO,
    ARCHETYPE_ENUM,
    detect_archetype,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(files: dict, plan_text: str = "") -> Path:
    """Create a temp project dir with given {relative_path: content} files."""
    tmp = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        fp = tmp / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    if plan_text:
        (tmp / "process-plan.md").write_text(plan_text, encoding="utf-8")
    return tmp


def _frontmatter_md(body: str = "body text", fields: str = "subagent_type: wicked-garden:crew:test") -> str:
    return f"---\n{fields}\n---\n{body}\n"


# ---------------------------------------------------------------------------
# AC-1: Public API contract
# ---------------------------------------------------------------------------

def test_detect_archetype_returns_required_keys():
    """AC-1: detect_archetype returns dict with archetype, confidence, signals."""
    result = detect_archetype({"files": [], "project_dir": "."})
    assert "archetype" in result
    assert "confidence" in result
    assert "signals" in result
    assert isinstance(result["archetype"], str)
    assert isinstance(result["confidence"], float)
    assert isinstance(result["signals"], list)
    assert len(result["signals"]) > 0


def test_detect_archetype_archetype_in_enum():
    """AC-1: returned archetype is always in the 7-value enum."""
    tmp = _make_project({"src/main.py": "x = 1"})
    result = detect_archetype({"files": ["src/main.py"], "project_dir": str(tmp)})
    assert result["archetype"] in ARCHETYPE_ENUM


def test_detect_archetype_never_raises_on_bad_input():
    """AC-1: detect_archetype does not raise on malformed input — fallback to code-repo."""
    result = detect_archetype(None)  # type: ignore[arg-type]
    assert result["archetype"] == "code-repo"
    assert result["confidence"] == 0.3
    assert any("fallback: detect_archetype raised" in s for s in result["signals"])


# ---------------------------------------------------------------------------
# Priority-order detection tests (one per archetype)
# ---------------------------------------------------------------------------

def test_schema_migration_detected_with_file_and_keyword():
    """AC-8: schema-migration fires on migration file + keyword in plan text."""
    tmp = _make_project(
        {"scripts/validate_addendum_schema.py": "# validator code\n" + "x = 1\n" * 5},
        plan_text="This PR does an addendum schema bump from 1.0 to 1.1.0 (addendum schema).",
    )
    result = detect_archetype(
        {"files": ["scripts/validate_addendum_schema.py"], "project_dir": str(tmp)}
    )
    assert result["archetype"] == "schema-migration"
    assert result["confidence"] >= 0.5


def test_multi_repo_detected_from_keyword():
    """AC-8: multi-repo fires on affected_repos in plan text."""
    tmp_no_signal = _make_project({"src/main.py": "x=1"})
    result = detect_archetype(
        {"files": ["src/main.py"], "project_dir": str(tmp_no_signal)},
        plan_path=None,
    )
    # No multi-repo signals — should not be multi-repo
    assert result["archetype"] != "multi-repo"

    # With keyword
    tmp = _make_project({"src/main.py": "x=1"}, plan_text="This project has affected_repos: [repo-a, repo-b].")
    result2 = detect_archetype(
        {"files": ["src/main.py"], "project_dir": str(tmp)},
        plan_path=tmp / "process-plan.md",
    )
    assert result2["archetype"] == "multi-repo"


def test_testing_only_detected_when_all_files_are_tests():
    """AC-8: testing-only fires when every changed file is a test or fixture."""
    tmp = _make_project({
        "tests/crew/test_foo.py": "def test_foo(): pass",
        "tests/crew/test_bar.py": "def test_bar(): pass",
    })
    result = detect_archetype({
        "files": ["tests/crew/test_foo.py", "tests/crew/test_bar.py"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] == "testing-only"
    assert result["confidence"] == 0.9


def test_testing_only_disqualified_by_production_file():
    """AC-8: testing-only is disqualified when one non-test file is present."""
    tmp = _make_project({
        "tests/crew/test_foo.py": "def test_foo(): pass",
        "scripts/crew/some.py": "x = 1",
    })
    result = detect_archetype({
        "files": ["tests/crew/test_foo.py", "scripts/crew/some.py"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] != "testing-only"


def test_config_infra_detected_from_gate_policy_json():
    """AC-8: config-infra fires on .claude-plugin/*.json files."""
    tmp = _make_project({".claude-plugin/gate-policy.json": '{"gates": {}}'})
    result = detect_archetype({
        "files": [".claude-plugin/gate-policy.json"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] == "config-infra"


def test_skill_agent_authoring_detected_from_agent_md_with_frontmatter():
    """AC-8: skill-agent-authoring fires on agents/*.md with YAML frontmatter."""
    tmp = _make_project({
        "agents/crew/my-agent.md": _frontmatter_md(),
    })
    result = detect_archetype({
        "files": ["agents/crew/my-agent.md"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] == "skill-agent-authoring"


def test_docs_only_detected_when_all_files_are_markdown():
    """AC-8: docs-only fires when every changed file is .md/.rst/.txt without frontmatter."""
    tmp = _make_project({
        "README.md": "# plain docs — no frontmatter",
        "CHANGELOG.md": "Some changes",
    })
    result = detect_archetype({
        "files": ["README.md", "CHANGELOG.md"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] == "docs-only"


def test_code_repo_fallback_when_only_source_files():
    """AC-8: code-repo fallback fires for plain Python source files."""
    tmp = _make_project({
        "scripts/crew/some_module.py": "x = 1",
        "scripts/other.py": "y = 2",
    })
    result = detect_archetype({
        "files": ["scripts/crew/some_module.py", "scripts/other.py"],
        "project_dir": str(tmp),
    })
    assert result["archetype"] == "code-repo"
    assert result["confidence"] == 0.7


# ---------------------------------------------------------------------------
# Priority-order conflict tests
# ---------------------------------------------------------------------------

def test_priority_order_multi_repo_beats_testing_only():
    """AC-8: priority 2 (multi-repo) wins over priority 3 (testing-only)."""
    tmp = _make_project({}, plan_text="This involves affected_repos: [repo-a, repo-b].")
    result = detect_archetype({
        "files": ["tests/test_foo.py"],
        "project_dir": str(tmp),
    })
    # multi-repo keyword in plan_text should win
    assert result["archetype"] == "multi-repo"


def test_dominance_ratio_boundary_exactly_4_to_1():
    """AC-8: at exactly 4:1 (non-md:md), strict > means NOT fallback → skill-agent-authoring.

    8 .py files and 2 skill .md files → ratio = 4:1 exactly. Strict > means
    8 > 4 * 2 = 8 is FALSE, so skill-agent-authoring wins.
    """
    tmp = _make_project({
        "agents/crew/agent-a.md": _frontmatter_md(),
        "agents/crew/agent-b.md": _frontmatter_md(),
        **{f"scripts/crew/module_{i}.py": f"# code {i}\n" for i in range(8)},
    })
    files = (
        ["agents/crew/agent-a.md", "agents/crew/agent-b.md"]
        + [f"scripts/crew/module_{i}.py" for i in range(8)]
    )
    result = detect_archetype({"files": files, "project_dir": str(tmp)})
    assert result["archetype"] == "skill-agent-authoring", (
        f"Expected skill-agent-authoring at exactly {DOMINANCE_RATIO}:1 ratio "
        f"(strict > is False), got {result['archetype']}"
    )


def test_dominance_ratio_boundary_3_to_1_falls_back_to_code_repo():
    """AC-8: wait — 3:1 is BELOW threshold, should also be skill-agent-authoring.

    The dominance formula: non_md > 4 * md. With 3 .py and 1 .md: 3 > 4 is False.
    So skill-agent-authoring wins. With 5 .py and 1 .md: 5 > 4 is True → code-repo.
    This test verifies the latter (5:1 triggers fallback).
    """
    tmp = _make_project({
        "agents/crew/agent-a.md": _frontmatter_md(),
        **{f"scripts/module_{i}.py": f"# code {i}\n" for i in range(5)},
    })
    files = ["agents/crew/agent-a.md"] + [f"scripts/module_{i}.py" for i in range(5)]
    result = detect_archetype({"files": files, "project_dir": str(tmp)})
    # 5 > 4*1 = 4 is True → downgraded to code-repo
    assert result["archetype"] == "code-repo", (
        f"Expected code-repo when 5 source files > 4*1 agent files, "
        f"got {result['archetype']}"
    )


# ---------------------------------------------------------------------------
# AC-8.1: Negative-signal conflict test (MAJOR finding from challenge)
# ---------------------------------------------------------------------------

def test_mixed_config_and_skill_agent_md():
    """AC-8.1: config-infra MUST be disqualified when YAML-frontmatter .md present.

    A synthetic PR with gate-policy.json edit (config-infra positive signal) AND a new
    agents/crew/qe-evaluator.md (skill-agent-authoring positive signal).
    config-infra's negative signal fires on the YAML-frontmatter .md file, so
    skill-agent-authoring wins.

    This test is the regression guard for the challenge-phase MAJOR finding (Vector 4):
    strict priority-order WITHOUT negative signals would mis-classify as config-infra
    (priority 4 > priority 5). The implementation MUST honor negative signals.
    """
    tmp = _make_project({
        ".claude-plugin/gate-policy.json": '{"gates": {}}',
        "agents/crew/qe-evaluator.md": _frontmatter_md(
            body="The qe-evaluator does archetype-aware evidence evaluation.",
            fields="subagent_type: wicked-garden:crew:qe-evaluator\ndescription: qe evaluator",
        ),
    })
    files = [".claude-plugin/gate-policy.json", "agents/crew/qe-evaluator.md"]
    result = detect_archetype({"files": files, "project_dir": str(tmp)})
    assert result["archetype"] == "skill-agent-authoring", (
        f"Expected skill-agent-authoring because config-infra negative signal fires "
        f"on YAML-frontmatter .md under agents/. Got {result['archetype']!r}. "
        "This is the AC-8.1 regression guard for challenge-phase Vector 4."
    )


# ---------------------------------------------------------------------------
# Low-confidence fallback
# ---------------------------------------------------------------------------

def test_fallback_with_no_files_returns_code_repo_low_confidence():
    """AC-1: empty file list falls back to code-repo with confidence 0.3."""
    tmp = _make_project({})  # empty temp dir — no files at all
    result = detect_archetype({"files": [], "project_dir": str(tmp)})
    assert result["archetype"] == "code-repo"
    assert result["confidence"] == 0.3


def test_detect_archetype_module_constant_dominance_ratio():
    """AC-8 / build-notes A3: DOMINANCE_RATIO is exactly 4."""
    assert DOMINANCE_RATIO == 4, (
        "DOMINANCE_RATIO must be 4 per challenge-phase A3 decision "
        "(strict > with 4:1 threshold)."
    )
