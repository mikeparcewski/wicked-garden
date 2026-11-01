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
  * HUB-FIRST, FAN-OUT ORDER (operator ruling 2026-10-31) — the worklist is taken in
    graph order: the most central symbols first (estate's PageRank, `wicked-estate rank`),
    then their neighbours, then theirs, layer by layer. The most important behaviour is
    mapped first and coverage grows by graph distance, so the configured minimum (80% by
    default) is reached with the load-bearing code covered. The order is deterministic, so
    a later run re-derives it and continues from the FRONTIER (the first unmapped node in
    order) — the mapped prefix is already in the store.

`--dry-run` swaps the model boundary for a deterministic stub (every node → a valid
rule) so the whole loop + coverage gate can be proven with ZERO model cost.

stdlib-only, cross-platform. Exits 0 when the pass completes within budget (all
persisted); non-zero only on a genuine harness/contract failure (fail-loud).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, _rule_extractor, rules_file  # noqa: E402

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


# The model CLI is there but cannot answer for this seat at all (no login, no key): in a seat
# container the nested CLI is usually not signed in. Not a judgment and not a passing outage.
_AUTH_MARKERS = ("not logged in", "please run /login", "please log in", "invalid api key",
                 "unauthorized", "authentication")


def _is_auth_failure(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _AUTH_MARKERS)


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


def _seat() -> str:
    """Who is writing: `extract-loop:<run agent>` inside a crew run (WICKED_RUN_AGENT), else
    `extract-loop`. Rides as the annotation author and the semantics validator, so wicked-core
    can count extractor seats that independently stated a rule."""
    import os
    agent = (os.environ.get("WICKED_RUN_AGENT") or "").strip()
    return f"extract-loop:{agent}" if agent else "extract-loop"


def _write_node(estate, sid: str, name: str, rule: dict | None, resolved: bool, reason: str,
                seat: str | None = None, read_back=None) -> None:
    """The two coordinated writes + read-back (vault record+verify). RESOLVED ⇒ a
    validated requirement + business_rule annotation; RISK ⇒ a non-blank requirement
    (validated=False) + a risk annotation — either way the node is ACCOUNTED, so the
    RISK-floor guarantees coverage completeness."""
    # The key is per SEAT: estate's `--replace` deletes every annotation of that symbol, type and
    # key whatever its author, so a shared key let a second seat's write erase the first seat's —
    # and wicked-core, which counts agreeing seats by author, would only ever see one. The default
    # seat (no run agent) keeps the historical key, so a standalone re-run still replaces itself.
    seat = seat or _seat()
    basis = sid if seat == "extract-loop" else f"{sid}|{seat}"
    rid = "RULE-%s" % hashlib.sha256(basis.encode()).hexdigest()[:12]
    if resolved and rule:
        stmt = rule["statement"]
        estate.annotate(sid, type="business_rule", key=rid, value=stmt,
                        confidence=float(rule.get("confidence", 0.9)),
                        provenance=str(rule.get("provenance", {}).get("source", "extract-loop")),
                        replace=True, author=seat)
        estate.set_requirement(sid, requirement=stmt, validated=True, validated_by=seat)
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
                        provenance="extract-loop:risk", replace=True, author=seat)
        estate.set_requirement(sid, requirement=risk_req, validated=False, validated_by=seat)
    # Read-back re-derive: never trust the write's exit code alone. A caller holding the store
    # reads it back directly (`read_back(sid, key)`, one query instead of a third process).
    if read_back is not None:
        durable = read_back(sid, rid)
    else:
        durable = any(a.get("key") == rid for a in estate.read_annotations(sid))
    if not durable:
        raise RuntimeError(f"write not durable: {sid} missing annotation {rid} on read-back")


_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def _stdlib_zstd():
    """`compression.zstd` (Python 3.14+), or None."""
    try:
        from compression import zstd
    except ImportError:
        return None
    return zstd


_CONTENT_LIMIT = 4 * 1024 * 1024  # decompressed bytes one file may take (as the checkout read)


def _maybe_decompress(blob, limit: int = _CONTENT_LIMIT) -> bytes:
    """Estate stores content zstd-compressed; node spans are byte offsets into the
    DECOMPRESSED text. Slicing the raw blob feeds the model binary noise — observed
    live as whole batches of 'cannot state a rule'. Returns b'' when the blob is
    compressed but no decompressor is available, or decompresses past `limit` (read bounded,
    never fully inflated first), which routes framing to the fallback instead of producing
    garbage."""
    b = blob if isinstance(blob, bytes) else bytes(blob)
    if not b.startswith(_ZSTD_MAGIC):
        return b
    zstd = _stdlib_zstd()
    if zstd is not None:
        out = zstd.ZstdDecompressor().decompress(b, max_length=limit + 1)
    else:
        try:
            import io
            import zstandard  # a dependency before 3.14 (wicked-garden#1370)
        except ImportError:
            return b""
        # Streamed: estate's frames do not carry their content size, and the one-shot
        # `decompress` refuses those ("could not determine content size in frame header").
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(b)) as reader:
            out = reader.read(limit + 1)
    return b"" if len(out) > limit else out


