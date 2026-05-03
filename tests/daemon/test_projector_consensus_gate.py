"""tests/daemon/test_projector_consensus_gate.py — Projector tests for Site 3
bus-cutover handlers ``_consensus_gate_completed`` and
``_consensus_gate_pending`` (#768, #770).

Covers:
  * test_gate_completed_creates_fresh_file: empty phase dir → file matches raw_payload.
  * test_gate_completed_appends_to_existing: pre-existing report + gate_completed event
    (append branch, raw_payload = yaml_block) → file equals existing + separator + yaml_block.
  * test_gate_pending_writes_template_when_absent: empty phase dir → pending template written.
  * test_gate_pending_noop_when_report_exists: pre-existing report → file unchanged.
  * test_idempotent_replay_gate_completed: replay same gate_completed (create) event twice
    → file unchanged on second apply.
  * test_idempotent_append_replay_no_double_append: replay same gate_completed (append) event
    twice → no double-append (SHA-256 fingerprint guard, #770).
  * test_projector_reconstructs_cumulative_file_from_yaml_block: simulate legacy hook output,
    replay per-section payload via the projector → projector output byte-identical to legacy
    hook output (T1 determinism).
  * test_both_handlers_are_registered: dispatch table contains both new event types.
  * test_flag_off_gate_completed_noop: flag-off → file not written.
  * test_flag_off_gate_pending_noop: flag-off → file not written.
  * test_missing_required_fields_gate_completed: missing project_id/phase/raw_payload → skip.
  * test_missing_project_directory_in_db: project row absent → warning, skip.
  * test_project_directory_null_in_db: project row present but directory=NULL → skip.

T1: deterministic — fixed-epoch timestamps, no wall-clock reads in assertions.
T2: no sleep-based sync.
T3: isolated — each test gets its own tmp_path + in-memory DB via mem_conn fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #768 #770 Site 3 bus-cutover.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure daemon/ and scripts/ are importable from the repo root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"

for p in (_REPO_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ---------------------------------------------------------------------------
# Helpers — project / phase directory setup
# ---------------------------------------------------------------------------

def _setup_project_in_db(conn, project_id: str, project_dir: Path) -> None:
    """Insert a minimal project row so db.get_project resolves project_dir."""
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()


def _make_project_dir(tmp_path: Path, project_id: str = "my-proj") -> Path:
    """Return a project directory under tmp_path (not yet created)."""
    return tmp_path / project_id


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------

_FIXED_TS = 1_700_000_001

_SAMPLE_YAML_BLOCK = textwrap.dedent("""\
    ---
    verdict: approved
    evidence_items_checked: 2
    reviewer: consensus-gate
    reviewed_at: 2026-01-01T00:00:00Z
    agreement_ratio: 0.9
    findings: []
    conditions: []
    ---
""")

_SAMPLE_PENDING_BLOCK = textwrap.dedent("""\
    ---
    verdict: pending
    evidence_items_checked: 0
    reviewer: consensus-gate
    reviewed_at: 2026-01-01T00:00:00Z
    agreement_ratio: 0.0
    findings: []
    conditions: []
    note: "consensus evaluation failed or was skipped — will be re-evaluated on next approve"
    ---
