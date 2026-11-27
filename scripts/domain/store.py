"""J6 v3 persistence and reuse (DES-j6-build §4, v1 §3.7-3.8): what a run writes onto the estate nodes, and what a
later run takes from it before any model call. 0 model calls.

**What is written** (through ``wicked-estate write-batch``, one transaction, ``replace`` by key; the store has no delete,
so a statement, group, follow-up or target that a later run no longer has is re-written with ``status: retired``,
which every reader skips):

- ``business_rule:<statement id>`` on the statement's anchor node. The value is JSON: ``statement`` (the rendered
  text, ``render.py``), ``contract`` (the whole statement as the checker left it: anchor, claims, context, verdicts,
  repair), ``status`` (Checked or open), ``batch_hash``, ``target_hash`` and ``fetched_files``.
- ``domain_target:<target id>`` on the target's anchor node: the target, its text hash, its batch (files and hash),
  its pieces, its statement ids, its not-rules and its state. This is what reuse reads.
- ``rule_group:<group hash>`` on the anchor of the group's first cited statement: the group (``prose.prose_all``)
  and its ``inputs`` (each statement it rests on, with the hash of its text as the writer read it) and ``desc``.
  A group is reused while every one of its inputs reads the same; only the others are written again.
- ``domain_followup:<row hash>`` on the target's node, or the file's node for a range or the scope.

**Reuse, per target of the new scope** (v1 §3.8; the proof's ``step10.decide``):

1. a prior target in the same file whose text hashes the same, and whose batch (every file the batch showed or
   the check fetched, exact bytes) hashes the same: everything is carried, with zero calls;
2. the batch changed, but every piece (the target and the enclosing unit of every line a statement cites) is found
   again by its exact text: the statements are moved to the new lines and re-validated (checked again);
3. anything else: the target is extracted again.

``target_hash`` is the hash of the pieces, so a ruling made on a statement can tell when its code has changed.
Known residue (v1 §3.8): a file outside the batch that changes a value the batch reads is not seen.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import graph as lib  # noqa: E402
from domain import lookup  # noqa: E402

RULE, TARGET, GROUP, FOLLOWUP, RULING = "business_rule", "domain_target", "rule_group", "domain_followup", "rule_ruling"
RUN = "domain_run"
TYPES = (RULE, TARGET, GROUP, FOLLOWUP)
RETIRED = "retired"
AUTHOR = "wicked-garden/domain-run"
ESTATE_ENV = "WICKED_ESTATE_BIN"
UNIT_KINDS = ("function", "method", "step", "module", "class", "constant", "variable", "interface", "type_alias")
PROSE_FILES = ("prompts/prose.txt", "prompts/prose_check.txt", "prompts/prose_repair.txt")
# garden#1610: the host code that decides what is stated (the M checks, graph.updates_records, extract.cite_copybooks,
# the scope and its config, the batches, the R context, the renderer, the answer parsing, the reuse and the stored rows)
# is no frozen file. A change to it that alters what is stated bumps HOST, which moves the stating version as a changed
# prompt would; tests/domain/test_v3_frozen.py pins these files, and every other file of the package is named there
# as not stating, so a new module is judged too.
HOST = 0
HOST_FILES = ("batches.py", "check.py", "cobol_ctx.py", "cobol_flow.py", "defs.py", "extract.py", "graph.py", "lookup.py",
              "model_calls.py", "r_stage.py", "reach.py", "render.py", "run.py", "scope.py", "scope_config.json",
              "store.py", "union.py")
# garden#1625: the same for the prose. The host code that decides what the prose says (the grouping, the housekeeping
# move, the repair guards, what a sentence may cite) is no frozen file; a change to it that alters the prose bumps
# PROSE_HOST, which moves the prose version. tests/domain/test_v3_frozen.py pins these files.
PROSE_HOST = 0
PROSE_HOST_FILES = ("prose.py",)


def _counter(name, n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError(f"store.{name} must be an integer 0 or above, not {n!r}")
    return n


def pipeline_versions(sums=os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHA256SUMS"), host=None,
                      prose_host=None):
    """The versions of the pipeline that states (extract, check, repair, R, cards, contract) and that writes the prose,
    from the frozen hashes in ``SHA256SUMS`` (tests/domain/test_v3_frozen.py ties them to the files). Each stored target
    and rule group carries the version that made it, and a run says how many were made by an earlier one
    (garden#1601); a fresh store makes them again. :data:`HOST` above 0 moves the stating version too (garden#1610),
    and :data:`PROSE_HOST` above 0 the prose version (garden#1625); at 0 each version is the frozen files' alone, so the
    stores made before the counters existed keep theirs."""
    host = _counter("HOST", HOST if host is None else host)
    prose_host = _counter("PROSE_HOST", PROSE_HOST if prose_host is None else prose_host)
    with open(sums) as fh:
        lines = sorted(" ".join(ln.split()) for ln in fh if ln.strip())
    def v(sel):
        return sha("\n".join(ln for ln in lines if sel(ln.split()[1])).encode())[:16]
    stating = v(lambda f: f not in PROSE_FILES)
    if host > 0:
        stating = sha(f"{stating}\0host {host}".encode())[:16]
    prose = v(lambda f: f in PROSE_FILES)
    if prose_host > 0:
        prose = sha(f"{prose}\0prose host {prose_host}".encode())[:16]
    return stating, prose


def sha(b):
    return hashlib.sha256(b).hexdigest()


STATING, PROSE = pipeline_versions()


def _blines(repo, f):
    try:
        return lib.fbytes(repo, f).split(b"\n")
    except OSError:
        return None


def window_sha(repo, f, a, b):
    """The hash of lines ``a..b`` of ``f`` (1-based, inclusive), exact bytes; ``None`` when the file or lines are gone."""
    L = _blines(repo, f)
    if L is None or a < 1 or b > len(L) or a > b:
        return None
    return sha(b"\n".join(L[a - 1:b]))


def batch_hash(repo, files):
    """The exact bytes of every file of a batch (v1 §3.8): no normalization, no line numbers."""
    h = hashlib.sha256()
    for f in sorted(set(files)):
        h.update(f.encode() + b"\0")
        try:
            h.update(lib.fbytes(repo, f))
        except OSError:
            h.update(b"\0missing")
        h.update(b"\0")
    return h.hexdigest()


MAX_CITED = 5000  # lines one citation may span; a longer (model-made) range counts by its first line only


def oversized(st):
    """The files a statement cites by a range longer than :data:`MAX_CITED` (their whole file is one piece)."""
    out = set()
    for c in st.get("claims") or []:
        for r in [r for key in ("lines", "guards") if isinstance(c, dict) and isinstance(c.get(key), list) for r in c[key]]:
            p = lookup.pref(r)
            if p and p[2] - p[1] >= MAX_CITED:
                out.add(p[0])
    return out


def cited(st):
    """The (file, line) pairs a statement cites: its claims' lines and guards, its concerns' lines (garden#1548: a
    concern can cite a test outside its paragraph), and its context references."""
    out = set()
    cs = st.get("concerns") if isinstance(st.get("concerns"), list) else []
    for c in list(st.get("claims") or []) + cs:
        if not isinstance(c, dict):
            continue
        refs = [r for key in ("lines", "guards") if isinstance(c.get(key), list) for r in c[key] if isinstance(r, str)]
        for r in refs:
            p = lookup.pref(r)
            if p:
                out.update((p[0], i) for i in range(p[1], (p[2] if p[2] - p[1] < MAX_CITED else p[1]) + 1))
    for x in st.get("context") or []:
        p = lookup.pref(x.get("at") or "") if isinstance(x, dict) else None
        if p:
            out.add((p[0], p[1]))
    return out


def _unit_spans(repo):
    spans = {}
    for n in lib.load(repo).nodes.values():
        if n["kind"] in UNIT_KINDS and n["el"] >= n["sl"]:
            spans.setdefault(n["file"], []).append(lib.span1(n))
    return spans


def enclosing(spans, targets, f, i):
    """The smallest unit holding line ``i`` of ``f``: an estate node's span, else a scope target's lines, else the file."""
    best = None
    for a, b in spans.get(f, []):
        if a <= i <= b and (best is None or b - a < best[1] - best[0]):
            best = (a, b)
    if best is None:
        best = next((tuple(t["lines"]) for t in targets if t["file"] == f and t["lines"][0] <= i <= t["lines"][1]), None)
    return best


def pieces(repo, t, statements, spans, targets):
    """[file, first line, line count, hash] for the target and the enclosing unit of every line its statements cite."""
    want = {(t["file"], t["lines"][0], t["lines"][1])}
    for st in statements:
        for f in oversized(st):
            want.add((f, 1, max(len(_blines(repo, f) or []), 1)))
        for f, i in cited(st):
            sp = enclosing(spans, targets, f, i)
            if sp is None:
                L = _blines(repo, f) or []
                sp = (1, max(len(L), 1))
            want.add((f, sp[0], sp[1]))
    out = []
    for f, a, b in sorted(want):
        out.append([f, a, b - a + 1, window_sha(repo, f, a, b)])
    return out


def target_hash(ps):
    return sha(json.dumps(ps, sort_keys=True).encode())


def find_window(repo, f, a, n, h):
    """Where the ``n`` lines that hashed ``h`` at line ``a`` of ``f`` now start (``a`` first), or ``None``."""
    L = _blines(repo, f)
    if L is None or h is None:
        return None
    if a + n - 1 <= len(L) and sha(b"\n".join(L[a - 1:a - 1 + n])) == h:
        return a
    found = [s for s in range(1, len(L) - n + 2) if sha(b"\n".join(L[s - 1:s - 1 + n])) == h]
    # moved to exactly one place; two copies of the text are not told apart by text, so the target is extracted again
    return found[0] if len(found) == 1 else None


# ---------------- the run's records ----------------
def target_record(repo, t, call, statements, not_rules, state, spans, targets):
    files = sorted(set(call["files"]) | {f for s in statements for f in s.get("fetched_files") or []})
    ps = pieces(repo, t, statements, spans, targets)
    return dict(target=t["id"], file=t["file"], lines=list(t["lines"]), text_sha=window_sha(repo, t["file"], *t["lines"]),
                batch_files=files, batch_hash=batch_hash(repo, files), pieces=ps, target_hash=target_hash(ps),
                statements=[s["id"] for s in statements], not_rules=not_rules, state=state, call=call["id"],
                pipeline=STATING)


def decide(repo, rec):
    """carry (0 calls) | revalidate (with the line moves {(file, old first line): new first line}) | extract."""
    if batch_hash(repo, rec["batch_files"]) == rec["batch_hash"]:
        return "carry", {}
    moves = {}
    for f, a, n, h in rec["pieces"]:
        s = find_window(repo, f, a, n, h)
        if s is None:
            return "extract", {}
        moves[(f, a)] = (n, s)
    return "revalidate", moves


def _move_ref(r, moves):
    p = lookup.pref(r)
    if not p:
        return r, True
    f, a, b = p
    for (mf, ma), (n, s) in moves.items():
        if mf == f and ma <= a and b <= ma + n - 1:
            d = s - ma
            return (f"{f}:{a + d}" if a == b else f"{f}:{a + d}-{b + d}"), True
    return r, False


def relocate(st, moves):
    """``st`` with every cited line moved by the piece holding it; ``None`` when a citation is in no piece."""
    st = json.loads(json.dumps(st))
    ok = True
    for c in list(st.get("claims") or []) + [x for x in (st.get("concerns") if isinstance(st.get("concerns"), list) else []) if isinstance(x, dict)]:
        for key in ("lines", "guards"):
            if isinstance(c.get(key), list) and c[key]:
                moved = [_move_ref(r, moves) for r in c[key]]
                c[key] = [r for r, _ in moved]
                ok &= all(m for _, m in moved)
    for x in st.get("context") or []:
        if isinstance(x, dict) and x.get("at"):
            x["at"], m = _move_ref(x["at"], moves)
            ok &= m
    a = st.get("anchor") or {}
    if a.get("file") and a.get("lines"):
        r, m = _move_ref(f"{a['file']}:{a['lines'][0]}-{a['lines'][1]}", moves)
        p = lookup.pref(r)
        if p:
            a["lines"] = [p[1], p[2]]
        ok &= m
    return st if ok else None


# ---------------- reading the store (read-only) ----------------
def load(db):
    """The store's live records: {type: {key suffix: value}} for every J6 type, retired ones left out, and only those
    on a node the store still has (a re-index that drops a node leaves its annotations behind; they are not live)."""
    out = {t: {} for t in TYPES + (RULING,)}
    if not db or not os.path.exists(db):
        return out
    con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        rows = con.execute(f"select a.key, a.value, a.type from annotations a join nodes n on n.symbol = a.node_sym "
                           f"where a.type in ({','.join('?' * (len(TYPES) + 1))}) order by a.id", TYPES + (RULING,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    con.close()
    for key, value, typ in rows:
        try:
            v = json.loads(value)
        except ValueError:
            continue
        name = key.split(":", 1)[1] if ":" in key else key
        if isinstance(v, dict) and v.get("status") == RETIRED:
            out[typ].pop(name, None)
            continue
        out[typ][name] = v
    return out


def prior_targets(prior):
    """The prior run's targets with their statements (copies): ``{"id": {target id: rec}, "text": {(file, text hash):
    [rec, ...]}}``, each rec with ``_statements``."""
    rules = prior[RULE]
    by = {"id": {}, "text": {}}
    for rec in prior[TARGET].values():
        sts = [json.loads(json.dumps(rules[i]["contract"])) for i in rec.get("statements") or [] if i in rules]
        if len(sts) != len(rec.get("statements") or []):
            continue  # a statement went missing: not reusable
        r = dict(rec, _statements=sts)
        by["id"][rec["target"]] = r
        by["text"].setdefault((rec["file"], rec["text_sha"]), []).append(r)
    return by


def match_prior(by, t, text_sha, used, current_ids=()):
    """The prior record for target ``t``: the same target id with the same text, else the one prior target in the same
    file whose text hashes the same, when no target of this scope has that prior target's id (its own target keeps it)
    and none has taken it. Two identical texts are never merged into one target."""
    r = by["id"].get(t["id"])
    if r and r["file"] == t["file"] and r["text_sha"] == text_sha and r["target"] not in used:
        return r
    same = by["text"].get((t["file"], text_sha), [])
    cands = [c for c in same if c["target"] not in used and c["target"] not in current_ids]
    return cands[0] if len(cands) == 1 and len(same) == 1 else None


# ---------------- writing (wicked-estate write-batch) ----------------
def symbol_for(repo, f, sym=None):
    """``sym`` when it is a node of the store, else the node that best stands for file ``f`` (its module, else its
    widest node); ``None`` when the file has no node."""
    g = lib.load(repo)
    if sym and sym in g.sym2sid:
        return sym
    ns = [n for n in g.nodes.values() if n["file"] == f]
    if not ns:
        return None
    mod = [n for n in ns if n["kind"] == "module"]
    best = (mod or sorted(ns, key=lambda n: (n["sl"] - n["el"], n["sl"])))[0]
    return best["sym"]


def content_hash(st):
    """What a statement says, apart from where it sits: its file and its claims (type, text, guards), never line
    numbers. A ruling on a statement keys on it, so a ruling never moves to a different statement that took the same
    positional id, and survives a move of the same statement."""
    a = st.get("anchor") if isinstance(st.get("anchor"), dict) else {}
    claims = [[c.get(k) for k in ("type", "text", "when", "unless", "of")] for c in st.get("claims") or [] if isinstance(c, dict)]
    return sha(json.dumps([a.get("file"), claims], sort_keys=True, default=str).encode())


def _compact(v):
    """JSON as serde_json's ``Value::to_string`` writes it: no spaces, UTF-8 as is."""
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def statement_key(st):
    """wicked-core's ``statement_key`` (crates/wicked-governance/src/domain_extract.rs, R04), byte for byte: ``v1:`` and
    the sha256 of ``[anchor file, claims as [i, type, text, when, unless, of]]``, the claims ordered by their index (a
    non-negative integer, anything else last) and then by their own JSON. A person's ruling names the statement by it,
    so a ruling never follows a statement whose claims or guards changed."""
    a = st.get("anchor") if isinstance(st.get("anchor"), dict) else {}
    cs = st.get("claims") if isinstance(st.get("claims"), list) else []
    claims = [[c.get(k) for k in ("i", "type", "text", "when", "unless", "of")] for c in cs if isinstance(c, dict)]
    top = 2 ** 64 - 1

    def order(c):
        i = c[0]
        ok = isinstance(i, int) and not isinstance(i, bool) and 0 <= i <= top
        return (i if ok else top, _compact(c))

    claims.sort(key=order)
    return "v1:" + sha(_compact([a.get("file"), claims]).encode())


