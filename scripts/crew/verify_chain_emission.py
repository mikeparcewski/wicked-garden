#!/usr/bin/env python3
"""Verify TaskCreate emission matched the facilitator plan's tasks[].

Usage:
    verify_chain_emission.py <path-to-plan.json> <chain-id>

Scans native task JSON files under ${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/ for
tasks whose metadata.chain_id matches the given chain_id, then compares the
count to the length of tasks[] in the plan file.

v10 Phase 3 (#813 successor, designed in jam session 03): when the
per-session native scan misses tasks (e.g. project spans sessions, or the
verifier runs in a fresh session after `crew:start`), fall back to the
cross-session task-audit JSONL written by the PostToolUse hook
(see scripts/crew/_task_audit_writer.py). Drift between the two sources
is logged to stderr but does NOT fail the verifier — the goal is to
catch real misemissions, not flag soak-window divergence.

Exit codes:
    0 — counts match, all plan tasks have a native task (or audit entry)
    1 — mismatch (prints delta to stderr), or plan unreadable

Zero external dependencies — stdlib only. Safe to run from a shell hook.

Issue #432 (original) + Phase 3 dual-read (decision memory:
v10-native-task-store-audit-trail-decision).
"""

import argparse
import json
import sys
from pathlib import Path


def _count_tasks_with_chain_native(chain_id: str) -> list[dict]:
    """Return native task dicts (per-session scan) whose metadata.chain_id matches."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from crew._task_reader import collect_tasks_for_chain  # type: ignore[import]
        return collect_tasks_for_chain(chain_id) or []
    except Exception:
        return []


def _count_tasks_with_chain_audit(chain_id: str) -> list[dict]:
    """Return cross-session audit-log entries whose chain_id matches.

    Phase 3 cross-session fallback. Empty list when the audit dir
    doesn't exist (PostToolUse hasn't fired or running on an old layout).
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from crew._task_audit_writer import scan_chain, latest_per_task  # type: ignore[import]
        return latest_per_task(scan_chain(chain_id))
    except Exception:
        return []


def _normalise_titles(tasks: list[dict]) -> list[str]:
    """Native + audit entries spell the title under different keys; pick whichever exists."""
    return [
        t.get("subject") or t.get("title") or "<untitled>"
        for t in tasks
    ]


def _count_tasks_with_chain(chain_id: str) -> tuple[int, list[str]]:
    """Return (count, titles) using the union of native + audit sources.

    Drift between the two sources is logged to stderr (visible to the
    caller) but does NOT change the count semantics — this is steering,
    not blocking. The audit fallback rescues the cross-session case
    where the per-session native scan misses tasks created earlier.
    """
    native = _count_tasks_with_chain_native(chain_id)
    audit = _count_tasks_with_chain_audit(chain_id)

    # Build a dedup set keyed on task_id (native and audit may overlap
    # for the current session; we want the UNION not the SUM).
    by_id: dict[str, dict] = {}
    for t in native:
        tid = t.get("id") or t.get("task_id")
        if tid:
            by_id[tid] = t
    for e in audit:
        tid = e.get("task_id")
        if tid and tid not in by_id:
            by_id[tid] = e

    # Drift logging: native says X, audit says Y, union says Z. If the
    # union extends past native by N, it's the cross-session rescue
    # firing — log so reviewers know the soak-window dual-read helped.
    if len(by_id) > len(native):
        sys.stderr.write(
            f"[verify_chain_emission] cross-session audit-log added "
            f"{len(by_id) - len(native)} tasks for chain {chain_id} "
            f"(native: {len(native)}, audit: {len(audit)}, union: {len(by_id)})\n"
        )

    titles = _normalise_titles(list(by_id.values()))
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
