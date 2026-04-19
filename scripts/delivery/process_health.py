#!/usr/bin/env python3
"""process_health.py — render the /wicked-garden:delivery:process-health surface.

Collects the facilitator-context dict from ``process_memory`` plus a few
extra summary rollups (kaizen by status, aging alerts) and prints a
human-readable report, JSON, or both.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT))

from delivery import process_memory as pm


def _rollup(memory: dict) -> dict:
    """Summarize kaizen + AIs for display."""
    kaizen = memory.get("kaizen") or []
    ais = memory.get("action_items") or []

    kaizen_by_status: dict[str, int] = {}
    for item in kaizen:
        status = item.get("status") or "unknown"
        kaizen_by_status[status] = kaizen_by_status.get(status, 0) + 1

    ais_by_status: dict[str, int] = {}
    for ai in ais:
        status = ai.get("status") or "unknown"
        ais_by_status[status] = ais_by_status.get(status, 0) + 1

    aging = [
        ai
        for ai in ais
        if ai.get("status") in ("open", "in-progress")
        and int(ai.get("age_sessions", 1)) >= pm.AGING_SESSION_THRESHOLD
    ]

    return {
        "kaizen_total": len(kaizen),
        "kaizen_by_status": kaizen_by_status,
        "action_items_total": len(ais),
        "action_items_by_status": ais_by_status,
        "aging_count": len(aging),
        "aging_items": aging,
    }


def render_report(project: str, memory: dict, rollup: dict) -> str:
    """Return a human-readable report body."""
    lines: list[str] = []
    lines.append(f"# Process Health — {project}")
    lines.append("")
    narrative = (memory.get("narrative") or "").strip()
    if narrative:
        lines.append("## Narrative")
        lines.append("")
        lines.append(narrative)
        lines.append("")

    lines.append("## Kaizen Backlog")
    lines.append("")
    lines.append(f"- Total items: **{rollup['kaizen_total']}**")
    if rollup["kaizen_by_status"]:
        status_parts = [
            f"{status}={count}"
            for status, count in sorted(rollup["kaizen_by_status"].items())
        ]
        lines.append(f"- By status: {', '.join(status_parts)}")
    lines.append("")

    lines.append("## Action Items")
    lines.append("")
    lines.append(f"- Total: **{rollup['action_items_total']}**")
    if rollup["action_items_by_status"]:
        status_parts = [
            f"{status}={count}"
            for status, count in sorted(rollup["action_items_by_status"].items())
        ]
        lines.append(f"- By status: {', '.join(status_parts)}")
    lines.append("")

    if rollup["aging_count"]:
        lines.append(
            f"## Aging Alerts (>= {pm.AGING_SESSION_THRESHOLD} sessions)"
        )
        lines.append("")
        lines.append("| ID | Title | Owner | Age | Status |")
        lines.append("|----|-------|-------|-----|--------|")
        for ai in rollup["aging_items"]:
            lines.append(
                f"| {ai.get('id', '')} | {ai.get('title', '')} "
                f"| {ai.get('owner') or '—'} | {ai.get('age_sessions', 1)} "
                f"| {ai.get('status', '')} |"
            )
        lines.append("")
    else:
        lines.append("## Aging Alerts")
        lines.append("")
        lines.append("_No action items have aged beyond threshold._")
        lines.append("")

    timeline = memory.get("pass_rate_timeline") or []
    if timeline:
        lines.append("## Recent Gate Pass-Rate")
        lines.append("")
        for sample in timeline[-5:]:
            lines.append(
                f"- {sample.get('recorded_at', '')}: "
                f"{sample.get('pass_rate', 0.0):.2f} "
                f"(session {sample.get('session_id') or '—'})"
            )
        lines.append("")

    lines.append("## Markdown artifact")
    lines.append("")
    lines.append(f"- `{pm._memory_md_path(project)}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render process-health summary for a crew project."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--format",
        default="text",
        choices=("text", "json", "both"),
        help="Output format. 'both' prints JSON to stderr and text to stdout.",
    )
    args = parser.parse_args(argv)

    memory = pm.load_memory(args.project)
    rollup = _rollup(memory)
    context = pm.facilitator_context(args.project)
    # Merge rollup into context for JSON consumers.
    payload = {
        "project": args.project,
        "context": context,
        "rollup": rollup,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return 0

    report = render_report(args.project, memory, rollup)
    if args.format == "both":
        sys.stderr.write(json.dumps(payload, indent=2) + "\n")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
