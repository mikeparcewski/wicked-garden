#!/usr/bin/env python3
"""
Outcome Feedback Loop + Statistical Validation for wicked-crew.

Records project outcomes, tracks signal accuracy, and generates
recommendations for keyword weight adjustments.

Storage: via StorageManager("wicked-crew") → control plane with local fallback
- feedback source: Per-project outcome records
- metrics source: Running per-signal-category metrics

Usage:
  feedback.py record --project NAME --outcome success|partial|failure \
                     --satisfaction 1-5 [--specialists-used spec1,spec2]
  feedback.py report                    # Signal accuracy report
  feedback.py suggest                   # Keyword weight adjustment suggestions
  feedback.py dashboard                 # Markdown dashboard output
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager

_sm = StorageManager("wicked-crew")

# Import SIGNAL_TO_SPECIALISTS for validation ground truth
# This is the only allowed import from smart_decisioning (no circular dep)
try:
    from smart_decisioning import SIGNAL_TO_SPECIALISTS, SIGNAL_KEYWORDS
except ImportError:
    _script_dir = Path(__file__).parent
    sys.path.insert(0, str(_script_dir))
    from smart_decisioning import SIGNAL_TO_SPECIALISTS, SIGNAL_KEYWORDS


@dataclass
class OutcomeRecord:
    """A recorded project outcome for feedback tracking."""
    project_name: str
    timestamp: str
    signals_predicted: List[str]
    signal_confidences: Dict[str, float]
    complexity_predicted: int
    specialists_routed: List[str]
    specialists_used: List[str]
    outcome: str  # success, partial, failure
    satisfaction: int  # 1-5
    notes: str = ""


def record_outcome(record: OutcomeRecord) -> Dict:
    """Store an outcome record via StorageManager. Returns dict with memory_payload.

    The memory_payload is returned for the CALLER (a Claude command) to store
    via /wicked-mem:store using Claude's native tool system — scripts should
    never call other plugins directly.
    """
    created = _sm.create("feedback", asdict(record))

    # Build reasoning narrative for the caller to store to memory
    missed = set(record.specialists_routed) - set(record.specialists_used)
    unexpected = set(record.specialists_used) - set(record.specialists_routed)

    reasoning_parts = [
        f"Project '{record.project_name}' outcome: {record.outcome} (satisfaction: {record.satisfaction}/5)",
        f"Predicted signals: {', '.join(record.signals_predicted) or 'none'}",
        f"Predicted complexity: {record.complexity_predicted}",
        f"Routed specialists: {', '.join(record.specialists_routed) or 'none'}",
        f"Actually used: {', '.join(record.specialists_used) or 'none'}",
    ]
    if missed:
        reasoning_parts.append(f"ROUTED BUT UNUSED (possible false positive): {', '.join(missed)}")
    if unexpected:
        reasoning_parts.append(f"USED BUT NOT ROUTED (possible false negative): {', '.join(unexpected)}")
    if record.notes:
        reasoning_parts.append(f"Notes: {record.notes}")

    is_significant = (
        record.outcome == "failure"
        or bool(missed)
        or bool(unexpected)
    )

    return {
        "id": created.get("id") if created else None,
        "memory_payload": {
            "title": f"Project outcome: {record.project_name} ({record.outcome})",
            "content": " | ".join(reasoning_parts),
            "type": "episodic",
            "tags": f"crew,feedback,outcome,{record.outcome}",
            "importance": "high" if is_significant else "medium",
        },
    }


def load_outcomes() -> List[OutcomeRecord]:
    """Load all outcome records via StorageManager."""
    items = _sm.list("feedback")
    records = []
    for data in items:
        # Strip SM-added fields before constructing OutcomeRecord
        filtered = {k: v for k, v in data.items()
                    if k in OutcomeRecord.__dataclass_fields__}
        try:
            records.append(OutcomeRecord(**filtered))
        except TypeError:
            continue
    return records


def compute_signal_metrics(outcomes: List[OutcomeRecord]) -> Dict[str, Dict]:
    """Compute per-signal-category precision/recall.

    Ground truth heuristic:
    - predicted = signal was in signals_predicted
    - needed = a specialist mapped to that signal was in specialists_used
    """
    metrics = {}
    for category in SIGNAL_KEYWORDS:
        tp = fp = fn = tn = 0
        mapped_specialists = SIGNAL_TO_SPECIALISTS.get(category, set())

        for record in outcomes:
            predicted = category in record.signals_predicted
            needed = any(
                spec in record.specialists_used
                for spec in mapped_specialists
            )
            if predicted and needed:
                tp += 1
            elif predicted and not needed:
                fp += 1
            elif not predicted and needed:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[category] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "samples": len(outcomes),
            "health": "good" if f1 >= 0.5 else ("weak" if f1 >= 0.3 else "poor"),
        }

    return metrics


def save_metrics(metrics: Dict[str, Dict]) -> None:
    """Save metrics via StorageManager (upsert by 'latest' id)."""
    existing = _sm.get("metrics", "latest")
    if existing:
        _sm.update("metrics", "latest", {"categories": metrics})
    else:
        _sm.create("metrics", {"id": "latest", "categories": metrics})


def generate_suggestions(metrics: Dict[str, Dict], min_samples: int = 10) -> List[Dict]:
    """Generate keyword weight adjustment suggestions.

    Only generates suggestions after min_samples projects to avoid overfitting.
    """
    suggestions = []
    sample_count = next(iter(metrics.values()), {}).get("samples", 0)

    if sample_count < min_samples:
        return [{
            "type": "info",
            "message": f"Need {min_samples - sample_count} more projects before generating suggestions. "
                       f"Current: {sample_count}/{min_samples}",
        }]

    for category, data in metrics.items():
        if data["precision"] < 0.5 and (data["tp"] + data["fp"]) >= 3:
            suggestions.append({
                "type": "precision_low",
                "category": category,
                "precision": data["precision"],
                "message": f"'{category}' signal fires too often without specialist use. "
                           f"Consider narrowing keywords or raising threshold.",
                "action": "narrow_keywords",
            })

        if data["recall"] < 0.3 and (data["tp"] + data["fn"]) >= 3:
            suggestions.append({
                "type": "recall_low",
                "category": category,
                "recall": data["recall"],
                "message": f"'{category}' signal misses projects that need its specialists. "
                           f"Consider adding keywords or using semantic detection.",
                "action": "add_keywords",
            })

    if not suggestions:
        suggestions.append({
            "type": "healthy",
            "message": f"All signals performing within acceptable range ({sample_count} samples).",
        })

    return suggestions


def format_dashboard(metrics: Dict[str, Dict]) -> str:
    """Format metrics as a markdown dashboard."""
    lines = ["# Signal Health Dashboard", ""]
    lines.append("| Category | Precision | Recall | F1 | Health | Samples |")
    lines.append("|----------|-----------|--------|-----|--------|---------|")

    for category in sorted(metrics.keys()):
        data = metrics[category]
        health_icon = {"good": "OK", "weak": "WARN", "poor": "BAD"}.get(data["health"], "?")
        lines.append(
            f"| {category} | {data['precision']:.1%} | {data['recall']:.1%} | "
            f"{data['f1']:.1%} | {health_icon} | {data['samples']} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Outcome feedback for wicked-crew signals")
    sub = parser.add_subparsers(dest="command")

    # record
    rec = sub.add_parser("record", help="Record a project outcome")
    rec.add_argument("--project", required=True, help="Project name")
    rec.add_argument("--outcome", required=True, choices=["success", "partial", "failure"])
    rec.add_argument("--satisfaction", type=int, required=True, choices=range(1, 6))
    rec.add_argument("--specialists-used", default="", help="Comma-separated specialists used")
    rec.add_argument("--notes", default="", help="Additional notes")
    rec.add_argument("--json", action="store_true")

    # report
    sub.add_parser("report", help="Show signal accuracy report")

    # suggest
    sug = sub.add_parser("suggest", help="Suggest keyword adjustments")
    sug.add_argument("--min-samples", type=int, default=10)

    # dashboard
    sub.add_parser("dashboard", help="Markdown dashboard output")

    args = parser.parse_args()

    if args.command == "record":
        # Load project state to get predicted signals
        data = _sm.get("projects", args.project)

        signals_predicted = []
        signal_confidences: Dict[str, float] = {}
        complexity_predicted = 0
        specialists_routed = []

        if data:
            signals_predicted = data.get("signals_detected", [])
            complexity_predicted = data.get("complexity_score", 0)
            specialists_routed = data.get("specialists_recommended", [])

        specialists_used = [s.strip() for s in args.specialists_used.split(",") if s.strip()]

        record = OutcomeRecord(
            project_name=args.project,
            timestamp=datetime.now(timezone.utc).isoformat(),
            signals_predicted=signals_predicted,
            signal_confidences=signal_confidences,
            complexity_predicted=complexity_predicted,
            specialists_routed=specialists_routed,
            specialists_used=specialists_used,
            outcome=args.outcome,
            satisfaction=args.satisfaction,
            notes=args.notes,
        )

        result = record_outcome(record)
        if args.json:
            print(json.dumps({"recorded": True, **result}))
        else:
            print(f"Outcome recorded for {args.project} (id: {result.get('id', 'n/a')})")

    elif args.command == "report":
        outcomes = load_outcomes()
        if not outcomes:
            print("No outcomes recorded yet. Use 'feedback.py record' after project completion.")
            return

        metrics = compute_signal_metrics(outcomes)
        save_metrics(metrics)

        for cat, data in sorted(metrics.items()):
            print(f"{cat}: precision={data['precision']:.1%} recall={data['recall']:.1%} "
                  f"f1={data['f1']:.1%} [{data['health']}]")

    elif args.command == "suggest":
        outcomes = load_outcomes()
        metrics = compute_signal_metrics(outcomes)
        suggestions = generate_suggestions(metrics, min_samples=args.min_samples)

        for s in suggestions:
            print(f"[{s['type']}] {s['message']}")

    elif args.command == "dashboard":
        outcomes = load_outcomes()
        if not outcomes:
            print("No outcomes recorded yet.")
            return
        metrics = compute_signal_metrics(outcomes)
        save_metrics(metrics)
        print(format_dashboard(metrics))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
