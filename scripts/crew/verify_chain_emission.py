#!/usr/bin/env python3
"""Verify TaskCreate emission matched the facilitator plan's tasks[].

Usage:
    verify_chain_emission.py <path-to-plan.json> <chain-id>

Scans native task JSON files under ${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/ for
tasks whose metadata.chain_id matches the given chain_id, then compares the
count to the length of tasks[] in the plan file.

Exit codes:
    0 — counts match, all plan tasks have a native task
    1 — mismatch (prints delta to stderr), or plan unreadable

Zero external dependencies — stdlib only. Safe to run from a shell hook.

Issue #432.
"""

import argparse
import json
import sys
from pathlib import Path


def _count_tasks_with_chain(chain_id: str) -> tuple[int, list[str]]:
    """Return (count, titles) of tasks whose metadata.chain_id matches.

    Routing: WG_DAEMON_ENABLED=false → direct file scan (unchanged);
             WG_DAEMON_ENABLED=true  → daemon HTTP with fallback (#596 v8-PR-2).
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from crew._task_reader import collect_tasks_for_chain  # type: ignore[import]
        tasks = collect_tasks_for_chain(chain_id)
    except Exception:
        tasks = []
    titles = [
        t.get("subject") or t.get("title") or "<untitled>"
        for t in tasks
    ]
    return (len(titles), titles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify TaskCreate emission matches plan tasks[].")
    parser.add_argument("plan_path", help="Path to process-plan.json")
    parser.add_argument("chain_id", help="Expected chain_id (e.g. {slug}.root)")
    args = parser.parse_args()

    try:
        plan = json.loads(Path(args.plan_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: cannot read plan — {exc}\n")
        sys.exit(1)

    plan_tasks = plan.get("tasks") or []
    expected = len(plan_tasks)

    actual, actual_titles = _count_tasks_with_chain(args.chain_id)

    if actual == expected:
        sys.stdout.write(f"OK: {actual}/{expected} tasks emitted for chain {args.chain_id}\n")
        sys.exit(0)

    delta = expected - actual
    sys.stderr.write(
        f"MISMATCH: plan has {expected} tasks, {actual} emitted for chain {args.chain_id} "
        f"(delta={delta:+d})\n"
    )
    plan_titles = [t.get("title", "<untitled>") for t in plan_tasks]
    missing_titles = [t for t in plan_titles if t not in actual_titles]
    if missing_titles:
        sys.stderr.write("Likely missing:\n")
        for title in missing_titles:
            sys.stderr.write(f"  - {title}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
