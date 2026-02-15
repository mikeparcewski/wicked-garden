#!/usr/bin/env python3
"""Wicked Delivery Data API — computed delivery metrics from kanban task data.

CLI mode (standard Plugin Data API):
    python3 api.py stats metrics
    python3 api.py stats metrics --project abc123
"""
import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

VALID_SOURCES = {"metrics"}
VALID_VERBS = {"stats"}
ROLLING_WINDOW_DAYS = 14
AGING_THRESHOLD_DAYS = 7


def _meta(source, total, limit=100, offset=0):
    """Build standard meta block."""
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _error(message, code, **details):
    """Print error to stderr and exit."""
    err = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _parse_iso(ts):
    """Parse ISO 8601 timestamp string to datetime."""
    if not ts:
        return None
    ts = ts.rstrip("Z")
    if "+" in ts[10:]:
        ts = ts[:ts.rindex("+")]
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _percentile(sorted_values, pct):
    """Compute percentile from sorted list."""
    if not sorted_values:
        return 0
    n = len(sorted_values)
    idx = pct * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])


# ==================== Kanban Discovery ====================


def _discover_kanban_api():
    """Find kanban api.py in plugin cache."""
    cache_root = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
    if not cache_root.exists():
        return None

    kanban_dirs = sorted(cache_root.glob("wicked-kanban/*/scripts/api.py"), reverse=True)
    return kanban_dirs[0] if kanban_dirs else None


def _get_kanban_tasks(project_id=None):
    """Invoke kanban api to get task data."""
    api_path = _discover_kanban_api()
    if not api_path:
        return None, "wicked-kanban not found in plugin cache"

    cmd = [sys.executable, str(api_path), "list", "tasks", "--limit", "10000"]
    if project_id:
        cmd.extend(["--project", project_id])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        return None, "kanban api timed out after 30s"

    if result.returncode != 0:
        return None, f"kanban api returned exit code {result.returncode}"

    try:
        response = json.loads(result.stdout)
        return response.get("data", []), None
    except json.JSONDecodeError:
        return None, "kanban api returned invalid JSON"


# ==================== Cache Integration ====================


def _get_cache():
    """Optionally discover wicked-startah cache."""
    try:
        cache_root = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
        startah_dirs = sorted(cache_root.glob("wicked-startah/*/scripts/cache.py"), reverse=True)
        if not startah_dirs:
            return None

        import importlib.util
        spec = importlib.util.spec_from_file_location("cache", startah_dirs[0])
        cache_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache_module)
        return cache_module.namespace("wicked-delivery")
    except Exception:
        return None


def _cache_key(tasks):
    """Generate cache key from task state."""
    task_count = len(tasks)
    latest = max((t.get("updated_at", "") for t in tasks), default="")
    return f"metrics:{task_count}:{latest}"


# ==================== Metrics Computation ====================