def live_ruling(prior, subject, ident, target_hash, st=None):
    """The person's ruling on statement ``st`` (``subject`` "statement") or on target ``ident`` ("target"), as
    ``wicked-core domain-ruling`` wrote it (``rule_ruling:<subject>:<id>``), when it still applies: made on this
    target's code (``target_hash``) and, for a statement, on this statement (its ``statement_key``). Else ``None``."""
    r = ((prior or {}).get(RULING) or {}).get(f"{subject}:{ident}")
    if not isinstance(r, dict) or r.get("action") not in ("confirm", "reject") or r.get("target_hash") != target_hash:
        return None
    if subject == "statement" and (st is None or r.get("statement_key") != statement_key(st)):
        return None
    return r


def run_row(repo, records, scope_in, scope_hash, run_id, at):
    """The run's own record (DES-C2 §8, F02): the scope it was asked, its hash, the run and when, as
    ``domain_run:<run id>`` on the first target of the scope that has a node, so a later model can say which scope it
    shows. ``None`` when no target has one."""
    sym = next((x for x in (symbol_for(repo, r["file"], r.get("anchor_symbol")) for r in records) if x), None)
    if sym is None:
        return None
    scope = {k: scope_in[k] for k in ("intent", "phrases", "description") if k in scope_in}
    value = dict(scope=scope, scope_hash=scope_hash, run_id=run_id, at=at)
    return dict(op="annotate", symbol=sym, key=f"{RUN}:{run_id}", value=json.dumps(value, sort_keys=True),
                type=RUN, author=AUTHOR, replace=True)


