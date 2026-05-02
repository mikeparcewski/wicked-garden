#!/usr/bin/env python3
"""resume_projector.py — per-project resume snapshot derived from the bus projector (#734).

The bus projector (`daemon/projector.py`) already consumes 13 event types
and writes them into a SQLite database (`daemon/db.py`). This module joins
the projector's tables into a per-project ``resume.json`` snapshot, written
atomically to ``crew/{project}/resume.json`` so a fresh session can read
"where am I" in one file lookup instead of replaying the bus.

The snapshot is a **derived projection** — never the source of truth. The
bus event log remains authoritative. ``verify`` re-derives the snapshot from
the projector and reports divergence; it deliberately refuses to silently
overwrite a snapshot that disagrees, so corruption surfaces instead of
hiding.

Stdlib-only. The hook bootstrap can import this safely.

Public API
----------
    build_snapshot(project_id, db_path=None)            -> dict
    write_snapshot(project_id, project_dir, ...)        -> Path
    read_snapshot(project_dir)                          -> dict | None
    verify_snapshot(project_id, project_dir, ...)       -> tuple[bool, str]
    snapshot_path(project_dir)                          -> Path
    SCHEMA_VERSION                                      -> str

CLI
---
    resume_projector.py replay <project_id> <project_dir>
    resume_projector.py read   <project_dir>
    resume_projector.py verify <project_id> <project_dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Snapshot file inside ``crew/{project}/``.
SNAPSHOT_FILENAME = "resume.json"

#: Snapshot schema version. Bump on incompatible field changes.
SCHEMA_VERSION = "1.0.0"

#: Pointers the snapshot exposes for each project. Paths are RELATIVE to the
#: project_dir so the snapshot is portable between machines.
_POINTER_TEMPLATES = {
    "process_plan": "process-plan.md",
    "dispatch_log": "phases/{phase}/dispatch-log.jsonl",
    "gate_result": "phases/{phase}/gate-result.json",
    "conditions_manifest": "phases/{phase}/conditions-manifest.json",
    "reeval_log": "phases/{phase}/reeval-log.jsonl",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _connect(db_path: "str | None" = None) -> "sqlite3.Connection | None":
    """Open the projector DB read-only. Return ``None`` if the DB does not exist.

    Resolution order: explicit ``db_path`` arg → ``WG_PROJECTOR_DB_PATH`` env →
    daemon default (``~/.something-wicked/wicked-garden-daemon/projections.db``).
    Read-only because resume_projector never mutates the projector tables.
    """
    resolved: str
    if db_path:
        resolved = db_path
    elif os.environ.get("WG_PROJECTOR_DB_PATH"):
        resolved = os.environ["WG_PROJECTOR_DB_PATH"]
    else:
        resolved = str(
            Path.home()
            / ".something-wicked"
            / "wicked-garden-daemon"
            / "projections.db"
        )
    if not Path(resolved).is_file():
        return None
    # Read-only URI mode keeps us honest about not mutating the projector.
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Snapshot construction
# ---------------------------------------------------------------------------

def build_snapshot(project_id: str, db_path: "str | None" = None) -> dict:
    """Return the snapshot dict for ``project_id`` derived from the projector.

    Returns a snapshot with ``project: null`` and empty lists when the project
    is not in the projector (lets callers persist a stub instead of erroring).
    Never raises on missing DB — returns the empty snapshot in that case too.
    The bus event log is the source of truth; this function is a read-only
    derivation over what the projector has already projected.
    """
    snapshot = _empty_snapshot(project_id)

    conn = _connect(db_path)
    if conn is None:
        snapshot["projector_available"] = False
        return snapshot
    snapshot["projector_available"] = True

    try:
        snapshot["project"] = _read_project(conn, project_id)
        snapshot["phases"] = _read_phases(conn, project_id)
        snapshot["gate_history"] = _read_gate_history(conn, project_id)
        snapshot["active_tasks_count"] = _read_active_tasks_count(conn, project_id)
        snapshot["last_event"] = _read_last_event(conn, project_id)
    finally:
        conn.close()

    snapshot["pointers"] = _build_pointers(snapshot)
    return snapshot


def _empty_snapshot(project_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "snapshot_taken_at": _now_iso(),
        "projector_available": False,
        "project": None,
        "phases": [],
        "gate_history": [],
        "active_tasks_count": 0,
        "last_event": None,
        "pointers": {},
    }


def _read_project(conn: sqlite3.Connection, project_id: str) -> "dict | None":
    row = conn.execute(
        """
        SELECT id, name, workspace, directory, archetype, complexity_score,
               rigor_tier, current_phase, status, chain_id,
               yolo_revoked_count, last_revoke_reason,
               created_at, updated_at
        FROM projects WHERE id = ?
        """,
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def _read_phases(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT phase, state, gate_score, gate_verdict, gate_reviewer,
               started_at, terminal_at, rework_iterations, updated_at
        FROM phases WHERE project_id = ?
        ORDER BY started_at IS NULL, started_at, phase
        """,
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _read_gate_history(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    """Read gate verdicts from event_log.

    Filters by ``chain_id LIKE '{project_id}.%'`` because the bus chain_id
    is always rooted at the project. event_log doesn't have project_id
    directly — chain_id is the projection key.
    """
    rows = conn.execute(
        """
        SELECT event_id, event_type, chain_id, payload_json, ingested_at
        FROM event_log
        WHERE event_type = 'wicked.gate.decided'
          AND chain_id LIKE ?
        ORDER BY event_id ASC
        """,
        (f"{project_id}.%",),
    ).fetchall()
    history: list[dict] = []
    for r in rows:
        try:
            payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
        except (TypeError, ValueError):
            payload = {}
        history.append({
            "event_id": r["event_id"],
            "chain_id": r["chain_id"],
            "phase": payload.get("phase"),
            "verdict": payload.get("result") or payload.get("verdict"),
            "score": payload.get("score"),
            "min_score": payload.get("min_score"),
            "reviewer": payload.get("reviewer") or payload.get("source_agent"),
            "decided_at": r["ingested_at"],
        })
    return history


def _read_active_tasks_count(conn: sqlite3.Connection, project_id: str) -> int:
    """Count tasks whose chain_id is rooted at this project and are still open."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM tasks
        WHERE chain_id LIKE ?
          AND status IN ('pending', 'in_progress')
        """,
        (f"{project_id}.%",),
    ).fetchone()
    return int(row["n"]) if row else 0


