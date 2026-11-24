#!/usr/bin/env python3
"""J6 v3 batches (DES-j6-build §2; DES-j6-v2 §3). 0 model calls.

COBOL: one unit per program (the program, its copybooks, and the JCL / PROC members that EXEC it), at most 15
targets per call. Everything else: per target, its lines plus the spans of the identifiers it uses (the verified
name lookup, lexical scope at the target's first line), packed at most 15 per call in scope order.

Ported from the J6 v3 proof (``proof-v3/scripts/batches.py``). The proof branched on the repository; the port
branches on the target's language, and a JCL member's program is found among the scoped programs by name (the
proof assumed CardDemo's ``app/cbl/<PROGRAM>.cbl``).

Usage: batches.py --root <tree> --db <estate.db> --scope <scope.json> --out <dir>   (writes <dir>/calls.json)
"""
import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import graph as lib  # noqa: E402
from domain import lookup as v2lib  # noqa: E402

PER_CALL = 15
REACHED = re.compile(r"^(\S+) -> (\S+) \((.+):(\d+)\)$")


def numbered(repo, f, lines=None):
    L = lib.flines(repo, f) or []
    rng = sorted(lines) if lines is not None else range(1, len(L) + 1)
    out, prev = [], None
    for i in rng:
        if not 1 <= i <= len(L):
            continue
        if prev is not None and i != prev + 1:
            out.append(f"{f}:....| ...")
        out.append(f"{f}:{i:04d}| {L[i - 1]}")
        prev = i
    return "\n".join(out)


def _write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


def cobol_plan(repo, S, T, out_dir):
    progs = [f for f in S["target_files"] if lib.ext(f) in (".cbl", ".cob")]
    by_name = {os.path.splitext(os.path.basename(p))[0].upper(): p for p in progs}
    unit_of = {f: f for f in S["target_files"] if f in progs}
    for line in S.get("reached_from") or []:
        m = REACHED.match(line)
        if m and m.group(2).upper() in by_name:
            unit_of.setdefault(m.group(3), by_name[m.group(2).upper()])
    v2lib.use_repo(repo)
    plan = []
    base = collections.Counter(os.path.basename(p) for p in progs)
    for p in progs:
        # a program's batch is named by its file name, or by its path when two scoped programs share a file name
        name = (os.path.basename(p) if base[os.path.basename(p)] == 1
                else f"{os.path.basename(p)}-{hashlib.sha256(p.encode()).hexdigest()[:8]}")
        files = list(dict.fromkeys([p] + v2lib.defs.copybooks(p) + [jf for jf, u in unit_of.items() if u == p and jf != p]))
        text = "\n".join(numbered(repo, f) for f in files)
        ts = sorted([t for t in T if unit_of.get(t["file"]) == p], key=lambda t: (t["file"] != p, t["file"], t["lines"][0]))
        text_file = os.path.join(out_dir, f"{name}.txt")
        for k in range(0, len(ts), PER_CALL):
            plan.append(dict(id=f"{name}-c{k // PER_CALL}", unit=p, files=files, shown={f: None for f in files},
                             targets=[t["id"] for t in ts[k:k + PER_CALL]], text_file=text_file, tokens=len(text) // 4))
        _write(text_file, text)
    return plan, set(unit_of)


def span_plan(repo, T, out_dir):
    per = []
    for t in T:
        f, (a, b) = t["file"], t["lines"]
        body = "\n".join((lib.flines(repo, f) or [])[a - 1:b])
        names = v2lib.ts_names_used(body) - {t.get("name")}
        spans = []
        v2lib.set_at(a)  # DES-j6-v3 §4 lexical-scope lookup at the target's first line
        for nm in sorted(names):
            d = v2lib.ts_define(repo, nm, f)
            if d and not (d[0] == f and a <= d[1] and d[2] <= b):
                spans.append(d)
        tok = (len(body) + sum(len("\n".join((lib.flines(repo, d[0]) or [])[d[1] - 1:d[2]])) for d in spans)) // 4
        per.append(dict(t=t, spans=spans, tokens=tok))
    v2lib.set_at(None)
    groups, cur = [], []
    for x in per:
        cur.append(x)
        if len(cur) == PER_CALL:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    plan = []
    for k, grp in enumerate(groups):
        shown = collections.defaultdict(set)
        for x in grp:
            shown[x["t"]["file"]].update(range(x["t"]["lines"][0], x["t"]["lines"][1] + 1))
            for f, a, b in x["spans"]:
                shown[f].update(range(a, b + 1))
        text = "\n".join(numbered(repo, f, v) for f, v in sorted(shown.items()))
        text_file = os.path.join(out_dir, f"call{k}.txt")
        _write(text_file, text)
        plan.append(dict(id=f"call{k}", unit=None, files=sorted(shown), shown={f: sorted(v) for f, v in shown.items()},
                         targets=[x["t"]["id"] for x in grp], text_file=text_file, tokens=len(text) // 4))
    stats = None
    if per:
        stats = dict(median=statistics.median(x["tokens"] for x in per), max=max(x["tokens"] for x in per),
                     defs_median=statistics.median(len(x["spans"]) for x in per))
    return plan, stats


def plan_batches(repo, S, out_dir):
    """The extract calls for scope ``S``: ``{calls: [...], n_calls, tokens, per_target}``; batch texts in out_dir."""
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    T = S["targets"]
    cob, cob_files = cobol_plan(repo, S, T, out_dir)
    rest = [t for t in T if t["file"] not in cob_files]
    spans, stats = span_plan(repo, rest, out_dir)
    plan = cob + spans
    return dict(calls=plan, n_calls=len(plan), tokens=[c["tokens"] for c in plan], per_target=stats,
                wall_s=round(time.time() - t0, 2))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    with open(a.scope) as fh:
        S = json.load(fh)
    res = plan_batches(lib.Repo(a.root, a.db), S, a.out)
    lib.jdump(res, os.path.join(a.out, "calls.json"))
    print(json.dumps({k: v for k, v in res.items() if k != "calls"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
