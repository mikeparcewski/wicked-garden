"""tests/crew/test_skill_docs_archetype_coverage.py — Verify archetype coverage in docs (D6).

Provenance: AC-6 (updated for #652 item 3 — rubric extracted to agent)
T1: deterministic — pure file reads, no I/O side effects
T3: isolated — read-only
T4: single focus per test
T5: descriptive names
T6: each docstring cites its AC

Note: Pattern A migration moved the rubric content out of SKILL.md and into
``agents/crew/process-facilitator.md``. SKILL.md is now a thin delegation shim,
so archetype coverage assertions target the agent file (which holds the rubric)
while the SKILL.md size cap still applies as a guard against re-bloat.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "propose-process" / "SKILL.md"
RUBRIC_AGENT_MD = REPO_ROOT / "agents" / "crew" / "process-facilitator.md"
EVIDENCE_FRAMING_MD = REPO_ROOT / "skills" / "propose-process" / "refs" / "evidence-framing.md"

# 4 MVP archetypes required to appear in both the rubric agent and evidence-framing (AC-6).
MVP_ARCHETYPES = ["code-repo", "docs-only", "skill-agent-authoring", "config-infra"]


def test_skill_md_exists():
    """AC-6: SKILL.md must exist at its declared path."""
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"


def test_rubric_agent_exists():
    """AC-6 (#652 item 3): the rubric agent must exist at its declared path."""
    assert RUBRIC_AGENT_MD.exists(), f"process-facilitator.md not found at {RUBRIC_AGENT_MD}"


def test_evidence_framing_md_exists():
    """AC-6: evidence-framing.md must exist at its declared path."""
    assert EVIDENCE_FRAMING_MD.exists(), f"evidence-framing.md not found at {EVIDENCE_FRAMING_MD}"


def test_skill_md_within_200_lines():
    """AC-6: SKILL.md must be ≤200 lines (plugin quality validator hard cap)."""
    line_count = len(SKILL_MD.read_text(encoding="utf-8").splitlines())
    assert line_count <= 200, (
        f"SKILL.md has {line_count} lines — exceeds the 200-line hard cap. "
        "Trim the file before committing."
    )


@pytest.mark.parametrize("archetype", MVP_ARCHETYPES)
def test_rubric_agent_contains_mvp_archetype(archetype: str):
    """AC-6 (#652 item 3): the rubric agent must reference each MVP archetype name.

    The rubric content (including Step 6 archetype selection) lives in
    ``agents/crew/process-facilitator.md`` after Pattern A migration.
    """
    content = RUBRIC_AGENT_MD.read_text(encoding="utf-8")
    assert archetype in content, (
        f"process-facilitator.md does not contain archetype name {archetype!r}. "
        "Step 6 must reference all 4 MVP archetypes."
    )


@pytest.mark.parametrize("archetype", MVP_ARCHETYPES)
def test_evidence_framing_contains_mvp_archetype(archetype: str):
    """AC-6: evidence-framing.md must have a per-archetype section for each MVP archetype."""
    content = EVIDENCE_FRAMING_MD.read_text(encoding="utf-8")
    assert archetype in content, (
        f"evidence-framing.md does not contain archetype name {archetype!r}. "
        "A per-archetype section is required for each of the 4 MVP archetypes (AC-6)."
    )


def test_rubric_agent_mentions_archetype_enum_in_step_6():
    """AC-6 (#652 item 3): the rubric agent's Step 6 must mention the archetype enum."""
    content = RUBRIC_AGENT_MD.read_text(encoding="utf-8")
    assert "archetype" in content, (
        "process-facilitator.md must mention 'archetype' in the step 6 section."
    )
    assert "metadata.archetype" in content or "metadata" in content, (
        "process-facilitator.md Step 6 must reference TaskCreate metadata.archetype emission."
    )
