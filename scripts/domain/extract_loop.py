#!/usr/bin/env python3
"""extract_loop.py — the deterministic extraction harness (vault `record`+`verify`).

The `domain-extractor` crew phase RUNS this (it does not loop itself: one agent,
max-turns 12, cannot iterate thousands of nodes). The harness owns COMPLETENESS;
the model is a bounded per-node adjunct (`_rule_extractor`) for the one thing code
can't do — stating the business rule. Vault discipline throughout:

  * WORKLIST = `wicked-core coverage`'s own `unaccounted_nodes` — the SAME authority
    the coverage gate re-derives against, so the harness denominator == the gate
    denominator (no drift). Re-seeded each pass; work never repeats (resumable).
  * RISK-FLOOR INVARIANT — every worklist node terminates RESOLVED-or-RISK. A model
    timeout / omission / invalid return is FORCED to RISK, never dropped, so coverage
    reaches 1.0 deterministically (RISK accounts a node; the model only upgrades
    RISK→RESOLVED quality).
  * RE-DERIVE, NEVER TRUST — coverage is recomputed cold from the store (never the
    harness's "I did N" claim); each write is read back.

`--dry-run` swaps the model boundary for a deterministic stub (every node → a valid
rule) so the whole loop + coverage gate can be proven with ZERO model cost.

stdlib-only, cross-platform. Exits 0 when the pass completes within budget (all
persisted); non-zero only on a genuine harness/contract failure (fail-loud).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, _rule_extractor  # noqa: E402

RESOLVE_THRESHOLD = 0.75


def _cohesion(sid: str, node_community: dict[str, str], community_sizes: dict[str, int]) -> float:
    """A cheap structural cohesion signal: a node in a real (multi-member) Louvain
    community frames a better-bounded rule than an edgeless singleton. Singleton
    (label == own id) ⇒ mild penalty; larger community ⇒ mild boost. Bounded [0.85, 1.1]."""
    label = node_community.get(sid, sid)
    size = community_sizes.get(label, 1)
    if label == sid or size <= 1:
        return 0.85
    return min(1.1, 0.95 + 0.03 * size)


def _stub_rule(node: dict) -> dict:
    """Deterministic no-model rule: a valid, confident business rule per node so a
    `--dry-run` pass drives coverage to 1.0 (proves the loop + gate, zero model cost)."""
    name = node.get("name", "unit")
    return {
        "symbol_id": node["symbol_id"],
        "statement": f"{name} performs its documented behavior as implemented",
        "confidence": 0.9,
        "provenance": {"source": "extract-loop:dry-run", "ref": node["symbol_id"],
                       "source_kinds": ["code-body"]},
    }


def _write_node(estate, sid: str, name: str, rule: dict | None, resolved: bool, reason: str) -> None:
    """The two coordinated writes + read-back (vault record+verify). RESOLVED ⇒ a
    validated requirement + business_rule annotation; RISK ⇒ a non-blank requirement
    (validated=False) + a risk annotation — either way the node is ACCOUNTED, so the
    RISK-floor guarantees coverage completeness."""
    rid = "RULE-%s" % hashlib.sha256(sid.encode()).hexdigest()[:12]
    if resolved and rule:
        stmt = rule["statement"]
        estate.annotate(sid, type="business_rule", key=rid, value=stmt,
                        confidence=float(rule.get("confidence", 0.9)),
                        provenance=str(rule.get("provenance", {}).get("source", "extract-loop")),
                        replace=True)
        estate.set_requirement(sid, requirement=stmt, validated=True)
    else:
        stmt = (rule or {}).get("statement") or ""
        risk_req = f"[RISK] {name}: {reason}" + (f" — {stmt}" if stmt else "")
        raw_conf = (rule or {}).get("confidence", 0.0)
        try:
            safe_conf = float(raw_conf)
        except (TypeError, ValueError):
            safe_conf = 0.0
        estate.annotate(sid, type="risk", key=rid, value=risk_req[:500],
                        confidence=safe_conf,
                        provenance="extract-loop:risk", replace=True)
        estate.set_requirement(sid, requirement=risk_req, validated=False)
    # Read-back re-derive: never trust the write's exit code alone.
    anns = estate.read_annotations(sid)
    if not any(a.get("key") == rid for a in anns):
        raise RuntimeError(f"write not durable: {sid} missing annotation {rid} on read-back")


def run(db: str, *, time_budget: float, limit: int, batch: int, dry_run: bool,
        project_dir: Path | None = None) -> int:
    if not db:
        raise RuntimeError("--db / $WICKED_ESTATE_DB is required but was not provided")
    estate = _clients.estate_client(db=db, project_dir=project_dir)
    core = _clients.core_client(project_dir=project_dir)
    if core is None:
        raise RuntimeError("wicked-core not resolvable — cannot re-derive coverage (set WICKED_CORE_BIN)")
    model_argv = None if dry_run else _clients.rule_model_argv(project_dir)
    if not dry_run and model_argv is None:
        raise RuntimeError("no rule model resolvable (set WICKED_RULE_MODEL_BIN or install claude); "
                           "use --dry-run for the deterministic stub")

    cov_out = str(Path(db).with_suffix(".coverage.json"))
    deadline = time.monotonic() + time_budget

    # Cohesion framing (quality only): total node_community over communities + singletons.
    try:
        clusters = estate.read_clusters()
        all_nodes = estate.list_nodes()
        node_community = _clients.total_node_community(clusters, all_nodes)
        community_sizes: dict[str, int] = {}
        for lbl in node_community.values():
            community_sizes[lbl] = community_sizes.get(lbl, 0) + 1
    except Exception as e:  # framing is best-effort; the loop still runs without it
        print(f"[extract-loop] cohesion framing unavailable ({e}); proceeding singleton-flat", file=sys.stderr)
        node_community, community_sizes = {}, {}

    processed = 0
    while True:
        cov = core.coverage(db, cov_out)
        worklist = _clients.unaccounted_nodes(cov)
        print(f"[extract-loop] coverage={cov.get('coverage')} unaccounted={len(worklist)} processed={processed}",
              file=sys.stderr)
        if not worklist:
            print("[extract-loop] coverage 1.0 — every behavior-bearing node accounted", file=sys.stderr)
            return 0
        if time.monotonic() >= deadline or (limit and processed >= limit):
            print(f"[extract-loop] budget reached (processed={processed}); {len(worklist)} unaccounted remain — "
                  "resume with another pass", file=sys.stderr)
            return 0

        # Take a bounded slice of the worklist for this batch.
        take = worklist[:batch]
        if limit:
            take = take[:max(0, limit - processed)]

        # Frame each node: source slice + cohesion neighbors (best-effort).
        framed, ids = [], set()
        for n in take:
            sid, name = n["symbol_id"], n.get("name", "")
            try:
                slice_txt = estate.source(sid)[:4000] if not dry_run else ""
            except Exception:
                slice_txt = ""
            framed.append(_rule_extractor.frame_context(n, slice_txt,
                          cluster_label=node_community.get(sid), neighbor_names=[]))
            ids.add(sid)

        # THE MODEL BOUNDARY (or the deterministic stub). A model failure over the
        # whole batch degrades every node to RISK — never a gap.
        by_id: dict[str, dict] = {}
        if dry_run:
            by_id = {n["symbol_id"]: _stub_rule(n) for n in take}
        else:
            try:
                for r in _rule_extractor.extract_rules(framed, model_argv):
                    if isinstance(r, dict) and r.get("symbol_id") in ids:
                        by_id[r["symbol_id"]] = r
            except Exception as e:
                print(f"[extract-loop] model batch failed ({e}); RISK-flooring the batch", file=sys.stderr)

        # Deterministic decision + write per node — RISK-FLOOR: every node terminates.
        for n in take:
            sid, name = n["symbol_id"], n.get("name", "")
            rule = by_id.get(sid)
            ok, reason = (_rule_extractor.validate_rule(rule, ids) if rule
                          else (False, "no rule returned for this node"))
            if ok:
                adjusted = float(rule["confidence"]) * _cohesion(sid, node_community, community_sizes)
                resolved = adjusted >= RESOLVE_THRESHOLD
                _write_node(estate, sid, name, rule, resolved,
                            "below confidence threshold" if not resolved else "")
            else:
                _write_node(estate, sid, name, rule, False, reason)
            processed += 1


def main(argv: list[str] | None = None) -> int:
    import os
    ap = argparse.ArgumentParser(description="Deterministic extraction harness (model-adjunct per node).")
    # Default to the run's store the governance env already sets, so a crew-dispatched
    # agent can just run the harness without threading the path.
    ap.add_argument("--db", default=os.environ.get("WICKED_ESTATE_DB"),
                    help="estate store path (default: $WICKED_ESTATE_DB)")
    ap.add_argument("--time-budget", type=float, default=780.0, help="seconds this pass may run (default 780)")
    ap.add_argument("--limit", type=int, default=0, help="max nodes this pass (0 = unbounded within time budget)")
    ap.add_argument("--batch", type=int, default=12, help="framed nodes per model call")
    ap.add_argument("--dry-run", action="store_true", help="deterministic stub instead of the model (zero cost)")
    args = ap.parse_args(argv)
    if not args.db:
        ap.error("--db is required (or set $WICKED_ESTATE_DB)")
    return run(args.db, time_budget=args.time_budget, limit=args.limit,
               batch=args.batch, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
