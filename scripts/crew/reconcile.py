#!/usr/bin/env python3
"""Reconcile diagnostic — surface drift between native TaskList + garden chain.

Walks both stores for one or more projects and reports diffs WITHOUT mutating
either side. Pure read + report.

Background
----------
Issue #579 documented drift between two stores:
  - Native TaskList: ${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json
  - Garden chain:    {project_dir}/process-plan.json + phases/{phase}/gate-result.json

The brainstorm decision (D3) selected Option C (read-only diagnostic) as the
interim shipment. Once drift patterns from real usage are visible, Option A
(garden chain becomes a projection of the TaskList truth) follows in a later
PR informed by what this command surfaces.

Drift types detected
--------------------
  missing_native — plan task has no matching native task with the expected
                   chain_id prefix
  stale_status   — native task and its plan phase disagree on completion
                   (phase approved/conditional but native still pending or
                   in_progress; phase rejected but native completed)
  orphan_native  — native task carries a chain_id whose project_slug does
                   not exist in any process-plan.json (deleted/renamed
                   project)
  phase_drift    — phase has a gate-result.json (APPROVE | CONDITIONAL) but
                   the corresponding gate-finding native task is still
                   pending — read-side complement to the WRITE path that
                   PR #653 just fixed

Hard constraints
----------------
  - Stdlib only.
  - READ ONLY — never write to either store. We assert this in the test
    suite by snapshotting mtimes around every reconcile call.
  - Fail-open — if a store is unreachable, report what we can reach plus a
    clear "could not read X" line.
  - Honor CLAUDE_CONFIG_DIR for the native task path (lesson from PR #678).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Resolve helpers from parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Drift type labels — kept as module-level constants so the test suite and
# downstream consumers can reference them without string typos.
DRIFT_MISSING_NATIVE: str = "missing_native"
DRIFT_STALE_STATUS: str = "stale_status"
DRIFT_ORPHAN_NATIVE: str = "orphan_native"
DRIFT_PHASE_GATE: str = "phase_drift"

# Verdicts that imply downstream native tasks should be completed.
_APPROVE_VERDICTS: frozenset[str] = frozenset({"APPROVE", "CONDITIONAL"})
_REJECT_VERDICTS: frozenset[str] = frozenset({"REJECT"})

# Native task statuses that indicate work is still open.
_OPEN_STATUSES: frozenset[str] = frozenset({"pending", "in_progress"})
_COMPLETED_STATUSES: frozenset[str] = frozenset({"completed"})

# Banner used in error reports when a store cannot be read.
_UNREACHABLE_PREFIX: str = "could not read"


# ---------------------------------------------------------------------------
# Path resolution (no DomainStore import — keep it pure stdlib + path-based)
# ---------------------------------------------------------------------------

def _projects_root() -> Path:
    """Return the projects root: ${WG_LOCAL_ROOT}/wicked-crew/projects.

    Mirrors the resolution used by phase_manager.get_project_dir but does NOT
    create the directory — reconcile is read-only.
    """
    # Try the canonical helper first; fall back to env / default.
    try:
        from _paths import get_local_path  # type: ignore[import-not-found]
        return get_local_path("wicked-crew", "projects")
    except Exception:
        base = (
            os.environ.get("WG_LOCAL_ROOT")
            or str(Path.home() / ".something-wicked" / "wicked-garden" / "local")
        )
        return Path(base) / "wicked-crew" / "projects"


def _project_dir(project_slug: str) -> Path:
    """Return the canonical project dir for ``project_slug``.

    No path-traversal protection is applied here because reconcile is read
    only — the worst case is an unreadable path, which we already fail-open
    on. Callers that want stricter validation should use
    ``phase_manager.get_project_dir``.
    """
    return _projects_root() / project_slug


def _claude_config_dir() -> Path:
    """Resolve ${CLAUDE_CONFIG_DIR:-~/.claude} (per PR #678 lesson)."""
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(raw) if raw else Path.home() / ".claude"


# ---------------------------------------------------------------------------
# Garden-chain readers (process-plan.json)
# ---------------------------------------------------------------------------

def _load_process_plan(project_slug: str) -> Tuple[Optional[dict], Optional[str]]:
    """Read process-plan.json for ``project_slug``.

    Returns ``(plan_dict, error_message)``. On success ``error_message`` is
    None. On failure ``plan_dict`` is None and ``error_message`` carries a
    one-line, human-readable diagnostic.
    """
    plan_path = _project_dir(project_slug) / "process-plan.json"
    if not plan_path.is_file():
        return None, f"{_UNREACHABLE_PREFIX} process-plan.json (not found at {plan_path})"
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"{_UNREACHABLE_PREFIX} process-plan.json: {exc}"
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"{_UNREACHABLE_PREFIX} process-plan.json: invalid JSON ({exc})"
    if not isinstance(plan, dict):
        return None, f"{_UNREACHABLE_PREFIX} process-plan.json: top-level not an object"
    return plan, None


def _phase_gate_results(project_slug: str) -> Dict[str, dict]:
    """Return ``{phase_name: gate-result-dict}`` for every phase with a result.

    Silently skips unreadable / malformed files — those are reported as
    drift if a native counterpart exists, but they don't crash the report.
    """
    out: Dict[str, dict] = {}
    phases_dir = _project_dir(project_slug) / "phases"
    if not phases_dir.is_dir():
        return out
    try:
        entries = sorted(phases_dir.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.is_dir():
            continue
        gate_file = entry / "gate-result.json"
        if not gate_file.is_file():
            continue
        try:
            data = json.loads(gate_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            out[entry.name] = data
    return out


# ---------------------------------------------------------------------------
# Native-task readers (CLAUDE_CONFIG_DIR/tasks/{session_id}/*.json)
# ---------------------------------------------------------------------------

def _scan_all_native_tasks() -> Tuple[List[dict], Optional[str]]:
    """Walk every session under ${CLAUDE_CONFIG_DIR}/tasks/ and return all tasks.

    Returns ``(tasks, error_message)``. The error string is set when the
    tasks root itself is unreachable; per-file read errors are silently
    skipped to keep the diagnostic resilient (a single malformed task file
    must not poison the entire report).
    """
    config_dir = _claude_config_dir()
    tasks_root = config_dir / "tasks"
    if not tasks_root.is_dir():
        return [], f"{_UNREACHABLE_PREFIX} native tasks (no directory at {tasks_root})"

    out: List[dict] = []
    try:
        for task_file in tasks_root.rglob("*.json"):
            try:
                data = json.loads(task_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            # Tag with source path so callers can attribute drift entries.
            data.setdefault("_session_id", task_file.parent.name)
            data.setdefault("_task_file", str(task_file))
            out.append(data)
    except OSError as exc:
        return out, f"{_UNREACHABLE_PREFIX} native tasks: {exc}"
    return out, None


def _project_slug_from_chain_id(chain_id: str) -> Optional[str]:
    """Extract the project slug from a metadata.chain_id.

    chain_id format (per CLAUDE.md): ``{slug}(.(root|{phase}))(.{gate})?``
    The slug is everything before the first dot.
    """
    if not isinstance(chain_id, str) or not chain_id:
        return None
    return chain_id.split(".", 1)[0] or None


def _matches_project_chain(task: dict, project_slug: str) -> bool:
    """Return True when ``task.metadata.chain_id`` belongs to ``project_slug``."""
    meta = task.get("metadata") or {}
    if not isinstance(meta, dict):
        return False
    return _project_slug_from_chain_id(meta.get("chain_id") or "") == project_slug


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def _phase_status_implies_completion(gate_result: dict) -> Optional[bool]:
    """Return True if phase verdict means downstream tasks should be completed,
    False if they should be open (rejected), or None when verdict is unknown.
    """
    verdict = (gate_result.get("verdict") or "").upper().strip()
    if verdict in _APPROVE_VERDICTS:
        return True
    if verdict in _REJECT_VERDICTS:
        return False
    return None


def _detect_missing_native(
    plan: dict,
    project_slug: str,
    native_tasks_for_project: List[dict],
) -> List[dict]:
    """Plan tasks with no matching native counterpart.

    Match heuristic: a plan task is "matched" when at least one native task
    in ``native_tasks_for_project`` has the same chain_id as the plan task's
    metadata.chain_id AND its subject contains the plan task title (case
    insensitive substring) OR matches the plan id exactly. Subjects vary
    slightly between writers, so substring is the most stable signal.
    """
    plan_tasks = plan.get("tasks") or []
    if not isinstance(plan_tasks, list):
        return []

    drift: List[dict] = []
    for plan_task in plan_tasks:
        if not isinstance(plan_task, dict):
            continue
        plan_id = plan_task.get("id") or "<unknown>"
        plan_title = (plan_task.get("title") or "").strip()
        plan_meta = plan_task.get("metadata") or {}
        expected_chain = plan_meta.get("chain_id") if isinstance(plan_meta, dict) else None

        if not expected_chain:
            # Plan task lacks chain_id — surface as missing_native because
            # we cannot verify emission at all.
            drift.append({
                "type": DRIFT_MISSING_NATIVE,
                "plan_task_id": plan_id,
                "plan_title": plan_title,
                "expected_chain_id": None,
                "reason": "plan task has no metadata.chain_id",
            })
            continue

        # Find candidates with the same chain_id.
        candidates = [
            t for t in native_tasks_for_project
            if (t.get("metadata") or {}).get("chain_id") == expected_chain
        ]
        if not candidates:
            drift.append({
                "type": DRIFT_MISSING_NATIVE,
                "plan_task_id": plan_id,
                "plan_title": plan_title,
                "expected_chain_id": expected_chain,
                "reason": "no native task with matching chain_id",
            })
            continue

        # Title heuristic — only flag when none of the candidates look like
        # this plan task. Several plan tasks may share a chain_id (gate
        # findings, sub-tasks), so we accept any candidate that contains the
        # title or whose subject is the plan id.
        if plan_title:
            needle = plan_title.lower()
            title_match = any(
                needle in (c.get("subject") or "").lower()
                or (c.get("subject") or "").lower() == plan_id.lower()
                for c in candidates
            )
            if not title_match:
                drift.append({
                    "type": DRIFT_MISSING_NATIVE,
                    "plan_task_id": plan_id,
                    "plan_title": plan_title,
                    "expected_chain_id": expected_chain,
                    "reason": (
                        f"chain_id present ({len(candidates)} task(s)) "
                        f"but no subject matches plan title"
                    ),
                })
    return drift


def _detect_stale_status(
    plan: dict,
    project_slug: str,
    native_tasks_for_project: List[dict],
    gate_results: Dict[str, dict],
) -> List[dict]:
    """Native task vs plan-phase status mismatches.

    For each native task, look up its phase via metadata.phase. If a
    gate-result for that phase exists with verdict APPROVE/CONDITIONAL but
    the native task is still pending/in_progress, flag stale_status. The
    converse (REJECT but completed) is also flagged.
    """
    drift: List[dict] = []
    for task in native_tasks_for_project:
        meta = task.get("metadata") or {}
        if not isinstance(meta, dict):
            continue
        phase = meta.get("phase")
        if not phase or phase not in gate_results:
            continue

        expects_complete = _phase_status_implies_completion(gate_results[phase])
        if expects_complete is None:
            continue

        status = task.get("status") or "unknown"
        if expects_complete and status in _OPEN_STATUSES:
            drift.append({
                "type": DRIFT_STALE_STATUS,
                "native_task_id": task.get("id"),
                "native_subject": task.get("subject"),
                "native_status": status,
                "phase": phase,
                "phase_verdict": gate_results[phase].get("verdict"),
                "expected_status": "completed",
                "reason": (
                    f"phase {phase!r} verdict is "
                    f"{gate_results[phase].get('verdict')!r} "
                    f"but native task still {status!r}"
                ),
            })
        elif (not expects_complete) and status in _COMPLETED_STATUSES:
            drift.append({
                "type": DRIFT_STALE_STATUS,
                "native_task_id": task.get("id"),
                "native_subject": task.get("subject"),
                "native_status": status,
                "phase": phase,
                "phase_verdict": gate_results[phase].get("verdict"),
                "expected_status": "pending or in_progress",
                "reason": (
                    f"phase {phase!r} was rejected but native task is "
                    f"{status!r}"
                ),
            })
    return drift


def _detect_phase_drift(
    plan: dict,
    project_slug: str,
    native_tasks_for_project: List[dict],
    gate_results: Dict[str, dict],
) -> List[dict]:
    """Phase has APPROVE/CONDITIONAL gate-result but no completed gate-finding task.

    Read-side complement to PR #653 (which fixed the WRITE path so future
    approvals do close the matching task). reconcile catches drift that
    landed BEFORE that fix shipped.
    """
    drift: List[dict] = []
    for phase, gate_result in gate_results.items():
        if _phase_status_implies_completion(gate_result) is not True:
            continue
        # Find any gate-finding task for this phase.
        gate_findings = [
            t for t in native_tasks_for_project
            if isinstance(t.get("metadata"), dict)
            and t["metadata"].get("phase") == phase
            and t["metadata"].get("event_type") == "gate-finding"
        ]
        if not gate_findings:
            drift.append({
                "type": DRIFT_PHASE_GATE,
                "phase": phase,
                "phase_verdict": gate_result.get("verdict"),
                "reason": (
                    f"phase {phase!r} has verdict "
                    f"{gate_result.get('verdict')!r} but no gate-finding "
                    f"task exists in the native store"
                ),
            })
            continue
        # If any are still open, flag — the gate verdict says we're done.
        open_findings = [
            t for t in gate_findings
            if (t.get("status") or "unknown") in _OPEN_STATUSES
        ]
        if open_findings:
            for t in open_findings:
                drift.append({
                    "type": DRIFT_PHASE_GATE,
                    "phase": phase,
                    "phase_verdict": gate_result.get("verdict"),
                    "native_task_id": t.get("id"),
                    "native_subject": t.get("subject"),
                    "native_status": t.get("status"),
                    "reason": (
                        f"phase {phase!r} verdict is "
                        f"{gate_result.get('verdict')!r} but gate-finding "
                        f"task still {t.get('status')!r}"
                    ),
                })
    return drift


def _detect_orphan_native(
    all_native_tasks: List[dict],
    known_project_slugs: set[str],
) -> List[dict]:
    """Native tasks whose chain_id project does NOT exist in the registry."""
    drift: List[dict] = []
    for task in all_native_tasks:
        meta = task.get("metadata") or {}
        if not isinstance(meta, dict):
            continue
        chain_id = meta.get("chain_id")
        slug = _project_slug_from_chain_id(chain_id) if chain_id else None
        if slug is None:
            continue
        if slug in known_project_slugs:
            continue
        drift.append({
            "type": DRIFT_ORPHAN_NATIVE,
            "native_task_id": task.get("id"),
            "native_subject": task.get("subject"),
            "chain_id": chain_id,
            "orphan_project_slug": slug,
            "reason": (
                f"native task carries chain_id for project {slug!r} "
                f"which has no process-plan.json"
            ),
        })
    return drift


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconcile_project(
    project_slug: str,
    *,
    _all_native_tasks: Optional[List[dict]] = None,
    _all_native_error: Optional[str] = None,
    _known_project_slugs: Optional[set[str]] = None,
) -> dict:
    """Walk the garden chain + native task store for ``project_slug``.

    Returns the reconcile-result dict (see module docstring for shape).
    The leading-underscore kwargs let ``reconcile_all`` share a single
    native-task scan across many projects without re-reading the same
    files; external callers should leave them unset.
    """
    plan, plan_error = _load_process_plan(project_slug)

    if _all_native_tasks is None:
        all_native_tasks, native_error = _scan_all_native_tasks()
    else:
        all_native_tasks = _all_native_tasks
        native_error = _all_native_error

    native_for_project = [
        t for t in all_native_tasks if _matches_project_chain(t, project_slug)
    ]

    gate_results = _phase_gate_results(project_slug)

    drift: List[dict] = []
    plan_task_count = 0
    if plan is not None:
        plan_task_count = len(plan.get("tasks") or [])
        drift.extend(_detect_missing_native(plan, project_slug, native_for_project))
        drift.extend(_detect_stale_status(plan, project_slug, native_for_project, gate_results))
        drift.extend(_detect_phase_drift(plan, project_slug, native_for_project, gate_results))

    # Orphan detection only when we have a registry of known slugs;
    # reconcile_all passes one in. Single-project mode skips it because we
    # can't tell "old chain" from "different project" without the registry.
    if _known_project_slugs is not None:
        drift.extend(_detect_orphan_native(all_native_tasks, _known_project_slugs))

    errors: List[str] = []
    if plan_error:
        errors.append(plan_error)
    if native_error:
        errors.append(native_error)

    summary = {
        "total_drift_count": len(drift),
        "missing_native_count": sum(1 for d in drift if d["type"] == DRIFT_MISSING_NATIVE),
        "stale_status_count": sum(1 for d in drift if d["type"] == DRIFT_STALE_STATUS),
        "orphan_native_count": sum(1 for d in drift if d["type"] == DRIFT_ORPHAN_NATIVE),
        "phase_drift_count": sum(1 for d in drift if d["type"] == DRIFT_PHASE_GATE),
    }

    return {
        "project_slug": project_slug,
        "garden_chain_tasks": plan_task_count,
        "native_tasks": len(native_for_project),
        "phases_with_gate_result": sorted(gate_results.keys()),
        "drift": drift,
        "summary": summary,
        "errors": errors,
    }


def _list_known_project_slugs() -> List[str]:
    """List every project slug that has a directory under projects_root.

    Slug = directory name. We don't require process-plan.json here — the
    presence of a project dir is enough to count as "known" so a project
    that hasn't run propose-process yet doesn't trigger orphan-native
    flags for tasks that ARE legitimately tied to it.
    """
    root = _projects_root()
    if not root.is_dir():
        return []
    try:
        return sorted(
            entry.name for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []


def reconcile_all() -> List[dict]:
    """Run reconcile_project for every project in the projects root.

    Shares a single native-task scan across all projects so the cost is
    O(projects + tasks) rather than O(projects * tasks).
    """
    slugs = _list_known_project_slugs()
    all_native_tasks, native_error = _scan_all_native_tasks()
    known_slugs_set = set(slugs)
    return [
        reconcile_project(
            slug,
            _all_native_tasks=all_native_tasks,
            _all_native_error=native_error,
            _known_project_slugs=known_slugs_set,
        )
        for slug in slugs
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_text_report(result: dict) -> str:
    """Render a single reconcile result as a human-readable text report."""
    lines: List[str] = []
    slug = result.get("project_slug", "<unknown>")
    summary = result.get("summary") or {}
    lines.append(f"Reconcile report — project: {slug}")
    lines.append("=" * (len(lines[-1])))
    lines.append(f"  Plan tasks (process-plan.json):   {result.get('garden_chain_tasks', 0)}")
    lines.append(f"  Native tasks (matching chain_id): {result.get('native_tasks', 0)}")
    phases = result.get("phases_with_gate_result") or []
    lines.append(f"  Phases with gate-result.json:     {len(phases)}"
                 + (f"  ({', '.join(phases)})" if phases else ""))
    lines.append("")
    lines.append("Drift summary:")
    lines.append(f"  total:          {summary.get('total_drift_count', 0)}")
    lines.append(f"  missing_native: {summary.get('missing_native_count', 0)}")
    lines.append(f"  stale_status:   {summary.get('stale_status_count', 0)}")
    lines.append(f"  orphan_native:  {summary.get('orphan_native_count', 0)}")
    lines.append(f"  phase_drift:    {summary.get('phase_drift_count', 0)}")

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
            ident = (
                entry.get("plan_task_id")
                or entry.get("native_task_id")
                or entry.get("phase")
                or "?"
            )
            lines.append(f"  [{kind}] {ident} — {reason}")
    else:
        lines.append("")
        lines.append("No drift detected.")
    return "\n".join(lines) + "\n"


def render_text_report_all(results: List[dict]) -> str:
    """Render multiple reconcile results, one section per project."""
    if not results:
        return "No projects found under the projects root.\n"
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
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Reconcile native TaskList vs garden chain stores. Pure read-only "
            "diagnostic — never mutates either store."
        ),
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", dest="project", help="Reconcile a single project slug.")
    group.add_argument("--all", action="store_true", help="Reconcile every known project.")
    p.add_argument("--json", dest="as_json", action="store_true",
                   help="Emit machine-readable JSON instead of the text report.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.all:
        results = reconcile_all()
        if args.as_json:
            sys.stdout.write(json.dumps(results, indent=2) + "\n")
        else:
            sys.stdout.write(render_text_report_all(results))
        return 0

    # Single-project mode.
    result = reconcile_project(args.project)
    if args.as_json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        sys.stdout.write(render_text_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
