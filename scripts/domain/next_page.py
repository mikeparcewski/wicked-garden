#!/usr/bin/env python3
"""next_page.py — HOST step `extract-next` of domain-extraction: does the generation map another page?

A run maps a repository one page (worklist) at a time and keeps going until the mapped share
reaches the repository's target, or the operator stops it. After each page's `extract-apply`, this
step:

  * measures the mapped share in the store (`wicked-core coverage`) against the repository's
    target (`wicked-core requirements-target`: its own, else the daemon-wide minimum);
  * adds the point to the generation's record (`generation.py`, beside the store, never in the
    seat-writable worktree) and prints ONE progress line —
    "Mapping wicked-crew · 3% → 12% → 19% · target 80% · page 4 · about 2 h 10 min left";
  * ends with the engine's decision line (`wicked-repeat {...}`, wicked-core's bounded loop):
    another page while the share is below the target and the budget holds; the operator's ask
    when the budget (`WICKED_DOMAIN_MAX_PAGES`, default 20, or `WICKED_DOMAIN_MAX_MINUTES`,
    default 240, per grant) is spent, nothing is left to map, or two pages mapped nothing new —
    map more, lower the target for this repository, or stop; done at the target.

The engine re-runs this step with the operator's choice in `WICKED_REPEAT_CHOICE`: `continue`
grants a fresh budget, `lower` sets the repository's own target to the share mapped so far (so
the coverage step passes and the graph is built, labelled with that share).

Usage (the preset's command, run from the run's worktree):
    wicked-garden run scripts/domain/next_page.py --db <store> --repo-root <repo>

Exit 0 with a decision printed; 1 on a failure (the run escalates like any failed step).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, generation, rules_file  # noqa: E402

CHOICE_ENV = "WICKED_REPEAT_CHOICE"
PASS_ENV = "WICKED_REPEAT_PASS"


def _left_to_map(coverage: dict, repo_root: str) -> int:
    """Unmapped behaviours in files the repository tracks (what another page could still map)."""
    tracked = rules_file.tracked_files(repo_root, rules_file.run_commit(repo_root, Path.cwd()))
    return sum(1 for n in _clients.unaccounted_nodes(coverage) if n.get("file") in tracked)


def run(db: str, repo_root: str, *, core=None, env: dict[str, str] | None = None,
        now: int | None = None) -> dict:
    env = os.environ if env is None else env
    core = core or _clients.host_core_client()
    repo = Path(repo_root).name or "the repository"
    run_id = (env.get("WICKED_RUN_ID") or "").strip() or "standalone"
    now = generation.now_ms() if now is None else now
    choice = (env.get(CHOICE_ENV) or "").strip()

    with tempfile.TemporaryDirectory(prefix="wicked-domain-next-") as tmp:
        cov = core.coverage(db, str(Path(tmp) / "coverage.json"))
    target, source = core.requirements_target(db)

    if run_id == "standalone":
        # Outside a run there is no generation to keep: decide on this page alone.
        doc = {"schema": generation.SCHEMA, "run_id": run_id, "repo": repo,
               "points": [generation.point_of(cov, 0, now)], "grant": {"page": 0, "at": now}}
    else:
        doc = generation.load(db, run_id)
        if doc is None:  # no `extract-prepare` opened one (an older prepare): start here
            doc = generation.open_record(db, run_id, cov, repo, at=now)
    points = doc["points"]
    # The engine's pass names the page (codex r1 on #1369): a retried or re-answered step records
    # the same page again, never another one.
    try:
        page = int(env.get(PASS_ENV) or 0)
    except ValueError:
        page = 0
    if page <= 0:
        page = points[-1]["page"] + (0 if choice else 1)
    page = max(page, 1)
    kept = next((p for p in points if p["page"] == page), None)
    if choice and kept is not None:
        # An answer to an ask: no page ran, so the page keeps its own time (codex r1: an
        # operator's 24 h wait read as mapping time).
        point = kept
    else:
        earlier = [p for p in points if p["page"] < page]
        start = max([p["at"] for p in earlier[-1:]] + [doc["grant"]["at"]])
        point = generation.point_of(cov, page, now, now - start)
    doc["points"] = sorted([p for p in points if p["page"] != page] + [point],
                           key=lambda p: p["page"])

    if choice == "continue" and doc["grant"]["page"] != page:
        doc["grant"] = {"page": page, "at": now}
    if choice == "lower" and 1 <= point["pct"] < target:
        target, source = core.requirements_target(db, set_pct=point["pct"])
        doc["lowered_to"] = target
    if run_id != "standalone":
        generation.save(db, run_id, doc)

    max_pages, max_minutes = generation.budget_from_env(env)
    decision = generation.decide(doc, repo=repo, target=target, now=now, max_pages=max_pages,
                                 max_minutes=max_minutes, left_to_map=_left_to_map(cov, repo_root))
    if choice == "lower" and decision["next"] == "done":
        decision["line"] += f" · target lowered to {target}% for {repo}"
    print(f"[extract-next] {decision['line']} (target from the {source})")
    print(generation.marker(decision))
    return decision


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host step: map another page, ask, or finish.")
    ap.add_argument("--db", required=True, help="the repository's code-graph store")
    ap.add_argument("--repo-root", required=True, help="the registered repository's root")
    args = ap.parse_args(argv)
    try:
        run(args.db, args.repo_root)
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[extract-next] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