class _DirectStore:
    """READ-ONLY direct sqlite access for structural context (CommandIQ req-engine v3 pattern):
    the per-node blast radius (1-hop caller/callee names) and source slices come straight from
    the store instead of one subprocess per node — the prior loop's latency dominator. All
    queries are reads; every write still goes through the estate CLI client (single surface)."""

    def __init__(self, db: str):
        import sqlite3
        from urllib.parse import quote
        self._c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
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
        # undirected USE adjacency for the hub-first fan-out: every relationship that says one
        # symbol uses another (calls, references, type relations, a route serving a handler).
        # Structural edges (contains, imports, defines, data flow) are not neighbourhood.
        self.adj = {}
        for r in self._c.execute("SELECT source, target, kind FROM edges"):
            kind = _edge_kind(r["kind"])
            if kind == "calls":
                self.callees.setdefault(r["source"], []).append(r["target"])
                self.callers.setdefault(r["target"], []).append(r["source"])
                self.in_deg[r["target"]] = self.in_deg.get(r["target"], 0) + 1
            if kind in _USE_EDGES and r["source"] != r["target"]:
                self.adj.setdefault(r["source"], set()).add(r["target"])
                self.adj.setdefault(r["target"], set()).add(r["source"])
        self._file_text = {}
        # When the store's content cannot be read here (zstd blobs on a Python without a zstd
        # decompressor), a caller that knows the repository root reads the file from it instead.
        self.repo_root: str | None = None

    _REPO_FILE_LIMIT = 4 * 1024 * 1024

    def _repo_file(self, rel: str, git_sha: str | None) -> bytes:
        """`rel` read from the registered repository (`repo_root`) — only when its bytes are the
        exact blob the store indexed (`git_sha`, git's blob id), since the node spans are offsets
        into THAT content. A regular file inside the root, opened without following a link and
        read bounded; b"" otherwise."""
        if not self.repo_root or not rel or not git_sha:
            return b""
        import stat as _stat
        root = os.path.realpath(self.repo_root)
        path = os.path.join(root, rel)
        if not os.path.realpath(path).startswith(root + os.sep):
            return b""
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        except OSError:
            return b""
        try:
            if not _stat.S_ISREG(os.fstat(fd).st_mode):
                return b""
            with os.fdopen(fd, "rb") as f:
                fd = -1
                data = f.read(self._REPO_FILE_LIMIT + 1)
        except OSError:
            return b""
        finally:
            if fd >= 0:
                os.close(fd)
        if len(data) > self._REPO_FILE_LIMIT:
            return b""
        blob_id = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
        if blob_id != git_sha:
            print(f"[extract-loop] {rel}: the checkout differs from the indexed content; its source "
                  "is left out", file=sys.stderr)
            return b""
        return data

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
                    "SELECT c.blob, f.git_sha FROM files f LEFT JOIN content c "
                    "ON c.git_sha = f.git_sha WHERE f.path = ?",
                    (file,),
                ).fetchone()
                if len(self._file_text) >= 128:  # bounded FIFO — long runs must not grow without limit
                    self._file_text.pop(next(iter(self._file_text)))
                text = _maybe_decompress(r["blob"]) if r and r["blob"] is not None else b""
                self._file_text[file] = text or self._repo_file(file, r["git_sha"] if r else None)
            blob = self._file_text[file]
            if end > start and end <= len(blob):
                return blob[start:end].decode("utf-8", errors="replace")[:cap]
        except Exception:
            pass
        return ""


_USE_EDGES = frozenset({"calls", "references", "instantiates", "extends", "implements",
                        "overrides", "serves", "invokes", "uses", "accesses"})


def _edge_kind(raw) -> str:
    """Normalise a stored edge kind: `calls`, `"calls"` and `{"other":"serves"}` → the bare word."""
    text = str(raw or "")
    try:
        import json as _json
        v = _json.loads(text)
    except ValueError:
        return text
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and len(v) == 1:
        return str(next(iter(v.values())))
    return text


_MAX_HUBS = 25

