#!/usr/bin/env python3
"""Post-cutover reconciler — projection-vs-event drift detector.

Ships alongside ``scripts/crew/reconcile.py`` (v1) during the bus-cutover
window (#746).  v1 is deprecated when Site 5 lands and removed in release N+5.

See ``docs/v9/adr-reconcile-v2.md`` and ``docs/v9/bus-cutover-staging-plan.md``
§5 for the design contract this module implements.

Background
----------
After the bus cutover, ``wicked.gate.decided`` and companion events become the
source of truth.  On-disk artifacts (gate-result.json, dispatcher-report.md,
reviewer-report.md, etc.) are *projections* of those events, materialised by
the wicked-garden-daemon projector.  The drift question shifts from:

  "do the two task stores agree?" (reconcile.py / v1)

to:

  "does every event have its projection, and does every projection trace to
   an event?" (this module / v2)

Drift classes (§5 of the staging plan)
---------------------------------------
  projection-stale           — event ingested; projection not yet materialised
                                (projector lagging, crashed, or slow handler)
  event-without-projection   — event in event_log but no matching file on disk
                                (handler missing, raised, or targeted wrong path)
  projection-without-event   — file on disk but no event_log row corresponds
                                (direct-write bypassing the bus, or GC'd event
                                 whose projection file survived)

Hard constraints (mirror v1)
----------------------------
  - Stdlib only.
  - READ ONLY — never write to either store.
  - Fail-open — projector DB unavailable → return empty list, never raise.
  - Honor WG_DAEMON_DB env var for DB path resolution (same as synthetic_drift.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Drift type labels — module-level constants so test suites and downstream
# consumers reference them without string typos.
# ---------------------------------------------------------------------------

DRIFT_PROJECTION_STALE: str = "projection-stale"
DRIFT_EVENT_WITHOUT_PROJECTION: str = "event-without-projection"
DRIFT_PROJECTION_WITHOUT_EVENT: str = "projection-without-event"

# ---------------------------------------------------------------------------
# Event types the projector is expected to materialise as on-disk artifacts.
# Maps event_type → (relative_projection_path_template, uses_phase_from_chain).
#
# For per-project + per-phase artifacts the template uses {slug} + {phase}.
# These are the primary bus-truth artifacts after cutover Site 3.
# ---------------------------------------------------------------------------

_PROJECTION_MAP: Dict[str, str] = {
    # Phase gate decisions
    "wicked.gate.decided": "phases/{phase}/gate-result.json",
    "wicked.gate.blocked": "phases/{phase}/gate-result.json",
    # Dispatch log entries (Site 1)
    "wicked.dispatch.log_entry_appended": "phases/{phase}/dispatch-log.jsonl",
    # Consensus artifacts (Site 2)
    "wicked.consensus.report_created": "phases/{phase}/consensus-report.json",
    "wicked.consensus.evidence_recorded": "phases/{phase}/consensus-evidence.json",
    # Reviewer report (Site 3 — this PR).
    # Both gate_completed (approved/rejected path) and gate_pending (deferred
    # verdict path) materialise the same reviewer-report.md file.  The drift
    # detector supports N event-types → 1 file; both entries are legal because
    # _collect_projection_files returns each path once, and
    # _detect_projection_without_event builds a set of resolved paths from
    # ALL known events — so a file covered by either event is not flagged.
    "wicked.consensus.gate_completed": "phases/{phase}/reviewer-report.md",
    "wicked.consensus.gate_pending": "phases/{phase}/reviewer-report.md",
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _projects_root() -> Path:
    """Return WG_LOCAL_ROOT/wicked-crew/projects — read-only, no mkdir."""
    base = (
        os.environ.get("WG_LOCAL_ROOT")
        or str(Path.home() / ".something-wicked" / "wicked-garden" / "local")
    )
    return Path(base) / "wicked-crew" / "projects"


def _daemon_db_path() -> Optional[Path]:
    """Resolve projector DB path.

    Priority:
      1. WG_DAEMON_DB env var
      2. default at ~/.something-wicked/wicked-garden-daemon/projections.db

    Returns None when the DB does not exist or lacks the event_log table.
    Caller treats None as "projector unavailable" and returns an empty list.
    """
    env = os.environ.get("WG_DAEMON_DB")
    if env:
        candidate = Path(env)
    else:
        candidate = (
            Path.home()
            / ".something-wicked"
            / "wicked-garden-daemon"
            / "projections.db"
        )

    if not candidate.is_file():
        return None

    # Verify event_log table exists — half-formed DBs must not pass.
    try:
        conn = sqlite3.connect(str(candidate))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_log'"
            ).fetchone()
            return candidate if row is not None else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _validate_explicit_db_path(candidate: Path) -> Optional[Path]:
    """Validate an explicitly-supplied DB path before opening it.

    Mirrors ``_daemon_db_path()``'s validation: checks file existence AND
    verifies the ``event_log`` table exists.  A wrong SQLite file (e.g. an
    empty DB or a different schema) must return None so the caller falls back
    to the documented empty-list "DB unavailable" result rather than silently
    reading the wrong data and faking drift.

    Returns the Path when valid, None otherwise.
    """
    if not candidate.is_file():
        return None

    try:
        conn = sqlite3.connect(str(candidate))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_log'"
            ).fetchone()
            return candidate if row is not None else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _open_db(path: Path) -> sqlite3.Connection:
    """Open projector DB read-only (best effort), WAL mode, no mutations."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Event-log readers
