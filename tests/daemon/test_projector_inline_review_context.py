"""tests/daemon/test_projector_inline_review_context.py — Site W1 (#787)
projector tests for ``inline-review-context.md`` materialised from
``wicked.crew.inline_review_context_recorded`` events fired by
``solo_mode.dispatch_human_inline()``.

Covers:
  * Handler registered in ``_HANDLERS``.
  * Flag-off contract (no write).
  * Missing-payload-fields contract (no write, debug log).
  * Happy path: full payload → markdown materialised with the same
    shape ``solo_mode._write_inline_review_context`` produces.
  * Content-hash idempotency on replay.
  * Project-row absent / NULL-directory edge cases.
  * Resolver mapping: event_type ↔ inline-review-context.md.

T1: deterministic — fixed-string ``recorded_at`` in payload.
T2: no sleep-based sync.
T3: isolated — each test gets its own tmp_path + in-memory DB.
T6: provenance: #787 Site W1 wave-2 cutover.
"""
from __future__ import annotations

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


_FIXED_RECORDED_AT = "2026-05-03T18:00:00Z"


def _setup_project_in_db(conn, project_id: str, project_dir: Path) -> None:
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
    project_id: str = "my-proj",
    phase: str = "build",
    gate_name: str = "build-quality",
    bullets: "list[str] | None" = None,
    raw_response: str = "Looks fine — APPROVE",
    gate_result_ref: str = "phases/build/gate-result.json",
    recorded_at: "str | None" = _FIXED_RECORDED_AT,
) -> dict:
    if bullets is None:
        bullets = ["Tests passing", "No security findings"]
    payload: dict = {
        "project_id": project_id,
        "phase": phase,
        "gate_name": gate_name,
        "bullets": bullets,
        "raw_response": raw_response,
        "gate_result_ref": gate_result_ref,
    }
    if recorded_at is not None:
        payload["recorded_at"] = recorded_at
    return {
        "event_id": 1,
        "event_type": "wicked.crew.inline_review_context_recorded",
        "chain_id": f"{project_id}.{phase}.gate",
        "created_at": 1_700_000_001,
        "payload": payload,
    }


def test_handler_is_registered() -> None:
    from daemon.projector import _HANDLERS, _inline_review_context_recorded

    assert "wicked.crew.inline_review_context_recorded" in _HANDLERS
    assert (
        _HANDLERS["wicked.crew.inline_review_context_recorded"]
        is _inline_review_context_recorded
    )


def test_flag_off_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _inline_review_context_recorded

    project_dir = tmp_path / "proj-flagoff"
    _setup_project_in_db(mem_conn, "proj-flagoff", project_dir)
    target = project_dir / "phases" / "build" / "inline-review-context.md"

    event = _make_event(project_id="proj-flagoff")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT": "off"}):
        _inline_review_context_recorded(mem_conn, event)

    assert not target.exists()


def test_missing_required_fields_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _inline_review_context_recorded

    project_dir = tmp_path / "proj-missing"
    _setup_project_in_db(mem_conn, "proj-missing", project_dir)
    target = project_dir / "phases" / "build" / "inline-review-context.md"

    event = _make_event(project_id="proj-missing")
    # Drop required field gate_name.
    del event["payload"]["gate_name"]
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT": "on"}):
        _inline_review_context_recorded(mem_conn, event)

    assert not target.exists()


def test_happy_path_materialises_markdown(mem_conn, tmp_path) -> None:
    from daemon.projector import _inline_review_context_recorded

    project_dir = tmp_path / "proj-happy"
    _setup_project_in_db(mem_conn, "proj-happy", project_dir)
    target = project_dir / "phases" / "build" / "inline-review-context.md"

    event = _make_event(
        project_id="proj-happy",
        bullets=["Tests passing", "Security clean"],
        raw_response="APPROVE",
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT": "on"}):
        _inline_review_context_recorded(mem_conn, event)

    assert target.exists()
    body = target.read_text(encoding="utf-8")
    # Spot-check headings + content the projector should always emit.
    assert "# Inline Gate Review: build-quality (build)" in body
    assert f"**Timestamp**: {_FIXED_RECORDED_AT}" in body
    assert "**Gate**: build-quality" in body
    assert "**Phase**: build" in body
    assert "## Evidence Summary" in body
    assert "- Tests passing" in body
    assert "- Security clean" in body
    assert "## User Response" in body
    assert "> APPROVE" in body
    assert "## Artifact Reference" in body
    assert "Gate result: `phases/build/gate-result.json`" in body


def test_replay_skips_rewrite_via_content_hash(mem_conn, tmp_path) -> None:
    from daemon.projector import _inline_review_context_recorded

    project_dir = tmp_path / "proj-replay"
    _setup_project_in_db(mem_conn, "proj-replay", project_dir)
    target = project_dir / "phases" / "build" / "inline-review-context.md"

    event = _make_event(project_id="proj-replay")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT": "on"}):
        _inline_review_context_recorded(mem_conn, event)
        first_mtime = target.stat().st_mtime_ns
        first_bytes = target.read_bytes()
        _inline_review_context_recorded(mem_conn, event)
        second_mtime = target.stat().st_mtime_ns
        second_bytes = target.read_bytes()

    assert first_bytes == second_bytes
    assert first_mtime == second_mtime, (
        "replay must short-circuit before atomic rename — identical mtime "
        "confirms content-hash guard fired"
    )


def test_missing_project_row_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _inline_review_context_recorded

    project_dir = tmp_path / "proj-no-db"
    target = project_dir / "phases" / "build" / "inline-review-context.md"
    # Intentionally do NOT register project in DB.

    event = _make_event(project_id="proj-no-db")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_INLINE_REVIEW_CONTEXT": "on"}):
        _inline_review_context_recorded(mem_conn, event)

    assert not target.exists()


def test_resolver_returns_inline_review_context() -> None:
    """_PROJECTION_RESOLVERS maps the event to inline-review-context.md."""
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"),
        "wicked.crew.inline_review_context_recorded",
        "proj.build.gate",
        {"project_id": "proj", "phase": "build", "gate_name": "g"},
    )
    names = {p.name for p in paths}
    assert names == {"inline-review-context.md"}