# wicked-garden#1366: in a JavaScript/TypeScript store, a call such as `s.startsWith(x)` or
# `map.get(k)` resolves to ANY local symbol of the same name, so a one-line helper that happens to
# share a builtin's name collects thousands of callers and PageRank makes it the first hub. A
# symbol whose name is a builtin method, in a JS/TS file, called from many files is such a
# collision: it is never a hub, never fanned out from (its "callers" are not its neighbourhood),
# and it is ordered after real code of the same distance. It is still mapped, in its turn.
_JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
_BUILTIN_NAMES = frozenset(
    # Object / Function
    "toString valueOf hasOwnProperty isPrototypeOf toJSON apply call bind constructor "
    "keys values entries assign create freeze is from of "
    # Array / iterables
    "at concat copyWithin every fill filter find findIndex findLast findLastIndex flat flatMap "
    "forEach includes indexOf join lastIndexOf map pop push reduce reduceRight reverse shift "
    "slice some sort splice toSorted toReversed unshift with length "
    # String
    "charAt charCodeAt codePointAt endsWith localeCompare match matchAll normalize padEnd "
    "padStart repeat replace replaceAll search split startsWith substring toLowerCase "
    "toUpperCase trim trimEnd trimStart "
    # Map / Set / WeakMap
    "add clear delete get has set size "
    # Promise
    "then catch finally resolve reject all allSettled race any "
    # Math / Number / JSON / Date / RegExp
    "abs ceil floor max min pow random round sign sqrt trunc parse stringify now test exec "
    "toFixed parseInt parseFloat isNaN isFinite getTime toISOString "
    # EventEmitter / streams / timers commonly shadowed
    "on off once emit write end close open next done send"
    .split()
)
_COLLISION_MIN_FILES = 8


def _bare_name(name: str) -> str:
    """`McpRegistry#test()` / `run-liveness/parse()` / `startsWith` -> the method's own name."""
    tail = re.split(r"[#./:]", name or "")[-1]
    return tail.split("(", 1)[0].strip()


# Test directories in any case (`Tests/` in .NET, `Specs/`); file-name patterns keep their case
# (`*Tests.cs` is a test, `Contest.py` is not).
_TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|specs?|e2e|fixtures?|testdata)/", re.IGNORECASE)
_TEST_PATH = re.compile(r"\.(test|spec)\.[^/]+$|(^|/)test_[^/]+\.py$|(^|/)tests?\.py$|"
                        r"_test\.(py|go|rs)$|_spec\.rb$|Tests?\.(cs|java|kt|swift|scala)$")


def is_test_path(file: str) -> bool:
    """A test, spec or fixture file: mapped in its turn, never where a page starts."""
    return bool(_TEST_DIR.search(file or "") or _TEST_PATH.search(file or ""))


# Files whose "behaviours" are keys and headings, not code: a data fixture, a manifest, a
# document. The indexer counts their keys as nodes, so coverage maps them, but what a seat states
# about a JSON key is not a requirement the product's code implements.
_DATA_EXTS = (".json", ".jsonc", ".json5", ".jsonl", ".yaml", ".yml", ".toml", ".lock", ".ini",
              ".cfg", ".conf", ".properties", ".csv", ".tsv", ".txt", ".md", ".mdx", ".rst",
              ".xml")


def is_data_path(file: str) -> bool:
    """A data, manifest or document file (by extension): its nodes are not product code."""
    return (file or "").lower().endswith(_DATA_EXTS)


def unconfirmed_reason(file: str, sourced: bool) -> str | None:
    """Why a rule stated about a unit in `file` is written unconfirmed whatever its confidence
    (wicked-garden#1370), or None when it may be validated: it needs its source, read on the
    host, and it must be product code, not a test or a data file (those are evidence of what the
    product does, recorded as accounted-for but never as a validated requirement)."""
    if is_test_path(file) or is_data_path(file):
        return NOT_PRODUCT_REASON
    if not sourced:
        return NO_SOURCE_REASON
    return None


def _not_a_hub(store, sid) -> bool:
    """A symbol that never seeds the fan-out: a JS/TS symbol named like a builtin method (its
    callers are any `x.get()` / `Math.round()` in the repo, wicked-garden#1366), or one in a test
    file (a page starts at the product's code)."""
    row = getattr(store, "node_row", {}).get(sid)
    if row is None:
        return False
    name, file = row[0], row[1] or ""
    if is_test_path(file):
        return True
    return file.endswith(_JS_EXTS) and _bare_name(name) in _BUILTIN_NAMES


def collision_sids(store) -> set:
    """The store's builtin-name collisions (wicked-garden#1366): a JS/TS symbol named like a
    builtin method that callers in at least `_COLLISION_MIN_FILES` distinct files reach."""
    out = set()
    for sid, row in getattr(store, "node_row", {}).items():
        name, file = row[0], row[1] or ""
        if not file.endswith(_JS_EXTS) or _bare_name(name) not in _BUILTIN_NAMES:
            continue
        files = {store.node_row.get(c, (None, None))[1] for c in getattr(store, "callers", {}).get(sid, ())}
        files.discard(None)
        if len(files) >= _COLLISION_MIN_FILES:
            out.add(sid)
    return out
# Positions per stripe window for parallel workers: the largest batch `_density_batch` may pick,
# so a full adaptive batch fits inside one window.
_STRIPE = 64


def hub_count(store) -> int:
    """How many hubs the fan-out starts from: about sqrt(connected nodes) / 4, between 1 and
    25 — one hub for a toy repo, a couple of dozen for a large one (so layer 0 is the
    load-bearing core, not a degree-sorted list of the whole graph)."""
    import math
    return max(1, min(_MAX_HUBS, round(math.sqrt(len(store.adj)) / 4)))


