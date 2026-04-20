"""tests/crew/test_migrate_qe_evaluator_name.py — Unit + integration tests for
migrate_qe_evaluator_name.py and reeval_addendum.normalize_reviewer_name.

Provenance: AC-36, AC-38 (design doc §6)
T1: deterministic — no randomness, no wall-clock, no sleep
T2: no sleep-based sync
T3: isolated — each test uses its own tempdir
T4: single behavior per test
T5: descriptive names
T6: each docstring cites its AC
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_CREW = _REPO_ROOT / "scripts" / "crew"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures"

for _p in [str(_SCRIPTS_CREW), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from reeval_addendum import normalize_reviewer_name  # noqa: E402
from migrate_qe_evaluator_name import (  # noqa: E402
    _has_legacy_entry,
    _migrate_file,
    _rewrite_record,
    _rewrite_reviewer,
    _rewrite_trigger,
    main,
)


# ---------------------------------------------------------------------------
# Unit: normalize_reviewer_name — 4 variants (AC-36, design §6)
# ---------------------------------------------------------------------------

def test_normalize_reviewer_name_legacy_short():
    """AC-36: 'qe-evaluator' maps to 'gate-adjudicator'."""
    assert normalize_reviewer_name("qe-evaluator") == "gate-adjudicator"


def test_normalize_reviewer_name_legacy_fq():
    """AC-36: 'wicked-garden:crew:qe-evaluator' maps to 'wicked-garden:crew:gate-adjudicator'."""
    assert normalize_reviewer_name("wicked-garden:crew:qe-evaluator") == "wicked-garden:crew:gate-adjudicator"


def test_normalize_reviewer_name_canonical_pass_through():
    """AC-36: 'gate-adjudicator' is already canonical — pass-through."""
    assert normalize_reviewer_name("gate-adjudicator") == "gate-adjudicator"


def test_normalize_reviewer_name_canonical_fq_pass_through():
    """AC-36: 'wicked-garden:crew:gate-adjudicator' is already canonical — pass-through."""
    assert normalize_reviewer_name("wicked-garden:crew:gate-adjudicator") == "wicked-garden:crew:gate-adjudicator"


# ---------------------------------------------------------------------------
# Unit: _rewrite_record helper
# ---------------------------------------------------------------------------

def test_rewrite_record_reviewer_and_trigger():
    """_rewrite_record rewrites both reviewer and trigger in a single record."""
    rec = {
        "reviewer": "qe-evaluator",
        "trigger": "qe-evaluator:testability",
        "chain_id": "proj.test",
    }
    out = _rewrite_record(rec)
    assert out["reviewer"] == "gate-adjudicator"
    assert out["trigger"] == "gate-adjudicator:testability"
    assert out["chain_id"] == "proj.test"  # unchanged


def test_rewrite_record_already_canonical():
    """_rewrite_record passes canonical records through unchanged."""
    rec = {
        "reviewer": "gate-adjudicator",
        "trigger": "gate-adjudicator:evidence-quality",
    }
    out = _rewrite_record(rec)
    assert out == rec


def test_rewrite_record_manifest_path():
    """_rewrite_record rewrites qe-evaluator substrings in manifest_path."""
    rec = {
        "manifest_path": "phases/testability/qe-evaluator-conditions.json",
        "trigger": "phase-end",
    }
    out = _rewrite_record(rec)
    assert "qe-evaluator" not in out["manifest_path"]
    assert "gate-adjudicator" in out["manifest_path"]


# ---------------------------------------------------------------------------
# Integration: fixture JSONL — idempotent on second run (AC-38)
# ---------------------------------------------------------------------------

def _make_temp_project_with_fixture() -> tuple[Path, Path]:
    """Create a temp project dir with a copy of the mixed fixture JSONL.

    Returns (project_dir, log_path).
    """
    tmp_dir = Path(tempfile.mkdtemp())
    phase_dir = tmp_dir / "phases" / "test-strategy"
    phase_dir.mkdir(parents=True)
    fixture_src = _FIXTURES_DIR / "reeval_log_mixed.jsonl"
    log_path = phase_dir / "reeval-log.jsonl"
    shutil.copy(fixture_src, log_path)
    return tmp_dir, log_path


def test_migration_run1_migrates_legacy_entries_and_creates_bak():
    """
    AC-38 — integration: first run migrates 5 legacy entries, leaves 3 canonical
    entries unchanged, creates .bak sidecar, exits 0.
    """
    project_dir, log_path = _make_temp_project_with_fixture()
    try:
        rc = main(["--project-dir", str(project_dir)])
        assert rc == 0, f"Expected exit 0, got {rc}"

        # .bak must exist
        bak_path = log_path.with_suffix(".jsonl.bak")
        assert bak_path.exists(), ".bak sidecar not created on first run"

        # All reviewer fields must be canonical
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 8, f"Expected 8 lines, got {len(lines)}"
        for line in lines:
            rec = json.loads(line)
            reviewer = rec.get("reviewer", "")
            assert reviewer == "gate-adjudicator", (
                f"Legacy reviewer found after migration: {reviewer!r} in {rec['chain_id']!r}"
            )
            trigger = rec.get("trigger", "")
            assert not trigger.startswith("qe-evaluator:"), (
                f"Legacy trigger found after migration: {trigger!r}"
            )
    finally:
        shutil.rmtree(project_dir)


def test_migration_run2_is_idempotent():
    """
    AC-38 — idempotency: second run skips already-migrated file, does NOT
    create a new .bak, output file identical to run-1 output, exits 0.
    """
    project_dir, log_path = _make_temp_project_with_fixture()
    try:
        # Run 1
        rc1 = main(["--project-dir", str(project_dir)])
        assert rc1 == 0

        bak_path = log_path.with_suffix(".jsonl.bak")
        assert bak_path.exists()
        bak_mtime_after_run1 = bak_path.stat().st_mtime
        content_after_run1 = log_path.read_bytes()

        # Run 2
        rc2 = main(["--project-dir", str(project_dir)])
        assert rc2 == 0

        # .bak must NOT have been overwritten (mtime unchanged)
        bak_mtime_after_run2 = bak_path.stat().st_mtime
        assert bak_mtime_after_run2 == bak_mtime_after_run1, (
            ".bak was overwritten on second run — idempotency violated"
        )

        # File contents must be identical to run-1 output
        content_after_run2 = log_path.read_bytes()
        assert content_after_run2 == content_after_run1, (
            "File content changed on second run — idempotency violated"
        )
    finally:
        shutil.rmtree(project_dir)


def test_migration_dry_run_makes_no_changes():
    """
    AC-38 — dry-run: --dry-run flag prints what would change but makes no writes,
    no .bak files, file content unchanged, exits 0.
    """
    project_dir, log_path = _make_temp_project_with_fixture()
    try:
        original_content = log_path.read_bytes()

        rc = main(["--dry-run", "--project-dir", str(project_dir)])
        assert rc == 0

        # No .bak should exist
        bak_path = log_path.with_suffix(".jsonl.bak")
        assert not bak_path.exists(), ".bak created during --dry-run (violation)"

        # File content must be unchanged
        assert log_path.read_bytes() == original_content, (
            "File was modified during --dry-run (violation)"
        )
    finally:
        shutil.rmtree(project_dir)
