#!/usr/bin/env python3
"""Wicked Crew Data API — standard Plugin Data API interface.

Usage:
    python3 api.py list projects [--limit N] [--offset N]
    python3 api.py get projects <name>
    python3 api.py create projects < payload.json
    python3 api.py update projects <name> < payload.json
    python3 api.py list phases --project <name> [--limit N]
    python3 api.py get phases <phase-name> --project <name>
    python3 api.py update phases <phase-name> --project <name> < payload.json
    python3 api.py list signals [--limit N] [--offset N]
    python3 api.py search signals --query Q
    python3 api.py stats signals
    python3 api.py list feedback [--limit N] [--offset N]
    python3 api.py stats feedback
    python3 api.py list specialists
    python3 api.py get specialists <name>
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CREW_BASE = Path.home() / ".something-wicked" / "wicked-crew"
PROJECTS_DIR = CREW_BASE / "projects"
FEEDBACK_DIR = CREW_BASE / "feedback"
SCRIPT_DIR = Path(__file__).parent
SIGNALS_FILE = SCRIPT_DIR / "data" / "default_signals.jsonl"
VALID_SOURCES = {"projects", "phases", "signals", "feedback", "specialists"}


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


def _read_input():
    """Read JSON input from stdin for write operations."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _error("Invalid JSON input", "INVALID_INPUT")


