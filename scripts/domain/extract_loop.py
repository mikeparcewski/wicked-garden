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


_INFRA_MARKERS = ("session limit", "rate limit", "rate_limit", "overloaded", "quota",
                  "credit balance", "billing", "unauthorized", "authentication",
                  "connection refused", "connection reset", "network", "econnrefused",
                  "usage limit", "insufficient")


def _is_infra_failure(exc: Exception) -> bool:
    """True when the model boundary failed for infrastructure reasons (quota, auth,
    network) rather than judgment. A per-batch timeout stays a judgment failure —
    THAT batch was too hard — but an account-level outage would fail every future
    batch identically, so it must stop the pass, not floor the worklist."""
    msg = str(exc).lower()
    return any(m in msg for m in _INFRA_MARKERS)


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


_RETRY_PAUSE = 45.0  # seconds between the two attempts on a suspect batch

_FLOOR_MARKERS = ("no rule returned for this node", "empty statement (model could not state a rule)")


def _has_statement(store, symbol_id: str) -> bool:
    """True when the node already carries a substantive statement (not a floor
    placeholder) — the signal that a failed retry must not degrade it. Reads the
    store snapshot; without a direct store the answer is unknowable cheaply, so
    the guard stays inactive (flat-path behavior unchanged)."""
    if store is None:
        return False
    req = (store.requirement_of(symbol_id) or "").strip()
    if not req:
        return False
    return not any(m in req for m in _FLOOR_MARKERS)


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
            # Reject booleans (float(True)==1.0 but booleans are not valid confidence
            # signals here). The chained comparison also rejects nan/inf naturally since
            # nan comparisons always return False.
            if isinstance(raw_conf, bool):
                raise TypeError
            _c = float(raw_conf)
            safe_conf = _c if (0.0 <= _c <= 1.0) else 0.0
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


_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def _maybe_decompress(blob) -> bytes:
    """Estate stores content zstd-compressed; node spans are byte offsets into the
    DECOMPRESSED text. Slicing the raw blob feeds the model binary noise — observed
    live as whole batches of 'cannot state a rule'. Returns b'' when the blob is
    compressed but no decompressor is available, which routes framing to the
    subprocess fallback instead of producing garbage."""
    b = blob if isinstance(blob, bytes) else bytes(blob)
    if not b.startswith(_ZSTD_MAGIC):
        return b
    try:
        from compression import zstd  # stdlib, Python 3.14+
        return zstd.decompress(b)
    except ImportError:
        pass
    try:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(b)
    except ImportError:
        return b""


