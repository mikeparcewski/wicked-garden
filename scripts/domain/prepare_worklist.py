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
        [--out .wicked/domain/worklist.json] [--limit 300]

Exit 0 with the worklist written (an empty one when nothing is left to map); 1 on a failure.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, _rule_extractor, extract_loop, rules_file  # noqa: E402

DEFAULT_LIMIT = 300


def prepare(db: str, repo_root: str, base: Path, out_rel: str, limit: int, *,
            estate=None, core=None) -> dict:
    # Binaries from the operator and the engine only — never from the seat-writable worktree.
    core = core or _clients.host_core_client()
    estate = estate or _clients.host_estate_client(db)
    rules_file.check_writable(base, out_rel)
    with tempfile.TemporaryDirectory(prefix="wicked-domain-prepare-") as tmp:
        cov = core.coverage(db, str(Path(tmp) / "coverage.json"))
    unmapped = _clients.unaccounted_nodes(cov)
    tracked = rules_file.tracked_files(repo_root)
    in_repo = [n for n in unmapped if n.get("file") in tracked]
    skipped = len(unmapped) - len(in_repo)

    store = extract_loop._DirectStore(db)
    hubs, how = extract_loop._centrality_hubs(estate, store)
    order, hops = extract_loop.hub_first_order(store, hubs)
    tail = len(order)
    in_repo.sort(key=lambda n: (order.get(n["symbol_id"], tail), n["symbol_id"]))
    take = in_repo[:limit] if limit > 0 else in_repo

    try:
        node_community = _clients.total_node_community(estate.read_clusters(), estate.list_nodes())
    except Exception as e:  # framing quality only
        print(f"[extract-prepare] communities unavailable ({e}); framing without them",
              file=sys.stderr)
        node_community = {}

    units = []
    room = rules_file.MAX_WORKLIST_BYTES - 64 * 1024  # what the seat reads, less the envelope
    for n in take:
        sid = n["symbol_id"]
        slice_txt = store.source_slice(sid)
        if not slice_txt:
            try:
                slice_txt = estate.source(sid)[:4000]
            except Exception:
                slice_txt = ""
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
    rules_file.write_json_file(base, out_rel, doc)
    front = units[0]["symbol_id"] if units else "-"
    print(f"[extract-prepare] {len(unmapped)} unmapped behaviour(s); {skipped} in files the "
          f"repository does not track (left out); {len(units)} framed into {out_rel}, "
          f"frontier {front}; {doc['order']}", file=sys.stderr)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host step: the hub-first extraction worklist.")
    ap.add_argument("--db", required=True, help="the repository's code-graph store")
    ap.add_argument("--repo-root", required=True, help="the registered repository's root")
    ap.add_argument("--out", default=rules_file.WORKLIST_REL,
                    help=f"worklist path under the working directory (default {rules_file.WORKLIST_REL})")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"most units in one worklist (default {DEFAULT_LIMIT}; 0 = all)")
    args = ap.parse_args(argv)
    try:
        prepare(args.db, args.repo_root, Path.cwd(), args.out, args.limit)
    except (RuntimeError, OSError, rules_file.RulesFileRefused) as e:
        print(f"[extract-prepare] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