def _validate_required(data, *fields):
    """Validate required fields are present."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        _error("Validation failed", "VALIDATION_ERROR",
               fields={f: "required field missing" for f in missing})


def _validate_safe_name(name, field="name"):
    """Validate name is safe for filesystem use (no path traversal)."""
    if not name or "/" in name or "\\" in name or ".." in name:
        _error(f"Invalid {field}", "VALIDATION_ERROR",
               fields={field: "must not contain path separators or '..'"})


def _load_project(project_dir):
    """Load project data from project.json."""
    pj = project_dir / "project.json"
    if pj.exists():
        try:
            with open(pj) as f:
                data = json.load(f)
            return {
                "name": data.get("name", project_dir.name),
                "current_phase": data.get("current_phase", "unknown"),
                "complexity_score": data.get("complexity_score", 0),
                "signals_detected": data.get("signals_detected", []),
                "phase_plan": data.get("phase_plan", []),
                "created_at": data.get("created_at"),
                "phases": data.get("phases", {}),
            }
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback to project.md frontmatter
    pm = project_dir / "project.md"
    if pm.exists():
        try:
            content = pm.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    fm = {}
                    for line in parts[1].split("\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            fm[k.strip()] = v.strip()
                    return {
                        "name": fm.get("name", project_dir.name),
                        "current_phase": fm.get("current_phase", "unknown"),
                        "complexity_score": 0,
                        "signals_detected": [],
                        "phase_plan": [],
                        "created_at": fm.get("created"),
                        "phases": {},
                    }
        except OSError:
            pass
    return None


def _save_project_json(project_dir, data):
    """Atomically save project.json."""
    pj = project_dir / "project.json"
    tmp = pj.with_suffix(".json.tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.rename(pj)
    except OSError as e:
        if tmp.exists():
            tmp.unlink()
        _error(f"Failed to save project: {e}", "WRITE_ERROR")


# === Projects ===

def cmd_list_projects(args):
    """List crew projects."""
    if not PROJECTS_DIR.exists():
        print(json.dumps({"data": [], "meta": _meta("projects", 0, args.limit, args.offset)}, indent=2))
        return

    projects = []
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        p = _load_project(d)
        if p:
            projects.append(p)

    total = len(projects)
    data = projects[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("projects", total, args.limit, args.offset)}, indent=2))


def cmd_get_project(name, args):
    """Get a specific project."""
    pd = PROJECTS_DIR / name
    if not pd.exists():
        _error("Project not found", "NOT_FOUND", resource="projects", id=name)

    p = _load_project(pd)
    if not p:
        _error("Could not read project", "READ_ERROR", resource="projects", id=name)

    # Include outcome summary
    outcome = pd / "outcome.md"
    if outcome.exists():
        try:
            content = outcome.read_text()
            if "## Desired Outcome" in content:
                after = content.split("## Desired Outcome")[1]
                paragraphs = after.strip().split("\n\n")
                if paragraphs:
                    p["outcome_summary"] = paragraphs[0].strip()[:500]
        except OSError:
            pass

    print(json.dumps({"data": p, "meta": _meta("projects", 1)}, indent=2))


def cmd_create_project(args):
    """Create a new crew project — reads JSON from stdin."""
    data = _read_input()
    _validate_required(data, "name", "description")

    name = data["name"]
    _validate_safe_name(name)
    pd = PROJECTS_DIR / name
    if pd.exists():
        _error(f"Project '{name}' already exists", "ALREADY_EXISTS", resource="projects", id=name)

    # Create directory structure
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "phases").mkdir(exist_ok=True)
    (pd / "phases" / "clarify").mkdir(exist_ok=True)

    # Build project.json
    project_data = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_phase": "clarify",
        "signals_detected": data.get("signals_detected", []),
        "complexity_score": data.get("complexity_score", 0),
        "specialists_recommended": data.get("specialists_recommended", []),
        "phase_plan": data.get("phase_plan", ["clarify", "build", "review"]),
        "phase_plan_mode": data.get("phase_plan_mode", "dynamic"),
        "phases": {},
        "task_lifecycle": {
            "staleness_threshold_minutes": 30,
            "recovery_mode": "auto",
            "user_overrides": {},
        },
    }
    _save_project_json(pd, project_data)

    # Create outcome.md
    outcome_path = pd / "outcome.md"
    outcome_path.write_text(
        f"# Outcome: {name}\n\n"
        f"## Desired Outcome\n\n{data['description']}\n\n"
        "## Success Criteria\n\n1. To be defined\n\n"
        "## Scope\n\n### In Scope\n- To be defined\n\n### Out of Scope\n- To be defined\n"
    )

    # Create clarify status
    status_path = pd / "phases" / "clarify" / "status.md"
    status_path.write_text(
        "---\nphase: clarify\nstatus: pending\n"
        f"started: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n---\n\n"
        "# Clarify Phase\n\nDefining the outcome and success criteria.\n"
    )

    print(json.dumps({"data": project_data, "meta": _meta("projects", 1)}, indent=2))


def cmd_update_project(name, args):
    """Update project fields — reads JSON from stdin."""
    _validate_safe_name(name)
    pd = PROJECTS_DIR / name
    if not pd.exists():
        _error("Project not found", "NOT_FOUND", resource="projects", id=name)

    pj = pd / "project.json"
    if not pj.exists():
        _error("project.json not found", "READ_ERROR", resource="projects", id=name)

    try:
        with open(pj) as f:
            project_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        _error("Could not read project.json", "READ_ERROR", resource="projects", id=name)

    data = _read_input()
    allowed = {"current_phase", "signals_detected", "complexity_score",
               "specialists_recommended", "phase_plan", "phase_plan_mode", "status"}
    for k, v in data.items():
        if k in allowed:
            project_data[k] = v

    _save_project_json(pd, project_data)
    print(json.dumps({"data": project_data, "meta": _meta("projects", 1)}, indent=2))


# === Phases ===

def cmd_list_phases(args):
    """List phases for a project."""
    if not args.project:
        _error("--project required for phases", "MISSING_PROJECT")

    pd = PROJECTS_DIR / args.project
    if not pd.exists():
        _error("Project not found", "NOT_FOUND", resource="projects", id=args.project)

    p = _load_project(pd)
    if not p:
        _error("Could not read project", "READ_ERROR", resource="projects", id=args.project)

    phases = []
    for phase_name, phase_data in p.get("phases", {}).items():
        phases.append({
            "name": phase_name,
            "status": phase_data.get("status", "pending"),
            "started_at": phase_data.get("started_at"),
            "completed_at": phase_data.get("completed_at"),
            "approved_at": phase_data.get("approved_at"),
            "approved_by": phase_data.get("approved_by"),
        })

    total = len(phases)
    data = phases[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("phases", total, args.limit, args.offset)}, indent=2))


def cmd_get_phase(phase_name, args):
    """Get a specific phase."""
    if not args.project:
        _error("--project required for phase get", "MISSING_PROJECT")

    pd = PROJECTS_DIR / args.project
    if not pd.exists():
        _error("Project not found", "NOT_FOUND", resource="projects", id=args.project)

    p = _load_project(pd)
    if not p:
        _error("Could not read project", "READ_ERROR", resource="projects", id=args.project)

    phase_data = p.get("phases", {}).get(phase_name)
    if not phase_data:
        _error("Phase not found", "NOT_FOUND", resource="phases", id=phase_name)

    result = {
        "name": phase_name,
        "project": args.project,
        **phase_data,
    }

    # Include status.md content if available
    status_md = pd / "phases" / phase_name / "status.md"
    if status_md.exists():
        try:
            result["status_detail"] = status_md.read_text()[:2000]
        except OSError:
            pass

    print(json.dumps({"data": result, "meta": _meta("phases", 1)}, indent=2))


def cmd_update_phase(phase_name, args):
    """Update phase status — reads JSON from stdin.

    Supports actions: start, complete, approve, skip
    """
    if not args.project:
        _error("--project required for phase update", "MISSING_PROJECT")

    _validate_safe_name(args.project)
    _validate_safe_name(phase_name, field="phase_name")

    pd = PROJECTS_DIR / args.project
    pj = pd / "project.json"
    if not pj.exists():
        _error("Project not found", "NOT_FOUND", resource="projects", id=args.project)

    try:
        with open(pj) as f:
            project_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        _error("Could not read project.json", "READ_ERROR")

    data = _read_input()
    action = data.get("action", "update")
    VALID_ACTIONS = {"start", "complete", "approve", "skip", "update"}
    if action not in VALID_ACTIONS:
        _error(f"Invalid action: {action}", "VALIDATION_ERROR",
               fields={"action": f"must be one of: {', '.join(sorted(VALID_ACTIONS))}"})
    now = datetime.now(timezone.utc).isoformat()

    if "phases" not in project_data:
        project_data["phases"] = {}
    if phase_name not in project_data["phases"]:
        project_data["phases"][phase_name] = {"status": "pending"}

    phase = project_data["phases"][phase_name]

    if action == "start":
        phase["status"] = "in_progress"
        phase["started_at"] = now
        project_data["current_phase"] = phase_name
    elif action == "complete":
        phase["status"] = "awaiting_approval"
        phase["completed_at"] = now
    elif action == "approve":
        phase["status"] = "approved"
        phase["approved_at"] = now
        phase["approved_by"] = data.get("approved_by", "api")
    elif action == "skip":
        phase["status"] = "skipped"
        phase["completed_at"] = now
        phase["notes"] = data.get("reason", "Skipped via API")
    elif action == "update":
        # Generic field update
        for k in ("status", "notes"):
            if k in data:
                phase[k] = data[k]

    _save_project_json(pd, project_data)
    print(json.dumps({"data": {"name": phase_name, "project": args.project, **phase}, "meta": _meta("phases", 1)}, indent=2))


# === Signals ===

def _load_signals():
    """Load all signals from the JSONL file."""
    signals = []
    if not SIGNALS_FILE.exists():
        return signals
    try:
        with open(SIGNALS_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    signals.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return signals


def cmd_list_signals(args):
    """List all signal definitions."""
    signals = _load_signals()
    total = len(signals)
    data = signals[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("signals", total, args.limit, args.offset)}, indent=2))


def cmd_search_signals(args):
    """Search signals by text."""
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    query_lower = args.query.lower()
    signals = _load_signals()

    results = []
    for s in signals:
        text = f"{s.get('category', '')} {s.get('text', '')}".lower()
        if query_lower in text:
            results.append(s)
        if len(results) >= args.limit:
            break

    print(json.dumps({"data": results, "meta": _meta("signals", len(results), args.limit, args.offset)}, indent=2))


def cmd_stats_signals(args):
    """Get signal statistics by category."""
    signals = _load_signals()
    categories = {}
    for s in signals:
        cat = s.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    data = {
        "total_signals": len(signals),
        "categories": categories,
    }
    print(json.dumps({"data": data, "meta": _meta("signals", len(signals))}, indent=2))


# === Feedback ===

def _load_feedback():
    """Load feedback outcomes from JSONL file."""
    outcomes_file = FEEDBACK_DIR / "outcomes.jsonl"
    items = []
    if not outcomes_file.exists():
        return items
    try:
        with open(outcomes_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return items


def cmd_list_feedback(args):
    """List feedback outcomes."""
    items = _load_feedback()
    total = len(items)
    data = items[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("feedback", total, args.limit, args.offset)}, indent=2))


def cmd_stats_feedback(args):
    """Get feedback statistics."""
    items = _load_feedback()
    outcomes = {}
    for item in items:
        outcome = item.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    # Load metrics if available
    metrics_file = FEEDBACK_DIR / "metrics.json"
    metrics = {}
    if metrics_file.exists():
        try:
            with open(metrics_file) as f:
                metrics = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    data = {
        "total_outcomes": len(items),
        "outcome_distribution": outcomes,
        "metrics": metrics,
    }
    print(json.dumps({"data": data, "meta": _meta("feedback", len(items))}, indent=2))


# === Specialists ===

def _discover_specialists():
    """Discover installed specialist plugins by checking for specialist.json."""
    specialists = []
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"

    if not cache_base.exists():
        return specialists

    for plugin_dir in sorted(cache_base.iterdir()):
        if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
            continue

        # Find latest version
        versions = sorted(plugin_dir.iterdir(), reverse=True)
        if not versions:
            continue
        latest = versions[0]

        spec_path = latest / ".claude-plugin" / "specialist.json"
        if not spec_path.exists():
            continue

        try:
            with open(spec_path) as f:
                spec = json.load(f)
            specialists.append({
                "name": plugin_dir.name,
                "role": spec.get("role", ""),
                "enhances": spec.get("enhances", []),
                "persona": spec.get("persona", {}).get("name", ""),
                "version": latest.name,
            })
        except (json.JSONDecodeError, OSError):
            continue

    return specialists


def cmd_list_specialists(args):
    """List installed specialists."""
    specialists = _discover_specialists()
    total = len(specialists)
    data = specialists[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("specialists", total, args.limit, args.offset)}, indent=2))


def cmd_get_specialist(name, args):
    """Get a specific specialist's details."""
    specialists = _discover_specialists()
    match = next((s for s in specialists if s["name"] == name), None)
    if not match:
        _error("Specialist not found", "NOT_FOUND", resource="specialists", id=name)

    print(json.dumps({"data": match, "meta": _meta("specialists", 1)}, indent=2))


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Wicked Crew Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in ("list", "get", "search", "stats", "create", "update", "delete"):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source")
        if verb in ("get", "update", "delete"):
            sub.add_argument("id", nargs="?", help="Resource ID/name")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--project", help="Project name (for phases)")
        sub.add_argument("--query", help="Search query")
        sub.add_argument("--filter", help="Filter expression")

    args = parser.parse_args()

    if not args.verb:
        parser.print_help()
        sys.exit(1)

    if args.source not in VALID_SOURCES:
        _error(f"Unknown source: {args.source}", "INVALID_SOURCE",
               source=args.source, valid=list(VALID_SOURCES))

    # Route to handler
    if args.verb == "list":
        handlers = {
            "projects": cmd_list_projects,
            "phases": cmd_list_phases,
            "signals": cmd_list_signals,
            "feedback": cmd_list_feedback,
            "specialists": cmd_list_specialists,
        }
        handlers[args.source](args)

    elif args.verb == "get":
        if not args.id:
            _error("ID required for get verb", "MISSING_ID")
        handlers = {
            "projects": lambda a: cmd_get_project(a.id, a),
            "phases": lambda a: cmd_get_phase(a.id, a),
            "specialists": lambda a: cmd_get_specialist(a.id, a),
        }
        if args.source not in handlers:
            _error(f"Get not supported for {args.source}", "UNSUPPORTED_VERB")
        handlers[args.source](args)

    elif args.verb == "search":
        handlers = {
            "signals": cmd_search_signals,
        }
        if args.source not in handlers:
            _error(f"Search not supported for {args.source}", "UNSUPPORTED_VERB")
        handlers[args.source](args)

    elif args.verb == "stats":
        handlers = {
            "signals": cmd_stats_signals,
            "feedback": cmd_stats_feedback,
        }
        if args.source not in handlers:
            _error(f"Stats not supported for {args.source}", "UNSUPPORTED_VERB")
        handlers[args.source](args)

    elif args.verb == "create":
        handlers = {
            "projects": cmd_create_project,
        }
        if args.source not in handlers:
            _error(f"Create not supported for {args.source}", "UNSUPPORTED_VERB")
        handlers[args.source](args)

    elif args.verb == "update":
        if not args.id:
            _error("ID required for update verb", "MISSING_ID")
        handlers = {
            "projects": lambda a: cmd_update_project(a.id, a),
            "phases": lambda a: cmd_update_phase(a.id, a),
        }
        if args.source not in handlers:
            _error(f"Update not supported for {args.source}", "UNSUPPORTED_VERB")
        handlers[args.source](args)

    elif args.verb == "delete":
        _error("Delete not supported for crew resources (use archive instead)", "UNSUPPORTED_VERB")


if __name__ == "__main__":
    main()
