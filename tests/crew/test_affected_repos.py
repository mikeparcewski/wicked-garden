"""tests/crew/test_affected_repos.py — Issue #722.

Covers the optional advisory ``affected_repos`` field surfaced by the
multi-repo reframe:

  - ``scripts/crew/validate_plan.py`` accepts the field when shaped as a
    list of non-empty strings, rejects malformed shapes, and stays
    backward-compatible (omitting the field is a clean pass).
  - ``scripts/crew/affected_repos.py`` renders the advisory line
    cleanly for crew:status / smaht:briefing consumers.

Test rules (T1-T6):
  T1: deterministic — pure function calls with self-contained dicts.
  T2: no sleep-based sync.
  T3: isolated — each test builds its own fixture from scratch.
  T4: single behavior per test.
  T5: descriptive names cite #722 intent.
  T6: every docstring cites Issue #722.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "crew"))

import affected_repos  # noqa: E402
import validate_plan  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_plan() -> dict:
    """Return a minimal valid process-plan dict. Issue #722."""
    return {
        "project_slug": "affected-repos-fixture",
        "summary": "Fixture for Issue #722 affected_repos coverage.",
        "rigor_tier": "standard",
        "complexity": 3,
        "factors": {
            key: {"reading": "LOW", "risk_level": "high_risk", "why": "fixture"}
            for key in validate_plan.REQUIRED_FACTOR_KEYS
        },
        "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
        "phases": [
            {"name": "build", "why": "do the work", "primary": ["backend-engineer"]}
        ],
        "tasks": [
            {
                "id": "t1",
                "title": "Implement",
                "phase": "build",
                "blockedBy": [],
                "metadata": {
                    "chain_id": "affected-repos-fixture.root",
                    "event_type": "coding-task",
                    "source_agent": "facilitator",
                    "phase": "build",
                    "rigor_tier": "standard",
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# validate_plan — schema acceptance / rejection
# ---------------------------------------------------------------------------


def test_validate_accepts_plan_without_affected_repos():
    """Issue #722: backward-compat — plans without the field stay clean."""
    plan = _base_plan()
    assert "affected_repos" not in plan
    assert validate_plan.validate(plan) == []


def test_validate_accepts_well_shaped_affected_repos():
    """Issue #722: list of non-empty strings is the documented shape."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "bar", "baz"]
    assert validate_plan.validate(plan) == []


def test_validate_accepts_empty_affected_repos_list():
    """Issue #722: an empty list is shape-valid (advisory absence)."""
    plan = _base_plan()
    plan["affected_repos"] = []
    assert validate_plan.validate(plan) == []


def test_validate_rejects_affected_repos_as_string():
    """Issue #722: a bare string is not a list — must be rejected."""
    plan = _base_plan()
    plan["affected_repos"] = "foo"
    violations = validate_plan.validate(plan)
    assert any(
        "affected_repos" in v and "must be a list of strings" in v
        for v in violations
    ), violations


def test_validate_rejects_affected_repos_with_non_string_entry():
    """Issue #722: every entry must be a string — numbers reject."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", 42]
    violations = validate_plan.validate(plan)
    assert any(
        "affected_repos[1]" in v and "non-empty string" in v
        for v in violations
    ), violations


def test_validate_rejects_affected_repos_with_blank_entry():
    """Issue #722: whitespace-only strings are not real repo names."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "   "]
    violations = validate_plan.validate(plan)
    assert any(
        "affected_repos[1]" in v and "non-empty string" in v
        for v in violations
    ), violations


def test_validate_rejects_affected_repos_as_dict():
    """Issue #722: dict shape (e.g. attempted DAG) is out of scope."""
    plan = _base_plan()
    # The full DAG belongs to the sibling-plugin design; if a user
    # tries to smuggle it in here we want a clear "shape" error.
    plan["affected_repos"] = {"foo": ["bar"]}
    violations = validate_plan.validate(plan)
    assert any(
        "affected_repos" in v and "must be a list of strings" in v
        for v in violations
    ), violations


def test_validate_warnings_unaffected_by_affected_repos():
    """Issue #722: the field never produces warnings."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "bar"]
    # warnings() returns advisory dicts; affected_repos must not feed it.
    out = validate_plan.warnings(plan)
    assert all("affected_repos" not in (w.get("code") or "") for w in out)
    assert all("affected_repos" not in (w.get("message") or "") for w in out)


# ---------------------------------------------------------------------------
# affected_repos.py — renderer
# ---------------------------------------------------------------------------


def test_extract_returns_empty_list_when_field_missing():
    """Issue #722: missing field → no repos to render."""
    assert affected_repos.extract_affected_repos({}) == []


def test_extract_returns_empty_list_when_field_is_not_a_list():
    """Issue #722: defensive — a malformed field renders silently."""
    assert affected_repos.extract_affected_repos({"affected_repos": "foo"}) == []
    assert affected_repos.extract_affected_repos({"affected_repos": 42}) == []


def test_extract_drops_non_string_and_blank_entries():
    """Issue #722: clean the list before rendering — never crash."""
    repos = affected_repos.extract_affected_repos(
        {"affected_repos": ["foo", "", 42, "  ", "bar"]}
    )
    assert repos == ["foo", "bar"]


def test_extract_preserves_order():
    """Issue #722: facilitator order may carry signal — do not sort."""
    repos = affected_repos.extract_affected_repos(
        {"affected_repos": ["zeta", "alpha", "mu"]}
    )
    assert repos == ["zeta", "alpha", "mu"]


def test_render_line_returns_empty_string_when_no_repos():
    """Issue #722: empty list → empty string → caller skips the section."""
    assert affected_repos.render_line([]) == ""


def test_render_line_includes_advisory_doc_pointer():
    """Issue #722: every rendered line cites the sibling-plugin doc."""
    line = affected_repos.render_line(["foo", "bar"])
    assert line.startswith("Affected repos: foo, bar ")
    assert "advisory" in line
    assert "docs/v9/sibling-plugin-monorepo.md" in line


def test_render_from_plan_round_trips_well_shaped_plan():
    """Issue #722: end-to-end render from a realistic plan dict."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "bar"]
    line = affected_repos.render_from_plan(plan)
    assert "foo, bar" in line
    assert "advisory" in line


def test_render_from_plan_silent_for_legacy_plan():
    """Issue #722: backward-compat — legacy plans render no advisory."""
    plan = _base_plan()
    assert affected_repos.render_from_plan(plan) == ""


def test_render_from_plan_silent_for_empty_list():
    """Issue #722: empty list is the same as absent, by design."""
    plan = _base_plan()
    plan["affected_repos"] = []
    assert affected_repos.render_from_plan(plan) == ""


# ---------------------------------------------------------------------------
# CLI behaviour — exercises the path crew:status / smaht:briefing follow
# ---------------------------------------------------------------------------


def _write_plan(tmp_path: Path, plan: dict) -> Path:
    plan_path = tmp_path / "process-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return plan_path


def test_cli_render_prints_line_when_repos_set(tmp_path, capsys):
    """Issue #722: `render --plan ...` prints exactly one advisory line."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "bar"]
    plan_path = _write_plan(tmp_path, plan)

    rc = affected_repos.main(["render", "--plan", str(plan_path)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("Affected repos: foo, bar")
    assert "advisory" in out


def test_cli_render_prints_nothing_when_repos_unset(tmp_path, capsys):
    """Issue #722: silence on legacy plans — nothing piped to status."""
    plan = _base_plan()
    plan_path = _write_plan(tmp_path, plan)

    rc = affected_repos.main(["render", "--plan", str(plan_path)])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_cli_render_silent_when_plan_missing(tmp_path, capsys):
    """Issue #722: missing plan must never break the briefing pipeline."""
    rc = affected_repos.main([
        "render",
        "--plan",
        str(tmp_path / "does-not-exist.json"),
    ])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_cli_render_silent_when_plan_unparseable(tmp_path, capsys):
    """Issue #722: malformed JSON falls back to silence (fail-open)."""
    plan_path = tmp_path / "process-plan.json"
    plan_path.write_text("not json at all {", encoding="utf-8")

    rc = affected_repos.main(["render", "--plan", str(plan_path)])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_cli_render_resolves_project_dir(tmp_path, capsys):
    """Issue #722: --project-dir resolves to <dir>/process-plan.json."""
    plan = _base_plan()
    plan["affected_repos"] = ["alpha"]
    _write_plan(tmp_path, plan)

    rc = affected_repos.main(["render", "--project-dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("Affected repos: alpha")


def test_cli_json_emits_stable_shape(tmp_path, capsys):
    """Issue #722: `json` mode is for programmatic consumers (smaht briefing)."""
    plan = _base_plan()
    plan["affected_repos"] = ["foo", "bar"]
    plan_path = _write_plan(tmp_path, plan)

    rc = affected_repos.main(["json", "--plan", str(plan_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"affected_repos": ["foo", "bar"]}


def test_cli_json_emits_empty_list_for_legacy_plan(tmp_path, capsys):
    """Issue #722: legacy plan → JSON consumers see [] not an error."""
    plan = _base_plan()
    plan_path = _write_plan(tmp_path, plan)

    rc = affected_repos.main(["json", "--plan", str(plan_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"affected_repos": []}
