#!/usr/bin/env python3
"""prepare_worklist.py — HOST step `extract-prepare` of domain-extraction (wicked-garden#1362).

Runs on the daemon host, where `wicked-core`, `wicked-estate` and the repository's code-graph
store are. It takes the behaviours that are not real requirements yet from `wicked-core
coverage` (the same authority the coverage gate recomputes against): the unmapped ones first,
then the risk-flagged placeholders an earlier page left (an empty statement, a rule under the
confidence threshold), then the MAPPED behaviours in files changed since the map was built
(`refresh.py`, wicked-garden#1425: a Refresh map re-asks them, so a fixed function does not keep its
old statement or finding), skipping any unit an earlier page of this generation already framed. It
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

from domain import (_clients, _rule_extractor, business_domains, extract_loop, generation,  # noqa: E402
                    refresh, rules_file)

# One page of a generation: what one seat turn states. 300 took a claude seat ~6 min on
# wicked-crew (rig run 7588cff1, 240 stated + 60 left as risks); a page carries a fixed cost
# around it (prepare, the page's review, apply, the next-page decision), so a larger page maps more
# per hour while the seat's turn stays well inside the engine's turn ceiling.
DEFAULT_LIMIT = 500
PAGE_SIZE_ENV = "WICKED_DOMAIN_PAGE_SIZE"
_ENVELOPE = 64 * 1024  # bytes kept for the document around the units (a first cut; trimmed after)


def _prior_answer(store, sid: str) -> str:
    """A placeholder's stored answer and why it did not count: the RISK requirement an earlier
    page wrote (`extract_loop._write_node`: "[RISK] <name>: <reason> — <statement>"), bounded;
    "" when the store holds none."""
    text = (store.requirement_of(sid) or "").strip()
    return text[:extract_loop.MAX_PRIOR_ANSWER] if text.startswith("[RISK]") else ""


def _in_store_and_tracked(db: str, tracked: set[str], ids: set[str]) -> set[str]:
    """Those of `ids` the store still has, in a file git tracks: what `extract-apply` would take a
    restatement for (it reads each through the same store and refuses an untracked file)."""
    if not ids:
        return set()
    store = extract_loop._DirectStore(db)
    out = set()
    for sid in ids:
        row = store.node_row.get(store.sid_of.get(sid))
        if row is not None and (row[1] or "") in tracked:
            out.add(sid)
    return out


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
        # The record decides what this page skips (agy r2 on #1375): no page without it.
        try:
            record = generation.open_record(db, run_id, cov, Path(repo_root).name)
        except (OSError, ValueError) as e:
            raise RuntimeError(f"the generation record could not be opened ({e})") from e
    # Units an earlier page of this generation framed are not asked again (a placeholder the
    # seat left empty stays one) unless the operator chose to ask them again (`again`, which
    # takes them out of `visited`, wicked-garden#1533); a later generation may try it again.
    seen = generation.visited(record)
    revisit = {n["symbol_id"] for n in placeholders}
    tracked = rules_file.tracked_files(repo_root)
    units = []
    stale, restate, skipped = [], {}, 0
    stale_line = "left for a later run"
    assignment_page = generation.assign_only(record)
    order_line = "assignment page"
    if not assignment_page:
        # Mapped behaviours whose code changed since the map was built: asked again, after the rest.
        # Only inside a run (the record is what lets apply accept them).
        stale, stale_line = ([], "outside a run: changed behaviours are not re-asked")
        if run_id:
            try:
                stale, stale_line = refresh.changed_units(
                    db, repo_root, tracked, {n["symbol_id"] for n in [*unmapped, *placeholders]})
            except refresh.RefreshUnreadable as e:
                # A store the refresh cannot read fails the step, said as such (e2e-1105 F40): never
                # a page that silently skips the changed behaviours and a map that then reads current.
                raise RuntimeError(f"Refresh map cannot tell what changed since the map was built: "
                                   f"{e}") from e
        restate = {n["symbol_id"]: n for n in stale}
        candidates = [n for n in [*unmapped, *placeholders, *stale] if n["symbol_id"] not in seen]
        in_repo = [n for n in candidates if n.get("file") in tracked]
        skipped = len(candidates) - len(in_repo)

        store = extract_loop._DirectStore(db)
        store.repo_root = repo_root  # source slices from the repository when the store's are unreadable
        hubs, how = extract_loop._centrality_hubs(estate, store)
        order, hops = extract_loop.hub_first_order(store, hubs)
        tail = len(order)
        # The product's code first, the unmapped before the placeholders before the changed mapped
        # behaviours, each hub-first; tests and fixtures (an older wicked-core still counts them) after
        # it, in the same order.
        def tier(sid: str) -> int:
            return 2 if sid in restate else (1 if sid in revisit else 0)
        in_repo.sort(key=lambda n: (extract_loop.is_test_path(n.get("file", "")),
                                    tier(n["symbol_id"]),
                                    order.get(n["symbol_id"], tail), n["symbol_id"]))
        take = in_repo[:limit] if limit > 0 else in_repo

        try:
            node_community = _clients.total_node_community(estate.read_clusters(), estate.list_nodes())
        except Exception as e:  # framing quality only
            print(f"[extract-prepare] communities unavailable ({e}); framing without them",
                  file=sys.stderr)
            node_community = {}

        room = rules_file.MAX_WORKLIST_BYTES - _ENVELOPE  # what the seat reads, less the envelope
        for n in take:
            sid = n["symbol_id"]
            # The store's content, else the repository's file at the same span. Never `estate source`
            # here: it looks a NAME up, and for a symbol id it answers "no symbols found" — text the
            # seat would read as the code.
            # A placeholder is asked again with its stored answer and why it did not count, and
            # with more of its source (wicked-garden#1536: every stated program of a CardDemo
            # re-ask was cut at the first-ask cap, before its logic, and came back under the line).
            prior = _prior_answer(store, sid) if sid in revisit and sid not in restate else ""
            slice_txt = (store.source_slice(sid, cap=extract_loop.REASK_SOURCE_CAP) if prior
                         else store.source_slice(sid))
            unit = _rule_extractor.frame_context(n, slice_txt, cluster_label=node_community.get(sid),
                                                 neighbor_names=store.blast_neighbors(sid))
            unit.update(kind=n.get("kind", ""), position=order.get(sid, tail) + 1,
                        hop=hops.get(sid))
            if prior:
                unit["prior_answer"] = prior
            if sid in restate:  # mapped before; its code changed since the map was built
                unit.update(changed_since_build=True, prior_statement=restate[sid]["prior"])
            room -= len(rules_file.encoded(unit))
            if room < 0:  # the seat refuses a bigger worklist; the rest is the next pass's
                break
            units.append(unit)

        n_hubs = min(len(hubs), extract_loop.hub_count(store))
        order_line = f"hub-first from {n_hubs} hub(s) by {how}, over {tail} node(s)"
    # The units OFF this page a send-back may restate (wicked-garden#1535): the units this run asked
    # on an earlier page or found changed since the map was built, still in the store and in a file
    # git tracks — the mapped units `extract-apply` takes a rule for (`apply_rules._restatable`).
    # A coverage review that sends the run back about an earlier page's rule gets it restated on
    # this page's file. Not the frontier (the unmapped and placeholders no page asked yet): a later
    # page frames those. Only the ids: the seat's `--check-rules` reads them; the host decides again
    # from its own record and the store, never from this list.
    restatable = _in_store_and_tracked(
        db, tracked, generation.visited(record) | generation.changed(record) | set(restate))
    off_page = sorted(restatable - {u["symbol_id"] for u in units})
    doc = {
        "schema": rules_file.WORKLIST_SCHEMA,
        "order": order_line,
        "coverage": {k: cov.get(k) for k in ("coverage", "behavior_bearing", "resolved",
                                              "risk_flagged", "unaccounted")},
        "unmapped": len(unmapped),
        "placeholders": len(placeholders),
        "changed_since_build": sum(1 for n in stale if n["symbol_id"] not in seen),
        "asked_before": len(seen),
        "not_in_repo": skipped,
        "units": units,
        extract_loop.OFF_PAGE_KEY: off_page,
    }
    # The repository's business domains (reqgraph Fix B): the stored catalog to pick from, or the
    # ask to propose one, and the resolved requirements with no domain yet to assign. A page
    # with no units can still assign domains.
    block, assign = business_domains.worklist_block(
        db, tracked, extract_loop.RESOLVE_THRESHOLD, business_domains.not_product,
        skip={u["symbol_id"] for u in units})
    doc["business_domains"] = block
    doc["assign"] = assign
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
        # A unit trimmed off the page that the host still takes a rule for stays restatable.
        doc[extract_loop.OFF_PAGE_KEY] = sorted(restatable - {u["symbol_id"] for u in units})
        if len(rules_file.encoded(doc)) > rules_file.MAX_WORKLIST_BYTES:
            raise RuntimeError(f"the worklist does not fit what the extract step reads "
                               f"({rules_file.MAX_WORKLIST_BYTES} bytes) even with no units")
    if run_id:
        # Not optional bookkeeping: the record decides what the next page skips and the page's
        # yield (codex on #1375), so a page whose units cannot be recorded is not prepared (and
        # no worklist is published for it).
        try:
            # Every changed unit found, not only this page's: the next page's decision counts
            # what is left of them (codex r1: a page full of unmapped units framed none).
            generation.frame_page(db, run_id, [u["symbol_id"] for u in units],
                                  changed_ids=sorted(restate), assign_count=len(doc["assign"]))
        except (OSError, ValueError) as e:
            raise RuntimeError(f"the page's units could not be recorded in the generation "
                               f"record ({e})") from e
    if run_id:
        # A new page starts with no answer (wicked-garden#1533, codex r1): an earlier page's rules
        # file holds entries for units an operator's "again" frames once more, and the harness
        # resumes after any entry the worklist holds, so it would hand the old empty answers back
        # with no model call. A same-page retry or send-back never re-runs this step.
        rules_file.remove_file(base, rules_file.RULES_REL)
    rules_file.write_json_file(base, out_rel, doc)
    if assignment_page:
        print(f"[extract-prepare] assignment page: {len(doc['assign'])} to assign", file=sys.stderr)
    else:
        front = units[0]["symbol_id"] if units else "-"
        no_source = sum(1 for u in units if not str(u.get("source") or "").strip())
        again = sum(1 for u in units if u["symbol_id"] in revisit)
        restated = sum(1 for u in units if u["symbol_id"] in restate)
        print(f"[extract-prepare] {len(unmapped)} unmapped behaviour(s) and {len(placeholders)} "
              f"placeholder(s), {len(seen)} asked by an earlier page of this run; {skipped} in files "
              f"the repository does not track (left out); {len(units)} framed into {out_rel} "
              f"({again} placeholder(s) asked again, {restated} changed since the map was built, "
              f"{no_source} with no source), frontier {front}; {doc['order']}; refresh: {stale_line}; "
              f"business domains: "
              f"{'propose' if block['propose'] else str(len(block['catalog'])) + ' stored'}, "
              f"{len(doc['assign'])} of {block['unassigned_resolved']} unassigned resolved to assign",
              file=sys.stderr)
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