# ---------------------------------------------------------------------------

def _phase_from_chain_id(chain_id: Optional[str]) -> Optional[str]:
    """Extract the phase segment from a chain_id.

    chain_id format: ``{slug}.{phase}(.{gate})?``
    The phase is the second dot-separated segment.
    Returns None when the chain_id is absent, too short, or malformed.
    """
    if not isinstance(chain_id, str) or not chain_id:
        return None
    parts = chain_id.split(".", 2)
    if len(parts) < 2:
        return None
    phase = parts[1]
    # Reserved non-phase tokens that reconcile.py uses at the root level.
    if phase in ("root", ""):
        return None
    return phase


def _project_slug_from_chain_id(chain_id: Optional[str]) -> Optional[str]:
    """Extract the project slug (first dot-segment) from a chain_id."""
    if not isinstance(chain_id, str) or not chain_id:
        return None
    return chain_id.split(".", 1)[0] or None


def _query_events_for_project(
    conn: sqlite3.Connection, project_slug: str
) -> List[Dict[str, Any]]:
    """Return event_log rows whose chain_id starts with ``{project_slug}.``.

    Rows are ordered by event_id ascending.  We fetch only the columns
    reconcile_v2 needs to avoid surprises when the daemon schema evolves.
    """
    # LIKE escape: project_slug may contain underscores which LIKE treats
    # as single-char wildcards.  Use ESCAPE clause to be safe.
    escaped = project_slug.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        rows = conn.execute(
            """
            SELECT event_id, event_type, chain_id, projection_status, error_message, ingested_at
            FROM   event_log
            WHERE  chain_id LIKE ? ESCAPE '\\'
            ORDER  BY event_id ASC
            """,
            (f"{escaped}.%",),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _event_log_head(conn: sqlite3.Connection) -> int:
    """Return the current MAX(event_id) in the event_log (0 when empty)."""
    try:
        row = conn.execute("SELECT MAX(event_id) FROM event_log").fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return 0


def _event_log_total(conn: sqlite3.Connection) -> int:
    """Return the total count of rows in event_log."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return 0


# ---------------------------------------------------------------------------
# Projection-file discovery
# ---------------------------------------------------------------------------

def _list_known_project_slugs() -> List[str]:
    """List every project directory under the projects root."""
    root = _projects_root()
    if not root.is_dir():
        return []
    try:
        return sorted(
            e.name
            for e in root.iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )
    except OSError:
        return []


def _materialize_projection_path(
    project_dir: Path, event_type: str, chain_id: Optional[str]
) -> Optional[Path]:
    """Return the expected on-disk path for an event type + chain_id pair.

    Returns None when the event type is not in _PROJECTION_MAP or the
    chain_id does not carry enough information to resolve the path.
    """
    template = _PROJECTION_MAP.get(event_type)
    if template is None:
        return None

    phase = _phase_from_chain_id(chain_id)
    if phase is None:
        return None

    rel = template.replace("{phase}", phase)
    return project_dir / rel


def _collect_projection_files(project_dir: Path) -> List[Path]:
    """Walk phases/ and return every file that could be a bus projection.

    Includes the known artifact filenames across all phases.  This is
    the exhaustive set for projection-without-event detection.

    ``conditions-manifest.json`` is intentionally excluded during the
    pre-Site-5 coexistence window.  Site 5 has not yet cut over, so no
    event in _PROJECTION_MAP maps to that file.  Including it here would
    fire a false ``projection-without-event`` finding for every existing
    CONDITIONAL phase.  Re-add it (and the matching _PROJECTION_MAP entry)
    when Site 5 ships — see docs/v9/bus-cutover-staging-plan.md §Site-5.
    """
    projection_names = {
        "gate-result.json",
        "dispatch-log.jsonl",
        "consensus-report.json",
        "consensus-evidence.json",
        "reviewer-report.md",
        # NOTE: "conditions-manifest.json" deliberately omitted — Site 5 not yet cut over.
    }
    phases_dir = project_dir / "phases"
    if not phases_dir.is_dir():
        return []
    out: List[Path] = []
    try:
        for phase_dir in sorted(phases_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            for name in projection_names:
                candidate = phase_dir / name
                if candidate.is_file():
                    out.append(candidate)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def _detect_projection_stale(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Events in projection_status='pending' with no materialised file.

    'pending' means the projector ingested the event but has not yet
    written the projection file (lagging or slow handler).
    """
    drift: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("projection_status") != "pending":
            continue
        proj_path = _materialize_projection_path(
            project_dir, ev["event_type"], ev.get("chain_id")
        )
        if proj_path is None:
            continue
        if not proj_path.exists():
            drift.append({
                "type": DRIFT_PROJECTION_STALE,
                "projection": str(proj_path.relative_to(project_dir)),
                "event_seq": ev["event_id"],
                "event_type": ev["event_type"],
                "chain_id": ev.get("chain_id"),
                "reason": (
                    f"event_seq {ev['event_id']} ({ev['event_type']!r}) "
                    f"is pending but projection has not been materialised"
                ),
            })
    return drift


def _detect_event_without_projection(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Events with no matching file on disk (handler missing/raised/wrong path).

    Covers both projection_status='error' (explicit handler failure) and
    projection_status='applied' where the file is unexpectedly absent
    (handler wrote elsewhere, or file was deleted post-projection).
    """
    drift: List[Dict[str, Any]] = []
    for ev in events:
        # Only check events we can map to a projection path.
        proj_path = _materialize_projection_path(
            project_dir, ev["event_type"], ev.get("chain_id")
        )
        if proj_path is None:
            continue
        # Projection absent on disk → drift regardless of projection_status.
        if not proj_path.exists():
            # Skip pending events — those are covered by projection_stale.
            if ev.get("projection_status") == "pending":
                continue
            drift.append({
                "type": DRIFT_EVENT_WITHOUT_PROJECTION,
                "event_seq": ev["event_id"],
                "event_type": ev["event_type"],
                "chain_id": ev.get("chain_id"),
                "expected_projection": str(proj_path.relative_to(project_dir)),
                "projection_status": ev.get("projection_status"),
                "error_message": ev.get("error_message"),
                "reason": (
                    f"event_seq {ev['event_id']} ({ev['event_type']!r}) "
                    f"has no materialised projection at "
                    f"{proj_path.relative_to(project_dir)}"
                ),
            })
    return drift


def _detect_projection_without_event(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Projection files on disk with no corresponding event_log row.

    Post-cutover analogue of reconcile.py's orphan_native: the projection
    exists but the bus event that should have produced it is absent (GC'd,
    direct-write bypassing the bus, or lint was off).
    """
    # Build a set of expected-projection paths from the known events so we
    # can quickly test each on-disk file against it.
    event_projection_paths: set = set()
    for ev in events:
        p = _materialize_projection_path(
            project_dir, ev["event_type"], ev.get("chain_id")
        )
        if p is not None:
            event_projection_paths.add(p.resolve())

    drift: List[Dict[str, Any]] = []
    for proj_path in _collect_projection_files(project_dir):
        if proj_path.resolve() not in event_projection_paths:
            drift.append({
                "type": DRIFT_PROJECTION_WITHOUT_EVENT,
                "projection": str(proj_path.relative_to(project_dir)),
                "reason": (
                    f"projection {proj_path.relative_to(project_dir)} "
                    f"has no corresponding event_log row (direct-write or GC'd event)"
                ),
            })
    return drift


# ---------------------------------------------------------------------------
# Projections materialised inventory
# ---------------------------------------------------------------------------

def _build_projections_materialised(project_dir: Path) -> Dict[str, Any]:
    """Inventory what projections currently exist on disk for a project."""
    phases_dir = project_dir / "phases"
    gate_result_phases: List[str] = []
    dispatch_log_phases: List[str] = []
    conditions_manifest_phases: List[str] = []
    reviewer_report_phases: List[str] = []
    consensus_report_phases: List[str] = []
    consensus_evidence_phases: List[str] = []

    process_plan = project_dir / "process-plan.json"

    if phases_dir.is_dir():
        try:
            for phase_dir in sorted(phases_dir.iterdir()):
                if not phase_dir.is_dir():
                    continue
                name = phase_dir.name
                if (phase_dir / "gate-result.json").is_file():
                    gate_result_phases.append(name)
                if (phase_dir / "dispatch-log.jsonl").is_file():
                    dispatch_log_phases.append(name)
                if (phase_dir / "conditions-manifest.json").is_file():
                    conditions_manifest_phases.append(name)
                if (phase_dir / "reviewer-report.md").is_file():
                    reviewer_report_phases.append(name)
                if (phase_dir / "consensus-report.json").is_file():
                    consensus_report_phases.append(name)
                if (phase_dir / "consensus-evidence.json").is_file():
                    consensus_evidence_phases.append(name)
        except OSError:
            pass

    return {
        "process_plan_json": str(process_plan) if process_plan.is_file() else None,
        "gate_result_files": gate_result_phases,
        "dispatch_log_files": dispatch_log_phases,
        "conditions_manifest_files": conditions_manifest_phases,
        "reviewer_report_files": reviewer_report_phases,
        "consensus_report_files": consensus_report_phases,
        "consensus_evidence_files": consensus_evidence_phases,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconcile_project(
    project_slug: str,
    *,
    conn: Optional["sqlite3.Connection"] = None,
    _daemon_conn: Optional["sqlite3.Connection"] = None,  # alias for internal use
    daemon_db_path: "Path | str | None" = None,
) -> Dict[str, Any]:
    """Run the post-cutover drift check for a single project.

    Args:
        project_slug: The project directory name (slug).
        conn: Optional pre-opened SQLite connection (for test injection).
              When None, opens and closes the DB internally.
        daemon_db_path: Optional path override for the projector DB.
              Honoured in single-project mode (mirrors ``reconcile_all``).
              When None, resolves via WG_DAEMON_DB env var or the default path.

    Returns a per-project result dict per the staging plan §5 schema.
    Errors are reported inside the result, not raised.
    """
    # Support both `conn` and `_daemon_conn` for backward compat with
    # internal callers that share a single connection across projects.
    effective_conn = conn or _daemon_conn

    project_dir = _projects_root() / project_slug
    errors: List[str] = []
    events: List[Dict[str, Any]] = []

    # Attempt to query the event log.
    owns_conn = False
    db_conn: Optional[sqlite3.Connection] = effective_conn
    if db_conn is None:
        # Resolve DB path: explicit override → env var / default path.
        if daemon_db_path is not None:
            resolved_path: Optional[Path] = _validate_explicit_db_path(
                Path(daemon_db_path)
            )
        else:
            resolved_path = _daemon_db_path()

        if resolved_path is not None:
            try:
                db_conn = _open_db(resolved_path)
                owns_conn = True
            except (sqlite3.Error, OSError) as exc:
                errors.append(f"could not open projector DB: {exc}")
        else:
            errors.append("projector DB unavailable (file missing or schema absent)")

    try:
        if db_conn is not None:
            events = _query_events_for_project(db_conn, project_slug)
    except sqlite3.Error as exc:
        errors.append(f"event_log query failed: {exc}")
    finally:
        if owns_conn and db_conn is not None:
            try:
                db_conn.close()
            except sqlite3.Error:
                pass

    drift: List[Dict[str, Any]] = []
    if project_dir.is_dir():
        drift.extend(_detect_projection_stale(events, project_dir))
        drift.extend(_detect_event_without_projection(events, project_dir))
        drift.extend(_detect_projection_without_event(events, project_dir))
    else:
        errors.append(f"project directory not found: {project_dir}")

    summary = {
        "total_drift_count": len(drift),
        "projection_stale_count": sum(
            1 for d in drift if d["type"] == DRIFT_PROJECTION_STALE
        ),
        "event_without_projection_count": sum(
            1 for d in drift if d["type"] == DRIFT_EVENT_WITHOUT_PROJECTION
        ),
        "projection_without_event_count": sum(
            1 for d in drift if d["type"] == DRIFT_PROJECTION_WITHOUT_EVENT
        ),
    }

    return {
        "project_slug": project_slug,
        "events_for_project": len(events),
        "projections_materialized": _build_projections_materialised(project_dir),
        "drift": drift,
        "summary": summary,
        "errors": errors,
    }


def reconcile_all(
    daemon_db_path: "Path | str | None" = None,
) -> List[Dict[str, Any]]:
    """Run the post-cutover drift check for every known project.

    Returns an empty list when the projector DB is unavailable — NEVER raises.
    Callers can distinguish "no drift found" from "DB unreachable" by checking
    whether the returned list contains entries with errors.

    Args:
        daemon_db_path: Optional path override for the projector DB.
            When None, resolves via WG_DAEMON_DB env var or the default path.

    Returns:
        List of per-project result dicts (staging plan §5 schema).
        Empty list when the projector DB is unreachable.
    """
    # Resolve DB path.
    if daemon_db_path is not None:
        resolved: Optional[Path] = Path(daemon_db_path)
        if not resolved.is_file():
            return []
    else:
        resolved = _daemon_db_path()

    if resolved is None:
        return []

    # Open one shared connection for the full scan — O(projects) rather than
    # O(projects * open_close_cost).
    try:
        shared_conn = _open_db(resolved)
    except (sqlite3.Error, OSError):
        return []

    try:
        slugs = _list_known_project_slugs()
        results: List[Dict[str, Any]] = []
        for slug in slugs:
            result = reconcile_project(slug, _daemon_conn=shared_conn)
            results.append(result)
        return results
    except Exception:  # pragma: no cover — unexpected; fail-open
        return []
    finally:
        try:
            shared_conn.close()
        except sqlite3.Error:
            pass


def _build_report_header(
    conn: Optional[sqlite3.Connection],
    command_invoked: str,
) -> Dict[str, Any]:
    """Build the §5 header block for the full report."""
    head_seq = 0
    total_seq = 0
    if conn is not None:
        try:
            head_seq = _event_log_head(conn)
            total_seq = _event_log_total(conn)
        except sqlite3.Error:
            pass

    # Simple projector health signal: if total > head, assume lagging
    # (head is the max event_id; total counts all rows including pending).
    lag = max(0, total_seq - head_seq) if total_seq > head_seq else 0
    if conn is None:
        projector_health = "unreachable"
    elif lag > 10:
        projector_health = "lagging"
    else:
        projector_health = "ok"

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "command_invoked": command_invoked,
        "event_log_head_seq": head_seq,
        "event_log_total_seq": total_seq,
        "lag_events": lag,
        "projector_health": projector_health,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_text_report(result: Dict[str, Any]) -> str:
    """Render a single project reconcile-v2 result as a human-readable report."""
    lines: List[str] = []
    slug = result.get("project_slug", "<unknown>")
    summary = result.get("summary") or {}
    lines.append(f"Reconcile-v2 report — project: {slug}")
    lines.append("=" * len(lines[-1]))
    lines.append(f"  Events for project:  {result.get('events_for_project', 0)}")
    lines.append("")
    lines.append("Drift summary (post-cutover):")
    lines.append(f"  total:                       {summary.get('total_drift_count', 0)}")
    lines.append(f"  projection-stale:             {summary.get('projection_stale_count', 0)}")
    lines.append(f"  event-without-projection:     {summary.get('event_without_projection_count', 0)}")
    lines.append(f"  projection-without-event:     {summary.get('projection_without_event_count', 0)}")

    errors = result.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Errors (fail-open — partial report shown):")
        for err in errors:
            lines.append(f"  - {err}")

    drift = result.get("drift") or []
    if drift:
        lines.append("")
        lines.append("Drift entries:")
        for entry in drift:
            kind = entry.get("type", "?")
            reason = entry.get("reason", "")
            lines.append(f"  [{kind}] {reason}")
    else:
        lines.append("")
        lines.append("No post-cutover drift detected.")

    return "\n".join(lines) + "\n"


def render_text_report_all(results: List[Dict[str, Any]]) -> str:
    """Render multiple project results, one section per project."""
    if not results:
        return "No projects found (or projector DB unavailable).\n"
    chunks: List[str] = []
    grand_total = 0
    for r in results:
        grand_total += int((r.get("summary") or {}).get("total_drift_count", 0))
        chunks.append(render_text_report(r))
    chunks.append(
        f"--- Aggregate ---\nProjects scanned: {len(results)}\n"
        f"Total drift entries: {grand_total}\n"
    )
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# CLI (mirrors v1 surface so operator muscle-memory transfers)
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Post-cutover reconciler: projection-vs-event drift detector. "
            "Reads-only — never mutates the projector DB or on-disk artifacts. "
            "v1 (reconcile.py) handles pre-cutover drift; this module handles post-cutover."
        ),
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--project",
        dest="project",
        help="Reconcile a single project slug.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Reconcile every known project.",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of the text report.",
    )
    p.add_argument(
        "--daemon-db",
        dest="daemon_db",
        help="Override projector DB path (default: WG_DAEMON_DB or ~/.something-wicked/...).",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    daemon_db_override = Path(args.daemon_db) if args.daemon_db else None

    if args.all:
        results = reconcile_all(daemon_db_path=daemon_db_override)
        if args.as_json:
            # Wire _build_report_header per staging plan §5 JSON schema.
            # Open a transient connection to read event_log head/total; if
            # the DB is unavailable reconcile_all already returned [] and we
            # emit an "unreachable" header.
            _header_conn: Optional[sqlite3.Connection] = None
            if daemon_db_override is not None:
                _resolved = _validate_explicit_db_path(daemon_db_override)
            else:
                _resolved = _daemon_db_path()
            if _resolved is not None:
                try:
                    _header_conn = _open_db(_resolved)
                except (sqlite3.Error, OSError):
                    _header_conn = None
            try:
                header = _build_report_header(
                    _header_conn,
                    command_invoked=" ".join(
                        ["reconcile_v2"] + (sys.argv[1:] if argv is None else list(argv))
                    ),
                )
            finally:
                if _header_conn is not None:
                    try:
                        _header_conn.close()
                    except sqlite3.Error:
                        pass
            payload = {"header": header, "results": results}
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        else:
            sys.stdout.write(render_text_report_all(results))
        return 0

    # Single-project mode — honour --daemon-db the same way --all does.
    result = reconcile_project(args.project, daemon_db_path=daemon_db_override)
    if args.as_json:
        # Wire _build_report_header for single-project JSON output too.
        _header_conn2: Optional[sqlite3.Connection] = None
        if daemon_db_override is not None:
            _resolved2 = _validate_explicit_db_path(daemon_db_override)
        else:
            _resolved2 = _daemon_db_path()
        if _resolved2 is not None:
            try:
                _header_conn2 = _open_db(_resolved2)
            except (sqlite3.Error, OSError):
                _header_conn2 = None
        try:
            header2 = _build_report_header(
                _header_conn2,
                command_invoked=" ".join(
                    ["reconcile_v2"] + (sys.argv[1:] if argv is None else list(argv))
                ),
            )
        finally:
            if _header_conn2 is not None:
                try:
                    _header_conn2.close()
                except sqlite3.Error:
                    pass
        payload2 = {"header": header2, "results": [result]}
        sys.stdout.write(json.dumps(payload2, indent=2) + "\n")
    else:
        sys.stdout.write(render_text_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
