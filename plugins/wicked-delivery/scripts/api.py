#!/usr/bin/env python3
"""Wicked Delivery Data API — computed delivery metrics from kanban task data.

CLI mode (standard Plugin Data API):
    python3 api.py stats metrics
    python3 api.py stats metrics --project abc123
    python3 api.py list commentary
"""
import argparse
import glob
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

VALID_SOURCES = {"metrics", "commentary"}
VALID_VERBS = {"stats", "list"}
STORAGE_DIR = Path.home() / ".something-wicked" / "wicked-delivery"
COST_MODEL_PATH = STORAGE_DIR / "cost_model.json"
SETTINGS_PATH = STORAGE_DIR / "settings.json"
COMMENTARY_CACHE_PATH = STORAGE_DIR / "commentary_cache.json"

# Defaults — overridden by settings.json if present
_DEFAULTS = {
    "rolling_window_days": 14,
    "aging_threshold_days": 7,
    "commentary": {
        "cooldown_minutes": 15,
        "thresholds": {
            "completion_rate": 0.10,
            "cycle_time_p95": 0.25,
            "throughput": 0.20,
            "aging_low": 10,
            "aging_high": 20,
        },
    },
}


def _load_settings():
    """Load settings from settings.json, merged with defaults."""
    settings = json.loads(json.dumps(_DEFAULTS))  # deep copy
    if not SETTINGS_PATH.exists():
        return settings
    try:
        with open(SETTINGS_PATH) as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return settings

    # Merge top-level scalars
    for k in ("rolling_window_days", "aging_threshold_days"):
        if k in user:
            settings[k] = user[k]

    # Merge commentary section
    if "commentary" in user and isinstance(user["commentary"], dict):
        uc = user["commentary"]
        if "cooldown_minutes" in uc:
            settings["commentary"]["cooldown_minutes"] = uc["cooldown_minutes"]
        if "thresholds" in uc and isinstance(uc["thresholds"], dict):
            for tk in settings["commentary"]["thresholds"]:
                if tk in uc["thresholds"]:
                    settings["commentary"]["thresholds"][tk] = uc["thresholds"][tk]

    return settings


# Load once at module level
_settings = _load_settings()
ROLLING_WINDOW_DAYS = _settings["rolling_window_days"]
AGING_THRESHOLD_DAYS = _settings["aging_threshold_days"]
DELTA_COMPLETION_RATE = _settings["commentary"]["thresholds"]["completion_rate"]
DELTA_CYCLE_TIME_P95 = _settings["commentary"]["thresholds"]["cycle_time_p95"]
DELTA_THROUGHPUT = _settings["commentary"]["thresholds"]["throughput"]
DELTA_AGING_LOW = _settings["commentary"]["thresholds"]["aging_low"]
DELTA_AGING_HIGH = _settings["commentary"]["thresholds"]["aging_high"]
COMMENTARY_COOLDOWN_MINUTES = _settings["commentary"]["cooldown_minutes"]


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


def _discover_plugin_api(plugin_name, script_name="api.py"):
    """Discover latest version of a plugin API script in cache."""
    cache_root = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
    pattern = str(cache_root / plugin_name / "*" / "scripts" / script_name)
    matches = sorted(glob.glob(pattern), reverse=True)
    return Path(matches[0]) if matches else None


