"""tests/crew/test_guide_filtering.py — phase + archetype-aware guide filtering.

Provenance: Issue #725 reframe — context-aware ``crew:guide`` (no starter mode).
T1: deterministic — pure-function filters, no I/O beyond tempdir for the
    metadata-walk test.
T3: isolated — each metadata-walk test scopes to its own tempdir.
T4: each test asserts one filter behaviour.
T5: descriptive names — name encodes the relevance combination under test.
T6: each docstring cites the AC it covers.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# conftest.py inserts scripts/ at sys.path[0] for `from crew import ...`.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from crew import guide  # noqa: E402


# ---------------------------------------------------------------------------
# Sample command catalog
#
# Mirrors the shape produced by ``read_command_metadata``: id + path +
# description + phase_relevance + archetype_relevance. Records here use a
# spread of declared-list / wildcard / missing-field combinations so each
# branch of the matcher is covered by at least one test below.
# ---------------------------------------------------------------------------

def _record(
    cid: str,
    *,
    phases: list[str] | None,
    archetypes: list[str] | None,
    description: str = "",
) -> dict:
    return {
        "id": cid,
        "path": f"/fake/{cid.replace(':', '_')}.md",
        "description": description,
        "phase_relevance": phases,
        "archetype_relevance": archetypes,
    }


@pytest.fixture()
def sample_commands() -> list[dict]:
    return [
        # Build-relevant in any archetype.
        _record(
            "wicked-garden:engineering:review",
            phases=["build", "review"],
            archetypes=["code-repo", "schema-migration"],
        ),
        # Bootstrap entry-point set (relevant when no project active).
        _record(
            "wicked-garden:setup",
            phases=["bootstrap"],
            archetypes=["*"],
        ),
        # Wildcard on both — always relevant.
        _record(
            "wicked-garden:help",
            phases=["*"],
            archetypes=["*"],
        ),
        # Build-only, archetype-specific.
        _record(
            "wicked-garden:search:blast-radius",
            phases=["build", "review"],
            archetypes=["*"],
        ),
        # Clarify-only.
        _record(
            "wicked-garden:jam:quick",
            phases=["clarify", "design"],
            archetypes=["*"],
        ),
        # Missing both fields entirely — must be retained with annotation.
        _record(
            "wicked-garden:legacy:undocumented",
            phases=None,
            archetypes=None,
        ),
        # Bootstrap + entry-point alongside crew start.
        _record(
            "wicked-garden:crew:start",
            phases=["bootstrap"],
            archetypes=["*"],
        ),
    ]


# ---------------------------------------------------------------------------
# AC: filter_by_phase
# ---------------------------------------------------------------------------

def test_filter_by_phase_returns_only_build_relevant_or_wildcard(sample_commands):
    """AC: ``filter_by_phase("build", ...)`` keeps ``["build"]`` + ``["*"]`` + missing."""
    result = guide.filter_by_phase(sample_commands, "build")
    ids = {c["id"] for c in result}

    assert "wicked-garden:engineering:review" in ids  # explicit build
    assert "wicked-garden:search:blast-radius" in ids  # explicit build
    assert "wicked-garden:help" in ids  # wildcard
    assert "wicked-garden:legacy:undocumented" in ids  # missing → kept w/ annotation

    # Negatives — these phases don't include build.
    assert "wicked-garden:setup" not in ids  # bootstrap-only
    assert "wicked-garden:crew:start" not in ids  # bootstrap-only
    assert "wicked-garden:jam:quick" not in ids  # clarify+design


def test_filter_by_phase_drops_non_matching_explicit_lists(sample_commands):
    """AC: explicitly-declared lists that exclude the target phase are dropped."""
    result = guide.filter_by_phase(sample_commands, "clarify")
    ids = {c["id"] for c in result}

    assert "wicked-garden:jam:quick" in ids  # clarify+design
    assert "wicked-garden:engineering:review" not in ids  # build,review only
    assert "wicked-garden:search:blast-radius" not in ids


# ---------------------------------------------------------------------------
# AC: filter_by_archetype
# ---------------------------------------------------------------------------

def test_filter_by_archetype_keeps_docs_only_or_wildcard(sample_commands):
    """AC: ``filter_by_archetype("docs-only", ...)`` keeps wildcard + missing."""
    result = guide.filter_by_archetype(sample_commands, "docs-only")
    ids = {c["id"] for c in result}

    # Wildcards survive any archetype.
    assert "wicked-garden:help" in ids
    assert "wicked-garden:setup" in ids
    assert "wicked-garden:search:blast-radius" in ids

    # engineering:review declares ["code-repo", "schema-migration"] — drop.
    assert "wicked-garden:engineering:review" not in ids


def test_archetype_wildcard_matches_every_archetype_filter(sample_commands):
    """AC: ``["*"]`` matches every archetype filter, regardless of value."""
    for archetype in ("code-repo", "docs-only", "config-infra", "schema-migration"):
        result = guide.filter_by_archetype(sample_commands, archetype)
        ids = {c["id"] for c in result}
        assert "wicked-garden:help" in ids, archetype
        assert "wicked-garden:setup" in ids, archetype


# ---------------------------------------------------------------------------
# AC: combined filter (intersection of phase + archetype)
# ---------------------------------------------------------------------------

def test_filter_for_context_intersects_phase_and_archetype(sample_commands):
    """AC: combined filter is the AND of phase + archetype matchers."""
    result = guide.filter_for_context(
        sample_commands, phase="build", archetype="docs-only"
    )
    ids = {c["id"] for c in result}

    # Wildcard survives both filters.
    assert "wicked-garden:help" in ids
    # Build wildcard archetype.
    assert "wicked-garden:search:blast-radius" in ids
    # Build but archetype excludes docs-only.
    assert "wicked-garden:engineering:review" not in ids
    # Clarify-only — fails phase filter.
    assert "wicked-garden:jam:quick" not in ids


def test_filter_for_context_keeps_code_repo_specific_command_in_build(sample_commands):
    """AC: archetype-specific commands surface in their declared archetype."""
    result = guide.filter_for_context(
        sample_commands, phase="build", archetype="code-repo"
    )
    ids = {c["id"] for c in result}

    assert "wicked-garden:engineering:review" in ids
    assert "wicked-garden:search:blast-radius" in ids


# ---------------------------------------------------------------------------
# AC: missing frontmatter → annotated, NOT silently dropped
# ---------------------------------------------------------------------------

def test_missing_frontmatter_command_is_kept_with_annotation(sample_commands):
    """AC: commands without relevance fields stay in results, tagged
    ``missing-relevance``. Silently dropping would hide bugs."""
    result = guide.filter_for_context(
        sample_commands, phase="build", archetype="code-repo"
    )
    legacy = [c for c in result if c["id"] == "wicked-garden:legacy:undocumented"]

    assert len(legacy) == 1
    annotations = legacy[0].get("annotations") or []
    assert guide.MISSING_RELEVANCE_ANNOTATION in annotations


def test_missing_frontmatter_annotation_is_idempotent(sample_commands):
    """AC: running both filters on a missing-field command emits the annotation
    exactly once — no duplicates from chaining filter_by_phase + by_archetype."""
    result = guide.filter_for_context(
        sample_commands, phase="test", archetype="docs-only"
    )
    legacy = [c for c in result if c["id"] == "wicked-garden:legacy:undocumented"]

    assert len(legacy) == 1
    annotations = legacy[0].get("annotations") or []
    assert annotations.count(guide.MISSING_RELEVANCE_ANNOTATION) == 1


# ---------------------------------------------------------------------------
# AC: bootstrap entry-point set (no active project)
# ---------------------------------------------------------------------------

def test_bootstrap_entry_points_returns_only_phase_bootstrap_commands(sample_commands):
    """AC: bootstrap mode returns commands tagged ``phase_relevance: ["bootstrap"]``."""
    result = guide.bootstrap_entry_points(sample_commands)
    ids = {c["id"] for c in result}

    assert ids == {"wicked-garden:setup", "wicked-garden:crew:start"}


# ---------------------------------------------------------------------------
# AC: empty input → empty result
# ---------------------------------------------------------------------------

def test_filter_on_empty_command_list_returns_empty():
    """AC: empty input yields empty output across every entry point."""
    assert guide.filter_by_phase([], "build") == []
    assert guide.filter_by_archetype([], "code-repo") == []
    assert guide.filter_for_context([], phase="build", archetype="code-repo") == []
    assert guide.bootstrap_entry_points([]) == []


# ---------------------------------------------------------------------------
# read_command_metadata — frontmatter walker (small tempdir-backed test)
# ---------------------------------------------------------------------------

_SAMPLE_BUILD_REVIEW = """---
description: "Sample build/review command"
phase_relevance: ["build", "review"]
archetype_relevance: ["code-repo"]
---

