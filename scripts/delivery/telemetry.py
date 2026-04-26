#!/usr/bin/env python3
"""
telemetry.py — cross-session quality telemetry capture for wicked-garden.

Closes Issue #443: quality trends invisible across sessions.

Responsibilities
----------------
1. Capture per-session quality metrics from crew + native-task state.
2. Append one record per session-close to a per-project JSONL timeline.
3. Expose read helpers for drift.py and status commands.

Storage
-------
Path (resolve via get_local_file from _paths):
    ~/.something-wicked/wicked-garden/projects/{slug}/metrics/{project}/timeline.jsonl

One JSONL record per session-close. Append-only. Never rewrites.

Captured fields (timeline.jsonl record schema)
----------------------------------------------
    version:              schema version (currently "1")
    session_id:           the session that closed (sanitized)
    project:              crew project name (or "_global" if none active)
    recorded_at:          UTC ISO8601 timestamp
    sample_window:        dict with first/last observation timestamps
    metrics:
        gate_pass_rate:      float 0..1 — APPROVE / total verdicts this session
        gate_avg_score:      float — mean gate score (APPROVE/CONDITIONAL) or None
        gate_verdict_count:  int — total verdicts observed this session
        gate_rework_count:   int — REJECT verdicts this session
        task_count:          int — native tasks observed this session
        task_completed:      int — tasks completed this session
        complexity_delta:    int — complexity_score at close minus at session open
        cycle_time_by_phase: {phase: seconds_to_approve} (float)
        skip_reeval_count:   int — --skip-reeval invocations this session
        rework_events:       int — alias for gate_rework_count for easy querying

Design rules
------------
- Stdlib-only (importable from hook scripts).
- Fail-open: every public entry point has a top-level try/except that returns
  None / False rather than raising. Hook callers must never break.
- Capture target: <100ms typical, <500ms worst (bounded by a single stat+read
  pass over the session's tasks dir).
- No external dependencies and no wicked-bus coupling. drift.py handles bus.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — inherit from wicked-garden local root layout
# ---------------------------------------------------------------------------

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

SCHEMA_VERSION = "1"
# Per-session capture worst-case budget. We bail out rather than block session-end.
_CAPTURE_BUDGET_SECONDS = 0.5
# Max tasks to scan in one capture. Covers any realistic session.
_MAX_TASKS_SCAN = 500
# Minimum total verdicts before gate_pass_rate is considered meaningful.
_MIN_VERDICTS_FOR_RATE = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize(s: str) -> str:
    return str(s).replace("/", "_").replace("\\", "_").replace("..", "_")


def _timeline_path(project: str) -> Path:
    """Resolve the per-project timeline.jsonl path.

    Uses get_local_file so the project-scoped root from _paths.py applies.
    Falls back to a home-relative path if _paths is unavailable.
    """
    safe_project = _sanitize(project) if project else "_global"
    try:
        from _paths import get_local_file
        return get_local_file("metrics", safe_project, "timeline.jsonl")
    except Exception:
        fallback = (
            Path.home() / ".something-wicked" / "wicked-garden" / "local"
            / "metrics" / safe_project / "timeline.jsonl"
        )
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


# ---------------------------------------------------------------------------
# Native task scanning — pure read, no mutations
# ---------------------------------------------------------------------------

def _native_tasks_dir(session_id: str) -> Path:
    """Return the native-tasks dir for the given session. Never raises."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        base = Path(config_dir)
    else:
        base = Path.home() / ".claude"
    return base / "tasks" / _sanitize(session_id)


def _iter_task_files(session_id: str, deadline: float) -> List[Path]:
    """List task JSON files for the session, bounded by _MAX_TASKS_SCAN + deadline."""
    tdir = _native_tasks_dir(session_id)
    if not tdir.exists():
        return []
    out: List[Path] = []
    try:
        for p in sorted(tdir.glob("*.json")):
            if time.monotonic() > deadline:
                break
            out.append(p)
            if len(out) >= _MAX_TASKS_SCAN:
                break
    except OSError:
        return []
    return out


