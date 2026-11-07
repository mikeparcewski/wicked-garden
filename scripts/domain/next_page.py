#!/usr/bin/env python3
"""next_page.py — HOST step `extract-next` of domain-extraction: does the generation map another page?

A run maps a repository one page (worklist) at a time and keeps going until the share of REAL
requirements reaches the repository's target, or the operator stops it. Real means resolved to a
stated, sourced business rule; risk-flagged placeholders are counted apart and never toward the
target (operator decision 2026-11-01, wicked-core#1233). After each page's `extract-apply`, this
step:

  * measures the real share in the store (`wicked-core coverage`) against the repository's
    target (`wicked-core requirements-target`: its own, else the daemon-wide minimum);
  * closes the page in the generation's record (`generation.py`, beside the store, never in the
    seat-writable worktree: its units are not asked again this run), adds the point and prints
    ONE progress line — "Mapping wicked-crew · real requirements 23% → 27% · minimum 80% · page 2
    · 4,397 placeholders · last page resolved 212 of 500 units · about 3 h left";
  * ends with the engine's decision line (`wicked-repeat {...}`, wicked-core's bounded loop):
    another page while the real share is below the target and the budget holds; the operator's
    ask when the budget (`WICKED_DOMAIN_MAX_PAGES`, default 20, or `WICKED_DOMAIN_MAX_MINUTES`,
    default 240, per grant) is spent, nothing is left to ask, the last page resolved under 1 in
    20 of its units, or two pages added no real requirement — map more, lower the target for this
    repository, or stop; done at the target once no mapped behaviour that changed since the map
    was built is left to re-ask (wicked-garden#1425).

The engine re-runs this step with the operator's choice in `WICKED_REPEAT_CHOICE`: `continue`
grants a fresh budget, `lower` sets the repository's own target to the share mapped so far (so
the coverage step passes and the graph is built, labelled with that share) and restates the
page's `.wicked/domain/apply-report.json` in the worktree against the lowered minimum, so the
work the coverage step's judge reads no longer says "minimum 80%, not met" (wicked-core e2e F29).

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
from domain.apply_rules import REPORT_REL  # noqa: E402

CHOICE_ENV = "WICKED_REPEAT_CHOICE"
PASS_ENV = "WICKED_REPEAT_PASS"


def _left_to_map(coverage: dict, repo_root: str, seen: set[str]) -> int:
    """Behaviours that are not real requirements yet (unmapped, or placeholders) in files the
    repository tracks that no page of this generation has asked about: what another page could
    still raise the real share with."""
    tracked = rules_file.tracked_files(repo_root)
    nodes = [*_clients.unaccounted_nodes(coverage), *_clients.placeholder_nodes(coverage)]
    return sum(1 for n in nodes if n.get("file") in tracked and n.get("symbol_id") not in seen)


# The restated report keeps these fields of the page's report (what `apply_rules.py` writes, minus
# its `refused` list), each only when it is a short scalar; the rest is rewritten from the store.
_KEPT_FIELDS = ("declared_seat", "author", "entries", "eligible", "unsourced", "not_product",
                "refused_count")
# `apply_rules.py` writes a few KiB; anything far larger is not its report.
REPORT_READ_LIMIT = 1024 * 1024


def _small_scalar(v) -> bool:
    return v is None or isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 500)


def _restate_apply_report(core, db: str, worktree: Path, target: int) -> None:
    """After "lower": rewrite the worktree's apply report (written by `extract-apply` against the
    old minimum) with the share and verdict `wicked-core coverage` gives NOW, against the
    repository's own target. Only an existing report is restated; one that cannot be read or
    written safely (a link, not a file, not JSON, nested too deep to parse or write back) is left
    alone and said so, never followed. The report sits in the seat-writable worktree, so nothing
    about it may fail the step: the lowered target already stands in the store."""
    # RecursionError: valid JSON nested thousands deep parses (or re-serialises) past the stack
    # (codex r1). A planted report must not turn the answer into a failed step.
    unsafe = (rules_file.RulesFileRefused, OSError, ValueError, RecursionError)
    try:
        report = rules_file.read_json_file(worktree, REPORT_REL, limit=REPORT_READ_LIMIT)
    except FileNotFoundError:
        return
    except unsafe as e:
        print(f"[extract-next] {REPORT_REL} not restated: {e!s:.200}", file=sys.stderr)
        return
    if not isinstance(report, dict):
        print(f"[extract-next] {REPORT_REL} not restated: not a JSON object", file=sys.stderr)
        return
    try:
        with tempfile.TemporaryDirectory(prefix="wicked-domain-next-") as tmp:
            after, met, line = core.coverage_against_minimum(db, str(Path(tmp) / "coverage.json"))
    except Exception as e:  # noqa: BLE001 - the target is lowered either way (pi r2)
        # Only the restatement is missing, and it says so; nothing here may fail the step.
        print(f"[extract-next] {REPORT_REL} not restated: {e}", file=sys.stderr)
        return
    # Only the page's own small scalar fields are carried over (codex r2): the file is seat-writable,
    # and re-serialising whatever it holds could blow up far past its size on the way out.
    kept = {k: v for k, v in report.items() if k in _KEPT_FIELDS and _small_scalar(v)}
    applied = report.get("applied")
    if isinstance(applied, dict):
        kept["applied"] = {k: v for k, v in applied.items()
                           if k in ("resolved", "risk", "kept") and _small_scalar(v)}
    report = kept
    report["coverage"] = {k: after.get(k) for k in ("coverage", "behavior_bearing", "resolved",
                                                     "risk_flagged", "unaccounted")}
    report["minimum_met"] = met
    report["coverage_line"] = line
    report["lowered_to"] = target
    try:
        rules_file.write_json_file(worktree, REPORT_REL, report)
    except unsafe as e:
        print(f"[extract-next] {REPORT_REL} not restated: {e!s:.200}", file=sys.stderr)


def run(db: str, repo_root: str, *, core=None, env: dict[str, str] | None = None,
        now: int | None = None, worktree: Path | None = None) -> dict:
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
    framed, page_real = generation.close_page(doc, cov)
    if choice and kept is not None:
        # An answer to an ask: no page ran, so the page keeps its own time (codex r1: an
        # operator's 24 h wait read as mapping time).
        point = kept
    else:
        earlier = [p for p in points if p["page"] < page]
        start = max([p["at"] for p in earlier[-1:]] + [doc["grant"]["at"]])
        point = generation.point_of(cov, page, now, now - start)
        if framed or kept is None or "framed" not in kept:
            point["framed"] = framed
            if page_real is not None:  # unknown from an older wicked-core: no yield shown
                point["page_real"] = page_real
        else:  # a retried step after the page closed: the page keeps its own count
            point["framed"] = kept["framed"]
            if "page_real" in kept:
                point["page_real"] = kept["page_real"]
    doc["points"] = sorted([p for p in points if p["page"] != page] + [point],
                           key=lambda p: p["page"])

    if choice == "continue" and doc["grant"]["page"] != page:
        doc["grant"] = {"page": page, "at": now}
    if choice == "lower" and 1 <= point["pct"] < target:
        target, source = core.requirements_target(db, set_pct=point["pct"])
        doc["lowered_to"] = target
    if choice == "lower" and worktree is not None and source == "repository":
        # A retried answer (the target already lowered) restates it too: the report says what
        # the store holds now, whichever attempt wrote the target. No repository target in force
        # (no share to lower to, so the daemon's minimum applies): the report is not touched.
        _restate_apply_report(core, db, worktree, target)
    if run_id != "standalone":
        generation.save(db, run_id, doc)

    max_pages, max_minutes = generation.budget_from_env(env)
    decision = generation.decide(doc, repo=repo, target=target, now=now, max_pages=max_pages,
                                 max_minutes=max_minutes,
                                 left_to_map=_left_to_map(cov, repo_root, generation.visited(doc)),
                                 changed_left=generation.changed_left(doc))
    if choice == "finish":
        decision = {"next": "done", "line": generation.progress_line(
            repo, doc["points"], target, next_page=None, left_to_map=0)
            + " · going on as the operator chose"}
    if choice == "lower" and decision["next"] == "done":
        decision["line"] += f" · minimum lowered to {target}% for {repo}"
    print(f"[extract-next] {decision['line']} (minimum from the {source})")
    print(generation.marker(decision))
    return decision


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host step: map another page, ask, or finish.")
    ap.add_argument("--db", required=True, help="the repository's code-graph store")
    ap.add_argument("--repo-root", required=True, help="the registered repository's root")
    args = ap.parse_args(argv)
    try:
        run(args.db, args.repo_root, worktree=Path.cwd())
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[extract-next] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
