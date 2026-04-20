"""tests/crew/test_legacy_reeval_scan.py — Unit tests for the CH-02 SessionStart
legacy reeval-log scan (_scan_for_legacy_reeval_entries in bootstrap.py).

Provenance: CH-02 (challenge resolution), t10 scope addition
T1: deterministic — no randomness, no I/O outside tempdir
T2: no sleep-based sync
T3: isolated — each test uses its own tempdir; monkeypatches Path.home()
T4: single behavior per test
T5: descriptive names
T6: each docstring cites its provenance
"""

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the function under test
# ---------------------------------------------------------------------------

_HOOKS_SCRIPTS = Path(__file__).resolve().parents[2] / "hooks" / "scripts"
if str(_HOOKS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SCRIPTS))

# Import the scan function directly from bootstrap.py
import importlib.util
_bootstrap_spec = importlib.util.spec_from_file_location(
    "bootstrap", _HOOKS_SCRIPTS / "bootstrap.py"
)
_bootstrap_mod = importlib.util.module_from_spec(_bootstrap_spec)
# Don't exec the module — import only the function via exec of the function source.
# Instead we import bootstrap carefully: we need to avoid running main() at import time.
# bootstrap.py uses if __name__ == "__main__", so we can safely import it.

# We need to make sure bootstrap's own imports don't fail if the plugin env isn't set.
# bootstrap.py sets sys.path itself; we just need CLAUDE_PLUGIN_ROOT-independent imports.
# The simplest approach: exec only the function we need from source.

import ast as _ast
import types as _types

_bootstrap_src = (_HOOKS_SCRIPTS / "bootstrap.py").read_text(encoding="utf-8")


def _extract_function(src: str, func_name: str) -> str:
    """Extract a top-level function definition by name from source text."""
    tree = _ast.parse(src)
    for node in tree.body:
        if isinstance(node, _ast.FunctionDef) and node.name == func_name:
            lines = src.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            return "\n".join(lines[start:end])
    raise ValueError(f"Function {func_name!r} not found in bootstrap.py")


_scan_src = _extract_function(_bootstrap_src, "_scan_for_legacy_reeval_entries")
_scan_ns: dict = {}
exec(_scan_src, {"Path": Path, "OSError": OSError, "__builtins__": __builtins__}, _scan_ns)
_scan_for_legacy_reeval_entries = _scan_ns["_scan_for_legacy_reeval_entries"]


# ---------------------------------------------------------------------------
# Helper: build a temp projects_root directory
# ---------------------------------------------------------------------------

def _make_crew_project(tmp_path: Path, project_name: str, phase: str = "design") -> Path:
    """Create a minimal crew project dir under tmp_path and return the phase dir."""
    phase_dir = tmp_path / project_name / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_none_when_no_projects_dir(tmp_path, monkeypatch):
    """CH-02: returns None when the projects directory does not exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = _scan_for_legacy_reeval_entries()
    assert result is None


def test_returns_none_when_no_legacy_entries(tmp_path, monkeypatch):
    """CH-02: returns None when all reeval-log.jsonl files contain only canonical entries."""
    projects_root = tmp_path / ".something-wicked" / "wicked-garden" / "projects"
    phase_dir = _make_crew_project(projects_root, "my-project")
    canonical_record = {
        "reviewer": "gate-adjudicator",
        "trigger": "gate-adjudicator:testability",
        "chain_id": "my-project.design",
    }
    (phase_dir / "reeval-log.jsonl").write_text(
        json.dumps(canonical_record) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = _scan_for_legacy_reeval_entries()
    assert result is None


def test_detects_legacy_reviewer_in_reeval_log(tmp_path, monkeypatch):
    """CH-02: returns a notice when 'reviewer': 'qe-evaluator' appears in reeval-log.jsonl."""
    projects_root = tmp_path / ".something-wicked" / "wicked-garden" / "projects"
    phase_dir = _make_crew_project(projects_root, "my-project")
    legacy_record = {
        "reviewer": "qe-evaluator",
        "trigger": "gate-adjudicator:testability",
        "chain_id": "my-project.design",
    }
    (phase_dir / "reeval-log.jsonl").write_text(
        json.dumps(legacy_record) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = _scan_for_legacy_reeval_entries()
    assert result is not None
    assert "qe-evaluator" in result
    assert "migrate_qe_evaluator_name.py" in result
    assert "docs/MIGRATION-v7.md" in result


def test_detects_legacy_trigger_prefix_in_amendments(tmp_path, monkeypatch):
    """CH-02: returns a notice when 'trigger': 'qe-evaluator:...' appears in amendments.jsonl."""
    projects_root = tmp_path / ".something-wicked" / "wicked-garden" / "projects"
    phase_dir = _make_crew_project(projects_root, "my-project")
    legacy_record = {
        "reviewer": "gate-adjudicator",
        "trigger": "qe-evaluator:testability",
        "chain_id": "my-project.design",
    }
    (phase_dir / "amendments.jsonl").write_text(
        json.dumps(legacy_record) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = _scan_for_legacy_reeval_entries()
    assert result is not None
    assert "migrate_qe_evaluator_name.py" in result


def test_notice_is_advisory_does_not_raise(tmp_path, monkeypatch):
    """CH-02: scan never raises — returns a string, not an exception."""
    projects_root = tmp_path / ".something-wicked" / "wicked-garden" / "projects"
    phase_dir = _make_crew_project(projects_root, "my-project")
    (phase_dir / "reeval-log.jsonl").write_text(
        '{"reviewer": "qe-evaluator", "chain_id": "x.design"}\n', encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Must not raise — advisory only
    result = _scan_for_legacy_reeval_entries()
    assert isinstance(result, str)
