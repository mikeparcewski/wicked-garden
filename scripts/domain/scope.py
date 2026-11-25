#!/usr/bin/env python3
"""J6 v3 scope (DES-j6-build §1 S2, §2): phrase -> code, "Reached from", config read, then the coverage check on
the scoped files -> targets. 0 model calls.

Ported from the J6 v3 proof (``proof-v3/scripts/scope.py``) with three changes: the proof's per-repository
branches are per-language (COBOL program ids named in the intent; TypeScript phrases matched against definitions),
S2 "Reached from" for TypeScript is the per-registration reach (``reach.py``, DES-j6-v3 §3) instead of v2's
depth-2 file list, and the proof's ground-truth reach fields are not computed (they were the proof's measurement).

Usage: scope.py --root <tree> --db <estate.db> --scope <scope-in.json> --out <scope.json>
``scope-in.json`` is ``{"intent": "...", "phrases": ["...", ...]}`` (phrases optional).
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import graph as lib  # noqa: E402
from domain import reach as reach_mod  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SHOWN_REACHED = 5  # S2 shows the first 5 by hop count, then "+N more"


def load_config():
    with open(os.path.join(HERE, "scope_config.json")) as fh:
        return json.load(fh)


def sub(s):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def key(w):
    w = w[:-1] if len(w) > 3 and w.endswith("s") else w
    return w[:5]


def tree_files(root):
    out = []
    for dp, dn, fn in os.walk(root):
        # sorted: the walk's order is the filesystem's, and the scope (its targets, prompts and hash) must not move
        dn[:] = sorted(d for d in dn if d not in (".git", "node_modules"))
        for f in sorted(fn):
            out.append(os.path.relpath(os.path.join(dp, f), root))
    return out


def scope_cobol(repo, intent, all_files):
    """A. COBOL program ids named in the intent match exactly; C. the JCL / PROC members that EXEC them (depth 1)
    and the DD datasets they bind (config read); copybooks the programs COPY are context."""
    found = collections.defaultdict(list)
    for f in all_files:
        if lib.ext(f) in (".cbl", ".cob"):
            found[os.path.splitext(os.path.basename(f))[0].upper()].append(f)
    # a program id in one file is that file; in more, the one whose path the intent types (`app/cbl/X.cbl`)
    progs = {p: fs[0] for p, fs in found.items() if len(fs) == 1}
    paths = {os.path.normpath(x) for x in re.findall(r"[\w./-]+\.(?:cbl|cob)\b", intent, re.I)}
    for p, fs in found.items():
        typed = [f for f in fs if os.path.normpath(f) in paths]
        if len(fs) > 1 and len(typed) == 1:
            progs[p] = typed[0]
    toks = sorted(set(re.findall(r"\b[A-Z][A-Z0-9]{5,7}\b", intent)))
    # A program id in more than one file is never resolved to one of them silently: the card asks which.
    twice = [t for t in toks if len(found.get(t, [])) > 1 and t not in progs]
    phrases = [t for t in toks if t in progs]
    unmatched = [t for t in toks if t not in found and re.search(r"\d", t)]
    asks = ([f"'{u}' matches no code: type a file, function or screen name, or drop it" for u in unmatched]
            + [f"'{t}' is in {len(found[t])} files ({', '.join(found[t])}): type the file" for t in twice])
    if not phrases:
        return dict(unmatched_phrases=unmatched, ambiguous_phrases=twice, questions=asks) if asks else None
    prog_files = [progs[p] for p in phrases]
    jcl = [f for f in all_files if lib.ext(f) in lib.JCL_EXT]
    reached = collections.OrderedDict()
    dd = collections.defaultdict(list)
    for p in phrases:
        for f in jcl:
            L = lib.flines(repo, f) or []
            for i, s in enumerate(L, 1):
                m = re.match(rf"^//(\S+)\s+EXEC\s+PGM={p}\b", s)
                if m:
                    reached.setdefault(f, []).append(f"{m.group(1)} -> {p} (:{i})")
                    j = i + 1
                    while j <= len(L) and not re.match(r"^//\S+\s+EXEC\b", L[j - 1]):
                        m2 = re.match(r"^//(\S+)\s+DD\b.*?DSN=([^,\s)]+)", L[j - 1])
                        if m2:
                            dd[p].append(f"{m2.group(1)}={m2.group(2)}")
                        j += 1
    copied = {m.group(1).upper() for f in prog_files for s in (lib.flines(repo, f) or [])
              for m in [re.match(r"^.{6}\s+COPY\s+([A-Z0-9-]+)", s)] if m}
    context_files = sorted(f2 for f2 in all_files if lib.ext(f2) == ".cpy"
                           and os.path.splitext(os.path.basename(f2))[0].upper() in copied)
    return dict(
        phrases={p: [progs[p]] for p in phrases}, unmatched_phrases=unmatched, ambiguous_phrases=twice,
        questions=asks,
        reached_from=[f"{line.split(' (:')[0]} ({f}:{line.split(' (:')[1].rstrip(')')})"
                      for f, lines in reached.items() for line in lines],
        reached_files=list(reached), config_read=dict(dd), target_files=prog_files + list(reached),
        matched_defs={}, context_files=context_files, big_files=[], matched_def_ids={})


def scope_ts(repo, phrase_list, cfg):
    """A/B. Each phrase's words (sub-word split, stemmed, stopwords dropped) all match a definition's name (else its
    name plus file name); C. the registrations whose own handler reaches a matched definition (reach.py)."""
    g = lib.load(repo)
    N = g.nodes
    stop = set(cfg["stopwords"])
    test_rx = re.compile(cfg["test_path"])
    vend_rx = re.compile(cfg["vendor_path"])
    docs = []
    for sid, n in N.items():
        f = n["file"] or ""
        if n["kind"] not in cfg["name_kinds"] or test_rx.search(f) or vend_rx.search(f) or not f.endswith((".ts", ".tsx")):
            continue
        docs.append((sid, n["name"], f, {key(w) for w in sub(n["name"])},
                     {key(w) for w in sub(os.path.splitext(os.path.basename(f))[0])}))
    # by place, so the order (and the scope hash) never depends on the store's row order
    docs.sort(key=lambda d: (d[2], N[d[0]]["sl"], d[1], N[d[0]]["sym"]))
    res, sel_files, sel_defs, questions = {}, collections.OrderedDict(), collections.defaultdict(set), []
    for p in phrase_list:
        ws = [key(w) for w in sub(p) if w not in stop]
        name_hits = [d for d in docs if all(w in d[3] for w in ws)]
        file_hits = [d for d in docs if all(w in (d[3] | d[4]) for w in ws)]
        hits = name_hits or file_hits
        res[p] = dict(words=ws, used="name" if name_hits else ("name+file" if file_hits else "none"), n=len(hits),
                      files=sorted({d[2] for d in hits}), defs=sorted({d[1] for d in hits}))
        if not hits:
            questions.append(f"'{p}' matches no code: type a file, function or screen name, or drop it")
        for d in hits:
            sel_files.setdefault(d[2], []).append(p)
            sel_defs[d[2]].add(d[0])
    tok = {}
    for f in sel_files:
        tok[f] = len(lib.fbytes(repo, f).decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")) // 4
    big = {f for f, t in tok.items() if t > cfg["big_file_tokens"]}
    cfg_read = collections.Counter()
    for f in sel_files:
        text = "\n".join(lib.flines(repo, f) or [])
        for m in re.finditer(r"process\.env\.([A-Z][A-Z0-9_]*)|process\.env\[\s*['\"`]([A-Z][A-Z0-9_]*)", text):
            cfg_read[m.group(1) or m.group(2)] += 1
    matched_defs = {f: sorted(N[s]["name"] for s in sel_defs[f]) for f in sel_files}
    scanned, hit = reach_mod.reached_from(repo, matched_defs)
    return dict(
        phrases=res, unmatched_phrases=[p for p in phrase_list if not res[p]["n"]], questions=questions,
        reached_from=[reach_mod.describe(r) for r in hit], reached_files=[],
        registrations_scanned=scanned, config_read=dict(cfg_read), target_files=list(sel_files), file_tokens=tok,
        big_files=sorted(big), matched_defs=matched_defs,
        matched_def_ids={f: sorted(sel_defs[f]) for f in big}, context_files=[])


# ---- step 1 coverage check (v1 §3.3) on the scoped files -> targets ----
BEHAV = ("function", "method", "step")


def targets_of(repo, sc):
    g = lib.load(repo)
    N = g.nodes
    by_file = collections.defaultdict(list)
    for s, n in N.items():
        by_file[n["file"]].append(s)
    targets, stats = [], {}

    def smallest_containing(f, a, b):
        best = None
        for s in by_file[f]:
            n = N[s]
            if n["kind"] not in ("module", "function", "method", "class", "step"):
                continue
            sa, sb = lib.span1(n)
            if sa <= a and b <= sb and (best is None or (sb - sa) < (lib.span1(N[best])[1] - lib.span1(N[best])[0])):
                best = s
        return best

    def module_of(f):
        ms = [s for s in by_file[f] if N[s]["kind"] == "module"]
        return ms[0] if ms else next((s for s in by_file[f] if N[s]["kind"] == "file"), None)

    big_files = set(sc.get("big_files") or [])
    for f in sc["target_files"]:
        if f in big_files:
            # a matched file over the size bar contributes only its matched definitions
            for s in sc["matched_def_ids"][f]:
                n = N[s]
                a, b = lib.span1(n)
                kind = "node" if n["kind"] in BEHAV else "range"
                targets.append(dict(id=n["sym"] if kind == "node" else f"{f}:L{a}-L{b}", kind=kind, node_kind=n["kind"],
                                    name=n["name"], file=f, lines=[a, b], anchor_symbol=n["sym"], anchor_name=n["name"],
                                    node_complete=None, matched_only=True))
            stats[f] = dict(matched_only=len(sc["matched_def_ids"][f]))
            continue
        L = lib.flines(repo, f) or []
        nl = len(L)
        code = lib.code_lines(repo, f)
        cov, starts = set(), set()
        for s in by_file[f]:
            n = N[s]
            if n["kind"] in ("file", "module"):
                continue
            a, b = lib.span1(n)
            if n["eb"] <= n["sb"] and n["kind"] not in ("step",):
                continue
            if a == 1 and b >= nl and nl > 5:
                continue
            cov.update(range(a, b + 1))
            starts.add(a)
        in_proc_from = lib.procedure_start(repo, f) if lib.ext(f) in lib.COBOL_EXT else 1
        unc = sorted(i for i in code if i not in cov)
        runs, cur = [], []
        for i in unc:
            newdef = lib.is_def_line(repo, f, i) and i not in starts
            if cur and (any(j in cov for j in range(cur[-1] + 1, i)) or newdef):
                runs.append(cur)
                cur = []
            cur.append(i)
        if cur:
            runs.append(cur)
        keep = [r for r in runs if not all(lib.is_decl(repo, f, i, in_proc=in_proc_from is not None and r[0] >= (in_proc_from or 1))
                                           for i in r)]
        bnodes = sorted([s for s in by_file[f] if N[s]["kind"] in BEHAV + ("module",)], key=lambda s: lib.span1(N[s])[0])
        complete = {}
        for s in bnodes:
            a, b = lib.span1(N[s])
            nxt = min([lib.span1(N[t])[0] for t in bnodes if lib.span1(N[t])[0] > b and N[t]["kind"] == N[s]["kind"]] + [nl + 1])
            complete[s] = not [i for i in range(b + 1, nxt) if i in code and i not in cov]
        mod = module_of(f)
        for r in keep:
            a, b = r[0], r[-1]
            anc = smallest_containing(f, a, b) or mod
            targets.append(dict(id=f"{f}:L{a}-L{b}", kind="range", file=f, lines=[a, b],
                                anchor_symbol=N[anc]["sym"] if anc else f"{f}#file",
                                anchor_name=N[anc]["name"] if anc else os.path.basename(f), node_complete=None))
        for s in bnodes:
            n = N[s]
            if n["kind"] == "module":
                continue
            a, b = lib.span1(n)
            targets.append(dict(id=n["sym"], kind="node", node_kind=n["kind"], name=n["name"], file=f, lines=[a, b],
                                anchor_symbol=n["sym"], anchor_name=n["name"], node_complete=complete[s]))
        stats[f] = dict(lines=nl, code=len(code), covered=len(code & cov), ranges=len(keep),
                        behaviour_nodes=len([s for s in bnodes if N[s]["kind"] != "module"]))
    # a node nested inside another node target is still its own target (v1); drop exact duplicates only
    seen, uniq = set(), []
    for t in targets:
        if t["id"] not in seen:
            seen.add(t["id"])
            uniq.append(t)
    for t in uniq:
        code = lib.code_lines(repo, t["file"])
        t["code_lines"] = len([i for i in range(t["lines"][0], t["lines"][1] + 1) if i in code])
    return uniq, stats


def scope_hash(sc):
    """The hash Start carries (DES-j6-build §1): the scoped files' bytes and the targets. ``run.py`` re-derives the
    scope and refuses when it differs ("the code changed since the preview")."""
    h = hashlib.sha256()
    for f in sorted(set(sc["target_files"]) | set(sc.get("context_files") or [])):
        h.update(f.encode() + b"\0")
        try:
            h.update(hashlib.sha256(lib.fbytes(sc["_repo"], f)).digest())
        except OSError:
            h.update(b"missing")
    # each target whole (id, file, lines, anchor): a re-index that moves a target's bounds is a different scope
    h.update(json.dumps([[t["id"], t["file"], t["lines"], t.get("anchor_symbol")] for t in sc["targets"]]).encode())
    return h.hexdigest()


def build_scope(repo, intent, phrases=None, cfg=None):
    """The S2 scope card's facts for ``intent`` (and the typed ``phrases``) over ``repo``."""
    t0 = time.time()
    cfg = cfg or load_config()
    all_files = tree_files(repo.root)
    out = dict(intent=intent, model_calls=0, phrases={}, unmatched_phrases=[], questions=[], reached_from=[],
               reached_files=[], config_read={}, target_files=[], matched_defs={}, context_files=[], big_files=[],
               matched_def_ids={})
    parts = [p for p in (scope_cobol(repo, intent, all_files), scope_ts(repo, phrases, cfg) if phrases else None) if p]
    for part in parts:
        for k, v in part.items():
            if isinstance(v, list):
                out[k] = out.get(k, []) + [x for x in v if x not in out.get(k, [])]
            elif isinstance(v, dict):
                out[k] = {**out.get(k, {}), **v}
            else:
                out[k] = out.get(k, 0) + v
    targets, stats = targets_of(repo, out)
    out.update(reached_from_count=len(out["reached_from"]), reached_shown=out["reached_from"][:SHOWN_REACHED],
               reached_more=max(0, len(out["reached_from"]) - SHOWN_REACHED), targets=targets, n_targets=len(targets),
               n_node=sum(1 for t in targets if t["kind"] == "node"), n_range=sum(1 for t in targets if t["kind"] == "range"),
               n_files=len(out["target_files"]), stats=stats)
    out["scope_hash"] = scope_hash(dict(out, _repo=repo))
    out["wall_s"] = round(time.time() - t0, 2)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--scope", required=True, help="scope-in.json: {intent, phrases}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    with open(a.scope) as fh:
        req = json.load(fh)
    sc = build_scope(lib.Repo(a.root, a.db), req.get("intent") or "", req.get("phrases") or None)
    lib.jdump(sc, a.out)
    print(json.dumps({k: sc[k] for k in ("n_files", "n_targets", "reached_from_count", "unmatched_phrases", "wall_s")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