def rows_for(repo, result, records, groups, prose_meta, followup_rows, prior, render, uncited=()):
    """The annotate rows of one run, and the prior keys it retires. ``render(statement)`` is the statement text."""
    rows, unplaced = [], []
    rec_by_stmt = {sid: r for r in records for sid in r["statements"]}

    def add(sym, typ, name, value):
        rows.append(dict(op="annotate", symbol=sym, key=f"{typ}:{name}", value=json.dumps(value, sort_keys=True),
                         type=typ, author=AUTHOR, replace=True))

    for st in result["statements"]:
        if st.get("status") not in ("Checked", "open"):
            continue
        rec = rec_by_stmt.get(st["id"])
        if rec is None:
            continue
        a = st.get("anchor") if isinstance(st.get("anchor"), dict) else {}
        ln = a.get("lines")
        usable = isinstance(a.get("file"), str) and isinstance(ln, list) and len(ln) == 2 and all(isinstance(x, int) for x in ln)
        # an open statement the writer left without a usable anchor is stored on its target's node, as itself
        sym = (symbol_for(repo, a["file"], a.get("symbol_id")) if usable
               else symbol_for(repo, rec["file"], rec.get("anchor_symbol")))
        if sym is None:
            unplaced.append(st["id"])
            continue
        try:
            text = render(st) if usable else None
        except (KeyError, IndexError, TypeError, ValueError):
            text = None
        add(sym, RULE, st["id"], dict(content_hash=content_hash(st), statement=text or "(open: the writer's statement could not be rendered; see its "
                                                         "follow-up)", contract=st, status=st["status"], batch_hash=rec["batch_hash"],
                                      target_hash=rec["target_hash"], fetched_files=st.get("fetched_files") or []))
    written = {RULE: {r["key"].split(":", 1)[1] for r in rows}}
    for rec in records:
        sym = symbol_for(repo, rec["file"], rec.get("anchor_symbol"))
        if sym is None:
            unplaced.append(rec["target"])
            continue
        add(sym, TARGET, rec["target"], {k: v for k, v in rec.items() if not k.startswith("_")})
    written[TARGET] = {r["target"] for r in records}
    by_id = {s["id"]: s for s in result["statements"]}
    written[GROUP] = set()
    for g in groups:
        sids = [c for s in ([g.get("rule")] if g.get("rule") else []) + (g.get("details") or []) for c in s.get("cites") or []]
        first = by_id.get(sids[0]) if sids else None
        name = sha(json.dumps(g, sort_keys=True).encode())[:16]
        if first is not None:
            sym = symbol_for(repo, first["anchor"]["file"], first["anchor"].get("symbol_id"))
        else:
            # every sentence withheld: the group (its reasons) is still stored, on the scope's first target
            sym = symbol_for(repo, records[0]["file"], records[0].get("anchor_symbol")) if records else None
        if sym:
            text_of = (prose_meta or {}).get("text_of") or {}
            # a group withheld whole (its writer's shape could not be checked) is never reused: its
            # statements went back to the writer in the same run, so its notice is this run's alone
            whole = any(isinstance(x, dict) and x.get("layer") == "group" for x in g.get("withheld") or [])
            add(sym, GROUP, name, dict(group=g, desc=(prose_meta or {}).get("desc"),
                                       pipeline=((prose_meta or {}).get("pipeline_of") or {}).get(
                                           g.get("g"), (prose_meta or {}).get("pipeline")),
                                       inputs={} if whole else {i: text_of.get(i) for i in _group_ids(g)},
                                       uncited={i: text_of.get(i) for i in uncited}))
            written[GROUP].add(name)
    written[FOLLOWUP] = set()
    for r in followup_rows:
        # a concern row (garden#1548) names no statement: its statement and concern index keep two rows apart; the
        # other rows hash as before, so their keys do not move
        keys = ("kind", "where", "statement", "target", "claim", "unknown") + (("concern_of", "concern") if "concern_of" in r else ())
        name = sha(json.dumps({k: r.get(k) for k in keys}, sort_keys=True).encode())[:16]
        f = (r.get("where") or {}).get("file")
        sym = symbol_for(repo, f) if f else None
        if sym is None and records:
            sym = symbol_for(repo, records[0]["file"])
        if sym:
            add(sym, FOLLOWUP, name, r)
            written[FOLLOWUP].add(name)
    for typ in TYPES:
        for name, v in (prior or {}).get(typ, {}).items():
            if name in written.get(typ, set()):
                continue
            sym = (v.get("_symbol") if isinstance(v, dict) else None) or _prior_symbol(prior, typ, name)
            if sym:
                add(sym, typ, name, dict(status=RETIRED))
    return rows, unplaced


