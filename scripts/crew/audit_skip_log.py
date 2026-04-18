#!/usr/bin/env python3
"""Audit skip-reeval-log.json entries across all phases (D9, AC-16).

Reads ``phases/*/skip-reeval-log.json`` from a project directory and returns
aggregated entries.  Entries without a ``resolved_at`` field are considered
unresolved and trigger a CONDITIONAL verdict in the final-audit gate.

Usage (as a module):
    from audit_skip_log import scan
    unresolved = scan(project_dir)

Usage (as a CLI):
    audit_skip_log.py <project-dir>

Stdlib-only.  No external dependencies.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


def scan(project_dir: "str | Path") -> List[Dict[str, Any]]:
    """Scan all phase directories for skip-reeval-log.json entries.

    Returns only unresolved entries (those lacking a non-empty ``resolved_at``
    field).  An empty list means no outstanding skips.

    Args:
        project_dir: Root directory of the crew project.  Must contain a
                     ``phases/`` subdirectory.

    Returns:
        List of unresolved skip-log entry dicts, each augmented with a
        ``_source_phase`` key indicating which phase the entry came from.
    """
    project_dir = Path(project_dir)
    phases_dir = project_dir / "phases"
    if not phases_dir.is_dir():
        return []

    unresolved: List[Dict[str, Any]] = []

    for phase_dir in sorted(phases_dir.iterdir()):
        if not phase_dir.is_dir():
            continue
        log_file = phase_dir / "skip-reeval-log.json"
        if not log_file.exists():
            continue
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Malformed or unreadable — treat as "entry present but unresolved"
            # so final-audit reviewers know to investigate
            unresolved.append({
                "_source_phase": phase_dir.name,
                "_parse_error": True,
                "note": f"Could not parse {log_file}",
            })
            continue

        # The log may be a single entry (dict) or a list of entries
        entries: List[Dict[str, Any]] = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            resolved_at = entry.get("resolved_at")
            if not resolved_at or not str(resolved_at).strip():
                augmented = dict(entry)
                augmented["_source_phase"] = phase_dir.name
                unresolved.append(augmented)

    return unresolved


def _summarise(entries: List[Dict[str, Any]]) -> str:
    """Return a human-readable summary for display or gate directives."""
    if not entries:
        return "No unresolved skip-reeval entries found."
    lines = [f"Found {len(entries)} unresolved skip-reeval log entry/entries:"]
    for entry in entries:
        phase = entry.get("_source_phase", "unknown")
        reason = entry.get("reason") or entry.get("note") or "(no reason recorded)"
        skipped_at = entry.get("skipped_at") or "(no timestamp)"
        lines.append(f"  [{phase}] skipped_at={skipped_at} reason={reason!r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <project-dir>",
            file=sys.stderr,
        )
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    unresolved = scan(project_dir)
    print(_summarise(unresolved))
    # Exit 1 if there are unresolved entries (useful for CI checks)
    sys.exit(1 if unresolved else 0)


if __name__ == "__main__":
    main()