# /wicked-garden:sample:edit
"""

_SAMPLE_NO_FRONTMATTER = """# /wicked-garden:sample:legacy

No frontmatter at all.
"""

_SAMPLE_DESCRIPTION_ONLY = """---
description: "Has description, no relevance fields"
---

# /wicked-garden:sample:partial
"""


def test_read_command_metadata_parses_inline_lists_and_id_namespace():
    """AC: ``read_command_metadata`` walks commands/**/*.md, parses inline-list
    relevance fields, and emits ``wicked-garden:domain:name`` ids."""
    with tempfile.TemporaryDirectory(prefix="wg-guide-fm-") as td:
        commands_dir = Path(td) / "commands"
        (commands_dir / "sample").mkdir(parents=True)
        (commands_dir / "sample" / "edit.md").write_text(_SAMPLE_BUILD_REVIEW)
        (commands_dir / "sample" / "legacy.md").write_text(_SAMPLE_NO_FRONTMATTER)
        (commands_dir / "sample" / "partial.md").write_text(_SAMPLE_DESCRIPTION_ONLY)
        (commands_dir / "root.md").write_text(_SAMPLE_BUILD_REVIEW)

        records = guide.read_command_metadata(commands_dir)

        by_id = {r["id"]: r for r in records}

        # Domain-namespaced id.
        edit = by_id["wicked-garden:sample:edit"]
        assert edit["phase_relevance"] == ["build", "review"]
        assert edit["archetype_relevance"] == ["code-repo"]
        assert edit["description"] == "Sample build/review command"

        # Root command (no domain).
        assert "wicked-garden:root" in by_id

        # No frontmatter → both relevance fields are None (not []).
        legacy = by_id["wicked-garden:sample:legacy"]
        assert legacy["phase_relevance"] is None
        assert legacy["archetype_relevance"] is None

        # Description present but relevance fields absent.
        partial = by_id["wicked-garden:sample:partial"]
        assert partial["description"] == "Has description, no relevance fields"
        assert partial["phase_relevance"] is None
        assert partial["archetype_relevance"] is None


def test_read_command_metadata_returns_empty_when_dir_missing():
    """AC: walking a non-existent directory returns ``[]`` (read-only contract)."""
    assert guide.read_command_metadata(Path("/nonexistent/wg-guide-test")) == []
