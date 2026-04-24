#!/usr/bin/env python3
"""Assemble the current_chain input for facilitator re-evaluation mode.

Usage:
    current_chain.py <chain-id> [--project-dir PATH] [--pretty]

Reads native task JSON files under ${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/,
filters to those whose metadata.chain_id matches, and emits a structured dict
suitable for passing as the ``current_chain`` input to the
``wicked-garden:propose-process`` skill in re-evaluate mode.

Output shape:
    {
      "chain_id": "<chain>",
      "tasks": [
        {"id", "title", "status", "phase", "event_type",
         "evidence_required", "blockedBy"}
      ],
      "counts": {"pending", "in_progress", "completed", "blocked", "total"},
      "evidence_manifests": [<list of paths discovered under project_dir>]
    }

When --project-dir is provided, the script looks under ``phases/*/evidence/``
and surfaces any manifest-like files (report.md, *.json, *.txt).

Zero external dependencies — stdlib only. Safe to invoke from shell or a hook.

Issue #431.
"""

import argparse
import json
import sys
from pathlib import Path


_TERMINAL = {"completed", "blocked"}
_EVIDENCE_HINTS = ("report.md", ".json", ".txt", "-results.", "manifest")


def _collect_tasks(chain_id: str) -> list[dict]:
    """Return task dicts whose metadata.chain_id matches.

    Routing: WG_DAEMON_ENABLED=false → direct file scan (unchanged);
             WG_DAEMON_ENABLED=true  → daemon HTTP with fallback (#596 v8-PR-2).
    """
    try:
        from crew._task_reader import collect_tasks_for_chain  # type: ignore[import]
        raw = collect_tasks_for_chain(chain_id)
    except Exception:
        raw = []

    out = []
    for item in raw:
        meta = item.get("metadata") or {}
        out.append({
            "id": item.get("id", ""),
            "title": item.get("subject") or item.get("title") or "<untitled>",
            "status": item.get("status") or "unknown",
            "phase": meta.get("phase"),
            "event_type": meta.get("event_type"),
            "evidence_required": meta.get("evidence_required") or [],
            "blockedBy": item.get("blockedBy") or [],
        })
    return out


def _count_by_status(tasks: list[dict]) -> dict:
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "blocked": 0, "total": len(tasks)}
    for t in tasks:
        status = t.get("status", "pending")
        if status in counts:
            counts[status] += 1
    return counts


def _discover_evidence(project_dir: Path) -> list[str]:
    """List evidence-manifest-looking files under phases/*/evidence/."""
    out = []
    if not project_dir.exists():
        return out
    for phase_dir in (project_dir / "phases").glob("*"):
        evidence_dir = phase_dir / "evidence"
        if not evidence_dir.is_dir():
            continue
        for item in evidence_dir.rglob("*"):
            if not item.is_file():
                continue
            name = item.name.lower()
            if any(hint in name for hint in _EVIDENCE_HINTS):
                out.append(str(item.relative_to(project_dir)))
    return sorted(out)


def assemble(chain_id: str, project_dir: Path | None = None) -> dict:
    tasks = _collect_tasks(chain_id)
    result = {
        "chain_id": chain_id,
        "tasks": tasks,
        "counts": _count_by_status(tasks),
        "evidence_manifests": [],
    }
    if project_dir is not None:
        result["evidence_manifests"] = _discover_evidence(project_dir)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble current_chain data for re-eval.")
    parser.add_argument("chain_id", help="Chain id to scan for (e.g. {slug}.root)")
    parser.add_argument("--project-dir", help="Optional crew project dir for evidence discovery")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve() if args.project_dir else None
    data = assemble(args.chain_id, project_dir)
    indent = 2 if args.pretty else None
    sys.stdout.write(json.dumps(data, indent=indent, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