def _read_last_event(conn: sqlite3.Connection, project_id: str) -> "dict | None":
    """Latest event for this project, by event_id (event_log primary key is monotonic)."""
    row = conn.execute(
        """
        SELECT event_id, event_type, chain_id, ingested_at
        FROM event_log
        WHERE chain_id LIKE ?
        ORDER BY event_id DESC LIMIT 1
        """,
        (f"{project_id}.%",),
    ).fetchone()
    if not row:
        return None
    return {
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "chain_id": row["chain_id"],
        "ingested_at": row["ingested_at"],
    }


def _build_pointers(snapshot: dict) -> dict:
    project = snapshot.get("project") or {}
    current_phase = project.get("current_phase") or ""
    out = {}
    for key, template in _POINTER_TEMPLATES.items():
        if "{phase}" in template and not current_phase:
            continue
        out[key] = template.format(phase=current_phase) if "{phase}" in template else template
    return out


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def snapshot_path(project_dir: "str | Path") -> Path:
    """Return the canonical ``resume.json`` path for a project_dir."""
    return Path(project_dir) / SNAPSHOT_FILENAME


def read_snapshot(project_dir: "str | Path") -> "dict | None":
    """Read ``resume.json`` from disk. Return ``None`` on missing or unreadable.

    Never raises. Corrupted JSON returns ``None`` so the caller can decide
    whether to replay from the projector or surface the corruption.
    """
    path = snapshot_path(project_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def write_snapshot(
    project_id: str,
    project_dir: "str | Path",
    db_path: "str | None" = None,
) -> Path:
    """Build the snapshot for ``project_id`` and write it atomically.

    Returns the path on success. Uses ``tempfile + os.replace`` for crash
    safety — same idiom as ``conditions_manifest.py`` and ``solo_mode.py``.
    Creates the project_dir if it does not exist; never mutates the
    projector DB.
    """
    snapshot = build_snapshot(project_id, db_path=db_path)
    target = snapshot_path(project_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(
        prefix=f".{SNAPSHOT_FILENAME}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception:
        # Best-effort cleanup; never leak temps.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def verify_snapshot(
    project_id: str,
    project_dir: "str | Path",
    db_path: "str | None" = None,
) -> "tuple[bool, str]":
    """Re-derive the snapshot from the projector and compare with on-disk.

    Returns ``(True, "")`` when on-disk matches a freshly-built snapshot
    on the load-bearing fields (project state, phases, gate history,
    active task count, last event id). Returns ``(False, reason)`` on
    divergence. The ``snapshot_taken_at`` timestamp is intentionally
    excluded from the comparison.

    NEVER auto-rewrites on divergence — corruption must surface, not hide.
    Caller decides whether to overwrite via ``write_snapshot``.
    """
    on_disk = read_snapshot(project_dir)
    if on_disk is None:
        return False, "no on-disk snapshot to verify (use write_snapshot to create)"
    fresh = build_snapshot(project_id, db_path=db_path)

    diff_fields: list[str] = []
    for field in ("schema_version", "project_id", "project", "phases",
                  "gate_history", "active_tasks_count", "last_event"):
        if on_disk.get(field) != fresh.get(field):
            diff_fields.append(field)

    if not diff_fields:
        return True, ""
    return False, (
        f"snapshot diverges from projector on {len(diff_fields)} field(s): "
        f"{', '.join(diff_fields)}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_replay(args: argparse.Namespace) -> int:
    path = write_snapshot(args.project_id, args.project_dir, db_path=args.db_path)
    print(f"WROTE: {path}")
    return 0


def _cli_read(args: argparse.Namespace) -> int:
    snap = read_snapshot(args.project_dir)
    if snap is None:
        print("NO SNAPSHOT")
        return 1
    print(json.dumps(snap, indent=2, sort_keys=True))
    return 0


def _cli_verify(args: argparse.Namespace) -> int:
    ok, reason = verify_snapshot(args.project_id, args.project_dir, db_path=args.db_path)
    if ok:
        print("OK")
        return 0
    print(f"DIVERGED: {reason}")
    return 1


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-project resume snapshot over the bus projector (#734)."
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override the projector DB path (default: WG_PROJECTOR_DB_PATH "
             "or ~/.something-wicked/wicked-garden-daemon/projections.db).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_replay = sub.add_parser(
        "replay",
        help="Build and atomically write resume.json from the projector.",
    )
    p_replay.add_argument("project_id")
    p_replay.add_argument("project_dir")
    p_replay.set_defaults(func=_cli_replay)

    p_read = sub.add_parser("read", help="Print the on-disk resume.json.")
    p_read.add_argument("project_dir")
    p_read.set_defaults(func=_cli_read)

    p_verify = sub.add_parser(
        "verify",
        help="Re-derive and compare against on-disk; non-zero on divergence.",
    )
    p_verify.add_argument("project_id")
    p_verify.add_argument("project_dir")
    p_verify.set_defaults(func=_cli_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