def _compute_metrics(tasks):
    """Compute all delivery metrics from raw task data."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ROLLING_WINDOW_DAYS)
    aging_cutoff = now - timedelta(days=AGING_THRESHOLD_DAYS)

    # Categorize tasks
    done_tasks = [t for t in tasks if t.get("swimlane") == "done"]
    todo_tasks = [t for t in tasks if t.get("swimlane") == "todo"]
    in_progress = [t for t in tasks if t.get("swimlane") == "in_progress"]

    # --- Throughput ---
    recent_done = []
    for t in done_tasks:
        updated = _parse_iso(t.get("updated_at"))
        if updated and updated >= cutoff:
            recent_done.append(t)

    tasks_per_day = round(len(recent_done) / ROLLING_WINDOW_DAYS, 2) if ROLLING_WINDOW_DAYS > 0 else 0

    # --- Cycle Time ---
    cycle_times = []
    for t in done_tasks:
        created = _parse_iso(t.get("created_at"))
        updated = _parse_iso(t.get("updated_at"))
        if created and updated and updated > created:
            hours = (updated - created).total_seconds() / 3600
            cycle_times.append(hours)

    cycle_times.sort()
    avg_hours = round(statistics.mean(cycle_times), 1) if cycle_times else 0
    median_hours = round(statistics.median(cycle_times), 1) if cycle_times else 0
    std_dev = round(statistics.stdev(cycle_times), 1) if len(cycle_times) > 1 else 0
    p50 = round(_percentile(cycle_times, 0.50), 1)
    p75 = round(_percentile(cycle_times, 0.75), 1)
    p95 = round(_percentile(cycle_times, 0.95), 1)

    # --- Backlog Health ---
    aging_tasks = []
    for t in todo_tasks:
        created = _parse_iso(t.get("created_at"))
        if created and created < aging_cutoff:
            age_hours = (now - created).total_seconds() / 3600
            aging_tasks.append(age_hours)

    oldest_hours = round(max(aging_tasks), 1) if aging_tasks else 0
    avg_age = round(statistics.mean(aging_tasks), 1) if aging_tasks else 0

    # --- Completion Rate ---
    total = len(done_tasks) + len(todo_tasks) + len(in_progress)
    rate = round(len(done_tasks) / total, 3) if total > 0 else 0

    return {
        "computed_at": now.isoformat(),
        "throughput": {
            "tasks_per_day": tasks_per_day,
            "period_days": ROLLING_WINDOW_DAYS,
            "completed_count": len(recent_done),
        },
        "cycle_time": {
            "avg_hours": avg_hours,
            "median_hours": median_hours,
            "std_dev_hours": std_dev,
            "sample_size": len(cycle_times),
            "p50": p50,
            "p75": p75,
            "p95": p95,
        },
        "backlog_health": {
            "aging_count": len(aging_tasks),
            "oldest_hours": oldest_hours,
            "avg_age_hours": avg_age,
            "total_todo": len(todo_tasks),
        },
        "completion_rate": {
            "rate": rate,
            "done": len(done_tasks),
            "in_progress": len(in_progress),
            "todo": len(todo_tasks),
            "total": total,
        },
    }


# ==================== CLI Handlers ====================


def cmd_stats(source, args):
    """Handle stats verb for metrics source."""
    if source != "metrics":
        _error(f"stats not supported for source: {source}", "INVALID_VERB", source=source)

    # Get raw task data from kanban
    tasks, error = _get_kanban_tasks(project_id=getattr(args, "project", None))

    if tasks is None:
        # Graceful degradation — return availability status, not error
        print(json.dumps({
            "data": {"available": False, "reason": error},
            "meta": _meta(source, 0),
        }, indent=2))
        return

    if not tasks:
        # No tasks — return zero metrics
        metrics = _compute_metrics([])
        print(json.dumps({"data": metrics, "meta": _meta(source, 1)}, indent=2))
        return

    # Check cache
    cache = _get_cache()
    key = _cache_key(tasks)

    if cache:
        try:
            cached = cache.get(key)
            if cached:
                print(json.dumps({"data": cached, "meta": _meta(source, 1)}, indent=2))
                return
        except Exception:
            pass

    # Compute metrics
    metrics = _compute_metrics(tasks)

    # Store in cache
    if cache:
        try:
            cache.set(key, metrics, ttl=300)
        except Exception:
            pass

    print(json.dumps({"data": metrics, "meta": _meta(source, 1)}, indent=2))


# ==================== Main ====================


def main():
    parser = argparse.ArgumentParser(description="Wicked Delivery Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in sorted(VALID_VERBS):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (metrics)")
        sub.add_argument("--project", help="Filter by kanban project ID")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--offset", type=int, default=0)

    args = parser.parse_args()

    if not args.verb:
        parser.print_help()
        sys.exit(1)

    if args.verb not in VALID_VERBS:
        _error(f"Unknown verb: {args.verb}", "INVALID_VERB",
               verb=args.verb, valid=list(VALID_VERBS))

    if args.source not in VALID_SOURCES:
        _error(f"Unknown source: {args.source}", "INVALID_SOURCE",
               source=args.source, valid=list(VALID_SOURCES))

    if args.verb == "stats":
        cmd_stats(args.source, args)


if __name__ == "__main__":
    main()