""")

_SEPARATOR = "\n\n---\n## Consensus Gate Evaluation\n\n"


def _make_gate_completed_create_event(
    *,
    event_id: int = 1,
    project_id: str = "my-proj",
    phase: str = "build",
    eval_id: str = "aabbccdd11223344",
    raw_payload: str | None = None,
) -> dict[str, Any]:
    """Build a wicked.consensus.gate_completed event (create branch)."""
    if raw_payload is None:
        raw_payload = _SAMPLE_YAML_BLOCK
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.gate_completed",
        "chain_id": f"{project_id}.{phase}.consensus.{eval_id}",
        "created_at": _FIXED_TS + event_id,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "verdict": "approved",
            "eval_id": eval_id,
            "branch": "create",
            "raw_payload": raw_payload,
        },
    }


def _make_gate_completed_append_event(
    *,
    event_id: int = 2,
    project_id: str = "my-proj",
    phase: str = "build",
    eval_id: str = "aabbccdd11223344",
    existing_content: str,
    yaml_block: str | None = None,
) -> dict[str, Any]:
    """Build a wicked.consensus.gate_completed event (append branch).

    raw_payload = yaml_block only (per-section payload contract, #770).
    The projector reads the existing file, applies _SEPARATOR, and appends
    raw_payload — reconstructing the cumulative file without carrying it in
    the event.
    """
    if yaml_block is None:
        yaml_block = _SAMPLE_YAML_BLOCK
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.gate_completed",
        "chain_id": f"{project_id}.{phase}.consensus.{eval_id}",
        "created_at": _FIXED_TS + event_id,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "verdict": "approved",
            "eval_id": eval_id,
            "branch": "append",
            "raw_payload": yaml_block,
        },
    }


def _make_gate_pending_event(
    *,
    event_id: int = 1,
    project_id: str = "my-proj",
    phase: str = "build",
    eval_id: str = "aabbccdd11223344",
    raw_payload: str | None = None,
) -> dict[str, Any]:
    """Build a wicked.consensus.gate_pending event."""
    if raw_payload is None:
        raw_payload = _SAMPLE_PENDING_BLOCK
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.gate_pending",
        "chain_id": f"{project_id}.{phase}.consensus.{eval_id}",
        "created_at": _FIXED_TS + event_id,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "eval_id": eval_id,
            "raw_payload": raw_payload,
        },
    }


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_both_handlers_are_registered_in_dispatch_table() -> None:
    """Site 3 handlers MUST be registered in _HANDLERS always (registered-always
    pattern, per Decision #6 / Council Condition C5 precedent from Site 1+2).
    Gating happens INSIDE the handler via flag check, not by removing it from
    the table."""
    from daemon.projector import (
        _HANDLERS,
        _consensus_gate_completed,
        _consensus_gate_pending,
    )

    assert "wicked.consensus.gate_completed" in _HANDLERS, (
        "wicked.consensus.gate_completed not registered in _HANDLERS — "
        "#769 handler-presence gate scan will miss it."
    )
    assert _HANDLERS["wicked.consensus.gate_completed"] is _consensus_gate_completed

    assert "wicked.consensus.gate_pending" in _HANDLERS, (
        "wicked.consensus.gate_pending not registered in _HANDLERS."
    )
    assert _HANDLERS["wicked.consensus.gate_pending"] is _consensus_gate_pending


# ---------------------------------------------------------------------------
# Flag-off contract
# ---------------------------------------------------------------------------


def test_flag_off_gate_completed_noop(mem_conn, tmp_path) -> None:
    """flag-off → file not written, project_event returns 'applied' (Decision #6)."""
    from daemon.projector import project_event

    project_id = "proj-flagoff-completed"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_completed_create_event(project_id=project_id)
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WG_BUS_AS_TRUTH_REVIEWER_REPORT", None)
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert not report_path.exists(), (
        "flag-off: reviewer-report.md must NOT be written when "
        "WG_BUS_AS_TRUTH_REVIEWER_REPORT is unset."
    )


def test_flag_off_gate_pending_noop(mem_conn, tmp_path) -> None:
    """flag-off → pending file not written."""
    from daemon.projector import project_event

    project_id = "proj-flagoff-pending"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_pending_event(project_id=project_id)
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WG_BUS_AS_TRUTH_REVIEWER_REPORT", None)
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert not report_path.exists()


# ---------------------------------------------------------------------------
# Core write behaviour (flag-on)
# ---------------------------------------------------------------------------


def test_gate_completed_creates_fresh_file(mem_conn, tmp_path) -> None:
    """Empty phase dir, single gate_completed event → file matches raw_payload."""
    from daemon.projector import project_event

    project_id = "proj-fresh"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    raw = _SAMPLE_YAML_BLOCK
    event = _make_gate_completed_create_event(
        project_id=project_id, raw_payload=raw
    )
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert report_path.exists(), "reviewer-report.md was not created."
    assert report_path.read_text(encoding="utf-8") == raw


def test_gate_completed_appends_to_existing(mem_conn, tmp_path) -> None:
    """Pre-existing report + gate_completed (append branch, per-section payload)
    → file equals existing + separator + yaml_block.

    raw_payload is now just the yaml_block (per-section contract, #770).
    The projector reads the existing file, applies _SEPARATOR, and appends
    raw_payload — reconstructing the same cumulative file the legacy hook wrote.
    """
    from daemon.projector import project_event

    project_id = "proj-append"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    # Pre-populate the file as the independent-reviewer agent would have done.
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    existing_content = "## Independent Review\n\nLooks good.\n"
    report_path = phase_dir / "reviewer-report.md"
    report_path.write_text(existing_content, encoding="utf-8")

    # Append event carries only the yaml_block (per-section payload, #770).
    event = _make_gate_completed_append_event(
        project_id=project_id,
        existing_content=existing_content,
    )
    # Expected: existing + separator + yaml_block (byte-identical to legacy hook output).
    expected_full = existing_content + _SEPARATOR + _SAMPLE_YAML_BLOCK

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert report_path.read_text(encoding="utf-8") == expected_full


def test_gate_pending_writes_template_when_absent(mem_conn, tmp_path) -> None:
    """Empty phase dir → pending template written (mirrors _write_pending_reviewer_report)."""
    from daemon.projector import project_event

    project_id = "proj-pending-fresh"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    raw = _SAMPLE_PENDING_BLOCK
    event = _make_gate_pending_event(project_id=project_id, raw_payload=raw)
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8") == raw


def test_gate_pending_noop_when_report_exists(mem_conn, tmp_path) -> None:
    """Pre-existing report + gate_pending → file unchanged (NO-OP contract).

    The hook's _write_pending_reviewer_report returns immediately if the file
    exists — never clobbers a real result.  The projector must mirror this.
    """
    from daemon.projector import project_event

    project_id = "proj-pending-noop"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    # Pre-populate with a real report.
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    real_report = "## Real Review\n\nAll checks passed.\n"
    report_path = phase_dir / "reviewer-report.md"
    report_path.write_text(real_report, encoding="utf-8")

    event = _make_gate_pending_event(
        project_id=project_id,
        raw_payload=_SAMPLE_PENDING_BLOCK,
    )

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    # The real report MUST NOT be clobbered.
    assert report_path.read_text(encoding="utf-8") == real_report


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotent_replay_gate_completed(mem_conn, tmp_path) -> None:
    """Replaying the same gate_completed (create branch) event twice → file unchanged.

    Create branch is idempotent by nature: writing the same bytes twice yields
    the same file.  Verify explicitly.
    """
    from daemon.projector import _consensus_gate_completed  # call handler directly

    project_id = "proj-idempotent"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    raw = _SAMPLE_YAML_BLOCK
    event = _make_gate_completed_create_event(project_id=project_id, raw_payload=raw)
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        _consensus_gate_completed(mem_conn, event)
        first_content = report_path.read_text(encoding="utf-8")

        # Second apply — same event, same bytes.
        _consensus_gate_completed(mem_conn, event)
        second_content = report_path.read_text(encoding="utf-8")

    assert first_content == second_content == raw, (
        "Idempotency failure: second apply changed file content."
    )


def test_idempotent_append_replay_no_double_append(mem_conn, tmp_path) -> None:
    """Replaying the same gate_completed (append branch) event twice → no double-append.

    The daemon consumer does NOT deduplicate before calling handlers (append_event_log
    uses INSERT OR REPLACE, not INSERT OR IGNORE).  The handler guards with a substring
    scan: the second apply detects the section is already present and skips — leaving
    the file unchanged.  (#770 idempotency requirement.)
    """
    from daemon.projector import _consensus_gate_completed

    project_id = "proj-append-idempotent"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    existing_content = "## Independent Review\n\nAll good.\n"
    report_path = phase_dir / "reviewer-report.md"
    report_path.write_text(existing_content, encoding="utf-8")

    event = _make_gate_completed_append_event(
        project_id=project_id,
        existing_content=existing_content,
    )
    expected_after_first = existing_content + _SEPARATOR + _SAMPLE_YAML_BLOCK

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        # First apply — append the section.
        _consensus_gate_completed(mem_conn, event)
        after_first = report_path.read_text(encoding="utf-8")
        assert after_first == expected_after_first, (
            "First append produced unexpected content."
        )

        # Second apply — same event; SHA-256 guard must skip the duplicate.
        _consensus_gate_completed(mem_conn, event)
        after_second = report_path.read_text(encoding="utf-8")

    assert after_second == after_first, (
        "Idempotency failure: second append-branch apply double-appended the section.\n"
        f"After first ({len(after_first)} chars): {after_first!r}\n"
        f"After second ({len(after_second)} chars): {after_second!r}"
    )


# ---------------------------------------------------------------------------
# Byte-for-byte parity with legacy hook (per-section payload, #770)
# ---------------------------------------------------------------------------


def test_projector_reconstructs_cumulative_file_from_yaml_block(mem_conn, tmp_path) -> None:
    """Simulates the full legacy hook sequence and verifies the projector
    reconstructs the byte-identical cumulative file from per-section payloads.

    Scenario: independent-reviewer writes a review header, then the hook fires
    and appends a consensus section.  Legacy hook output = header + separator +
    yaml_block.  Projector receives raw_payload = yaml_block (per-section, #770)
    with the file pre-seeded with the header.

    Assertion: projector output is byte-identical to the legacy hook cumulative
    output.  T1 determinism: fixed timestamp in yaml_block, no wall-clock reads.
    """
    project_id = "proj-parity"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    # Simulate what the independent-reviewer agent wrote before the hook fired.
    independent_review = "## Independent Review\n\nCode looks good. No blockers.\n"

    # Simulate the yaml_block the hook builds (fixed timestamp for T1).
    fixed_yaml_block = textwrap.dedent("""\
        ---
        verdict: approved
        evidence_items_checked: 3
        reviewer: consensus-gate
        reviewed_at: 2026-01-01T12:00:00Z
        agreement_ratio: 0.9
        findings: []
        conditions: []
        ---
    """)

    # Reference: what the legacy hook would have written to disk directly.
    # Legacy hook: existing + separator + yaml_block.
    legacy_output = independent_review + _SEPARATOR + fixed_yaml_block

    ref_dir = tmp_path / "reference" / "phases" / "build"
    ref_dir.mkdir(parents=True)
    ref_path = ref_dir / "reviewer-report.md"
    ref_path.write_text(legacy_output, encoding="utf-8")

    # Projector path: pre-seed the file (as independent-reviewer wrote it),
    # then replay the append event with raw_payload = yaml_block only.
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    report_path = phase_dir / "reviewer-report.md"
    report_path.write_text(independent_review, encoding="utf-8")

    event = _make_gate_completed_append_event(
        project_id=project_id,
        existing_content=independent_review,
        yaml_block=fixed_yaml_block,
    )

    from daemon.projector import project_event

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    proj_content = report_path.read_text(encoding="utf-8")
    ref_content = ref_path.read_text(encoding="utf-8")

    # Byte-identical: projector reconstructs the same file the legacy hook wrote.
    assert proj_content == ref_content, (
        "Projector output is not byte-identical to the legacy hook output.\n"
        f"Projector wrote {len(proj_content)} chars; reference has {len(ref_content)} chars.\n"
        f"Projector: {proj_content!r}\nReference: {ref_content!r}"
    )

    # Structural equivalence: same non-empty lines in the same order.
    proj_lines = [line for line in proj_content.splitlines() if line.strip()]
    ref_lines = [line for line in ref_content.splitlines() if line.strip()]
    assert proj_lines == ref_lines


# ---------------------------------------------------------------------------
# Defensive: missing required fields
# ---------------------------------------------------------------------------


def test_missing_project_id_gate_completed(mem_conn, tmp_path) -> None:
    """Missing project_id → skips, never raises, returns 'applied'."""
    from daemon.projector import project_event

    event = _make_gate_completed_create_event()
    del event["payload"]["project_id"]

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"


def test_missing_phase_gate_completed(mem_conn, tmp_path) -> None:
    """Missing phase → skips."""
    from daemon.projector import project_event

    project_id = "proj-missing-phase"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_completed_create_event(project_id=project_id)
    del event["payload"]["phase"]

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"


def test_missing_raw_payload_gate_completed(mem_conn, tmp_path) -> None:
    """Missing raw_payload → skips, file not created."""
    from daemon.projector import project_event

    project_id = "proj-missing-raw"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_completed_create_event(project_id=project_id)
    del event["payload"]["raw_payload"]
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert not report_path.exists()


def test_missing_required_fields_gate_pending(mem_conn, tmp_path) -> None:
    """Missing raw_payload in gate_pending → skips, file not created."""
    from daemon.projector import project_event

    project_id = "proj-pending-missing-raw"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_pending_event(project_id=project_id)
    del event["payload"]["raw_payload"]
    report_path = project_dir / "phases" / "build" / "reviewer-report.md"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert not report_path.exists()


# ---------------------------------------------------------------------------
# Defensive: project_dir resolution failures
# ---------------------------------------------------------------------------


def test_missing_project_directory_in_db(mem_conn, tmp_path) -> None:
    """Project row absent → warning logged, file not written."""
    from daemon.projector import project_event

    # Intentionally do NOT insert a project row into the DB.
    event = _make_gate_completed_create_event(project_id="ghost-project")
    report_path = (
        tmp_path / "ghost-project" / "phases" / "build" / "reviewer-report.md"
    )

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert not report_path.exists(), (
        "File must not be written when project row is absent from DB."
    )


def test_project_directory_null_in_db(mem_conn, tmp_path) -> None:
    """Project row present but directory=NULL → warning, file not written."""
    from daemon.projector import project_event

    project_id = "proj-null-dir"
    mem_conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, None, "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    mem_conn.commit()

    event = _make_gate_completed_create_event(project_id=project_id)

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
        status = project_event(mem_conn, event)

    assert status == "applied"
    # No file path to check since we don't know where it would go —
    # the point is it does not raise.