def _query_crew_projects():
    """Get project completion data from wicked-crew."""
    crew_api = _discover_plugin_api("wicked-crew")
    if not crew_api:
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(crew_api), "list", "projects"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("data", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def _query_crew_signal_stats():
    """Get signal statistics from wicked-crew."""
    crew_api = _discover_plugin_api("wicked-crew")
    if not crew_api:
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(crew_api), "stats", "signals"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("data", {})
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def _query_mem_stats():
    """Get memory statistics from wicked-mem."""
    mem_script = _discover_plugin_api("wicked-mem", "memory.py")
    if not mem_script:
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(mem_script), "stats"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


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


# ==================== Cost Model ====================


def _load_cost_model():
    """Load cost model from JSON config. Returns None if not configured."""
    if not COST_MODEL_PATH.exists():
        return None

    try:
        with open(COST_MODEL_PATH) as f:
            model = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Invalid cost model at {COST_MODEL_PATH}: {e}", file=sys.stderr)
        return None

    # Validate required fields
    if not isinstance(model, dict):
        print("Warning: cost_model.json must be a JSON object", file=sys.stderr)
        return None

    if "priority_costs" not in model or not isinstance(model["priority_costs"], dict):
        print("Warning: cost_model.json missing valid priority_costs", file=sys.stderr)
        return None

    return model


def _compute_cost(tasks, metrics, cost_model):
    """Compute cost estimation from task data and cost model."""
    priority_costs = cost_model["priority_costs"]
    complexity_costs = cost_model.get("complexity_costs", {})
    currency = cost_model.get("currency", "USD")

    by_priority = {}
    total = 0.0

    for p_key, unit_cost in priority_costs.items():
        try:
            unit = float(unit_cost)
        except (ValueError, TypeError):
            continue
        count = sum(1 for t in tasks if t.get("priority") == p_key)
        subtotal = round(count * unit, 2)
        by_priority[p_key] = {
            "count": count,
            "unit_cost": unit,
            "subtotal": subtotal,
        }
        total += subtotal

    # Complexity costs (applied per-task if task has metadata.complexity)
    complexity_total = 0.0
    if complexity_costs:
        for t in tasks:
            task_complexity = None
            meta = t.get("metadata", {})
            if isinstance(meta, dict):
                task_complexity = meta.get("complexity")
            if task_complexity is not None:
                cost = complexity_costs.get(str(task_complexity), 0)
                try:
                    complexity_total += float(cost)
                except (ValueError, TypeError):
                    pass

    total_estimated = round(total + complexity_total, 2)
    completed_count = metrics.get("throughput", {}).get("completed_count", 0)
    roi = round(completed_count / total_estimated, 3) if total_estimated > 0 else 0

    return {
        "total_estimated": total_estimated,
        "by_priority": by_priority,
        "complexity_total": round(complexity_total, 2),
        "roi": roi,
        "roi_description": "completed_tasks / total_estimated_cost",
        "currency": currency,
        "cost_model_source": str(COST_MODEL_PATH),
    }


# ==================== Metrics Computation ====================


def _compute_metrics(tasks, cost_model=None):
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

    metrics = {
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

    # --- Velocity Trend (F11) ---
    velocity_trend = []
    for day_offset in range(ROLLING_WINDOW_DAYS):
        day = (now - timedelta(days=day_offset)).date()
        day_str = day.isoformat()
        day_created = sum(1 for t in tasks if _parse_iso(t.get("created_at", "")) and _parse_iso(t.get("created_at", "")).date() == day)
        day_completed = sum(1 for t in done_tasks if _parse_iso(t.get("updated_at", "")) and _parse_iso(t.get("updated_at", "")).date() == day)
        velocity_trend.append({"date": day_str, "created": day_created, "completed": day_completed})
    metrics["velocity_trend"] = list(reversed(velocity_trend))  # chronological order

    # --- Improvement (F12) ---
    # Compare current week vs previous week for key metrics
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    current_week_done = [t for t in done_tasks if _parse_iso(t.get("updated_at", "")) and _parse_iso(t.get("updated_at", "")) >= week_ago]
    prev_week_done = [t for t in done_tasks if _parse_iso(t.get("updated_at", "")) and two_weeks_ago <= _parse_iso(t.get("updated_at", "")) < week_ago]

    current_throughput = len(current_week_done) / 7 if current_week_done else 0
    prev_throughput = len(prev_week_done) / 7 if prev_week_done else 0

    metrics["improvement"] = {
        "throughput_wow": round(_pct_delta(prev_throughput, current_throughput) or 0, 3),
        "completion_count_current": len(current_week_done),
        "completion_count_previous": len(prev_week_done),
    }

    # --- Effort Distribution (F13) ---
    effort_by_priority = {}
    for t in tasks:
        p = t.get("priority", (t.get("metadata") or {}).get("priority", "unset"))
        effort_by_priority[p] = effort_by_priority.get(p, 0) + 1

    effort_by_swimlane = {}
    for t in tasks:
        sw = t.get("swimlane", "unknown")
        effort_by_swimlane[sw] = effort_by_swimlane.get(sw, 0) + 1

    metrics["effort"] = {
        "by_priority": effort_by_priority,
        "by_status": effort_by_swimlane,
        "total_tasks": len(tasks),
    }

    # --- Value (F14) ---
    metrics["value"] = {
        "features_shipped": len([t for t in done_tasks if "feature" in t.get("name", "").lower() or "feat" in t.get("name", "").lower()]),
        "bugs_resolved": len([t for t in done_tasks if "bug" in t.get("name", "").lower() or "fix" in t.get("name", "").lower()]),
        "total_completed": len(done_tasks),
    }

    # --- Cost Trend (F16) ---
    if cost_model:
        cost_trend = []
        priority_costs = cost_model.get("priority_costs", {})
        for day_offset in range(ROLLING_WINDOW_DAYS):
            day = (now - timedelta(days=day_offset)).date()
            day_str = day.isoformat()
            day_tasks = [t for t in done_tasks if _parse_iso(t.get("updated_at", "")) and _parse_iso(t.get("updated_at", "")).date() == day]
            day_cost = sum(float(priority_costs.get(t.get("priority", "P2"), 0.75)) for t in day_tasks)
            cost_trend.append({"date": day_str, "cost": round(day_cost, 2), "task_count": len(day_tasks)})
        metrics["cost_trend"] = list(reversed(cost_trend))

    # --- Multi-source integration (F15) ---
    sources_queried = ["kanban"]
    sources_unavailable = []

    # Crew integration
    crew_projects = _query_crew_projects()
    if crew_projects is not None:
        sources_queried.append("crew")
        completed_projects = [p for p in crew_projects if (p.get("phases") or {}).values() and
                             all(ph.get("status") in ("approved", "skipped") for ph in (p.get("phases") or {}).values())]
        metrics["project_completion"] = {
            "total_projects": len(crew_projects),
            "completed_projects": len(completed_projects),
            "completion_rate": round(len(completed_projects) / len(crew_projects), 3) if crew_projects else 0,
        }

        signal_stats = _query_crew_signal_stats()
        if signal_stats:
            metrics["signal_coverage"] = {
                "total_signals": signal_stats.get("total_signals", 0),
                "categories": signal_stats.get("categories", {}),
            }
    else:
        sources_unavailable.append("crew")

    # Mem integration
    mem_stats = _query_mem_stats()
    if mem_stats is not None:
        sources_queried.append("mem")
        metrics["knowledge"] = {
            "total_memories": mem_stats.get("total", 0),
            "by_type": mem_stats.get("by_type", {}),
        }
    else:
        sources_unavailable.append("mem")

    metrics["_sources"] = {
        "queried": sources_queried,
        "unavailable": sources_unavailable,
    }

    return metrics


# ==================== Commentary Engine ====================


def _pct_delta(old, new):
    """Compute percentage delta. Returns None if old is 0."""
    if old == 0:
        return None
    return (new - old) / abs(old)


def _generate_commentary(metrics, previous_snapshot=None):
    """Generate rule-based delivery insights from metrics and deltas."""
    entries = []
    now = datetime.now(timezone.utc).isoformat()
    is_baseline = previous_snapshot is None

    throughput = metrics.get("throughput", {})
    cycle_time = metrics.get("cycle_time", {})
    backlog = metrics.get("backlog_health", {})
    completion = metrics.get("completion_rate", {})

    if is_baseline:
        # First run — generate informational baseline entries
        entries.append({
            "category": "baseline",
            "severity": "info",
            "message": f"Baseline established: {throughput.get('tasks_per_day', 0)} tasks/day, "
                       f"{completion.get('rate', 0):.1%} completion rate, "
                       f"{backlog.get('aging_count', 0)} aging tasks.",
            "metric": "all",
            "previous_value": None,
            "current_value": None,
            "delta_pct": None,
            "generated_at": now,
        })
        return entries

    prev = previous_snapshot.get("metrics_snapshot", {})
    prev_throughput = prev.get("throughput", {})
    prev_cycle = prev.get("cycle_time", {})
    prev_backlog = prev.get("backlog_health", {})
    prev_completion = prev.get("completion_rate", {})

    # --- Completion rate ---
    old_rate = prev_completion.get("rate", 0)
    new_rate = completion.get("rate", 0)
    delta = _pct_delta(old_rate, new_rate)
    if delta is not None and abs(delta) > DELTA_COMPLETION_RATE:
        direction = "increased" if delta > 0 else "decreased"
        severity = "positive" if delta > 0 else "warning"
        entries.append({
            "category": "completion_rate",
            "severity": severity,
            "message": f"Completion rate {direction} by {abs(delta):.1%} "
                       f"(from {old_rate:.1%} to {new_rate:.1%}).",
            "metric": "completion_rate.rate",
            "previous_value": old_rate,
            "current_value": new_rate,
            "delta_pct": round(delta, 3),
            "generated_at": now,
        })

    # --- Cycle time p95 ---
    old_p95 = prev_cycle.get("p95", 0)
    new_p95 = cycle_time.get("p95", 0)
    delta = _pct_delta(old_p95, new_p95)
    if delta is not None and abs(delta) > DELTA_CYCLE_TIME_P95:
        direction = "increased" if delta > 0 else "decreased"
        severity = "warning" if delta > 0 else "positive"
        entries.append({
            "category": "cycle_time",
            "severity": severity,
            "message": f"Cycle time p95 {direction} by {abs(delta):.1%} "
                       f"(from {old_p95:.1f}h to {new_p95:.1f}h). "
                       f"{'Investigate outliers.' if delta > 0 else 'Workflow improving.'}",
            "metric": "cycle_time.p95",
            "previous_value": old_p95,
            "current_value": new_p95,
            "delta_pct": round(delta, 3),
            "generated_at": now,
        })

    # --- Throughput ---
    old_tpd = prev_throughput.get("tasks_per_day", 0)
    new_tpd = throughput.get("tasks_per_day", 0)
    delta = _pct_delta(old_tpd, new_tpd)
    if delta is not None and abs(delta) > DELTA_THROUGHPUT:
        direction = "increased" if delta > 0 else "decreased"
        severity = "positive" if delta > 0 else "warning"
        entries.append({
            "category": "throughput",
            "severity": severity,
            "message": f"Throughput {direction} by {abs(delta):.1%} "
                       f"(from {old_tpd} to {new_tpd} tasks/day).",
            "metric": "throughput.tasks_per_day",
            "previous_value": old_tpd,
            "current_value": new_tpd,
            "delta_pct": round(delta, 3),
            "generated_at": now,
        })

    # --- Backlog aging threshold crossing ---
    old_aging = prev_backlog.get("aging_count", 0)
    new_aging = backlog.get("aging_count", 0)
    crossed_up = old_aging < DELTA_AGING_HIGH and new_aging >= DELTA_AGING_HIGH
    crossed_down = old_aging >= DELTA_AGING_HIGH and new_aging < DELTA_AGING_LOW
    if crossed_up:
        entries.append({
            "category": "backlog_health",
            "severity": "warning",
            "message": f"Backlog aging count crossed {DELTA_AGING_HIGH} threshold "
                       f"(from {old_aging} to {new_aging}). Consider triaging stale tasks.",
            "metric": "backlog_health.aging_count",
            "previous_value": old_aging,
            "current_value": new_aging,
            "delta_pct": None,
            "generated_at": now,
        })
    elif crossed_down:
        entries.append({
            "category": "backlog_health",
            "severity": "positive",
            "message": f"Backlog aging count dropped below {DELTA_AGING_LOW} "
                       f"(from {old_aging} to {new_aging}). Backlog is healthy.",
            "metric": "backlog_health.aging_count",
            "previous_value": old_aging,
            "current_value": new_aging,
            "delta_pct": None,
            "generated_at": now,
        })

    # If no thresholds crossed, note stability
    if not entries:
        entries.append({
            "category": "stable",
            "severity": "info",
            "message": "All metrics within normal ranges. No significant changes detected.",
            "metric": "all",
            "previous_value": None,
            "current_value": None,
            "delta_pct": None,
            "generated_at": now,
        })

    return entries


def _load_commentary_cache():
    """Load previous commentary cache from disk."""
    if not COMMENTARY_CACHE_PATH.exists():
        return None
    try:
        with open(COMMENTARY_CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_commentary_cache(metrics, entries):
    """Save commentary + metrics snapshot to disk."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "metrics_snapshot": metrics,
        "commentary": entries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(COMMENTARY_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError as e:
        print(f"Warning: Could not save commentary cache: {e}", file=sys.stderr)


def _should_regenerate_commentary(previous_cache):
    """Check if cooldown has elapsed since last commentary generation."""
    if previous_cache is None:
        return True
    generated = _parse_iso(previous_cache.get("generated_at"))
    if generated is None:
        return True
    elapsed = (datetime.now(timezone.utc) - generated).total_seconds() / 60
    return elapsed >= COMMENTARY_COOLDOWN_MINUTES


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
        cost_model = _load_cost_model()
        metrics = _compute_metrics([], cost_model)
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

    # Load cost model (needed for both metrics and cost computation)
    cost_model = _load_cost_model()

    # Compute metrics
    metrics = _compute_metrics(tasks, cost_model)

    # Add cost if configured
    if cost_model:
        metrics["cost"] = _compute_cost(tasks, metrics, cost_model)

    # Store in cache
    if cache:
        try:
            cache.set(key, metrics, ttl=300)
        except Exception:
            pass

    print(json.dumps({"data": metrics, "meta": _meta(source, 1)}, indent=2))


def cmd_list(source, args):
    """Handle list verb for commentary source."""
    if source != "commentary":
        _error(f"list not supported for source: {source}", "INVALID_VERB", source=source)

    cache = _load_commentary_cache()
    if cache is None:
        print(json.dumps({
            "data": [],
            "meta": _meta(source, 0, limit=args.limit, offset=args.offset),
        }, indent=2))
        return

    entries = cache.get("commentary", [])
    total = len(entries)
    offset = getattr(args, "offset", 0)
    limit = getattr(args, "limit", 100)
    page = entries[offset:offset + limit]

    print(json.dumps({
        "data": page,
        "meta": _meta(source, total, limit=limit, offset=offset),
    }, indent=2))


# ==================== Main ====================


def main():
    parser = argparse.ArgumentParser(description="Wicked Delivery Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in sorted(VALID_VERBS):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (metrics, commentary)")
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
    elif args.verb == "list":
        cmd_list(args.source, args)


if __name__ == "__main__":
    main()
