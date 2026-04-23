"""tests/crew/test_validator_schema_pointers.py — issue #563.

Verifies that validate_plan and gate_result_schema surface a schema-doc
pointer when they reject input, so callers don't have to grep to find the
authoritative schema.

Rules:
  T1: deterministic — pure string inspection
  T3: isolated — no filesystem side effects beyond reading module state
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite the tracking issue
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import validate_plan  # noqa: E402
from gate_result_schema import (  # noqa: E402
    GateResultSchemaError,
    SCHEMA_DOC as GATE_SCHEMA_DOC,
)


# ---------------------------------------------------------------------------
# validate_plan.py — per-section schema pointers
# ---------------------------------------------------------------------------


def test_validate_plan_schema_doc_is_exported():
    """Issue #563: SCHEMA_DOC constant is the authoritative doc pointer."""
    assert validate_plan.SCHEMA_DOC == "skills/propose-process/refs/output-schema.md"


def test_validate_plan_factors_pointer_has_factors_anchor():
    """Issue #563: factors-shape violations should cite the factors section."""
    ptr = validate_plan._schema_pointer_for("factors — missing required factor key 'novelty'")
    assert validate_plan.SCHEMA_DOC in ptr
    assert "factors" in ptr.lower()


def test_validate_plan_tasks_pointer_strips_index_suffix():
    """tasks[0].metadata violations route to the tasks section, not 'tasks[0]'."""
    ptr = validate_plan._schema_pointer_for("tasks[0].metadata — missing required key 'chain_id'")
    assert validate_plan.SCHEMA_DOC in ptr
    assert "tasks" in ptr.lower()


def test_validate_plan_file_level_errors_return_empty_pointer():
    """Copilot #569 review: file-level failures (invalid JSON, missing file)
    and unknown sections return empty so the CLI doesn't misleadingly cite
    a schema doc whose fix is elsewhere."""
    assert validate_plan._schema_pointer_for("invalid JSON — Expecting value") == ""
    assert validate_plan._schema_pointer_for("cannot read file — Permission denied") == ""
    assert validate_plan._schema_pointer_for("newthing — invalid") == ""


# ---------------------------------------------------------------------------
# gate_result_schema.py — schema_doc attribute + str(exc)
# ---------------------------------------------------------------------------


def test_gate_result_error_exposes_schema_doc_attribute():
    """Issue #563: every GateResultSchemaError carries a schema_doc pointer."""
    exc = GateResultSchemaError("test-reason", offending_field="reviewer")
    assert exc.schema_doc == GATE_SCHEMA_DOC
    assert "gate_result_schema.py" in exc.schema_doc


def test_gate_result_error_str_includes_schema_doc():
    """str(exc) surfaces the schema pointer so log lines self-cite the source."""
    exc = GateResultSchemaError("invalid-verdict-enum:MAYBE", offending_field="verdict")
    rendered = str(exc)
    assert "invalid-verdict-enum:MAYBE" in rendered
    assert "See:" in rendered
    assert "gate_result_schema.py" in rendered


def test_gate_result_error_respects_explicit_schema_doc_override():
    """Callers can override schema_doc for dialect-specific references."""
    exc = GateResultSchemaError(
        "test-reason",
        schema_doc="custom/path.md § Alt",
    )
    assert exc.schema_doc == "custom/path.md § Alt"
    assert "custom/path.md" in str(exc)
