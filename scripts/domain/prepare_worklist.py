#!/usr/bin/env python3
"""prepare_worklist.py — HOST step `extract-prepare` of domain-extraction (wicked-garden#1362).

Runs on the daemon host, where `wicked-core`, `wicked-estate` and the repository's code-graph
store are. It takes the unmapped behaviours from `wicked-core coverage` (the same authority the
coverage gate recomputes against), keeps those in files the repository tracks, orders them
hub-first (estate's PageRank hubs, then their neighbours by graph distance — the order
`extract_loop.py` uses, so a later run continues from the frontier), frames each one (its
source slice, callers and callees, community) and writes up to `--limit` of them to the
WORKLIST file in the run's worktree. The seat container's extract step reads only that file.

Usage (the preset's command, run from the run's worktree):
    wicked-garden run scripts/domain/prepare_worklist.py --db <store> --repo-root <repo> \
        [--out .wicked/domain/worklist.json] [--limit 500]

Exit 0 with the worklist written (an empty one when nothing is left to map); 1 on a failure.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, _rule_extractor, extract_loop, generation, rules_file  # noqa: E402

# One page of a generation: what one seat turn states. 300 took a claude seat ~6 min on
# wicked-crew (rig run 7588cff1, 240 stated + 60 left as risks); a page carries a fixed cost
# around it (prepare, the page's review, apply, the next-page decision), so a larger page maps more
# per hour while the seat's turn stays well inside the engine's turn ceiling.
DEFAULT_LIMIT = 500
PAGE_SIZE_ENV = "WICKED_DOMAIN_PAGE_SIZE"
_ENVELOPE = 64 * 1024  # bytes kept for the document around the units (a first cut; trimmed after)


class StaleIndex(RuntimeError):
    """The code graph does not describe the run's tree: no page is prepared."""


def check_index_current(store, repo_root: str, commit: str | None, first_page: bool) -> None:
    """Before the first page: the store must be indexed at the run's tree (`commit`), or the
    worklist would frame code the run does not have (wicked-garden#1370). A launch re-indexes the
    repository's graph at the run's base (the engine's own indexer, D8); this step does not index
    (a checkout of a commit would run filters the seat-writable repository config can name), it
    refuses with the reason. A later page only says the graph has moved (another launch on the
    same repository re-indexed it): its sources still come from the indexed bytes, so its units
    stay exact."""
    if commit is None:
        return  # not a git repository, or no commit yet: nothing to compare against
    indexed = store.indexed_commit()
    if indexed == commit:
        return
    repo = Path(repo_root).name or "the repository"
    what = (f"is indexed at {indexed[:12]}" if indexed else "records no commit it was indexed at")
    msg = (f"the code graph of {repo} {what}, but this run's tree is at {commit[:12]}")
    if not first_page:
        print(f"[extract-prepare] {msg}; mapping on against the graph as indexed", file=sys.stderr)
        return
    raise StaleIndex(f"{msg}. Its units would not be the code this run maps, so no page is "
                     f"prepared. Launch the job again: a launch re-indexes {repo}'s graph at the "
                     "run's base (if it refuses again, the re-index is failing: check the "
                     "daemon log for 'repo graph not re-indexed at the run base')")


