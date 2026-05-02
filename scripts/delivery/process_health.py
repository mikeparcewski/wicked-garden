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
from delivery import drift as drift_mod
from delivery import telemetry as tm


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


def _spc_section(project: str) -> dict:
    """Build the SPC drift summary for a project (issue #719).

    Classifies the gate_pass_rate timeline + per-gate min_score series,
    surfaces the warmup status, and lists recent persisted flags. Always
    returns a dict — empty fields when telemetry hasn't accumulated yet.
    """
    timeline = tm.read_timeline(project)
    classifications: list[dict] = []
    # Always classify the headline metric.
    headline = drift_mod.classify(timeline, "gate_pass_rate")
    classifications.append(headline)
    # Per-(phase, tier) min_score series — one classification per gate slot
    # observed in the most recent record. We synthesize a synthetic series by
    # pulling each slot's min_score from each timeline record.
    if timeline:
        latest_slots = (timeline[-1].get("metrics") or {}).get("gate_breakdown") or {}
        for slot_key in sorted(latest_slots.keys()):
            synth: list[dict] = []
            for rec in timeline:
                gb = (rec.get("metrics") or {}).get("gate_breakdown") or {}
                slot = gb.get(slot_key) or {}
                min_score = slot.get("min_score")
                if isinstance(min_score, (int, float)):
                    synth.append({"metrics": {f"{slot_key}.min_score": float(min_score)}})
            if len(synth) >= 5:
                classifications.append(
                    drift_mod.classify(synth, f"{slot_key}.min_score")
                )
    flags = drift_mod.list_recent_flags(project, limit=10)
    # PR #730 review: warmup gate inside drift.classify() counts numeric samples
    # (skipping records with None for the metric). Mirror that here so the
    # report doesn't show "satisfied" while the headline classification still
    # reports insufficient_warmup=true. headline_metric_samples is the most
    # honest count to surface — derived from the headline classification's
    # session_count (which already skipped None).
    headline_classification = classifications[0] if classifications else {}
    metric_sample_count = headline_classification.get("session_count", len(timeline))
    return {
        "sample_count": metric_sample_count,
        "timeline_length": len(timeline),
        "warmup_min_samples": drift_mod.WARMUP_MIN_SAMPLES,
        "warmup_satisfied": metric_sample_count >= drift_mod.WARMUP_MIN_SAMPLES,
        "classifications": classifications,
        "recent_flags": flags,
    }


def render_spc(spc: dict) -> str:
    """Format the SPC section as a markdown block."""
    lines = ["## SPC Drift", ""]
    lines.append(
        f"- Samples: **{spc['sample_count']}** "
        f"(warmup threshold: {spc['warmup_min_samples']})"
    )
    lines.append(
        f"- Warmup: **{'satisfied' if spc['warmup_satisfied'] else 'PENDING'}**"
    )
    lines.append("")
    lines.append("### Classifications")
    lines.append("")
    for cls in spc["classifications"]:
        zone = cls.get("zone", "unknown")
        metric = cls.get("metric", "?")
        n = cls.get("session_count", 0)
        rules = ", ".join(cls.get("we_rules") or []) or "—"
        lines.append(
            f"- `{metric}` n={n} zone=**{zone}** drift={cls.get('drift', False)} "
            f"rules=[{rules}]"
        )
    lines.append("")
    flags = spc.get("recent_flags") or []
    if flags:
        lines.append("### Recent flags")
        lines.append("")
        lines.append("| Recorded | Metric | Rule | Severity |")
        lines.append("|----------|--------|------|----------|")
        for f in flags:
            lines.append(
                f"| {f.get('recorded_at', '—')} | {f.get('metric', '—')} "
                f"| {f.get('rule', '—')} | {f.get('severity', '—')} |"
            )
    else:
        lines.append("_No SPC flags persisted yet._")
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
    parser.add_argument(
        "--spc",
        action="store_true",
        help="Include SPC drift section (issue #719). Default off for back-compat.",
    )
    args = parser.parse_args(argv)

    memory = pm.load_memory(args.project)
    rollup = _rollup(memory)
    context = pm.facilitator_context(args.project)
    spc = _spc_section(args.project) if args.spc else None
    # Merge rollup into context for JSON consumers.
    payload = {
        "project": args.project,
        "context": context,
        "rollup": rollup,
    }
    if spc is not None:
        payload["spc"] = spc

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return 0

    report = render_report(args.project, memory, rollup)
    if spc is not None:
        report += "\n" + render_spc(spc)
    if args.format == "both":
        sys.stderr.write(json.dumps(payload, indent=2) + "\n")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