def hub_first_order(store, hubs: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Every node's extraction position and hop distance: multi-source BFS over the undirected
    use graph from `hubs` (most central first), neighbours in degree order. A node the BFS
    cannot reach (another component) is seeded next, highest degree first, its distance
    counting on from the last layer — so the order stays total and deterministic.

    Returns (rank, hops), both keyed by symbol string."""
    deg = {sid: len(ns) for sid, ns in store.adj.items()}
    sym_of = store.sym_of
    collide = collision_sids(store)

    def by_degree(sids):
        # A builtin-name collision's degree is its false callers: it goes after real code.
        # …and so do tests and builtin-named symbols (agy r1 on #1369): never ahead of the product.
        return sorted(sids, key=lambda x: (x in collide, _not_a_hub(store, x), -deg.get(x, 0),
                                           sym_of.get(x, "")))

    rank: dict[str, int] = {}
    hops: dict[str, int] = {}
    seen: set[int] = set()
    # Seeds: hubs that exist AND have use-graph neighbours (a file or module PageRank ranks high
    # through imports alone would fan out to nothing and burn the hub slot), each once.
    seeds = list(dict.fromkeys(
        store.sid_of[h] for h in hubs
        if store.sid_of.get(h) in store.adj and not _not_a_hub(store, store.sid_of[h])
    ))[: hub_count(store)]
    remaining = by_degree(store.sym_of.keys())
    cursor = 0  # forward-only: each candidate is skipped at most once (no N² rescans)
    base = 0
    while True:
        frontier = [s for s in seeds if s not in seen]
        if not frontier:
            while cursor < len(remaining) and remaining[cursor] in seen:
                cursor += 1
            if cursor >= len(remaining):
                break
            frontier = [remaining[cursor]]
        for s in frontier:
            seen.add(s)
        depth = base
        while frontier:
            nxt_layer = []
            for s in frontier:
                sym = sym_of.get(s)
                if sym is not None:
                    rank[sym] = len(rank)
                    hops[sym] = depth
                if s in collide:
                    continue  # its "neighbours" are every caller of a builtin's name
                for n in by_degree(store.adj.get(s, ())):
                    if n not in seen:
                        seen.add(n)
                        nxt_layer.append(n)
            frontier = nxt_layer
            depth += 1
        base = depth
        seeds = []
    return rank, hops


def _centrality_hubs(estate, store) -> tuple[list[str], str]:
    """The hubs to fan out from and who answered: estate's PageRank (`rank`), else the store's
    own degree (a store without the `rank` command, or a failed call — said on stderr)."""
    try:
        ranked = list(dict.fromkeys(estate.rank(200)))
        hubs = [h for h in ranked
                if store.sid_of.get(h) in store.adj and not _not_a_hub(store, store.sid_of[h])]
        if hubs:
            return hubs, "estate rank (PageRank)"
        print("[extract-loop] estate rank named no symbol with use-graph neighbours; hubs by degree "
              "instead", file=sys.stderr)
    except Exception as e:  # centrality is ordering quality, never a reason to stop
        print(f"[extract-loop] estate rank unavailable ({e}); hubs by degree instead", file=sys.stderr)
    by_deg = sorted((s for s in store.adj if not _not_a_hub(store, s)),
                    key=lambda s: (-len(store.adj[s]), store.sym_of.get(s, "")))
    return [store.sym_of[s] for s in by_deg[:_MAX_HUBS] if s in store.sym_of], "degree"


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
        from urllib.parse import quote
        con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
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


_OUT_OF_TIME = -1  # _ask_model: the budget ran out mid-batch; nothing from it is kept
_NO_MODEL = -2  # _ask_model (file mode): the model CLI cannot answer for this seat (not signed in)


def _ask_model(take: list[dict], framed: list[dict], ids: set[str], model_argv, dry_run: bool,
               deadline: float | None = None):
    """THE MODEL BOUNDARY (or the deterministic stub) for one batch: the rules by symbol id, or
    75 (EX_TEMPFAIL) when an outage persisted after one retry — the pass stops and nothing from
    the batch is written. A judgment failure over the whole batch returns {} (every node then
    RISK-floors — never a gap). With a `deadline` (file mode), no call or retry pause runs past
    it: a batch the budget cannot finish returns _OUT_OF_TIME and is left for the next pass."""
    by_id: dict[str, dict] = {}

    def left() -> float | None:
        return None if deadline is None else deadline - time.monotonic()

    def no_time(need: float = 1.0) -> bool:
        rem = left()
        return rem is not None and rem < need
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
            if no_time():
                return _OUT_OF_TIME
            try:
                rules = (_rule_extractor.extract_rules(framed, model_argv) if deadline is None
                         else _rule_extractor.extract_rules(framed, model_argv, timeout=left()))
                for r in rules:
                    if not isinstance(r, dict):
                        continue
                    rid = r.get("symbol_id")
                    if rid in ids:
                        by_id[rid] = r
                    elif isinstance(rid, str) and rid.strip().rstrip(".") in canon:
                        r["symbol_id"] = canon[rid.strip().rstrip(".")]
                        by_id[r["symbol_id"]] = r
            except Exception as e:
                if deadline is not None and _is_auth_failure(e):
                    print(f"[extract-loop] the rule model cannot answer in this seat ({e})",
                          file=sys.stderr)
                    return _NO_MODEL
                if _is_infra_failure(e):
                    infra_exc = e
                elif "exceeded" in str(e) and no_time(_RETRY_PAUSE + 30):
                    return _OUT_OF_TIME  # the budget, not the batch, ran out
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
                return 75  # EX_TEMPFAIL — the caller ends the pass
            if no_time(_RETRY_PAUSE + 30):
                return _OUT_OF_TIME
            print("[extract-loop] transient zero-yield/infra on batch — retrying once "
                  f"in {int(_RETRY_PAUSE)}s", file=sys.stderr)
            time.sleep(_RETRY_PAUSE)

    return by_id


def run(db: str, *, time_budget: float, limit: int, batch: int, dry_run: bool,
        project_dir: Path | None = None, cluster_offset: int = 0, workers: int = 0) -> int:
    # Parallel workers stripe the STATIC order: worker k of N owns every window w (of _STRIPE
    # consecutive positions) with w % N == k, so two workers never select the same node however
    # fast either finishes. `workers` defaults to offset + 1 (a lone worker owns everything).
    offset = max(0, cluster_offset)
    workers = max(workers, offset + 1)
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

    # HUB-FIRST, FAN-OUT ORDER: computed once per pass over the whole graph (deterministic, so
    # every run derives the same order and resumes at the frontier).
    order: dict[str, int] = {}
    hops: dict[str, int] = {}
    if store is not None:
        hubs, how = _centrality_hubs(estate, store)
        order, hops = hub_first_order(store, hubs)
        print(f"[extract-loop] order: hub-first from {min(len(hubs), hub_count(store))} hub(s) by {how}, "
              f"fanning out over {len(order)} node(s)", file=sys.stderr)

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

        # HUB-FIRST ORDER: the unmapped worklist in graph order — hubs, then their neighbours,
        # then theirs. Consecutive nodes are graph neighbours, so a batch holds RELATED symbols
        # (shared context grounds the model's rules better AND cheaper), with a density-adaptive
        # batch size (thin wrappers pack bigger batches, dense logic smaller). The head of the
        # ordered worklist IS the frontier: everything before it is already mapped. Flat slice
        # as fallback (no direct store).
        if store is not None and order:
            tail = len(order)
            worklist.sort(key=lambda n: (order.get(n["symbol_id"], tail), n["symbol_id"]))
            if workers > 1:
                def window(n):
                    return order.get(n["symbol_id"], tail) // _STRIPE
                mine = [n for n in worklist if window(n) % workers == offset]
                if not mine:
                    print(f"[extract-loop] worker {offset} of {workers}: its windows are mapped; "
                          f"{len(worklist)} unaccounted remain in other workers' windows", file=sys.stderr)
                    return 0
                # One window at a time, so a batch never crosses into another worker's stripe.
                head = [n for n in mine if window(n) == window(mine[0])]
            else:
                head = worklist
            take = head[: _density_batch(head, store, batch)]
            front = take[0]["symbol_id"]
            print(f"[extract-loop] frontier: {front} (hop {hops.get(front, '?')}, "
                  f"position {order.get(front, tail) + 1} of {tail})", file=sys.stderr)
        else:
            take = worklist[:batch]
        if limit:
            take = take[:max(0, limit - processed)]

        # Frame each node: source slice + blast-radius neighbors (direct reads; the old
        # per-node subprocess path survives only as the fallback).
        framed, ids, sourced = [], set(), {}
        for n in take:
            sid, name = n["symbol_id"], n.get("name", "")
            slice_txt, neighbors = "", []
            if not dry_run:
                if store is not None:
                    slice_txt = store.source_slice(sid)
                    neighbors = store.blast_neighbors(sid)
                # Sourced only by the store's indexed bytes: the `estate source` fallback below
                # looks a NAME up (for a symbol id it can answer "no symbols found", or another
                # symbol's code), so it may frame the unit but never makes a rule validatable.
                sourced[sid] = bool(slice_txt.strip())
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
        by_id = _ask_model(take, framed, ids, model_argv, dry_run)
        if isinstance(by_id, int):
            return by_id

        # Deterministic decision + write per node — RISK-FLOOR: every node terminates.
        for n in take:
            sid = n["symbol_id"]
            decide_and_write(estate, store, sid, n.get("name", ""), by_id.get(sid), ids,
                             node_community, community_sizes,
                             unconfirmed=(None if dry_run else
                                          unconfirmed_reason(n.get("file", ""),
                                                             sourced.get(sid, False))))
            processed += 1


NO_SOURCE_REASON = "no source: its indexed code could not be read, so the statement is unconfirmed"
NOT_PRODUCT_REASON = ("not product code (a test, data or document file): recorded, unconfirmed, "
                      "never a validated requirement")


def decide_and_write(estate, store, sid: str, name: str, rule: dict | None, ids: set[str],
                     node_community: dict[str, str], community_sizes: dict[str, int],
                     seat: str | None = None, read_back=None,
                     unconfirmed: str | None = None) -> str:
    """The deterministic decision + write for ONE node (RISK-FLOOR: it terminates RESOLVED or
    RISK). Shared by this harness and the host apply step (`apply_rules.py`), so a rule stated
    in a seat container is judged exactly like one the host's own model returned. `unconfirmed`
    is why a rule about this node may not be validated ([`unconfirmed_reason`]: no source read
    on the host, or not product code): it is then written unconfirmed (RISK, not validated)
    whatever its confidence (wicked-garden#1370). Returns "resolved", "risk", "unconfirmed" (a
    valid rule written unconfirmed for that reason; a RISK write) or "kept" (a statement-less
    floor skipped over existing content)."""
    ok, reason = (_rule_extractor.validate_rule(rule, ids) if rule
                  else (False, "no rule returned for this node"))
    if ok and unconfirmed:
        _write_node(estate, sid, name, rule, False, unconfirmed, seat=seat, read_back=read_back)
        return "unconfirmed"
    if ok:
        adjusted = float(rule["confidence"]) * _cohesion(sid, node_community, community_sizes)
        resolved = adjusted >= RESOLVE_THRESHOLD
        _write_node(estate, sid, name, rule, resolved,
                    "below confidence threshold" if not resolved else "", seat=seat, read_back=read_back)
        return "resolved" if resolved else "risk"
    if (rule or {}).get("statement"):
        _write_node(estate, sid, name, rule, False, reason, seat=seat, read_back=read_back)
        return "risk"
    if _has_statement(store, sid):
        # Statement-less floor over existing content would DEGRADE the store — a re-queued
        # node keeps its prior statement instead. Floors only ever fill blanks; content is
        # monotonic.
        print(f"[extract-loop] floor skipped for {sid} (existing statement kept)", file=sys.stderr)
        return "kept"
    _write_node(estate, sid, name, rule, False, reason, seat=seat, read_back=read_back)
    return "risk"


# --- FILE MODE: the seat-container half of domain-extraction (wicked-garden#1362) ------------
#
# A seat container has no `wicked-core`, no `wicked-estate` and no writable store. The host's
# `extract-prepare` step leaves the framed hub-first WORKLIST in the run's worktree; here the
# model states the rules and they go to the RULES file beside it — never to a store. The host's
# `extract-apply` step checks that file and writes it (`apply_rules.py`).

def read_worklist(base: Path, rel: str) -> dict:
    """The worklist the host prepared, shape-checked (it sits in a seat-writable tree)."""
    doc = rules_file.read_json_file(base, rel, limit=rules_file.MAX_WORKLIST_BYTES)
    if not isinstance(doc, dict) or doc.get("schema") != rules_file.WORKLIST_SCHEMA:
        raise rules_file.RulesFileRefused(
            f"{rel!r} is not a {rules_file.WORKLIST_SCHEMA} worklist")
    units = doc.get("units")
    if not isinstance(units, list) or not all(
            isinstance(u, dict) and isinstance(u.get("symbol_id"), str) for u in units):
        raise rules_file.RulesFileRefused(f"{rel!r} has no list of units with symbol ids")
    return doc


def _units_batch(units: list[dict], base_batch: int) -> int:
    """`_density_batch` over the framed source the worklist already carries."""
    if not units:
        return base_batch
    sample = units[: min(len(units), 12)]
    avg = sum(len(str(u.get("source") or "")[:2000]) for u in sample) / len(sample)
    mult = 1.6 if avg < 300 else (0.6 if avg > 1500 else 1.0)
    return max(4, min(64, int(base_batch * mult)))


def to_entry(sid: str, rule: dict | None) -> dict:
    """A model's rule as a rules-file entry that conforms to the schema. What the model got
    wrong stays wrong (an empty statement, missing provenance) so the host's validator
    RISK-flags it; what cannot be carried at all (a non-number confidence, unknown keys,
    oversized or control-character text) is dropped or clamped here."""
    rule = rule if isinstance(rule, dict) else {}
    stmt = rule.get("statement")
    stmt = rules_file._CONTROL_RE.sub(" ", stmt)[: rules_file.MAX_STATEMENT] \
        if isinstance(stmt, str) else ""
    conf = rule.get("confidence")
    ok_conf = isinstance(conf, (int, float)) and not isinstance(conf, bool) \
        and conf == conf and 0.0 <= conf <= 1.0
    entry = {"symbol_id": sid, "statement": stmt, "confidence": float(conf) if ok_conf else 0.0}
    prov = rule.get("provenance")
    if isinstance(prov, dict):
        # Carry what the schema can hold (as the store-mode harness ignores extra keys): known
        # keys only, text cleaned and clamped, source kinds filtered to the valid ones.
        clean: dict = {}
        for key, limit in (("source", rules_file.MAX_PROVENANCE_STR),
                           ("ref", rules_file.MAX_SYMBOL_ID)):
            if isinstance(prov.get(key), str):
                clean[key] = rules_file._CONTROL_RE.sub(" ", prov[key])[:limit]
        kinds = prov.get("source_kinds")
        if isinstance(kinds, list):
            clean["source_kinds"] = [k for k in kinds if isinstance(k, str)
                                     and k in rules_file.SOURCE_KINDS][: rules_file.MAX_SOURCE_KINDS]
        if rules_file.check_rule_entry({**entry, "provenance": clean}) is None:
            entry["provenance"] = clean
    if rules_file.check_rule_entry(entry) is not None:  # e.g. text that is not valid Unicode
        entry["statement"] = ""
    return entry


def run_files(base: Path, worklist_rel: str, rules_rel: str, *, time_budget: float, limit: int,
              batch: int, dry_run: bool) -> int:
    worklist = read_worklist(base, worklist_rel)
    units = worklist["units"]
    rules_file.check_writable(base, rules_rel)  # an unusable destination fails before any model call
    seat = rules_file.seat_name(os.environ.get("WICKED_RUN_AGENT"))
    model_argv = None if dry_run else _clients.rule_model_argv(base)
    if not dry_run and model_argv is None:
        print("[extract-loop] no rule model in this seat (no `claude` on PATH and no "
              "WICKED_RULE_MODEL_BIN). State the rules yourself as the extractor skill says, then "
              f"check the file: extract_loop.py --check-rules {rules_rel}", file=sys.stderr)
        return 2

    # Resume: entries already in a conforming rules file are kept and their units skipped.
    done: list[dict] = []
    try:
        _, done, refused = rules_file.check_rules_doc(rules_file.read_json_file(base, rules_rel))
        if refused:
            print(f"[extract-loop] {len(refused)} entr(ies) of the existing {rules_rel} are outside "
                  "the schema and are dropped", file=sys.stderr)
    except FileNotFoundError:
        pass
    except rules_file.RulesFileRefused as e:
        print(f"[extract-loop] starting {rules_rel} afresh: {e}", file=sys.stderr)
    unit_ids = {u["symbol_id"] for u in units}
    done = [e for e in done if e["symbol_id"] in unit_ids]  # an earlier pass's leftovers drop out
    stated = {e["symbol_id"] for e in done}
    pending = [u for u in units if u["symbol_id"] not in stated]
    print(f"[extract-loop] file mode: {len(units)} unit(s) in the worklist, {len(stated)} already "
          f"stated, {len(pending)} to go; {worklist.get('order', '')}", file=sys.stderr)

    deadline = time.monotonic() + time_budget
    processed = 0
    rc = 0
    while pending:
        if time.monotonic() >= deadline or (limit and processed >= limit):
            print(f"[extract-loop] budget reached; {len(pending)} unit(s) left — re-invoke to "
                  "resume", file=sys.stderr)
            break
        take = pending[: _units_batch(pending, batch)]
        if limit:
            take = take[: max(0, limit - processed)]
        room = rules_file.MAX_RULES - len(done)
        if room <= 0:
            print(f"[extract-loop] {rules_rel} holds the most entries one file may carry "
                  f"({rules_file.MAX_RULES}); stopping here", file=sys.stderr)
            break
        take = take[:room]
        framed = [_rule_extractor.frame_context(
            u, str(u.get("source") or "")[:4000], cluster_label=u.get("cluster"),
            neighbor_names=[str(x) for x in (u.get("neighbors") or [])][:8]) for u in take]
        ids = {u["symbol_id"] for u in take}
        by_id = _ask_model(take, framed, ids, model_argv, dry_run, deadline=deadline)
        if by_id == _NO_MODEL:
            print("[extract-loop] no usable rule model in this seat. State the rules yourself as "
                  "the extractor skill says, then check the file: extract_loop.py --check-rules "
                  f"{rules_rel}", file=sys.stderr)
            rc = 2
            break
        if by_id == _OUT_OF_TIME:
            print("[extract-loop] the budget ran out inside a batch; it is left for the next "
                  "pass", file=sys.stderr)
            break
        if isinstance(by_id, int):
            rc = by_id
            break
        grown = done + [to_entry(u["symbol_id"], by_id.get(u["symbol_id"])) for u in take]
        doc = rules_file.rules_doc(seat, grown)
        if len(rules_file.encoded(doc)) > rules_file.MAX_RULES_BYTES:
            print(f"[extract-loop] {rules_rel} is at the size one file may carry; stopping here",
                  file=sys.stderr)
            break
        done = grown
        rules_file.write_json_file(base, rules_rel, doc)
        processed += len(take)
        pending = pending[len(take):]
    if rc == 0 and units and not done:
        # Nothing stated (the budget or a limit ran out on the first batch): no file, so the host's
        # apply step refuses instead of applying an empty one; resume continues from the start.
        print("[extract-loop] no unit was stated in this pass", file=sys.stderr)
        rc = 75
    final = rules_file.rules_doc(seat, done)
    if rc == 0 and len(rules_file.encoded(final)) <= rules_file.MAX_RULES_BYTES:
        # Also when nothing new was stated (an empty worklist, a finished resume), so the host's
        # apply step finds the file. After an outage (rc 75) a pass that stated nothing leaves no
        # file, and apply refuses rather than applying an empty one. A rewrite that would outgrow
        # the limit keeps the conforming checkpoint already on disk.
        rules_file.write_json_file(base, rules_rel, final)
    with_rule = sum(1 for e in done if e["statement"].strip())
    print(f"[extract-loop] {len(done)} of {len(units)} unit(s) in {rules_rel} ({with_rule} with a "
          f"stated rule); the host's extract-apply step checks and writes them", file=sys.stderr)
    return rc


def check_rules(base: Path, rules_rel: str, worklist_rel: str | None) -> int:
    """`--check-rules`: is the rules file inside the schema? Exit 0 when every entry conforms."""
    try:
        seat, accepted, refused = rules_file.check_rules_doc(
            rules_file.read_json_file(base, rules_rel))
    except FileNotFoundError:
        print(f"[extract-loop] no rules file at {rules_rel}", file=sys.stderr)
        return 1
    except rules_file.RulesFileRefused as e:
        print(f"[extract-loop] REFUSED: {e}", file=sys.stderr)
        return 1
    left = ""
    if worklist_rel:
        try:
            units = read_worklist(base, worklist_rel)["units"]
        except (FileNotFoundError, rules_file.RulesFileRefused) as e:
            print(f"[extract-loop] worklist {worklist_rel}: {e}", file=sys.stderr)
            return 1
        unit_ids = {u["symbol_id"] for u in units}
        refused += [{"index": None, "symbol_id": e["symbol_id"],
                     "why": "is not a unit of the worklist (copy the symbol_id verbatim)"}
                    for e in accepted if e["symbol_id"] not in unit_ids]
        have = {e["symbol_id"] for e in accepted}
        left = f"; {sum(1 for u in units if u['symbol_id'] not in have)} worklist unit(s) not stated"
    for r in refused[:50]:
        print(f"[extract-loop] entry {r['index'] if r['index'] is not None else '-'} "
              f"({r['symbol_id'] or '?'}): {r['why']}", file=sys.stderr)
    print(f"[extract-loop] {rules_rel}: {len(accepted)} entr(ies) conform, {len(refused)} outside "
          f"the schema (seat {seat or '-'}){left}", file=sys.stderr)
    return 0 if not refused else 1


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
                    help="parallel workers: this worker's index (0-based) among --workers")
    ap.add_argument("--workers", type=int, default=0,
                    help="parallel workers sharing the hub-first order (default: --cluster-offset + 1); "
                         "each owns a disjoint stripe of it")
    ap.add_argument("--worklist", default=None,
                    help="FILE MODE (seat container): the host-prepared worklist, relative to the "
                         f"working directory (the preset's is {rules_file.WORKLIST_REL})")
    ap.add_argument("--rules-out", default=None,
                    help="FILE MODE: where the stated rules go, relative to the working directory "
                         f"(the preset's is {rules_file.RULES_REL}); no store is written")
    ap.add_argument("--check-rules", default=None, metavar="RULES",
                    help="check a rules file against the schema and exit (0 = it conforms)")
    args = ap.parse_args(argv)
    base = Path.cwd()
    if args.check_rules:
        return check_rules(base, args.check_rules, args.worklist)
    if args.worklist or args.rules_out:
        if not (args.worklist and args.rules_out):
            ap.error("file mode needs both --worklist and --rules-out")
        try:
            return run_files(base, args.worklist, args.rules_out, time_budget=args.time_budget,
                             limit=args.limit, batch=args.batch, dry_run=args.dry_run)
        except FileNotFoundError as e:
            print(f"[extract-loop] no worklist at {e}: the host's extract-prepare step writes it",
                  file=sys.stderr)
            return 1
        except rules_file.RulesFileRefused as e:
            print(f"[extract-loop] REFUSED: {e}", file=sys.stderr)
            return 1
    if not args.db:
        ap.error("--db is required (or set $WICKED_ESTATE_DB)")
    return run(args.db, time_budget=args.time_budget, limit=args.limit,
               batch=args.batch, dry_run=args.dry_run, cluster_offset=args.cluster_offset,
               workers=args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
