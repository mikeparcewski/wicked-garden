"""phase_state_migration.py — standalone CLI for the v8-PR-3 (#590) migration.

Maps legacy ``completed`` phase rows in the daemon SQLite DB to canonical
states:
  - gate_score IS NOT NULL or gate_verdict IS NOT NULL → ``approved``
    (AC-linked evidence present from a prior gate decision)
  - otherwise → ``skipped``
    (no gate evidence; treat as a no-gate-required skip)

This script is idempotent: re-running after the first successful run is a
no-op because the ``_migrations`` table guards against double-application.

The same migration logic also runs automatically on every ``init_schema``
call (daemon startup), so running this script manually is only needed to
pre-migrate an existing DB before upgrading to v8.

Usage
-----
    python3 scripts/crew/phase_state_migration.py
    python3 scripts/crew/phase_state_migration.py --db /path/to/projections.db
    python3 scripts/crew/phase_state_migration.py --dry-run

Exit codes
----------
    0  migration applied (or was already applied)
    1  unexpected error

Provenance: #590, #588 (v8 thesis 3)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: allow running this script directly without installing the package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAEMON_DIR = _REPO_ROOT / "daemon"
for _p in (str(_REPO_ROOT), str(_DAEMON_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _count_completed(conn: "sqlite3.Connection") -> int:  # type: ignore[name-defined]
    """Return the number of phase rows currently in ``completed`` state."""
    row = conn.execute(
        "SELECT COUNT(*) FROM phases WHERE state = 'completed'"
    ).fetchone()
    return int(row[0]) if row else 0


def _preview_completed(conn: "sqlite3.Connection") -> list[dict]:  # type: ignore[name-defined]
    """Return all ``completed`` rows with the new state they would be migrated to."""
    rows = conn.execute(
        "SELECT project_id, phase, gate_score, gate_verdict "
        "FROM phases WHERE state = 'completed'"
    ).fetchall()
    results = []
    for row in rows:
        # row: (project_id=0, phase=1, gate_score=2, gate_verdict=3)
        has_evidence = (row[2] is not None) or (row[3] is not None)
        results.append({
            "project_id": row[0],
            "phase": row[1],
            "gate_score": row[2],
            "gate_verdict": row[3],
            "would_migrate_to": "approved" if has_evidence else "skipped",
        })
    return results


def _is_already_applied(conn: "sqlite3.Connection") -> bool:  # type: ignore[name-defined]
    """Return True if the migration has already been recorded in _migrations."""
    try:
        row = conn.execute(
            "SELECT name FROM _migrations WHERE name = 'phase_state_completed_to_canonical'"
        ).fetchone()
        return row is not None
    except Exception:  # _migrations table may not exist on very old DBs
        return False


def run_migration(conn: "sqlite3.Connection", dry_run: bool = False) -> dict:  # type: ignore[name-defined]
    """Execute (or preview) the completed-state migration.

    Parameters
    ----------
    conn:
        Open SQLite connection with the daemon schema.
    dry_run:
        If True, compute what would be migrated but make no changes.

    Returns
    -------
    dict
        ``{applied: bool, already_applied: bool, rows_approved: int,
           rows_skipped: int, dry_run: bool}``
    """
    already = _is_already_applied(conn)
    if already and not dry_run:
        return {"applied": False, "already_applied": True,
                "rows_approved": 0, "rows_skipped": 0, "dry_run": dry_run}

    preview = _preview_completed(conn)
    rows_approved = sum(1 for r in preview if r["would_migrate_to"] == "approved")
    rows_skipped = sum(1 for r in preview if r["would_migrate_to"] == "skipped")

    if dry_run:
        return {"applied": False, "already_applied": already,
                "rows_approved": rows_approved, "rows_skipped": rows_skipped,
                "rows": preview, "dry_run": True}

    if not preview:
        # No rows to migrate — record the migration as applied and return.
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, ?)",
            ("phase_state_completed_to_canonical", int(time.time())),
        )
        conn.commit()
        return {"applied": True, "already_applied": False,
                "rows_approved": 0, "rows_skipped": 0, "dry_run": False}

    now = int(time.time())
    for row in preview:
        conn.execute(
            "UPDATE phases SET state = ?, updated_at = ? "
            "WHERE project_id = ? AND phase = ? AND state = 'completed'",
            (row["would_migrate_to"], now, row["project_id"], row["phase"]),
        )
    conn.execute(
        "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, ?)",
        ("phase_state_completed_to_canonical", now),
    )
    conn.commit()
    return {"applied": True, "already_applied": False,
            "rows_approved": rows_approved, "rows_skipped": rows_skipped,
            "dry_run": False}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy 'completed' phase rows to canonical states."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to projections.db.  Defaults to WG_DAEMON_DB env or ~/.something-wicked/...",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing anything.",
    )
    args = parser.parse_args(argv)

    try:
        from daemon.db import connect, init_schema  # type: ignore[import]
    except ImportError as exc:
        print(f"ERROR: cannot import daemon.db — {exc}", file=sys.stderr)
        print("Run this script from the repository root.", file=sys.stderr)
        return 1

    try:
        conn = connect(args.db)
        # init_schema creates _migrations table if it doesn't exist yet.
        init_schema(conn)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot open/init DB — {exc}", file=sys.stderr)
        return 1

    try:
        result = run_migration(conn, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: migration failed — {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if result.get("already_applied"):
        print("Migration 'phase_state_completed_to_canonical' already applied — no-op.")
        return 0

    if args.dry_run:
        print(f"DRY RUN — no changes written.")
        print(f"  Rows that would be migrated to 'approved': {result['rows_approved']}")
        print(f"  Rows that would be migrated to 'skipped':  {result['rows_skipped']}")
        if result.get("rows"):
            print("\n  Detail:")
            for r in result["rows"]:
                print(f"    {r['project_id']}/{r['phase']}: "
                      f"completed → {r['would_migrate_to']} "
                      f"(gate_score={r['gate_score']!r}, gate_verdict={r['gate_verdict']!r})")
        return 0

    print("Migration 'phase_state_completed_to_canonical' applied.")
    print(f"  Rows migrated to 'approved': {result['rows_approved']}")
    print(f"  Rows migrated to 'skipped':  {result['rows_skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