def _read_task(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_iso(ts: Any) -> Optional[float]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

def _extract_metrics_from_tasks(
    tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract quality metrics from the session's native task records.

    Looks at metadata.event_type == 'gate-finding' for verdict + score,
    and at task status for completion counts. Phase-transition events
    contribute cycle-time samples.
    """
    approve = 0
    conditional = 0
    reject = 0
    scores: List[float] = []
    task_count = 0
    task_completed = 0
    phase_started: Dict[str, float] = {}
    cycle_time_by_phase: Dict[str, float] = {}

    for t in tasks:
        if not isinstance(t, dict):
            continue
        task_count += 1
        status = t.get("status")
        if status == "completed":
            task_completed += 1

        meta = t.get("metadata") or {}
        if not isinstance(meta, dict):
            continue
        et = meta.get("event_type")

        if et == "gate-finding":
            verdict = str(meta.get("verdict", "")).upper()
            if verdict == "APPROVE":
                approve += 1
            elif verdict == "CONDITIONAL":
                conditional += 1
            elif verdict == "REJECT":
                reject += 1
            score = meta.get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))

        elif et == "phase-transition":
            phase = meta.get("phase") or meta.get("from_phase")
            ts_end = _parse_iso(t.get("updated_at") or t.get("created_at"))
            if phase and ts_end is not None:
                start = phase_started.get(phase)
                if start is not None and ts_end >= start:
                    cycle_time_by_phase[phase] = round(ts_end - start, 3)
                # Any transition on the phase resets its start anchor.
                phase_started[phase] = ts_end

    total_verdicts = approve + conditional + reject
    if total_verdicts >= _MIN_VERDICTS_FOR_RATE:
        # CONDITIONAL counts as partial pass: weight 0.5 so CONDITIONAL-heavy
        # sessions don't mask real degradation but also aren't full failures.
        pass_rate = (approve + 0.5 * conditional) / total_verdicts
    else:
        pass_rate = None

    avg_score = round(sum(scores) / len(scores), 4) if scores else None

    return {
        "gate_pass_rate": pass_rate,
        "gate_avg_score": avg_score,
        "gate_verdict_count": total_verdicts,
        "gate_rework_count": reject,
        "rework_events": reject,
        "task_count": task_count,
        "task_completed": task_completed,
        "cycle_time_by_phase": cycle_time_by_phase,
    }


def _extract_session_extras() -> Dict[str, Any]:
    """Read session-level counters (skip_reeval, complexity delta)."""
    skip_reeval_count = 0
    complexity_open: Optional[int] = None
    complexity_close: Optional[int] = None
    active_project: Optional[str] = None
    try:
        from _session import SessionState
        state = SessionState.load()
        # These fields are optional — gracefully absent on older sessions.
        raw_skip = getattr(state, "skip_reeval_count", None)
        if isinstance(raw_skip, int):
            skip_reeval_count = raw_skip
        complexity_open = getattr(state, "complexity_at_session_open", None)
        complexity_close = getattr(state, "complexity_score", None)
        active_project = getattr(state, "active_project", None)
    except Exception:
        pass  # fail open — session state unavailable is not fatal for telemetry

    complexity_delta = 0
    if isinstance(complexity_open, int) and isinstance(complexity_close, int):
        complexity_delta = complexity_close - complexity_open

    return {
        "skip_reeval_count": skip_reeval_count,
        "complexity_delta": complexity_delta,
        "active_project": active_project,
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def capture_session(
    session_id: str,
    project: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Capture telemetry for a session-close and append to the timeline.

    Returns the appended record dict on success, or None on any failure.
    Never raises. Honors _CAPTURE_BUDGET_SECONDS so hook callers stay fast.
    """
    try:
        t0 = time.monotonic()
        deadline = t0 + _CAPTURE_BUDGET_SECONDS

        extras = _extract_session_extras()
        raw_project = project or extras.get("active_project") or "_global"
        resolved_project = _sanitize(raw_project)

        # Task reading routed via _task_reader (#596 v8-PR-2).
        # WG_DAEMON_ENABLED=false → direct file scan (unchanged behaviour).
        tasks: List[Dict[str, Any]] = []
        # task_files: initialised before the try-block so the direct-scan fallback
        # path populates it.  The happy-path (daemon-routed read_session_tasks)
        # leaves task_files empty but tasks populated; sample_window now uses
        # len(tasks) (tasks_observed) rather than len(task_files) so the metric
        # is accurate for both paths (issues #647, #660).
        task_files: List[Path] = []
        try:
            _scripts_root = str(Path(__file__).resolve().parents[1])
            import sys as _sys
            if _scripts_root not in _sys.path:
                _sys.path.insert(0, _scripts_root)
            from crew._task_reader import read_session_tasks  # type: ignore[import]
            tasks = read_session_tasks(session_id, limit=_MAX_TASKS_SCAN)
        except Exception:
            # Fallback: direct file read (pre-PR-2 path, always available).
            task_files = _iter_task_files(session_id, deadline)
            for p in task_files:
                if time.monotonic() > deadline:
                    break
                t = _read_task(p)
                if t is not None:
                    tasks.append(t)

        metrics = _extract_metrics_from_tasks(tasks)
        metrics["skip_reeval_count"] = extras["skip_reeval_count"]
        metrics["complexity_delta"] = extras["complexity_delta"]

        # Build sample window from the first/last task timestamps observed.
        first_ts: Optional[str] = None
        last_ts: Optional[str] = None
        for t in tasks:
            c = t.get("created_at")
            u = t.get("updated_at") or c
            if isinstance(c, str):
                first_ts = c if first_ts is None or c < first_ts else first_ts
            if isinstance(u, str):
                last_ts = u if last_ts is None or u > last_ts else last_ts

        record = {
            "version": SCHEMA_VERSION,
            "session_id": _sanitize(session_id),
            "project": resolved_project,
            "recorded_at": _utc_now_iso(),
            "sample_window": {
                "first_observation": first_ts,
                "last_observation": last_ts,
                # tasks_observed counts tasks from whichever path ran (#660):
                # daemon-routed happy path (len(tasks)) or direct file scan
                # (also len(tasks) after tasks are populated from task_files).
                # Previously used len(task_files) which was always 0 on the
                # happy path, making the metric meaningless for daemon-routed
                # sessions.  Renamed from task_files_scanned for clarity.
                "tasks_observed": len(tasks),
            },
            "metrics": metrics,
        }

        _append_record(resolved_project, record)
        return record
    except Exception as exc:
        # Never break session teardown.
        print(f"[wicked-garden] telemetry capture error: {exc}", file=sys.stderr)
        return None


def _append_record(project: str, record: Dict[str, Any]) -> None:
    """Append a JSON record as a single JSONL line. Parent dirs auto-created."""
    path = _timeline_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use a single line — no embedded newlines in JSON default encoding.
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_timeline(project: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return the decoded records for a project's timeline.

    Most-recent-last ordering matches append order. Corrupt lines are skipped
    rather than raising — drift analysis is best-effort.
    """
    path = _timeline_path(project)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit is not None and limit > 0:
        out = out[-limit:]
    return out


def timeline_path_for(project: str) -> str:
    """String path helper for commands that need to surface the location."""
    return str(_timeline_path(project))


# ---------------------------------------------------------------------------
# CLI entry — used by hook + status command
# ---------------------------------------------------------------------------

def _cli_capture(args: List[str]) -> int:
    session_id = args[0] if args else os.environ.get("CLAUDE_SESSION_ID", "default")
    project = args[1] if len(args) > 1 else None
    rec = capture_session(session_id, project)
    if rec is None:
        print(json.dumps({"ok": False, "reason": "capture returned None"}))
        return 0  # fail-open
    print(json.dumps({"ok": True, "record": rec}))
    return 0


def _cli_show(args: List[str]) -> int:
    if not args:
        print(json.dumps({"ok": False, "reason": "project required"}))
        return 0
    project = args[0]
    limit = None
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            limit = None
    records = read_timeline(project, limit=limit)
    print(json.dumps({"ok": True, "project": project, "records": records,
                      "path": timeline_path_for(project)}))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "Usage:\n"
            "  telemetry.py capture [session_id] [project]\n"
            "  telemetry.py show <project> [limit]\n"
            "  telemetry.py path <project>\n",
            file=sys.stderr,
        )
        return 0
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "capture":
        return _cli_capture(rest)
    if cmd == "show":
        return _cli_show(rest)
    if cmd == "path":
        if not rest:
            print(json.dumps({"ok": False, "reason": "project required"}))
            return 0
        print(timeline_path_for(rest[0]))
        return 0
    print(json.dumps({"ok": False, "reason": f"unknown command: {cmd}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