def prepare(db: str, repo_root: str, base: Path, out_rel: str, limit: int, *,
            estate=None, core=None) -> dict:
    # Binaries from the operator and the engine only — never from the seat-writable worktree.
    core = core or _clients.host_core_client()
    estate = estate or _clients.host_estate_client(db)
    rules_file.check_writable(base, out_rel)
    run_id = (os.environ.get("WICKED_RUN_ID") or "").strip()
    commit = rules_file.run_commit(repo_root, base)
    store = extract_loop._DirectStore(db)
    store.repo_root = repo_root  # the indexed bytes from the repository's objects
    try:
        first_page = not run_id or generation.load(db, run_id) is None
    except ValueError:  # not a run id: no record, so this is the first page
        first_page = True
    check_index_current(store, repo_root, commit, first_page)
    with tempfile.TemporaryDirectory(prefix="wicked-domain-prepare-") as tmp:
        cov = core.coverage(db, str(Path(tmp) / "coverage.json"))
    unmapped = _clients.unaccounted_nodes(cov)
    # The generation's record opens at the first page (its starting share and time); a later page
    # of the same run keeps it. Host-side, beside the store — never in the seat-writable worktree.
    if run_id:
        try:
            generation.open_record(db, run_id, cov, Path(repo_root).name)
        except (OSError, ValueError) as e:  # progress display only; the page is still prepared
            print(f"[extract-prepare] the generation record could not be opened ({e})",
                  file=sys.stderr)
    tracked = rules_file.tracked_files(repo_root, commit)
    in_repo = [n for n in unmapped if n.get("file") in tracked]
    skipped = len(unmapped) - len(in_repo)

    hubs, how = extract_loop._centrality_hubs(estate, store)
    order, hops = extract_loop.hub_first_order(store, hubs)
    tail = len(order)
    # The product's code first, hub-first; tests and fixtures after it, in the same order.
    in_repo.sort(key=lambda n: (extract_loop.is_test_path(n.get("file", "")),
                                order.get(n["symbol_id"], tail), n["symbol_id"]))
    take = in_repo[:limit] if limit > 0 else in_repo

    try:
        node_community = _clients.total_node_community(estate.read_clusters(), estate.list_nodes())
    except Exception as e:  # framing quality only
        print(f"[extract-prepare] communities unavailable ({e}); framing without them",
              file=sys.stderr)
        node_community = {}

    units = []
    room = rules_file.MAX_WORKLIST_BYTES - _ENVELOPE  # what the seat reads, less the envelope
    for n in take:
        sid = n["symbol_id"]
        # The store's content, else the repository's file at the same span. Never `estate source`
        # here: it looks a NAME up, and for a symbol id it answers "no symbols found" — text the
        # seat would read as the code.
        slice_txt = store.source_slice(sid)
        unit = _rule_extractor.frame_context(n, slice_txt, cluster_label=node_community.get(sid),
                                             neighbor_names=store.blast_neighbors(sid))
        unit.update(kind=n.get("kind", ""), position=order.get(sid, tail) + 1,
                    hop=hops.get(sid))
        room -= len(rules_file.encoded(unit))
        if room < 0:  # the seat refuses a bigger worklist; the rest is the next pass's
            break
        units.append(unit)

    n_hubs = min(len(hubs), extract_loop.hub_count(store))
    doc = {
        "schema": rules_file.WORKLIST_SCHEMA,
        "order": f"hub-first from {n_hubs} hub(s) by {how}, over {tail} node(s)",
        "coverage": {k: cov.get(k) for k in ("coverage", "behavior_bearing", "resolved",
                                              "risk_flagged", "unaccounted")},
        "unmapped": len(unmapped),
        "not_in_repo": skipped,
        "units": units,
    }
    # The per-unit budget above is an estimate (nesting indents every line); the published
    # document must fit what the seat reads, so trim to the largest prefix that does.
    if len(rules_file.encoded(doc)) > rules_file.MAX_WORKLIST_BYTES:
        lo, hi = 0, len(units)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(rules_file.encoded({**doc, "units": units[:mid]})) <= rules_file.MAX_WORKLIST_BYTES:
                lo = mid
            else:
                hi = mid - 1
        units = units[:lo]
        doc["units"] = units
    rules_file.write_json_file(base, out_rel, doc)
    front = units[0]["symbol_id"] if units else "-"
    no_source = sum(1 for u in units if not str(u.get("source") or "").strip())
    print(f"[extract-prepare] {len(unmapped)} unmapped behaviour(s); {skipped} in files the "
          f"repository does not track (left out); {len(units)} framed into {out_rel} "
          f"({no_source} with no source), frontier {front}; {doc['order']}", file=sys.stderr)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host step: the hub-first extraction worklist.")
    ap.add_argument("--db", required=True, help="the repository's code-graph store")
    ap.add_argument("--repo-root", required=True, help="the registered repository's root")
    ap.add_argument("--out", default=rules_file.WORKLIST_REL,
                    help=f"worklist path under the working directory (default {rules_file.WORKLIST_REL})")
    ap.add_argument("--limit", type=int, default=None,
                    help=f"most units in one worklist (default ${PAGE_SIZE_ENV}, else "
                         f"{DEFAULT_LIMIT}; 0 = all)")
    args = ap.parse_args(argv)
    if args.limit is None:
        try:
            args.limit = int(os.environ.get(PAGE_SIZE_ENV) or DEFAULT_LIMIT)
        except ValueError:
            args.limit = DEFAULT_LIMIT
        if args.limit <= 0:  # the setting is a page size; "all of it" is only --limit 0
            args.limit = DEFAULT_LIMIT
    try:
        prepare(args.db, args.repo_root, Path.cwd(), args.out, args.limit)
    except StaleIndex as e:
        print(f"[extract-prepare] REFUSED: {e}", file=sys.stderr)
        return 1
    except (RuntimeError, OSError, rules_file.RulesFileRefused) as e:
        print(f"[extract-prepare] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
