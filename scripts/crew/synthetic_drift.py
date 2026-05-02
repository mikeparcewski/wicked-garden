#!/usr/bin/env python3
"""Synthetic drift fixture builder for the bus-cutover staging plan (#746).

The organic baseline at ``docs/audits/bus-cutover-drift-baseline-2026-05-02.json``
falls below issue #746's sample-size floor (>=10 projects OR >=50 phases)
and #746 takes calendar waits off the table. This module deterministically
synthesises every drift class the reconciler knows about so the cutover
gates (Sites 3-5 of section 3 in the staging plan) have a concrete signal
that the detector works on demand.

Drift classes:
  pre-cutover (reconcile.py): missing_native, stale_status, orphan_native, phase_drift
  post-cutover (staging plan section 5): projection-stale,
    event-without-projection, projection-without-event

Post-cutover fixtures require the projector DB. When unreachable the
builder returns ``{"ok": False, "reason": "daemon_db_unavailable"}``
rather than fabricating event_log rows under ``~/.something-wicked/``.

Constraints: stdlib only; never writes outside ``workspace_dir``;
``teardown_drift_fixture`` is idempotent; every synthesised event uses
``{project}.{phase}.{discriminator}`` chain_ids per the bus dedupe
gotcha (memory: bus-chain-id-must-include-uniqueness-segment-gotcha).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: All drift classes the suite can synthesise.  Order is intentional:
#: pre-cutover classes first, post-cutover classes last.
SUPPORTED_DRIFT_CLASSES: Tuple[str, ...] = (
    # Current reconciler (pre-cutover)
    "missing_native",
    "stale_status",
    "orphan_native",
    "phase_drift",
    # Post-cutover (per staging plan section 5)
    "projection-stale",
    "event-without-projection",
    "projection-without-event",
)

#: Drift classes that require the projector DB.  Builder returns ``ok: False``
#: with reason ``daemon_db_unavailable`` when the DB cannot be opened.
_DAEMON_DB_BEARING: frozenset[str] = frozenset({
    "projection-stale",
    "event-without-projection",
    "projection-without-event",
})

#: Reasons a build can fail without raising.  Documented so test layers can
#: branch on them.
REASON_DAEMON_UNAVAILABLE: str = "daemon_db_unavailable"
REASON_UNSUPPORTED_CLASS: str = "unsupported_drift_class"
REASON_BAD_INPUT: str = "bad_input"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: dict) -> None:
    """Atomically-ish write a JSON file (best effort, stdlib only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _project_dir(workspace_dir: Path, project_slug: str) -> Path:
    """Mirror reconcile.py's WG_LOCAL_ROOT/wicked-crew/projects/{slug} layout."""
    return workspace_dir / "wicked-crew" / "projects" / project_slug


def _sessions_dir(workspace_dir: Path) -> Path:
    """Mirror CLAUDE_CONFIG_DIR/tasks/ layout."""
    return workspace_dir / "claude-config" / "tasks"


def _make_plan_task(
    *,
    task_id: str,
    title: str,
    phase: str,
    chain_id: str,
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "phase": phase,
        "blockedBy": [],
        "metadata": {
            "chain_id": chain_id,
            "event_type": "task",
            "source_agent": "synthetic-drift-builder",
            "phase": phase,
            "rigor_tier": "standard",
        },
    }


def _make_native_task(
    *,
    task_id: str,
    subject: str,
    status: str,
    chain_id: str,
    phase: str,
    event_type: str = "task",
) -> dict:
    return {
        "id": task_id,
        "subject": subject,
        "status": status,
        "metadata": {
            "chain_id": chain_id,
            "event_type": event_type,
            "source_agent": "synthetic-drift-builder",
            "phase": phase,
            "rigor_tier": "standard",
        },
    }


def _build_plan(slug: str, tasks: List[dict], phases: List[str] | None = None) -> dict:
    return {
        "project_slug": slug,
        "summary": "synthetic-drift fixture",
        "rigor_tier": "standard",
        "complexity": 2,
        "factors": {},
        "specialists": [],
        "phases": phases or ["build"],
        "tasks": tasks,
    }


# ---------------------------------------------------------------------------
# Daemon DB access (post-cutover classes only)
# ---------------------------------------------------------------------------

def _daemon_db_path(override: Optional[Path]) -> Optional[Path]:
    """Resolve the daemon DB path.

    Priority order:
      1. explicit ``override`` arg from the caller (used by tests)
      2. ``WG_DAEMON_DB`` env var
      3. default at ``~/.something-wicked/wicked-garden-daemon/projections.db``

    Returns None if no path resolves to an existing file OR the file
    exists but does NOT have the expected ``event_log`` schema.  The
    post-cutover classes interpret this as "daemon unavailable" and
    decline to build — we never run init_schema ourselves because that
    would be production-state mutation from a synthetic-drift fixture.
    """
    candidate: Optional[Path] = None
    if override is not None:
        candidate = Path(override)
    else:
        env = os.environ.get("WG_DAEMON_DB")
        if env:
            candidate = Path(env)
        else:
            candidate = Path.home() / ".something-wicked" / "wicked-garden-daemon" / "projections.db"

    if candidate is None or not candidate.is_file():
        return None
    if not _daemon_db_has_event_log(candidate):
        return None
    return candidate


def _daemon_db_has_event_log(path: Path) -> bool:
    """Return True when ``path`` is a sqlite DB exposing the event_log table.

    Used by ``_daemon_db_path`` so a half-initialised DB at the default
    location does not falsely pass the reachability check.
    """
    try:
        conn = sqlite3.connect(str(path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='event_log'"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _open_daemon_db(path: Path) -> sqlite3.Connection:
    """Open projections DB (WAL + FK on). Caller must have initialised the schema."""
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _next_event_id(conn: sqlite3.Connection) -> int:
    """Synthetic event_id: max(existing+1, 1_000_000_000+now) so it stays
    visually distinct from real ingestion sequences during teardown audits."""
    row = conn.execute("SELECT MAX(event_id) FROM event_log").fetchone()
    head = (row[0] or 0) if row else 0
    return max(head + 1, 1_000_000_000 + int(time.time()))


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    event_type: str,
    chain_id: str,
    payload: dict,
    projection_status: str = "applied",
    error_message: Optional[str] = None,
) -> None:
    """Insert one synthetic event_log row. Standalone (does not import
    from daemon/) so production surface stays independent of this fixture."""
    payload_json = json.dumps(payload, separators=(",", ":"))
    conn.execute(
        """
        INSERT INTO event_log
            (event_id, event_type, chain_id, payload_json, projection_status, error_message, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, event_type, chain_id, payload_json, projection_status, error_message, int(time.time())),
    )
    conn.commit()


def _delete_event(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM event_log WHERE event_id = ?", (event_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Builders — one per drift class
# ---------------------------------------------------------------------------

def _build_missing_native(workspace_dir: Path, slug: str) -> dict:
    """Plan task with chain_id but no matching native task file."""
    proj_dir = _project_dir(workspace_dir, slug)
    plan_path = proj_dir / "process-plan.json"
    chain_id = f"{slug}.build"
    plan = _build_plan(slug, [
        _make_plan_task(
            task_id="t-missing",
            title="Implement missing-native fixture target",
            phase="build",
            chain_id=chain_id,
        ),
    ])
    _write_json(plan_path, plan)
    return {
        "ok": True,
        "drift_class": "missing_native",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "process_plan_path": str(plan_path),
        "missing_chain_ids": [chain_id],
        "expected_drift_types": ["missing_native"],
        "expected_drift_count": 1,
        "created_paths": [str(plan_path)],
        "created_event_ids": [],
        "daemon_db_path": None,
    }


def _build_stale_status(workspace_dir: Path, slug: str) -> dict:
    """Plan completed via APPROVE gate but native task still in_progress."""
    proj_dir = _project_dir(workspace_dir, slug)
    plan_path = proj_dir / "process-plan.json"
    gate_path = proj_dir / "phases" / "build" / "gate-result.json"
    session = "synthetic-session-stale"
    chain_id = f"{slug}.build"

    plan = _build_plan(slug, [
        _make_plan_task(
            task_id="t-stale",
            title="Build the thing for stale-status fixture",
            phase="build",
            chain_id=chain_id,
        ),
    ])
    _write_json(plan_path, plan)
    _write_json(gate_path, {"verdict": "APPROVE", "min_score": 0.7, "score": 0.85})

    native_task = _make_native_task(
        task_id="native-stale",
        subject="Build the thing for stale-status fixture",
        status="in_progress",
        chain_id=chain_id,
        phase="build",
    )
    native_path = _sessions_dir(workspace_dir) / session / f"{native_task['id']}.json"
    _write_json(native_path, native_task)

    return {
        "ok": True,
        "drift_class": "stale_status",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "process_plan_path": str(plan_path),
        "gate_result_path": str(gate_path),
        "native_task_path": str(native_path),
        "expected_drift_types": ["stale_status"],
        "expected_drift_count": 1,
        "created_paths": [str(plan_path), str(gate_path), str(native_path)],
        "created_event_ids": [],
        "daemon_db_path": None,
    }


def _build_orphan_native(workspace_dir: Path, slug: str) -> dict:
    """Native task with chain_id whose project slug has no process-plan.

    The orphan slug deliberately does NOT match ``slug`` — the orphan
    project is named ``ghost-<slug>`` so the registry sees ``slug`` (the
    fixture project dir does get created) but never sees ``ghost-<slug>``.
    The reconciler reports the ghost as orphan_native against the ``slug``
    reconcile pass when invoked through reconcile_all.
    """
    ghost_slug = f"ghost-{slug}"
    # Create a "real" project dir for the slug so reconcile_all can scan it.
    # The fixture's drift comes from the orphan native task, not from this
    # placeholder plan.
    plan_path = _project_dir(workspace_dir, slug) / "process-plan.json"
    _write_json(plan_path, _build_plan(slug, []))

    session = "synthetic-session-orphan"
    chain_id = f"{ghost_slug}.root"
    native_task = _make_native_task(
        task_id="native-orphan",
        subject="Orphan native task for orphan_native fixture",
        status="in_progress",
        chain_id=chain_id,
        phase="clarify",
    )
    native_path = _sessions_dir(workspace_dir) / session / f"{native_task['id']}.json"
    _write_json(native_path, native_task)

    return {
        "ok": True,
        "drift_class": "orphan_native",
        "project_slug": slug,
        "ghost_project_slug": ghost_slug,
        "workspace_dir": str(workspace_dir),
        "process_plan_path": str(plan_path),
        "orphan_native_path": str(native_path),
        "orphan_chain_id": chain_id,
        "expected_drift_types": ["orphan_native"],
        "expected_drift_count": 1,
        "created_paths": [str(plan_path), str(native_path)],
        "created_event_ids": [],
        "daemon_db_path": None,
    }


def _build_phase_drift(workspace_dir: Path, slug: str) -> dict:
    """Phase has APPROVE gate-result but the gate-finding native task is open."""
    proj_dir = _project_dir(workspace_dir, slug)
    plan_path = proj_dir / "process-plan.json"
    gate_path = proj_dir / "phases" / "build" / "gate-result.json"
    session = "synthetic-session-phase-drift"

    # Plan task with matching chain_id so missing_native does NOT fire.
    plan_chain_id = f"{slug}.build"
    plan = _build_plan(slug, [
        _make_plan_task(
            task_id="t-phase",
            title="Phase drift fixture target",
            phase="build",
            chain_id=plan_chain_id,
        ),
    ])
    _write_json(plan_path, plan)
    _write_json(gate_path, {"verdict": "APPROVE", "min_score": 0.7, "score": 0.9})

    # Plan-task-matching native task (status completed → no stale_status drift).
    plan_match_path = _sessions_dir(workspace_dir) / session / "native-plan-match.json"
    _write_json(plan_match_path, _make_native_task(
        task_id="native-plan-match",
        subject="Phase drift fixture target",
        status="completed",
        chain_id=plan_chain_id,
        phase="build",
    ))

    # Gate-finding native task — same chain prefix, distinct discriminator
    # per the bus-chain-id uniqueness gotcha.
    gate_chain_id = f"{slug}.build.gate-finding-001"
    finding_path = _sessions_dir(workspace_dir) / session / "native-gate-finding.json"
    _write_json(finding_path, _make_native_task(
        task_id="native-gate-finding",
        subject="Gate finding for build phase",
        status="in_progress",   # open while gate verdict says APPROVE → phase_drift
        chain_id=gate_chain_id,
        phase="build",
        event_type="gate-finding",
    ))

    return {
        "ok": True,
        "drift_class": "phase_drift",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "process_plan_path": str(plan_path),
        "gate_result_path": str(gate_path),
        "native_task_paths": [str(plan_match_path), str(finding_path)],
        "expected_drift_types": ["phase_drift"],
        "expected_drift_count": 1,
        "created_paths": [
            str(plan_path), str(gate_path),
            str(plan_match_path), str(finding_path),
        ],
        "created_event_ids": [],
        "daemon_db_path": None,
    }


def _build_projection_stale(
    workspace_dir: Path,
    slug: str,
    daemon_db_path: Path,
) -> dict:
    """event_log row exists with no on-disk projection (projector lagging).

    Per staging plan section 5: insert a wicked.gate.decided event whose
    handler-target file is absent. Manifest carries event_seq + expected
    projection path so contract tests can assert the row+absence pair
    without needing the post-cutover reconciler shipped yet.
    """
    conn = _open_daemon_db(daemon_db_path)
    try:
        event_id = _next_event_id(conn)
        chain_id = f"{slug}.design.gate-decided-{event_id}"
        payload = {
            "project_id": slug,
            "phase": "design",
            "verdict": "APPROVE",
            "score": 0.82,
            "min_score": 0.7,
            "synthetic": True,
            "_synthetic_drift_class": "projection-stale",
        }
        _insert_event(
            conn,
            event_id=event_id,
            event_type="wicked.gate.decided",
            chain_id=chain_id,
            payload=payload,
            projection_status="pending",  # mirrors a projector that hasn't applied yet
        )
    finally:
        conn.close()

    expected_projection = (
        _project_dir(workspace_dir, slug) / "phases" / "design" / "gate-result.json"
    )
    # Do NOT write the projection — the absence is the drift signal.
    return {
        "ok": True,
        "drift_class": "projection-stale",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "expected_projection_path": str(expected_projection),
        "event_seq": event_id,
        "event_chain_id": chain_id,
        "event_type": "wicked.gate.decided",
        "expected_drift_types": ["projection-stale"],
        "expected_drift_count": 1,
        "created_paths": [],
        "created_event_ids": [event_id],
        "daemon_db_path": str(daemon_db_path),
        "_post_cutover_only": True,
    }


def _build_event_without_projection(
    workspace_dir: Path,
    slug: str,
    daemon_db_path: Path,
) -> dict:
    """event_log row exists, no on-disk artifact at the expected projection path.

    Section 5: caused by missing handler, handler ran-and-silently-failed,
    or wrong target path. Insert event with projection_status=error;
    manifest names the absent expected file.
    """
    conn = _open_daemon_db(daemon_db_path)
    try:
        event_id = _next_event_id(conn)
        chain_id = f"{slug}.review.consensus-report-created-{event_id}"
        payload = {
            "project_id": slug,
            "phase": "review",
            "report_path": "phases/review/consensus-report.json",
            "synthetic": True,
            "_synthetic_drift_class": "event-without-projection",
        }
        _insert_event(
            conn,
            event_id=event_id,
            event_type="wicked.consensus.report_created",
            chain_id=chain_id,
            payload=payload,
            projection_status="error",
            error_message="synthetic: handler did not materialise projection",
        )
    finally:
        conn.close()

    expected_projection = (
        _project_dir(workspace_dir, slug) / "phases" / "review" / "consensus-report.json"
    )
    # Explicitly do NOT create the file.
    return {
        "ok": True,
        "drift_class": "event-without-projection",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "expected_projection_path": str(expected_projection),
        "event_seq": event_id,
        "event_chain_id": chain_id,
        "event_type": "wicked.consensus.report_created",
        "expected_drift_types": ["event-without-projection"],
        "expected_drift_count": 1,
        "created_paths": [],
        "created_event_ids": [event_id],
        "daemon_db_path": str(daemon_db_path),
        "_post_cutover_only": True,
    }


def _build_projection_without_event(
    workspace_dir: Path,
    slug: str,
    daemon_db_path: Path,
) -> dict:
    """File on disk with no corresponding event in event_log.

    Section 5: post-cutover analogue of orphan_native (GC'd events whose
    projections survived, or a direct write that bypassed the bus). Write
    artifact, emit nothing. We open the DB only to record head_seq at
    build time so the manifest can scope "no event" precisely.
    """
    # We open the DB just to confirm reachability — no inserts are made.
    conn = _open_daemon_db(daemon_db_path)
    try:
        # Grab the head so the manifest can record what "no event" means
        # at fixture-build time (helps the post-cutover reconciler scope).
        row = conn.execute("SELECT MAX(event_id) FROM event_log").fetchone()
        head_seq = (row[0] or 0) if row else 0
    finally:
        conn.close()

    proj_dir = _project_dir(workspace_dir, slug)
    orphan_projection = proj_dir / "phases" / "build" / "gate-result.json"
    _write_json(orphan_projection, {
        "verdict": "APPROVE",
        "min_score": 0.7,
        "score": 0.88,
        "_synthetic_drift_class": "projection-without-event",
    })

    return {
        "ok": True,
        "drift_class": "projection-without-event",
        "project_slug": slug,
        "workspace_dir": str(workspace_dir),
        "orphan_projection_path": str(orphan_projection),
        "event_log_head_at_build": head_seq,
        "expected_drift_types": ["projection-without-event"],
        "expected_drift_count": 1,
        "created_paths": [str(orphan_projection)],
        "created_event_ids": [],
        "daemon_db_path": str(daemon_db_path),
        "_post_cutover_only": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_drift_fixture(
    drift_class: str,
    *,
    project_slug: str,
    workspace_dir: Path,
    daemon_db_path: Optional[Path] = None,
) -> dict:
    """Build a synthetic project state that exactly reproduces ``drift_class``.

    Returns a manifest dict.  On success the manifest carries ``ok: True``
    plus paths + expected detector output.  On failure it carries
    ``ok: False`` and a ``reason`` string.  Never raises on bad input.

    See ``SUPPORTED_DRIFT_CLASSES`` for valid ``drift_class`` values.
    """
    if drift_class not in SUPPORTED_DRIFT_CLASSES:
        return {
            "ok": False,
            "reason": REASON_UNSUPPORTED_CLASS,
            "drift_class": drift_class,
            "supported": list(SUPPORTED_DRIFT_CLASSES),
        }

    if not project_slug or not isinstance(project_slug, str):
        return {"ok": False, "reason": REASON_BAD_INPUT, "detail": "project_slug must be a non-empty string"}

    workspace_dir = Path(workspace_dir)
    if not workspace_dir.is_dir():
        return {"ok": False, "reason": REASON_BAD_INPUT, "detail": f"workspace_dir does not exist: {workspace_dir}"}

    # Pre-cutover classes never need the daemon DB.
    if drift_class == "missing_native":
        return _build_missing_native(workspace_dir, project_slug)
    if drift_class == "stale_status":
        return _build_stale_status(workspace_dir, project_slug)
    if drift_class == "orphan_native":
        return _build_orphan_native(workspace_dir, project_slug)
    if drift_class == "phase_drift":
        return _build_phase_drift(workspace_dir, project_slug)

    # Post-cutover classes — require daemon DB reachable.
    db_path = _daemon_db_path(daemon_db_path)
    if db_path is None:
        return {
            "ok": False,
            "reason": REASON_DAEMON_UNAVAILABLE,
            "drift_class": drift_class,
            "detail": (
                "projector DB not reachable. Set WG_DAEMON_DB or pass "
                "daemon_db_path to build the post-cutover fixtures."
            ),
        }

    if drift_class == "projection-stale":
        return _build_projection_stale(workspace_dir, project_slug, db_path)
    if drift_class == "event-without-projection":
        return _build_event_without_projection(workspace_dir, project_slug, db_path)
    if drift_class == "projection-without-event":
        return _build_projection_without_event(workspace_dir, project_slug, db_path)

    # Defensive — should never reach here because of the SUPPORTED guard.
    return {"ok": False, "reason": REASON_UNSUPPORTED_CLASS, "drift_class": drift_class}


def teardown_drift_fixture(manifest: dict) -> None:
    """Remove every artifact ``build_drift_fixture`` created.

    Idempotent — calling teardown twice on the same manifest is a no-op.
    Silently skips paths that were already removed.  Fail-open: a failure
    deleting one artifact does not stop the next.

    For daemon-db-bearing fixtures, also deletes the synthetic event_log
    rows by event_id.
    """
    if not isinstance(manifest, dict):
        return
    if not manifest.get("ok"):
        # Failed builds have nothing to clean up.
        return

    # Delete on-disk artifacts.
    for raw_path in manifest.get("created_paths") or []:
        try:
            p = Path(raw_path)
            if p.is_file():
                p.unlink()
        except OSError:
            pass

    # For projects we created under workspace_dir/wicked-crew/projects/{slug},
    # also remove the now-empty project tree so reconcile_all stops listing it.
    slug = manifest.get("project_slug")
    workspace = manifest.get("workspace_dir")
    if slug and workspace:
        proj_dir = _project_dir(Path(workspace), slug)
        if proj_dir.is_dir():
            shutil.rmtree(proj_dir, ignore_errors=True)
    ghost_slug = manifest.get("ghost_project_slug")
    if ghost_slug and workspace:
        ghost_dir = _project_dir(Path(workspace), ghost_slug)
        if ghost_dir.is_dir():
            shutil.rmtree(ghost_dir, ignore_errors=True)

    # Wipe the synthetic native sessions root entries we touched.  We only
    # remove session dirs whose names start with ``synthetic-session-`` so a
    # real session under the same workspace stays untouched.
    if workspace:
        sessions = _sessions_dir(Path(workspace))
        if sessions.is_dir():
            for entry in sessions.iterdir():
                if entry.is_dir() and entry.name.startswith("synthetic-session-"):
                    shutil.rmtree(entry, ignore_errors=True)

    # Delete daemon-DB synthetic event_log rows.
    db_raw = manifest.get("daemon_db_path")
    event_ids = manifest.get("created_event_ids") or []
    if db_raw and event_ids:
        db_path = Path(db_raw)
        if db_path.is_file():
            try:
                conn = _open_daemon_db(db_path)
                try:
                    for eid in event_ids:
                        _delete_event(conn, int(eid))
                finally:
                    conn.close()
            except sqlite3.Error:
                # Fail-open: a daemon that's gone away can't have its rows deleted.
                pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Synthetic drift fixture builder for the bus-cutover staging "
            "plan (#746). Creates and tears down deterministic fixtures "
            "for every drift class the reconciler knows about."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List supported drift classes.")  # noqa: F841

    p_build = sub.add_parser("build", help="Build a fixture for one drift class.")
    p_build.add_argument("--class", dest="drift_class", required=True,
                         help=f"One of: {', '.join(SUPPORTED_DRIFT_CLASSES)}")
    p_build.add_argument("--workspace", required=True,
                         help="Workspace dir (typically a tempdir).")
    p_build.add_argument("--slug", default="synthetic-drift-project",
                         help="Project slug to use for the fixture.")
    p_build.add_argument("--daemon-db", default=None,
                         help="Optional projector DB path override.")
    p_build.add_argument("--manifest-out", default=None,
                         help="Write manifest JSON to this path (default: stdout).")

    p_tear = sub.add_parser("teardown", help="Tear down a fixture by manifest path.")
    p_tear.add_argument("--manifest", required=True,
                        help="Path to the manifest JSON written by ``build``.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "list":
        sys.stdout.write(json.dumps({
            "supported": list(SUPPORTED_DRIFT_CLASSES),
            "post_cutover_classes": sorted(_DAEMON_DB_BEARING),
        }, indent=2) + "\n")
        return 0

    if args.cmd == "build":
        workspace = Path(args.workspace)
        if not workspace.is_dir():
            sys.stderr.write(f"workspace does not exist: {workspace}\n")
            return 2
        daemon_db = Path(args.daemon_db) if args.daemon_db else None
        manifest = build_drift_fixture(
            args.drift_class,
            project_slug=args.slug,
            workspace_dir=workspace,
            daemon_db_path=daemon_db,
        )
        out_text = json.dumps(manifest, indent=2)
        if args.manifest_out:
            Path(args.manifest_out).write_text(out_text + "\n", encoding="utf-8")
        else:
            sys.stdout.write(out_text + "\n")
        # Exit 0 even when ok=False — tests interpret the manifest payload.
        return 0

    if args.cmd == "teardown":
        manifest_path = Path(args.manifest)
        if not manifest_path.is_file():
            sys.stderr.write(f"manifest not found: {manifest_path}\n")
            return 2
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"could not read manifest: {exc}\n")
            return 2
        teardown_drift_fixture(manifest)
        sys.stdout.write(json.dumps({"ok": True, "torn_down": manifest.get("drift_class")}, indent=2) + "\n")
        return 0

    sys.stderr.write(f"unknown command: {args.cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
