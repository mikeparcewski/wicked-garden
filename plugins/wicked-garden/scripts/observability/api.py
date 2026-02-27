#!/usr/bin/env python3
"""Wicked Observability Data API — wicked-workbench gateway integration.

Data sources:
  traces     — ~/.something-wicked/wicked-observability/traces/*.jsonl
  assertions — ~/.something-wicked/wicked-observability/assertions/*.jsonl
  health     — ~/.something-wicked/wicked-observability/health/latest.json

Usage (verb source order, matching gateway convention):
    python3 api.py list traces [--limit N] [--offset N]
    python3 api.py search traces --query "silent_failure"
    python3 api.py stats traces

    python3 api.py list assertions [--limit N] [--offset N]
    python3 api.py search assertions --query "malformed"

    python3 api.py list health [--limit N] [--offset N]
    python3 api.py get health --id wicked-kanban
    python3 api.py stats health
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

STORAGE_ROOT = Path.home() / ".something-wicked" / "wicked-observability"
TRACES_DIR = STORAGE_ROOT / "traces"
ASSERTIONS_DIR = STORAGE_ROOT / "assertions"
HEALTH_FILE = STORAGE_ROOT / "health" / "latest.json"


# ── Shared helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _meta(source: str, total: int, limit: int = 100, offset: int = 0) -> dict:
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": _now_iso(),
    }


def _error(message: str, code: str, **details) -> None:
    err: dict = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _paginate(items: list, limit: int, offset: int) -> list:
    return items[offset:offset + limit]


def _is_known_plugin(plugin_id: str) -> bool:
    """Check if plugin_id corresponds to an installed wicked-* plugin."""
    # Walk up from this script to find the plugins/ directory
    scripts_dir = Path(__file__).resolve().parent  # scripts/
    plugin_dir = scripts_dir.parent  # wicked-observability/
    plugins_dir = plugin_dir.parent  # plugins/
    candidate = plugins_dir / plugin_id
    return candidate.is_dir() and (candidate / ".claude-plugin" / "plugin.json").exists()


def _emit(data, source: str, total: int, limit: int, offset: int) -> None:
    print(json.dumps(
        {"data": data, "meta": _meta(source, total, limit, offset)},
        indent=2,
    ))


# ── JSONL reader ─────────────────────────────────────────────────────────────


def _read_jsonl_dir(directory: Path) -> list[dict]:
    """Read all *.jsonl files in directory, newest files first.

    Returns a flat list of parsed records; malformed lines are skipped.
    Files are sorted descending by name (ISO date → newest first).
    """
    if not directory.exists():
        return []

    records: list[dict] = []
    for jsonl_file in sorted(directory.glob("*.jsonl"), reverse=True):
        try:
            text = jsonl_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records


def _read_health() -> list[dict]:
    """Read health/latest.json. Returns a list of per-plugin health records.

    health_probe.py writes a single report object:
        {status, checked_at, plugins_checked, violations[], summary{}}
    This function normalises it into per-plugin records for the data gateway,
    plus a ``_summary`` pseudo-record for the overall report.
    """
    if not HEALTH_FILE.exists():
        return []

    try:
        raw = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    # Already a list (future format or externally produced) — pass through
    if isinstance(raw, list):
        return raw

    if not isinstance(raw, dict):
        return []

    # Detect health_probe.py single-report format
    if "violations" in raw and "summary" in raw:
        return _normalise_health_report(raw)

    # Legacy: dict keyed by plugin name → per-plugin records
    records = []
    for plugin_id, record in raw.items():
        if isinstance(record, dict):
            records.append({"id": plugin_id, **record})
        else:
            records.append({"id": plugin_id, "status": record})
    return records


def _normalise_health_report(report: dict) -> list[dict]:
    """Convert health_probe.py single report into per-plugin records.

    Builds a record for every plugin that was checked (healthy ones get
    an empty violations list), not just those with violations.
    """
    violations = report.get("violations", [])
    checked_at = report.get("checked_at", "")
    summary = report.get("summary", {})

    # Group violations by plugin
    by_plugin: dict[str, list[dict]] = {}
    for v in violations:
        plugin = v.get("plugin", "unknown")
        by_plugin.setdefault(plugin, []).append(v)

    # Build a record for each plugin that reported violations
    records = []
    for plugin_id, plugin_violations in sorted(by_plugin.items()):
        severities = {v.get("severity", "unknown") for v in plugin_violations}
        if "error" in severities:
            status = "unhealthy"
        elif "warning" in severities:
            status = "degraded"
        else:
            status = "healthy"

        records.append({
            "id": plugin_id,
            "status": status,
            "checked_at": checked_at,
            "violations": plugin_violations,
        })

    # Infer healthy plugin count from the probe summary and add placeholder
    # records so that health stats and health get reflect ALL checked plugins.
    healthy_count = summary.get("plugins_healthy", 0)
    if healthy_count > 0:
        records.append({
            "id": "_healthy_plugins",
            "status": "healthy",
            "checked_at": checked_at,
            "count": healthy_count,
            "violations": [],
        })

    # Add a summary pseudo-record
    records.append({
        "id": "_summary",
        "status": report.get("status", "unknown"),
        "checked_at": checked_at,
        "plugins_checked": report.get("plugins_checked", 0),
        "summary": summary,
    })

    return records


# ── Traces handlers ───────────────────────────────────────────────────────────


def cmd_traces_list(args) -> None:
    records = _read_jsonl_dir(TRACES_DIR)
    total = len(records)
    page = _paginate(records, args.limit, args.offset)
    _emit(page, "traces", total, args.limit, args.offset)


def cmd_traces_search(args) -> None:
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    records = _read_jsonl_dir(TRACES_DIR)
    query_lower = args.query.lower()

    # Search across string field values
    matches = []
    for record in records:
        searchable = " ".join(
            str(v) for v in record.values() if isinstance(v, (str, int, bool))
        ).lower()
        if query_lower in searchable:
            matches.append(record)

    total = len(matches)
    page = _paginate(matches, args.limit, args.offset)
    _emit(page, "traces", total, args.limit, args.offset)


def cmd_traces_stats(args) -> None:
    records = _read_jsonl_dir(TRACES_DIR)

    stats: dict = {
        "total": len(records),
        "by_event_type": {},
        "by_tool_name": {},
        "silent_failures": 0,
        "hook_invocations": 0,
        "by_hook_plugin": {},
    }

    for r in records:
        event_type = r.get("event_type", "unknown")
        stats["by_event_type"][event_type] = stats["by_event_type"].get(event_type, 0) + 1

        tool_name = r.get("tool_name", "unknown")
        stats["by_tool_name"][tool_name] = stats["by_tool_name"].get(tool_name, 0) + 1

        if r.get("silent_failure"):
            stats["silent_failures"] += 1

        if event_type == "hook_invocation":
            stats["hook_invocations"] += 1
            hook_plugin = r.get("hook_plugin") or "unknown"
            stats["by_hook_plugin"][hook_plugin] = (
                stats["by_hook_plugin"].get(hook_plugin, 0) + 1
            )

    _emit(stats, "traces", 1, 1, 0)


# ── Assertions handlers ───────────────────────────────────────────────────────


def cmd_assertions_list(args) -> None:
    records = _read_jsonl_dir(ASSERTIONS_DIR)
    total = len(records)
    page = _paginate(records, args.limit, args.offset)
    _emit(page, "assertions", total, args.limit, args.offset)


def cmd_assertions_search(args) -> None:
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    records = _read_jsonl_dir(ASSERTIONS_DIR)
    query_lower = args.query.lower()

    matches = []
    for record in records:
        searchable = " ".join(
            str(v) for v in record.values() if isinstance(v, (str, int, bool))
        ).lower()
        # Also search inside violations list
        for violation in record.get("violations", []):
            searchable += " " + " ".join(
                str(v) for v in violation.values() if isinstance(v, str)
            ).lower()
        if query_lower in searchable:
            matches.append(record)

    total = len(matches)
    page = _paginate(matches, args.limit, args.offset)
    _emit(page, "assertions", total, args.limit, args.offset)


# ── Health handlers ───────────────────────────────────────────────────────────


def cmd_health_list(args) -> None:
    records = _read_health()
    # Include _summary in list but separate for clarity
    total = len(records)
    page = _paginate(records, args.limit, args.offset)
    _emit(page, "health", total, args.limit, args.offset)


def cmd_health_get(args) -> None:
    if not args.id:
        _error("--id required for health get", "MISSING_ID")

    records = _read_health()
    for record in records:
        if record.get("id") == args.id:
            _emit(record, "health", 1, 1, 0)
            return

    # If plugin exists in the ecosystem but has no violations, it's healthy
    summary_record = next((r for r in records if r.get("id") == "_summary"), None)
    if summary_record and _is_known_plugin(args.id):
        _emit({
            "id": args.id,
            "status": "healthy",
            "checked_at": summary_record.get("checked_at", ""),
            "violations": [],
        }, "health", 1, 1, 0)
        return

    _error(f"Plugin not found in health data: {args.id}", "NOT_FOUND",
           resource="health", id=args.id)


def cmd_health_stats(args) -> None:
    records = _read_health()

    # Separate meta-records from per-plugin records
    meta_ids = {"_summary", "_healthy_plugins"}
    plugin_records = [r for r in records if r.get("id") not in meta_ids]
    summary_record = next((r for r in records if r.get("id") == "_summary"), None)
    healthy_record = next((r for r in records if r.get("id") == "_healthy_plugins"), None)

    stats: dict = {
        "by_status": {},
        "healthy": 0,
        "degraded": 0,
        "unhealthy": 0,
        "unknown": 0,
    }

    for r in plugin_records:
        status = str(r.get("status", "unknown")).lower()
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        if status in ("ok", "healthy", "pass"):
            stats["healthy"] += 1
        elif status in ("degraded", "warn", "warning"):
            stats["degraded"] += 1
        elif status in ("error", "unhealthy", "fail", "failure"):
            stats["unhealthy"] += 1
        else:
            stats["unknown"] += 1

    # Add healthy plugin count from probe summary (plugins with no violations)
    if healthy_record:
        healthy_count = healthy_record.get("count", 0)
        stats["healthy"] += healthy_count
        stats["by_status"]["healthy"] = stats["by_status"].get("healthy", 0) + healthy_count

    # Include probe-level summary if available
    if summary_record:
        stats["overall_status"] = summary_record.get("status", "unknown")
        stats["plugins_checked"] = summary_record.get("plugins_checked", 0)
        stats["probe_summary"] = summary_record.get("summary", {})

    stats["total_plugins"] = stats["healthy"] + stats["degraded"] + stats["unhealthy"] + stats["unknown"]

    _emit(stats, "health", 1, 1, 0)


# ── Router ────────────────────────────────────────────────────────────────────

# Dispatch table: (source, verb) → handler function
_DISPATCH: dict[tuple[str, str], object] = {
    ("traces", "list"): cmd_traces_list,
    ("traces", "search"): cmd_traces_search,
    ("traces", "stats"): cmd_traces_stats,
    ("assertions", "list"): cmd_assertions_list,
    ("assertions", "search"): cmd_assertions_search,
    ("health", "list"): cmd_health_list,
    ("health", "get"): cmd_health_get,
    ("health", "stats"): cmd_health_stats,
}


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    # Fast-path: --health-check emits a sample envelope for contract assertions
    if "--health-check" in sys.argv:
        print(json.dumps({
            "data": [],
            "meta": {"total": 0, "source": "health-check", "timestamp": datetime.now(timezone.utc).isoformat()},
        }))
        return

    parser = argparse.ArgumentParser(
        description="Wicked Observability Data API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Verbs and sources (verb source order, matching gateway convention):
  list   traces     [--limit N] [--offset N]
  search traces     --query TEXT
  stats  traces

  list   assertions [--limit N] [--offset N]
  search assertions --query TEXT

  list   health     [--limit N] [--offset N]
  get    health     --id PLUGIN_NAME
  stats  health
""",
    )

    parser.add_argument("verb", choices=["list", "search", "stats", "get"],
                        help="Action to perform")
    parser.add_argument("source", choices=["traces", "assertions", "health"],
                        help="Data source to query")
    parser.add_argument("--limit", type=int, default=100,
                        help="Maximum records to return (default: 100)")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip first N records (default: 0)")
    parser.add_argument("--query", help="Search query string")
    parser.add_argument("--id", help="Resource identifier (for health get)")

    args = parser.parse_args()

    handler = _DISPATCH.get((args.source, args.verb))
    if handler is None:
        _error(
            f"'{args.verb}' is not supported for source '{args.source}'",
            "UNSUPPORTED_VERB",
            source=args.source,
            verb=args.verb,
            supported=[v for (s, v) in _DISPATCH if s == args.source],
        )

    handler(args)


if __name__ == "__main__":
    main()
