#!/usr/bin/env python3
"""prepare_worklist.py — HOST step `extract-prepare` of domain-extraction (wicked-garden#1362).

Runs on the daemon host, where `wicked-core`, `wicked-estate` and the repository's code-graph
store are. It takes the behaviours that are not real requirements yet from `wicked-core
coverage` (the same authority the coverage gate recomputes against): the unmapped ones first,
then the risk-flagged placeholders an earlier page left (an empty statement, a rule under the
confidence threshold), skipping any unit an earlier page of this generation already framed. It
keeps those in files the repository tracks, orders them hub-first (estate's PageRank hubs, then their neighbours by graph distance — the order
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


def prepare(db: str, repo_root: str, base: Path, out_rel: str, limit: int, *,
            estate=None, core=None) -> dict:
    # Binaries from the operator and the engine only — never from the seat-writable worktree.
    core = core or _clients.host_core_client()
    estate = estate or _clients.host_estate_client(db)
    rules_file.check_writable(base, out_rel)
    with tempfile.TemporaryDirectory(prefix="wicked-domain-prepare-") as tmp:
        cov = core.coverage(db, str(Path(tmp) / "coverage.json"))
    unmapped = _clients.unaccounted_nodes(cov)
    placeholders = _clients.placeholder_nodes(cov)
    # The generation's record opens at the first page (its starting share and time); a later page
    # of the same run keeps it. Host-side, beside the store — never in the seat-writable worktree.
    run_id = (os.environ.get("WICKED_RUN_ID") or "").strip()
    record = None
    if run_id:
        try:
            record = generation.open_record(db, run_id, cov, Path(repo_root).name)
        except (OSError, ValueError) as e:  # progress display only; the page is still prepared
            print(f"[extract-prepare] the generation record could not be opened ({e})",
                  file=sys.stderr)
    # Units an earlier page of this generation framed are not asked again (a placeholder the
    # seat left empty stays one; a later generation may try it again).
    seen = generation.visited(record)
    revisit = {n["symbol_id"] for n in placeholders}
    candidates = [n for n in [*unmapped, *placeholders] if n["symbol_id"] not in seen]
    tracked = rules_file.tracked_files(repo_root)
    in_repo = [n for n in candidates if n.get("file") in tracked]
    skipped = len(candidates) - len(in_repo)

    store = extract_loop._DirectStore(db)
    store.repo_root = repo_root  # source slices from the repository when the store's are unreadable
    hubs, how = extract_loop._centrality_hubs(estate, store)
    order, hops = extract_loop.hub_first_order(store, hubs)
    tail = len(order)
    # The product's code first, the unmapped before the placeholders, each hub-first; tests and
    # fixtures (an older wicked-core still counts them) after it, in the same order.
    in_repo.sort(key=lambda n: (extract_loop.is_test_path(n.get("file", "")),
                                n["symbol_id"] in revisit,
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
        "placeholders": len(placeholders),
        "asked_before": len(seen),
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
    if run_id and record is not None:
        try:
            generation.frame_page(db, run_id, [u["symbol_id"] for u in units])
        except (OSError, ValueError) as e:  # the next page may then re-ask these units
            print(f"[extract-prepare] the page's units could not be recorded ({e})",
                  file=sys.stderr)
    front = units[0]["symbol_id"] if units else "-"
    no_source = sum(1 for u in units if not str(u.get("source") or "").strip())
    again = sum(1 for u in units if u["symbol_id"] in revisit)
    print(f"[extract-prepare] {len(unmapped)} unmapped behaviour(s) and {len(placeholders)} "
          f"placeholder(s), {len(seen)} asked by an earlier page of this run; {skipped} in files "
          f"the repository does not track (left out); {len(units)} framed into {out_rel} "
          f"({again} placeholder(s) asked again, {no_source} with no source), frontier {front}; "
          f"{doc['order']}", file=sys.stderr)
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
    except (RuntimeError, OSError, rules_file.RulesFileRefused) as e:
        print(f"[extract-prepare] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
