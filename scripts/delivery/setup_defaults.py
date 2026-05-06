#!/usr/bin/env python3
"""setup_defaults.py — defaults and helpers for /wicked-garden:delivery:setup.

Holds the cost-model presets, sensitivity presets, and the
complexity-cost scaling helper that used to live inline in the slash
command body. Exposes a tiny CLI so the slash command can fetch the
values without hard-coding them in markdown.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys

# Cost-model presets keyed by the four user-facing labels in delivery:setup Q3.
COST_MODEL_DEFAULTS: dict[str, dict[str, float]] = {
    "ai_tokens": {"P0": 2.50, "P1": 1.50, "P2": 0.75, "P3": 0.40},
    "dev_hours": {"P0": 8.0, "P1": 4.0, "P2": 2.0, "P3": 1.0},
    "story_points": {"P0": 13, "P1": 8, "P2": 5, "P3": 3},
    # custom: caller collects values directly from the user
    "custom": {},
}

# Commentary sensitivity presets used by section 3 / section 6.
# completion / cycle_time_p95 / throughput / aging_low / aging_high / cooldown_minutes
SENSITIVITY_PRESETS: dict[str, dict[str, float]] = {
    "conservative": {
        "completion_rate": 0.20,
        "cycle_time_p95": 0.40,
        "throughput": 0.30,
        "aging_low": 15,
        "aging_high": 30,
        "cooldown_minutes": 30,
    },
    "balanced": {
        "completion_rate": 0.10,
        "cycle_time_p95": 0.25,
        "throughput": 0.20,
        "aging_low": 10,
        "aging_high": 20,
        "cooldown_minutes": 15,
    },
    "aggressive": {
        "completion_rate": 0.05,
        "cycle_time_p95": 0.15,
        "throughput": 0.10,
        "aging_low": 5,
        "aging_high": 15,
        "cooldown_minutes": 10,
    },
}


def scale_complexity_costs(priority_costs: dict[str, float]) -> dict[str, float]:
    """Generate complexity 0-7 costs scaled from a priority-cost dict.

    Linear interpolation: complexity 0 -> ~20% of P3, complexity 7 -> ~150% of P0.
    """
    if not priority_costs:
        return {}
    p0 = float(priority_costs.get("P0", 0))
    p3 = float(priority_costs.get("P3", 0))
    low = p3 * 0.20
    high = p0 * 1.50
    span = high - low
    return {str(i): round(low + (span * (i / 7)), 4) for i in range(8)}


def build_settings(
    sensitivity: str,
    rolling_window_days: int,
    aging_threshold_days: int,
) -> dict:
    """Compose the settings.json payload from a sensitivity preset."""
    preset = SENSITIVITY_PRESETS[sensitivity]
    return {
        "rolling_window_days": rolling_window_days,
        "aging_threshold_days": aging_threshold_days,
        "commentary": {
            "sensitivity": sensitivity,
            "cooldown_minutes": preset["cooldown_minutes"],
            "thresholds": {
                "completion_rate": preset["completion_rate"],
                "cycle_time_p95": preset["cycle_time_p95"],
                "throughput": preset["throughput"],
                "aging_low": preset["aging_low"],
                "aging_high": preset["aging_high"],
            },
        },
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cost-defaults", help="Print COST_MODEL_DEFAULTS as JSON")
    sub.add_parser("sensitivity-presets", help="Print SENSITIVITY_PRESETS as JSON")
    scale = sub.add_parser("scale-complexity", help="Scale complexity 0-7 costs from priority costs JSON")
    scale.add_argument("priority_json", help='JSON like {"P0":2.5,"P1":1.5,"P2":0.75,"P3":0.4}')
    settings = sub.add_parser("build-settings", help="Compose the settings.json payload")
    settings.add_argument("sensitivity", choices=sorted(SENSITIVITY_PRESETS))
    settings.add_argument("--rolling-window-days", type=int, default=14)
    settings.add_argument("--aging-threshold-days", type=int, default=7)
    args = parser.parse_args()
    if args.cmd == "cost-defaults":
        json.dump(COST_MODEL_DEFAULTS, sys.stdout, indent=2)
    elif args.cmd == "sensitivity-presets":
        json.dump(SENSITIVITY_PRESETS, sys.stdout, indent=2)
    elif args.cmd == "scale-complexity":
        priority = json.loads(args.priority_json)
        json.dump(scale_complexity_costs(priority), sys.stdout, indent=2)
    elif args.cmd == "build-settings":
        json.dump(
            build_settings(args.sensitivity, args.rolling_window_days, args.aging_threshold_days),
            sys.stdout,
            indent=2,
        )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
