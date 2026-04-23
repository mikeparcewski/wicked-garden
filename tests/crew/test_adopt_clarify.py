"""tests/crew/test_adopt_clarify.py — issue #565 adopt-clarify fast-path.

Verifies that adopt_clarify_from_memo writes the clarify required
deliverables from a source memo, records an addendum citing the memo,
and does NOT auto-approve the phase (safety property).

Rules:
  T1: deterministic — uses tmp_path for isolation
  T3: isolated — no network / no shared state
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite the tracking issue
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402
from phase_manager import (  # noqa: E402
    PhaseState,
    ProjectState,
    adopt_clarify_from_memo,
)


_MEMO_BODY = (
    "# Wiki-Driven Contracts\n\n"
    "## Objective\n"
    "Ship a schema-first contract layer that removes duplicate schema definitions.\n\n"
    "## Complexity\n"
    "Medium — 3 services affected, no external API changes.\n\n"
    "## Acceptance Criteria\n"
    "- All 3 services load schema from a single source.\n"
    "- Unit tests cover the load path.\n"
    "- Migration is reversible within 1 day.\n"
)


def _state_at_clarify():
    return ProjectState(
        name="adopt-test",
        current_phase="clarify",
        created_at="2026-04-22T00:00:00Z",
        phase_plan=["clarify", "build", "test"],
        phases={"clarify": PhaseState(status="in_progress")},
        extras={"rigor_tier": "standard"},
    )


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """Pin get_project_dir to tmp so tests don't touch the real project store."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(phase_manager, "get_project_dir", lambda name: project_dir)
    return project_dir


@pytest.fixture
def memo(tmp_path):
    """Create a memo file for adoption."""
    path = tmp_path / "docs" / "wiki-driven-contracts.md"
    path.parent.mkdir(parents=True)
    path.write_text(_MEMO_BODY)
    return path


# ---------------------------------------------------------------------------
# Happy path — deliverables written, addendum recorded, no auto-approve
# ---------------------------------------------------------------------------


def test_adopt_writes_all_required_deliverables(isolated_project, memo):
    """Issue #565: adopt-clarify writes objective/complexity/acceptance-criteria files."""
    state = _state_at_clarify()
    result = adopt_clarify_from_memo(state, memo)
    adopted = set(result["adopted_deliverables"])
    assert {"objective.md", "complexity.md", "acceptance-criteria.md"} <= adopted

    for fname in adopted:
        path = isolated_project / "phases" / "clarify" / fname
        assert path.exists(), f"missing {fname}"
        assert path.stat().st_size >= 100, f"{fname} too small"


def test_adopt_embeds_memo_path_in_deliverable_frontmatter(isolated_project, memo):
    """Each written file cites the memo via 'adopted_from' frontmatter for provenance."""
    state = _state_at_clarify()
    adopt_clarify_from_memo(state, memo)
    objective = (isolated_project / "phases" / "clarify" / "objective.md").read_text()
    assert "adopted_from:" in objective
    assert str(memo) in objective


def test_adopt_includes_case_count_for_acceptance_criteria(isolated_project, memo):
    """acceptance-criteria.md carries the required case_count frontmatter key."""
    state = _state_at_clarify()
    adopt_clarify_from_memo(state, memo)
    ac = (isolated_project / "phases" / "clarify" / "acceptance-criteria.md").read_text()
    assert "case_count:" in ac


def test_adopt_does_not_approve_phase(isolated_project, memo):
    """Safety property: adoption does NOT flip clarify to approved."""
    state = _state_at_clarify()
    adopt_clarify_from_memo(state, memo)
    assert state.phases["clarify"].status == "in_progress"


def test_adopt_writes_addendum_citing_memo(isolated_project, memo):
    """Addendum record preserves memo provenance for the gate audit trail."""
    state = _state_at_clarify()
    result = adopt_clarify_from_memo(state, memo, memo_as="design-memo-adoption")
    assert result["addendum_written"] is True
    addendum_path = isolated_project / "process-plan.addendum.jsonl"
    assert addendum_path.exists()
    content = addendum_path.read_text()
    assert "adopt-clarify:memo-adoption" in content
    assert str(memo) in content


# ---------------------------------------------------------------------------
# Validation and safety checks
# ---------------------------------------------------------------------------


def test_adopt_rejects_missing_memo(isolated_project, tmp_path):
    """Non-existent memo path raises ValueError rather than writing stub files."""
    state = _state_at_clarify()
    missing = tmp_path / "does-not-exist.md"
    with pytest.raises(ValueError, match="Memo not found"):
        adopt_clarify_from_memo(state, missing)


def test_adopt_rejects_empty_memo(isolated_project, tmp_path):
    """Empty memo raises ValueError — garbage in, garbage out guard."""
    state = _state_at_clarify()
    empty = tmp_path / "empty.md"
    empty.write_text("   \n\n  ")
    with pytest.raises(ValueError, match="empty"):
        adopt_clarify_from_memo(state, empty)


def test_adopt_refuses_to_clobber_without_force(isolated_project, memo):
    """Existing non-empty deliverables block adoption unless --force is passed."""
    state = _state_at_clarify()
    phase_dir = isolated_project / "phases" / "clarify"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "objective.md").write_text("# Existing work — please don't clobber\n" * 10)

    with pytest.raises(ValueError, match="already exist"):
        adopt_clarify_from_memo(state, memo)


def test_adopt_force_overwrites_existing_deliverables(isolated_project, memo):
    """--force overwrites existing files; caller accepts the risk."""
    state = _state_at_clarify()
    phase_dir = isolated_project / "phases" / "clarify"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "objective.md").write_text("# Existing\n" * 10)

    adopt_clarify_from_memo(state, memo, force=True)
    after = (phase_dir / "objective.md").read_text()
    assert "adopted_from:" in after


def test_adopt_refuses_when_clarify_already_approved(isolated_project, memo):
    """Can't adopt into an approved phase — the adoption would be misleading."""
    state = _state_at_clarify()
    state.phases["clarify"].status = "approved"
    with pytest.raises(ValueError, match="clarify"):
        adopt_clarify_from_memo(state, memo)


def test_adopt_refuses_when_clarify_skipped(isolated_project, memo):
    """A skipped clarify is also terminal — adoption would conflict with the skip."""
    state = _state_at_clarify()
    state.phases["clarify"].status = "skipped"
    with pytest.raises(ValueError, match="clarify"):
        adopt_clarify_from_memo(state, memo)


def test_adopt_materializes_missing_clarify_phase_state(isolated_project, memo):
    """Copilot #568 review: a project without an explicit clarify PhaseState
    (legacy/minimal projects) is implicitly pending — adopt-clarify should
    create the entry on demand instead of erroring."""
    state = _state_at_clarify()
    del state.phases["clarify"]
    result = adopt_clarify_from_memo(state, memo)
    assert "clarify" in state.phases
    assert state.phases["clarify"].status == "pending"
    assert "objective.md" in result["adopted_deliverables"]


def test_adopt_refuses_when_current_phase_moved_past_clarify(isolated_project, memo):
    """Copilot #568 review: enforce current_phase=='clarify' so projects that
    already moved to design/build can't have clarify deliverables backfilled,
    which would corrupt phase provenance."""
    state = _state_at_clarify()
    state.current_phase = "design"
    with pytest.raises(ValueError, match="clarify"):
        adopt_clarify_from_memo(state, memo)