def _group_ids(g):
    return sorted({c for x in ([g["rule"]] if g.get("rule") else []) + list(g.get("details") or []) + list(g.get("withheld") or [])
                   for c in x.get("cites") or []})


def _prior_symbol(prior, typ, name):
    return (prior.get("_symbols") or {}).get(f"{typ}:{name}")


def load_symbols(db, prior):
    """Record where each prior record lives (its node's symbol id), so a later run can retire it."""
    prior["_symbols"] = {}
    if not db or not os.path.exists(db):
        return prior
    con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        for key, data in con.execute(f"select a.key, n.data from annotations a join nodes n on n.symbol = a.node_sym "
                                     f"where a.type in ({','.join('?' * len(TYPES))})", TYPES):
            try:
                prior["_symbols"][key] = json.loads(data)["symbol"]
            except (ValueError, KeyError):
                pass
    except sqlite3.OperationalError:
        pass
    con.close()
    return prior


def estate_bin():
    return os.environ.get(ESTATE_ENV) or "wicked-estate"


def write(db, rows):
    """Apply ``rows`` in one ``wicked-estate write-batch`` (all or nothing). Returns its JSON report."""
    if not rows:
        return dict(rows=0, annotations=0, replaced=0)
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False) as fh:
        fh.write("\n".join(json.dumps(r) for r in rows) + "\n")
        path = fh.name
    try:
        r = subprocess.run([estate_bin(), "write-batch", path, "--json", "--db", db], capture_output=True, text=True,
                           timeout=600)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError(f"wicked-estate write-batch failed ({r.returncode}): {(r.stderr or r.stdout).strip()[:2000]}")
    try:
        return json.loads(r.stdout)
    except ValueError:
        return dict(raw=r.stdout.strip())
