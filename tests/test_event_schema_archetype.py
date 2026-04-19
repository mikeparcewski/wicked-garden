"""tests/test_event_schema_archetype.py — Archetype field validation in _event_schema.py (D5).

Provenance: AC-5
T1: deterministic — pure in-memory, no I/O
T3: isolated — no shared state
T4: single focus per test
T5: descriptive names
T6: each docstring cites its AC
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _event_schema import validate_metadata, VALID_ARCHETYPES  # noqa: E402


_BASE_METADATA = {
    "chain_id": "my-project.clarify",
    "event_type": "task",
    "source_agent": "facilitator",
    "phase": "clarify",
}


# ---------------------------------------------------------------------------
# AC-5: All 7 valid enum values are accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archetype", sorted(VALID_ARCHETYPES))
def test_all_7_valid_archetype_values_accepted(archetype: str):
    """AC-5: all 7 archetype enum values must be accepted without error."""
    metadata = {**_BASE_METADATA, "archetype": archetype}
    err = validate_metadata(metadata)
    assert err is None, (
        f"archetype={archetype!r} should be accepted, got error: {err}"
    )


def test_valid_archetype_set_has_exactly_7_values():
    """AC-5: VALID_ARCHETYPES must contain exactly 7 values."""
    expected = {
        "code-repo",
        "docs-only",
        "skill-agent-authoring",
        "config-infra",
        "multi-repo",
        "testing-only",
        "schema-migration",
    }
    assert VALID_ARCHETYPES == expected, (
        f"VALID_ARCHETYPES mismatch. Expected {sorted(expected)}, "
        f"got {sorted(VALID_ARCHETYPES)}"
    )


# ---------------------------------------------------------------------------
# AC-5: Invalid archetype value triggers validation error
# ---------------------------------------------------------------------------

def test_invalid_archetype_value_triggers_validation_error():
    """AC-5: an 8th unknown archetype value must trigger validation failure (warn/strict)."""
    metadata = {**_BASE_METADATA, "archetype": "invalid-type"}
    err = validate_metadata(metadata)
    assert err is not None, "Invalid archetype should produce a validation error"
    assert "invalid-type" in err, f"Error should reference the invalid value, got: {err}"


def test_another_invalid_archetype_value_triggers_error():
    """AC-5: 'monolith' is not in the enum and must trigger validation failure."""
    metadata = {**_BASE_METADATA, "archetype": "monolith"}
    err = validate_metadata(metadata)
    assert err is not None, "archetype='monolith' should produce a validation error"


# ---------------------------------------------------------------------------
# AC-5: Absent archetype is backward-compat (optional field)
# ---------------------------------------------------------------------------

def test_absent_archetype_is_valid():
    """AC-5: metadata without archetype field is valid (backward-compat, optional field)."""
    metadata = {**_BASE_METADATA}
    assert "archetype" not in metadata
    err = validate_metadata(metadata)
    assert err is None, f"Absent archetype should be valid (optional), got: {err}"