class _DirectStore:
    """READ-ONLY direct sqlite access for structural context (CommandIQ req-engine v3 pattern):
    the per-node blast radius (1-hop caller/callee names) and source slices come straight from
    the store instead of one subprocess per node — the prior loop's latency dominator. All
    queries are reads; every write still goes through the estate CLI client (single surface)."""

    def __init__(self, db: str):
        import sqlite3
        self._c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        self._c.row_factory = sqlite3.Row
        # symbols: sym string ↔ sid
        self.sid_of = {}
        self.sym_of = {}
        for r in self._c.execute("SELECT sid, sym FROM symbols"):
            self.sid_of[r["sym"]] = r["sid"]
            self.sym_of[r["sid"]] = r["sym"]
        # node names + files + spans (span parsed lazily from data JSON only when sourcing)
        self.node_row = {}
        self._req = {}
        try:
            rows = self._c.execute("SELECT symbol, name, file, data, requirement FROM nodes")
        except sqlite3.OperationalError:  # older stores predate the requirement column
            rows = self._c.execute("SELECT symbol, name, file, data, NULL FROM nodes")
        for r in rows:
            self.node_row[r["symbol"]] = (r["name"], r["file"], r["data"])
            self._req[r["symbol"]] = r[4] or ""
        # calls adjacency (edge kinds are stored JSON-quoted, e.g. '"calls"')
        self.callees = {}
        self.callers = {}
        self.in_deg = {}
        for r in self._c.execute("SELECT source, target FROM edges WHERE kind IN ('calls', '\"calls\"')"):
            self.callees.setdefault(r["source"], []).append(r["target"])
            self.callers.setdefault(r["target"], []).append(r["source"])
            self.in_deg[r["target"]] = self.in_deg.get(r["target"], 0) + 1
        self._file_text = {}

    def requirement_of(self, symbol_id: str) -> str:
        sid = self.sid_of.get(symbol_id)
        return self._req.get(sid, "") if sid is not None else ""

    def name_of_sid(self, sid: int) -> str:
        row = self.node_row.get(sid)
        return row[0] if row else self.sym_of.get(sid, "?")

    def blast_neighbors(self, symbol_id: str, cap: int = 8) -> list[str]:
        """1-hop callers + callees as 'role:name' strings, importance-ranked (callers first)."""
        sid = self.sid_of.get(symbol_id)
        if sid is None:
            return []
        out = []
        for other in sorted(self.callers.get(sid, []), key=lambda x: -self.in_deg.get(x, 0))[: cap // 2]:
            out.append(f"caller:{self.name_of_sid(other)}")
        for other in sorted(self.callees.get(sid, []), key=lambda x: -self.in_deg.get(x, 0))[: cap - len(out)]:
            out.append(f"callee:{self.name_of_sid(other)}")
        return out

    def leverage(self, symbol_id: str) -> int:
        sid = self.sid_of.get(symbol_id)
        if sid is None:
            return 0
        return self.in_deg.get(sid, 0) + len(self.callees.get(sid, []))

    def source_slice(self, symbol_id: str, cap: int = 4000) -> str:
        sid = self.sid_of.get(symbol_id)
        row = self.node_row.get(sid) if sid is not None else None
        if row is None:
            return ""
        _, file, data = row
        try:
            import json as _json
            span = _json.loads(data).get("location", {}).get("span", {})
            start, end = int(span.get("start_byte", 0)), int(span.get("end_byte", 0))
            if file not in self._file_text:
                r = self._c.execute(
                    "SELECT c.blob FROM files f JOIN content c ON c.git_sha = f.git_sha WHERE f.path = ?",
                    (file,),
                ).fetchone()
                if len(self._file_text) >= 128:  # bounded FIFO — long runs must not grow without limit
                    self._file_text.pop(next(iter(self._file_text)))
                self._file_text[file] = _maybe_decompress(r["blob"]) if r else b""
            blob = self._file_text[file]
            if end > start and end <= len(blob):
                return blob[start:end].decode("utf-8", errors="replace")[:cap]
        except Exception:
            pass
        return ""


def _annotation_preflight(db: str) -> None:
    """Cheap id-scheme migration pre-flight (fail-open, warning only). Estate's
    2026-08 id-scheme migration ("2": type-nested method/field SymbolIds) re-mints
    definition ids on the forced full re-extract; annotation rows written under the
    old scheme keep their OLD node_sym sids and orphan silently. Signature: a sampled
    annotation node_sym no longer resolves to a live node. Warn LOUDLY before this
    pass writes new annotations next to orphaned ones — but never block: garden is
    fail-open, and a partially-orphaned store is still valid to (re-)extract into."""
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            total, orphaned = con.execute(
                "SELECT count(*), COALESCE(sum(CASE WHEN n.symbol IS NULL THEN 1 ELSE 0 END), 0) "
                "FROM (SELECT DISTINCT node_sym FROM annotations LIMIT 500) a "
                "LEFT JOIN nodes n ON n.symbol = a.node_sym"
            ).fetchone()
            if not total or not orphaned:
                return
            # id_scheme meta is written per-repo ('repo:<label>:id_scheme') or bare.
            schemes = ", ".join(
                f"{k}={v}" for k, v in con.execute(
                    "SELECT k, v FROM meta WHERE k = 'id_scheme' OR k LIKE '%:id_scheme'")
            ) or "no id_scheme meta key"
            print(
                f"[extract-loop] WARNING: {orphaned}/{total} sampled annotation node_syms no longer "
                f"exist in nodes ({schemes}) — the estate id-scheme migration signature. Prior "
                "business_rule/risk annotations + node_semantics keyed to old method/field ids are "
                "ORPHANED. Required order: `wicked-estate index <repo>` with the new binary → re-run "
                "this extract loop → `wicked-core domain-graph`. Proceeding fail-open; this pass "
                "writes against CURRENT ids only.",
                file=sys.stderr,
            )
        finally:
            con.close()
    except Exception:
        pass  # no annotations table / missing DB / locked store — pre-flight is best-effort


def _density_batch(members: list[dict], store, base_batch: int) -> int:
    """Density-adaptive batch size (planner idea, deterministic form): thin wrappers pack
    bigger batches, dense logic packs smaller — clamped 4..64."""
    if not members:
        return base_batch
    sample = members[: min(len(members), 12)]
    avg = sum(len(store.source_slice(m["symbol_id"], cap=2000)) for m in sample) / len(sample)
    mult = 1.6 if avg < 300 else (0.6 if avg > 1500 else 1.0)
    return max(4, min(64, int(base_batch * mult)))


def run(db: str, *, time_budget: float, limit: int, batch: int, dry_run: bool,
        project_dir: Path | None = None, cluster_offset: int = 0) -> int:
    if not db:
        raise RuntimeError("--db / $WICKED_ESTATE_DB is required but was not provided")
    _annotation_preflight(db)
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

    # STRUCTURAL SUBSTRATE (CommandIQ req-engine v3 pattern): direct read-only store access
    # for blast-radius context + source slices — no per-node subprocess (the prior loop's
    # latency dominator). Best-effort: any failure falls back to the flat, context-free path.
    try:
        store = _DirectStore(db)
    except Exception as e:
        print(f"[extract-loop] direct store unavailable ({e}); flat context-free fallback", file=sys.stderr)
        store = None

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

        # STRUCTURAL ORDER: group the worklist by community, rank clusters by aggregate call
        # leverage (in+out degree) so high-impact groups extract first, members likewise ranked
        # within their cluster. Batches then hold RELATED symbols — shared context makes the
        # model's rules better grounded AND cheaper — with a density-adaptive batch size
        # (thin wrappers pack bigger batches, dense logic smaller). Flat slice as fallback.
        if store is not None and node_community:
            clusters_seen: dict[str, list] = {}
            for n in worklist:
                clusters_seen.setdefault(node_community.get(n["symbol_id"], "~singleton"), []).append(n)
            def _cluster_leverage(members: list) -> int:
                return sum(store.leverage(m["symbol_id"]) for m in members[:50])
            # cluster_offset lets parallel workers each own a different leverage-ranked
            # cluster instead of all fighting over the head (offset 0 = head).
            ranked = sorted(clusters_seen.values(), key=_cluster_leverage, reverse=True)
            head = ranked[max(0, cluster_offset) % len(ranked)]
            head.sort(key=lambda n: store.leverage(n["symbol_id"]), reverse=True)
            take = head[: _density_batch(head, store, batch)]
        else:
            take = worklist[:batch]
        if limit:
            take = take[:max(0, limit - processed)]

        # Frame each node: source slice + blast-radius neighbors (direct reads; the old
        # per-node subprocess path survives only as the fallback).
        framed, ids = [], set()
        for n in take:
            sid, name = n["symbol_id"], n.get("name", "")
            slice_txt, neighbors = "", []
            if not dry_run:
                if store is not None:
                    slice_txt = store.source_slice(sid)
                    neighbors = store.blast_neighbors(sid)
                if slice_txt == "":
                    try:
                        slice_txt = estate.source(sid)[:4000]
                    except Exception:
                        slice_txt = ""
            framed.append(_rule_extractor.frame_context(n, slice_txt,
                          cluster_label=node_community.get(sid), neighbor_names=neighbors))
            ids.add(sid)

        # THE MODEL BOUNDARY (or the deterministic stub). A model failure over the
        # whole batch degrades every node to RISK — never a gap.
        by_id: dict[str, dict] = {}
        if dry_run:
            by_id = {n["symbol_id"]: _stub_rule(n) for n in take}
        else:
            # Providers blip: an occasional empty response or transient error is normal,
            # a REPEAT on the same batch is an outage. One in-pass retry (after a short
            # pause) before EX_TEMPFAIL keeps transients from costing a whole pass.
            for attempt in (1, 2):
                by_id = {}
                floor_batch = False
                infra_exc = None
                # Models normalize punctuation-bearing ids (a trailing '.' in the symbol
                # grammar came back stripped, dropping EVERY rule of certain batches as a
                # "mismatch" and mimicking an outage). Exact match first; else re-canonize
                # by trailing-dot-insensitive lookup. Anything else stays a hallucination.
                canon = {sid.rstrip("."): sid for sid in ids}
                try:
                    for r in _rule_extractor.extract_rules(framed, model_argv):
                        if not isinstance(r, dict):
                            continue
                        rid = r.get("symbol_id")
                        if rid in ids:
                            by_id[rid] = r
                        elif isinstance(rid, str) and rid.strip().rstrip(".") in canon:
                            r["symbol_id"] = canon[rid.strip().rstrip(".")]
                            by_id[r["symbol_id"]] = r
                except Exception as e:
                    if _is_infra_failure(e):
                        infra_exc = e
                    elif "exceeded" in str(e) and attempt == 1:
                        # A batch timeout is often provider slowness, not batch difficulty
                        # — one retry before conceding. A repeat floors (termination), it
                        # does not abort: a genuinely oversized batch must not wedge passes.
                        print(f"[extract-loop] model batch timeout ({e}) — retrying once "
                              f"in {int(_RETRY_PAUSE)}s", file=sys.stderr)
                        time.sleep(_RETRY_PAUSE)
                        continue
                    else:
                        print(f"[extract-loop] model batch failed ({e}); RISK-flooring the batch",
                              file=sys.stderr)
                        floor_batch = True
                if floor_batch or by_id:
                    break
                if infra_exc is None and len(take) < 4:
                    # Tiny batch, no objects, no classified error: could be one genuinely
                    # unstatable node — floor it rather than wedge the loop.
                    break
                if attempt == 2:
                    # An outage is not a judgment. Flooring here would burn the whole
                    # remaining worklist into placeholders — stop the pass instead;
                    # nothing from this batch is written, resume re-derives it. NO
                    # parseable rule objects for a whole real batch is the same outage
                    # signature (notice printed with exit 0, or a wholesale empty array);
                    # per-unit objects with explicit empty statements are a JUDGMENT and
                    # floor as designed.
                    why = f"infra: {infra_exc}" if infra_exc else f"zero-yield ({len(take)} framed, 0 rule objects)"
                    print(f"[extract-loop] {why} — persisted after retry; pass aborted, batch NOT floored",
                          file=sys.stderr)
                    return 75  # EX_TEMPFAIL
                print("[extract-loop] transient zero-yield/infra on batch — retrying once "
                      f"in {int(_RETRY_PAUSE)}s", file=sys.stderr)
                time.sleep(_RETRY_PAUSE)

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
            elif (rule or {}).get("statement"):
                _write_node(estate, sid, name, rule, False, reason)
            elif _has_statement(store, sid):
                # Statement-less floor over existing content would DEGRADE the store —
                # a re-queued node keeps its prior statement instead. Floors only ever
                # fill blanks; content is monotonic.
                print(f"[extract-loop] floor skipped for {sid} (existing statement kept)",
                      file=sys.stderr)
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
    ap.add_argument("--cluster-offset", type=int, default=0,
                    help="parallel workers: take the Nth leverage-ranked cluster instead of the head")
    args = ap.parse_args(argv)
    if not args.db:
        ap.error("--db is required (or set $WICKED_ESTATE_DB)")
    return run(args.db, time_budget=args.time_budget, limit=args.limit,
               batch=args.batch, dry_run=args.dry_run, cluster_offset=args.cluster_offset)


if __name__ == "__main__":
    raise SystemExit(main())
