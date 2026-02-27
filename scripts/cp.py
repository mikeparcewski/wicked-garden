#!/usr/bin/env python3
"""
cp.py — Generic CLI proxy for the wicked-control-plane.

Single entry point that replaces all domain-specific api.py files.
Routes any {domain} {source} {verb} to the CP's REST API.

Usage:
    python3 cp.py {domain} {source} {verb} [id] [--param value ...]

Examples:
    python3 cp.py memory memories list --limit 10
    python3 cp.py memory memories search --query "patterns"
    python3 cp.py memory memories get abc123
    python3 cp.py memory memories create < payload.json
    python3 cp.py memory memories update abc123 < payload.json
    python3 cp.py memory memories delete abc123
    python3 cp.py kanban tasks list --project_id my-proj
    python3 cp.py kanban tasks stats
    python3 cp.py crew projects archive my-project
    python3 cp.py knowledge graph hotspots --limit 20
    python3 cp.py knowledge graph traverse abc123 --depth 2

    # Special commands:
    python3 cp.py manifest                                # full manifest
    python3 cp.py manifest {domain} {source} {verb}       # endpoint detail
    python3 cp.py query "SELECT * FROM memories LIMIT 5"  # direct SQL

Domain names: accepts either plugin names (wicked-mem, wicked-kanban) or
CP domain names (memory, kanban). Normalized automatically.

Output: JSON to stdout (the CP's {data, meta} envelope).
Errors: JSON to stderr, exit code 1.
"""

import json
import sys
from pathlib import Path

# Resolve _control_plane from the same scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _control_plane import get_client


def _error(message: str, code: str = "ERROR") -> None:
    print(json.dumps({"error": message, "code": code}), file=sys.stderr)
    sys.exit(1)


def _read_stdin() -> dict:
    """Read JSON payload from stdin for write operations."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _error("Invalid JSON on stdin", "INVALID_INPUT")
        return {}  # unreachable


def main() -> None:
    args = sys.argv[1:]

    if not args:
        _error("Usage: cp.py {domain} {source} {verb} [id] [--param value ...]")

    # Special commands
    if args[0] == "manifest":
        cp = get_client()
        if len(args) == 1:
            result = cp.manifest()
        elif len(args) >= 4:
            result = cp.manifest_detail(args[1], args[2], args[3])
        else:
            _error("Usage: cp.py manifest [domain source verb]")
            return
        if result is None:
            _error("Control plane unreachable", "CP_UNAVAILABLE")
        print(json.dumps(result, indent=2))
        return

    if args[0] == "query":
        if len(args) < 2:
            _error("Usage: cp.py query 'SELECT ...'")
        cp = get_client()
        result = cp.query(" ".join(args[1:]))
        if result is None:
            _error("Control plane unreachable", "CP_UNAVAILABLE")
        print(json.dumps(result, indent=2))
        return

    # Standard data API: {domain} {source} {verb} [id] [--param value ...]
    if len(args) < 3:
        _error("Usage: cp.py {domain} {source} {verb} [id] [--param value ...]")

    domain, source, verb = args[0], args[1], args[2]
    rest = args[3:]

    # Parse [id] and [--param value ...] from remaining args
    record_id = None
    params: dict[str, str] = {}

    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg.startswith("--"):
            key = arg.lstrip("-").replace("-", "_")
            if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                params[key] = rest[i + 1]
                i += 2
            else:
                params[key] = "true"
                i += 1
        else:
            if record_id is None:
                record_id = arg
            i += 1

    # Read payload from stdin for write verbs
    payload = None
    if verb in ("create", "update", "bulk-update", "bulk-delete", "evaluate",
                "ingest", "capture"):
        payload = _read_stdin()
        if not payload and verb in ("create", "evaluate", "ingest"):
            _error(f"Verb '{verb}' requires JSON payload on stdin", "MISSING_PAYLOAD")

    cp = get_client()
    result = cp.request(
        domain, source, verb,
        id=record_id,
        payload=payload,
        params=params if params else None,
    )

    if result is None:
        _error("Control plane request failed", "CP_ERROR")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
