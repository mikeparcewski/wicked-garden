#!/usr/bin/env python3
"""scope_delta.py — Compute scope-delta metrics for the clarify HITL gate.

Issue #847: the facilitator's clarify HITL gate previously fired only on
intent ambiguity (the six triggers in ``skills/propose-process/refs/
ambiguity.md``). It missed the failure where the rubric silently
expanded a 24-issue wave plan to absorb a 1M-insertion sibling project
because no trigger looked at scope-size deltas.

This helper computes the four scope-delta metrics that drive the
seventh trigger added in #847:

- ``new_items``: items in the proposed plan not present in the
  baseline plan (matched by id).
- ``oversize_factor``: ratio of the largest new item's size to the
  median size of items already in the baseline plan. Trips the trigger
  at >= 3.0.
- ``total_size_ratio``: total proposed-plan size / baseline-plan size.
  Trips the trigger at >= 2.0.
- ``epic_or_project_added``: True iff any new item carries a label
  matching the epic/project regex.

Stdlib-only; designed for the propose-process facilitator agent or
the slim caller to consume programmatically. Returns a dict; the
facilitator agent should surface the trigger as a clarifying question
when any threshold is crossed (per ambiguity.md trigger #7).

The "size" of an item is whatever the caller measures consistently —
LOC, file count, sub-task count, or a fused score. The helper does not
prescribe a unit; it just compares apples to apples.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, Iterable, List, Optional


# Issue #847: items labeled with these patterns are project-sized by
# convention and must not be silently absorbed into a wave plan.
EPIC_LABEL_PATTERNS = (
    re.compile(r"^epic$", re.IGNORECASE),
    re.compile(r"^project$", re.IGNORECASE),
    re.compile(r"^large$", re.IGNORECASE),
    re.compile(r"^xlarge$", re.IGNORECASE),
    re.compile(r"^xxl$", re.IGNORECASE),
)

# Threshold defaults — surfaced as constants so callers can override
# but the trigger doctrine in ambiguity.md stays in sync.
DEFAULT_OVERSIZE_FACTOR_TRIP = 3.0
DEFAULT_TOTAL_SIZE_RATIO_TRIP = 2.0


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return float(sorted_values[mid])
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def _has_epic_label(labels: Optional[Iterable[str]]) -> bool:
    if not labels:
        return False
    for label in labels:
        if not isinstance(label, str):
            continue
        for pattern in EPIC_LABEL_PATTERNS:
            if pattern.match(label.strip()):
                return True
    return False


def _normalize_item(raw: Any) -> Dict[str, Any]:
    """Coerce a raw item entry to the canonical shape.

    Accepts either a dict ({"id", "size", "labels"}) or a bare string
    (treated as id with size=1, no labels). Anything else is dropped.
    """
    if isinstance(raw, dict):
        item_id = raw.get("id") or raw.get("name") or raw.get("title")
        size = raw.get("size", 1)
        labels = raw.get("labels", [])
        if item_id is None:
            return {}
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = 1.0
        # Labels normalization (Gemini PR #860 review): a bare string must
        # become a single-element list, not be decomposed by list("epic")
        # into ['e','p','i','c']. A non-iterable type (int, None, etc.)
        # falls back to []. Only str/list/tuple yield meaningful labels.
        if isinstance(labels, str):
            labels_list = [labels]
        elif isinstance(labels, (list, tuple)):
            labels_list = list(labels)
        else:
            labels_list = []
        return {"id": str(item_id), "size": size, "labels": labels_list}
    if isinstance(raw, str):
        return {"id": raw, "size": 1.0, "labels": []}
    return {}


def compute_scope_delta(
    baseline: List[Any],
    proposed: List[Any],
    *,
    oversize_factor_trip: float = DEFAULT_OVERSIZE_FACTOR_TRIP,
    total_size_ratio_trip: float = DEFAULT_TOTAL_SIZE_RATIO_TRIP,
) -> Dict[str, Any]:
    """Compute scope-delta metrics for the clarify HITL gate (#847).

    Args:
        baseline: List of items the user explicitly named in the
            original ask. Each entry is a dict
            ``{"id": str, "size": float, "labels": [str]}`` or a bare
            string id.
        proposed: List of items in the proposed plan, same shape.
        oversize_factor_trip: Threshold at or above which the
            oversize_factor trips the trigger (default 3.0).
        total_size_ratio_trip: Threshold at or above which the
            total_size_ratio trips the trigger (default 2.0).

    Returns:
        Dict with:
          - ``new_items``: list of {id, size, labels} for items in
            proposed but not baseline.
          - ``baseline_median_size`` / ``baseline_total_size``.
          - ``proposed_total_size``.
          - ``oversize_factor``: max(new_item.size) / baseline_median_size,
            or None when baseline_median_size is 0.
          - ``total_size_ratio``: proposed_total / baseline_total, or
            None when baseline_total is 0.
          - ``epic_or_project_added``: True iff any new item has an
            epic-class label.
          - ``triggers``: ordered list of human-readable strings naming
            which thresholds tripped. Empty list = no trigger fired.

    The trigger fires whenever ``triggers`` is non-empty.
    """
    base = [it for it in (_normalize_item(x) for x in baseline) if it]
    prop = [it for it in (_normalize_item(x) for x in proposed) if it]

    base_ids = {it["id"] for it in base}
    new_items = [it for it in prop if it["id"] not in base_ids]

    baseline_sizes = [it["size"] for it in base]
    baseline_median = _median(baseline_sizes)
    baseline_total = sum(baseline_sizes)
    proposed_total = sum(it["size"] for it in prop)

    if new_items and baseline_median > 0:
        max_new_size = max(it["size"] for it in new_items)
        oversize_factor = max_new_size / baseline_median
    else:
        oversize_factor = None

    if baseline_total > 0:
        total_size_ratio = proposed_total / baseline_total
    else:
        total_size_ratio = None

    epic_added = any(_has_epic_label(it.get("labels")) for it in new_items)

    triggers: List[str] = []
    if oversize_factor is not None and oversize_factor >= oversize_factor_trip:
        triggers.append(
            f"oversize-factor: largest new item is {oversize_factor:.1f}x "
            f"the baseline median (trip threshold: {oversize_factor_trip}x)"
        )
    if total_size_ratio is not None and total_size_ratio >= total_size_ratio_trip:
        triggers.append(
            f"total-size-ratio: proposed plan is {total_size_ratio:.1f}x "
            f"the baseline total size (trip threshold: {total_size_ratio_trip}x)"
        )
    if epic_added:
        epic_ids = [
            it["id"] for it in new_items if _has_epic_label(it.get("labels"))
        ]
        triggers.append(
            f"epic-or-project-label: new item(s) {epic_ids} carry an "
            "epic/project-class label and should be planned separately"
        )

    return {
        "new_items": new_items,
        "baseline_median_size": baseline_median,
        "baseline_total_size": baseline_total,
        "proposed_total_size": proposed_total,
        "oversize_factor": oversize_factor,
        "total_size_ratio": total_size_ratio,
        "epic_or_project_added": epic_added,
        "triggers": triggers,
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compute scope-delta metrics for the clarify HITL gate "
            "(Issue #847). Pass --baseline and --proposed as JSON file "
            "paths or '-' to read from stdin."
        )
    )
    parser.add_argument("--baseline", required=True,
                        help="Path to JSON file with baseline items, or '-' for stdin.")
    parser.add_argument("--proposed", required=True,
                        help="Path to JSON file with proposed items, or '-' for stdin (mutually exclusive with --baseline -).")
    parser.add_argument("--oversize-factor-trip", type=float,
                        default=DEFAULT_OVERSIZE_FACTOR_TRIP,
                        help=f"Override oversize-factor trip (default {DEFAULT_OVERSIZE_FACTOR_TRIP}).")
    parser.add_argument("--total-size-ratio-trip", type=float,
                        default=DEFAULT_TOTAL_SIZE_RATIO_TRIP,
                        help=f"Override total-size-ratio trip (default {DEFAULT_TOTAL_SIZE_RATIO_TRIP}).")
    parser.add_argument("--exit-nonzero-on-trip", action="store_true",
                        help="Exit 1 if any trigger fires.")
    args = parser.parse_args()

    def _load(path: str) -> List[Any]:
        if path == "-":
            return json.loads(sys.stdin.read())
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Copilot PR #860 review: stdin can only be consumed once. Reject the
    # ambiguous '--baseline - --proposed -' case explicitly so a second
    # empty read doesn't surface as a confusing JSONDecodeError.
    if args.baseline == "-" and args.proposed == "-":
        print(
            "Error: --baseline and --proposed cannot BOTH be '-'. "
            "stdin can only be consumed once. Pass at most one of them as "
            "'-' and the other as a file path.",
            file=sys.stderr,
        )
        sys.exit(2)

    baseline = _load(args.baseline)
    proposed = _load(args.proposed)
    if not isinstance(baseline, list) or not isinstance(proposed, list):
        print("Error: baseline and proposed must each be a JSON array.",
              file=sys.stderr)
        sys.exit(2)

    result = compute_scope_delta(
        baseline, proposed,
        oversize_factor_trip=args.oversize_factor_trip,
        total_size_ratio_trip=args.total_size_ratio_trip,
    )
    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    if args.exit_nonzero_on_trip and result["triggers"]:
        sys.exit(1)


if __name__ == "__main__":
    _cli()
