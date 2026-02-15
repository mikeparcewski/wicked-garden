#!/usr/bin/env python3
"""PostToolUse hook: refresh delivery metrics and delta-triggered commentary.

Fires on TaskUpdate and TaskCreate. Computes fresh metrics from kanban,
compares against cached commentary snapshot, and regenerates commentary
if thresholds are crossed and cooldown has elapsed.

Reads hook input from stdin (JSON), prints {"ok": true} to stdout.
Stdlib-only — no external dependencies.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STORAGE_DIR = Path.home() / ".something-wicked" / "wicked-delivery"
SETTINGS_PATH = STORAGE_DIR / "settings.json"
COMMENTARY_CACHE_PATH = STORAGE_DIR / "commentary_cache.json"

# Defaults — overridden by settings.json
_DEFAULTS = {
    "cooldown_minutes": 15,
    "thresholds": {
        "completion_rate": 0.10,
        "cycle_time_p95": 0.25,
        "throughput": 0.20,
        "aging_low": 10,
        "aging_high": 20,
    },
}


def _load_settings():
    """Load commentary settings from settings.json."""
    settings = json.loads(json.dumps(_DEFAULTS))
    if not SETTINGS_PATH.exists():
        return settings
    try:
        with open(SETTINGS_PATH) as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return settings
    uc = user.get("commentary", {})
    if not isinstance(uc, dict):
        return settings
    if "cooldown_minutes" in uc:
        settings["cooldown_minutes"] = uc["cooldown_minutes"]
    ut = uc.get("thresholds", {})
    if isinstance(ut, dict):
        for k in settings["thresholds"]:
            if k in ut:
                settings["thresholds"][k] = ut[k]
    return settings


_cfg = _load_settings()


def _discover_delivery_api():
    """Find delivery api.py — prefer local repo, fall back to cache."""
    # Check if running from plugin root
    plugin_root = Path(__file__).resolve().parent.parent.parent
    local_api = plugin_root / "scripts" / "api.py"
    if local_api.exists():
        return local_api

    # Fall back to cache
    cache_root = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
    if not cache_root.exists():
        return None
    apis = sorted(cache_root.glob("wicked-delivery/*/scripts/api.py"), reverse=True)
    return apis[0] if apis else None


def _load_commentary_cache():
    """Load previous commentary cache."""
    if not COMMENTARY_CACHE_PATH.exists():
        return None
    try:
        with open(COMMENTARY_CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _parse_iso(ts):
    """Parse ISO timestamp."""
    if not ts:
        return None
    ts = ts.rstrip("Z")
    if "+" in ts[10:]:
        ts = ts[:ts.rindex("+")]
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _cooldown_ok(cache):
    """Check if cooldown has elapsed."""
    if cache is None:
        return True
    generated = _parse_iso(cache.get("generated_at"))
    if generated is None:
        return True
    elapsed = (datetime.now(timezone.utc) - generated).total_seconds() / 60
    return elapsed >= _cfg["cooldown_minutes"]


def _refresh_metrics(api_path):
    """Call api.py stats metrics and return parsed result."""
    try:
        result = subprocess.run(
            [sys.executable, str(api_path), "stats", "metrics"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        response = json.loads(result.stdout)
        return response.get("data")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def _check_deltas(new_metrics, old_snapshot):
    """Check if any metric crossed a threshold. Returns True if commentary should regenerate."""
    if old_snapshot is None:
        return True

    prev = old_snapshot.get("metrics_snapshot", {})
    t = _cfg["thresholds"]

    # Completion rate
    old_rate = prev.get("completion_rate", {}).get("rate", 0)
    new_rate = new_metrics.get("completion_rate", {}).get("rate", 0)
    if old_rate > 0 and abs((new_rate - old_rate) / old_rate) > t["completion_rate"]:
        return True

    # Cycle time p95
    old_p95 = prev.get("cycle_time", {}).get("p95", 0)
    new_p95 = new_metrics.get("cycle_time", {}).get("p95", 0)
    if old_p95 > 0 and abs((new_p95 - old_p95) / old_p95) > t["cycle_time_p95"]:
        return True

    # Throughput
    old_tpd = prev.get("throughput", {}).get("tasks_per_day", 0)
    new_tpd = new_metrics.get("throughput", {}).get("tasks_per_day", 0)
    if old_tpd > 0 and abs((new_tpd - old_tpd) / old_tpd) > t["throughput"]:
        return True

    # Backlog aging crossing thresholds
    old_aging = prev.get("backlog_health", {}).get("aging_count", 0)
    new_aging = new_metrics.get("backlog_health", {}).get("aging_count", 0)
    aging_high = t["aging_high"]
    aging_low = t["aging_low"]
    if (old_aging < aging_high and new_aging >= aging_high) or (old_aging >= aging_high and new_aging < aging_low):
        return True

    return False


def _regenerate_commentary(metrics, previous_cache):
    """Import commentary generation from api.py and save."""
    # Use the api module's commentary functions
    api_path = _discover_delivery_api()
    if not api_path:
        return

    # Import api module dynamically
    import importlib.util
    spec = importlib.util.spec_from_file_location("delivery_api", api_path)
    api_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_module)

    entries = api_module._generate_commentary(metrics, previous_cache)
    api_module._save_commentary_cache(metrics, entries)


def main():
    # Read hook input from stdin (required by hook protocol)
    try:
        if not sys.stdin.isatty():
            json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    api_path = _discover_delivery_api()
    if not api_path:
        print(json.dumps({"ok": True}))
        return

    # Always refresh metrics (fast — subprocess to api.py)
    metrics = _refresh_metrics(api_path)
    if metrics is None or metrics.get("available") is False:
        print(json.dumps({"ok": True}))
        return

    # Check if commentary needs regeneration
    cache = _load_commentary_cache()
    if _cooldown_ok(cache) and _check_deltas(metrics, cache):
        _regenerate_commentary(metrics, cache)

    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
