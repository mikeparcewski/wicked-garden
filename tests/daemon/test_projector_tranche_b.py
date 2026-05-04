"""tests/daemon/test_projector_tranche_b.py — Wave-2 Tranche B projector
handler tests for the four JSONL append-stream cutovers (#746).

Sites covered:
  * W6 ``wicked.amendment.appended``         → amendments.jsonl (per-phase)
  * W7 ``wicked.reeval.addendum_appended``   → reeval-log.jsonl + process-plan.addendum.jsonl (DUAL FILE)
  * W8 ``wicked.convergence.transition_recorded`` → convergence-log.jsonl
  * W10a ``wicked.review.semantic_gap_recorded``  → semantic-gap-report.json (full-file rewrite)

Common contract for the three append-stream handlers (W6/W7/W8):
  * Flag-off → no-op
  * Missing required payload fields (project_id, phase, raw_payload) → no-op
  * Project row absent / NULL directory → warn + no-op
  * Idempotency: line-presence check (replay short-circuit)
  * Append uses ``open("a") + fsync`` with newline normalisation

W10a is full-file rewrite (not append) so it uses content-hash idempotency
+ atomic temp+rename, same shape as Site 5's gate-result handler.

T1: deterministic.  T3: isolated tmp_path + in-memory DB.  T6: provenance #746 wave-2 B.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _REPO_ROOT / "scripts" / "crew"

for p in (_REPO_ROOT, _SCRIPTS, _SCRIPTS_CREW):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _setup_project(conn, project_id: str, project_dir: Path) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()


def _make_event(
    *,
    event_type: str,
    project_id: str,
    phase: str,
    raw_payload: str,
    extras: "dict | None" = None,
    chain_id: "str | None" = None,
) -> dict:
    payload = {
        "project_id": project_id,
        "phase": phase,
        "raw_payload": raw_payload,
    }
    if extras:
        payload.update(extras)
    return {
        "event_id": 1,
        "event_type": event_type,
        "chain_id": chain_id or f"{project_id}.{phase}.x",
        "created_at": 1_700_000_001,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Registration — all four handlers in _HANDLERS
# ---------------------------------------------------------------------------


def test_all_tranche_b_handlers_registered() -> None:
    from daemon.projector import (
        _HANDLERS,
        _amendment_appended,
        _reeval_addendum_appended,
        _convergence_transition_recorded,
        _semantic_gap_recorded,
    )

    assert _HANDLERS["wicked.amendment.appended"] is _amendment_appended
    assert _HANDLERS["wicked.reeval.addendum_appended"] is _reeval_addendum_appended
    assert _HANDLERS["wicked.convergence.transition_recorded"] is _convergence_transition_recorded
    assert _HANDLERS["wicked.review.semantic_gap_recorded"] is _semantic_gap_recorded


# ---------------------------------------------------------------------------
# W6 — amendments.jsonl
# ---------------------------------------------------------------------------


def test_amendment_flag_off_no_append(mem_conn, tmp_path) -> None:
    from daemon.projector import _amendment_appended

    project_dir = tmp_path / "proj-amend-off"
    _setup_project(mem_conn, "proj-amend-off", project_dir)
    target = project_dir / "phases" / "build" / "amendments.jsonl"

    event = _make_event(
        event_type="wicked.amendment.appended",
        project_id="proj-amend-off",
        phase="build",
        raw_payload='{"amendment_id": "AMD-x", "summary": "x"}',
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_AMENDMENTS": "off"}):
        _amendment_appended(mem_conn, event)

    assert not target.exists()


def test_amendment_happy_path_appends_line(mem_conn, tmp_path) -> None:
    from daemon.projector import _amendment_appended

    project_dir = tmp_path / "proj-amend-on"
    _setup_project(mem_conn, "proj-amend-on", project_dir)
    target = project_dir / "phases" / "build" / "amendments.jsonl"

    line = '{"amendment_id": "AMD-test-001", "summary": "test"}'
    event = _make_event(
        event_type="wicked.amendment.appended",
        project_id="proj-amend-on",
        phase="build",
        raw_payload=line,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_AMENDMENTS": "on"}):
        _amendment_appended(mem_conn, event)

    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert content == line + "\n"


def test_amendment_replay_idempotent(mem_conn, tmp_path) -> None:
    from daemon.projector import _amendment_appended

    project_dir = tmp_path / "proj-amend-replay"
    _setup_project(mem_conn, "proj-amend-replay", project_dir)
    target = project_dir / "phases" / "build" / "amendments.jsonl"

    line = '{"amendment_id": "AMD-x", "summary": "x"}'
    event = _make_event(
        event_type="wicked.amendment.appended",
        project_id="proj-amend-replay",
        phase="build",
        raw_payload=line,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_AMENDMENTS": "on"}):
        _amendment_appended(mem_conn, event)
        first = target.read_text(encoding="utf-8")
        _amendment_appended(mem_conn, event)
        second = target.read_text(encoding="utf-8")

    assert first == second, "replay must short-circuit (line already present)"


# ---------------------------------------------------------------------------
# W7 — reeval-log.jsonl + process-plan.addendum.jsonl (DUAL FILE)
# ---------------------------------------------------------------------------


def test_reeval_addendum_writes_both_files(mem_conn, tmp_path) -> None:
    from daemon.projector import _reeval_addendum_appended

    project_dir = tmp_path / "proj-reeval"
    _setup_project(mem_conn, "proj-reeval", project_dir)
    per_phase = project_dir / "phases" / "design" / "reeval-log.jsonl"
    project_log = project_dir / "process-plan.addendum.jsonl"

    line = '{"chain_id": "proj.design.reeval-1", "trigger": "re-eval"}'
    event = _make_event(
        event_type="wicked.reeval.addendum_appended",
        project_id="proj-reeval",
        phase="design",
        raw_payload=line,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REEVAL_ADDENDUM": "on"}):
        _reeval_addendum_appended(mem_conn, event)

    assert per_phase.exists()
    assert project_log.exists()
    expected_line = line + "\n"
    assert per_phase.read_text(encoding="utf-8") == expected_line
    assert project_log.read_text(encoding="utf-8") == expected_line


def test_reeval_addendum_replay_idempotent_per_file(mem_conn, tmp_path) -> None:
    """Replay must not double-append in EITHER file."""
    from daemon.projector import _reeval_addendum_appended

    project_dir = tmp_path / "proj-reeval-replay"
    _setup_project(mem_conn, "proj-reeval-replay", project_dir)
    per_phase = project_dir / "phases" / "design" / "reeval-log.jsonl"
    project_log = project_dir / "process-plan.addendum.jsonl"

    line = '{"chain_id": "p.design.r-1", "trigger": "re-eval"}'
    event = _make_event(
        event_type="wicked.reeval.addendum_appended",
        project_id="proj-reeval-replay",
        phase="design",
        raw_payload=line,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REEVAL_ADDENDUM": "on"}):
        _reeval_addendum_appended(mem_conn, event)
        _reeval_addendum_appended(mem_conn, event)

    assert per_phase.read_text(encoding="utf-8") == line + "\n"
    assert project_log.read_text(encoding="utf-8") == line + "\n"


def test_reeval_addendum_flag_off_no_writes(mem_conn, tmp_path) -> None:
    from daemon.projector import _reeval_addendum_appended

    project_dir = tmp_path / "proj-reeval-off"
    _setup_project(mem_conn, "proj-reeval-off", project_dir)

    event = _make_event(
        event_type="wicked.reeval.addendum_appended",
        project_id="proj-reeval-off",
        phase="design",
        raw_payload='{"trigger": "x"}',
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REEVAL_ADDENDUM": "off"}):
        _reeval_addendum_appended(mem_conn, event)

    assert not (project_dir / "phases" / "design" / "reeval-log.jsonl").exists()
    assert not (project_dir / "process-plan.addendum.jsonl").exists()


# ---------------------------------------------------------------------------
# W8 — convergence-log.jsonl
# ---------------------------------------------------------------------------


def test_convergence_happy_path_appends(mem_conn, tmp_path) -> None:
    from daemon.projector import _convergence_transition_recorded

    project_dir = tmp_path / "proj-conv"
    _setup_project(mem_conn, "proj-conv", project_dir)
    target = project_dir / "phases" / "build" / "convergence-log.jsonl"

    line = '{"artifact_id": "A-1", "from_state": "Designed", "to_state": "Built"}'
    event = _make_event(
        event_type="wicked.convergence.transition_recorded",
        project_id="proj-conv",
        phase="build",
        raw_payload=line,
        extras={"artifact_id": "A-1"},
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONVERGENCE": "on"}):
        _convergence_transition_recorded(mem_conn, event)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == line + "\n"


def test_convergence_flag_off_no_append(mem_conn, tmp_path) -> None:
    from daemon.projector import _convergence_transition_recorded

    project_dir = tmp_path / "proj-conv-off"
    _setup_project(mem_conn, "proj-conv-off", project_dir)
    target = project_dir / "phases" / "build" / "convergence-log.jsonl"

    event = _make_event(
        event_type="wicked.convergence.transition_recorded",
        project_id="proj-conv-off",
        phase="build",
        raw_payload='{"artifact_id": "A-1"}',
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONVERGENCE": "off"}):
        _convergence_transition_recorded(mem_conn, event)

    assert not target.exists()


# ---------------------------------------------------------------------------
# W10a — semantic-gap-report.json (full-file rewrite, content-hash idempotency)
# ---------------------------------------------------------------------------


def test_semantic_gap_writes_to_review_phase_regardless_of_event_phase(
    mem_conn, tmp_path,
) -> None:
    """Semantic-gap report always lands at phases/review/, not the event's phase."""
    from daemon.projector import _semantic_gap_recorded

    project_dir = tmp_path / "proj-sg"
    _setup_project(mem_conn, "proj-sg", project_dir)
    target = project_dir / "phases" / "review" / "semantic-gap-report.json"

    body = json.dumps({"verdict": "ALIGNED", "score": 0.95}, indent=2)
    # NOTE: event "phase" is "build" but the projector pins to "review".
    event = _make_event(
        event_type="wicked.review.semantic_gap_recorded",
        project_id="proj-sg",
        phase="build",
        raw_payload=body,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SEMANTIC_GAP": "on"}):
        _semantic_gap_recorded(mem_conn, event)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == body


def test_semantic_gap_replay_short_circuits_via_content_hash(
    mem_conn, tmp_path,
) -> None:
    from daemon.projector import _semantic_gap_recorded

    project_dir = tmp_path / "proj-sg-replay"
    _setup_project(mem_conn, "proj-sg-replay", project_dir)
    target = project_dir / "phases" / "review" / "semantic-gap-report.json"

    body = json.dumps({"verdict": "DIVERGENT", "score": 0.6})
    event = _make_event(
        event_type="wicked.review.semantic_gap_recorded",
        project_id="proj-sg-replay",
        phase="review",
        raw_payload=body,
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SEMANTIC_GAP": "on"}):
        _semantic_gap_recorded(mem_conn, event)
        first_mtime = target.stat().st_mtime_ns
        _semantic_gap_recorded(mem_conn, event)
        second_mtime = target.stat().st_mtime_ns

    assert first_mtime == second_mtime, (
        "replay must skip atomic-rename when content-hash matches"
    )


def test_semantic_gap_flag_off_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _semantic_gap_recorded

    project_dir = tmp_path / "proj-sg-off"
    _setup_project(mem_conn, "proj-sg-off", project_dir)
    target = project_dir / "phases" / "review" / "semantic-gap-report.json"

    event = _make_event(
        event_type="wicked.review.semantic_gap_recorded",
        project_id="proj-sg-off",
        phase="review",
        raw_payload='{}',
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SEMANTIC_GAP": "off"}):
        _semantic_gap_recorded(mem_conn, event)

    assert not target.exists()


# ---------------------------------------------------------------------------
# Resolvers — projection paths match the handlers' targets
# ---------------------------------------------------------------------------


def test_amendment_resolver_returns_amendments_jsonl() -> None:
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"),
        "wicked.amendment.appended",
        "proj.build.AMD-x",
        {"project_id": "proj", "phase": "build"},
    )
    assert {p.name for p in paths} == {"amendments.jsonl"}


def test_reeval_addendum_resolver_returns_dual_paths() -> None:
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"),
        "wicked.reeval.addendum_appended",
        "proj.design.reeval-1",
        {"project_id": "proj", "phase": "design"},
    )
    names = sorted(str(p).split("proj/")[-1] for p in paths)
    assert names == [
        "phases/design/reeval-log.jsonl",
        "process-plan.addendum.jsonl",
    ]


def test_semantic_gap_resolver_pins_to_review_phase() -> None:
    """Resolver returns phases/review/semantic-gap-report.json regardless
    of the chain_id's phase segment."""
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"),
        "wicked.review.semantic_gap_recorded",
        "proj.build.semantic-gap-x",  # event-phase is "build" — projector pins "review"
        {"project_id": "proj", "phase": "build"},
    )
    assert len(paths) == 1
    assert str(paths[0]).endswith("phases/review/semantic-gap-report.json")
