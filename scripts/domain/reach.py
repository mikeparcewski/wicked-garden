"""J6 v3 S2 "Reached from" at registration grain (DES-j6-build §2; DES-j6-v3 §3). 0 model calls.

A route or CLI registration is listed only when ITS OWN handler (the registration statement, its parentheses
balanced, chained ``.x(`` lines included) reaches a matched definition within ``max_hops`` hops, by the verified
lookup (lexical scope, then top level, then a relative import: ``lookup.ts_define_scoped``). Ported from the v3
calibration script (``design-v3/cal/reach.py``) at the adopted setting: 2 hops, the #1366 hub predicate off.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import graph as lib  # noqa: E402
from domain import lookup as v2lib  # noqa: E402

ROUTE = re.compile(r"\b(app|server|fastify|router|r)\.(get|post|put|delete|patch|route|all)\(\s*['\"`]([^'\"`]+)")
ROUTE_OPEN = re.compile(r"\b(app|server|fastify|router|r)\.(get|post|put|delete|patch|route|all)\(\s*$")
CLI = re.compile(r"\.command\(\s*['\"`]([^'\"`]+)")
MAX_HOPS = 2


def strip_strings(s):
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`", "''", s)


def stmt_span(L, i, cap=600):
    """from the registration line to the end of its call statement (balanced parens, then chained `.x(` lines)."""
    depth, j, started = 0, i, False
    while j <= min(len(L), i + cap):
        t = strip_strings(L[j - 1].split("//")[0])
        for ch in t:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
        if started and depth <= 0:
            nxt = L[j].lstrip() if j < len(L) else ""
            if not nxt.startswith("."):
                return i, j
        j += 1
    return i, min(len(L), i + cap)


def reached_from(repo, matched_defs, max_hops=MAX_HOPS):
    """The registrations whose handler reaches a matched definition: ``matched_defs`` is ``{file: [name, ...]}``
    (scope's matched definitions). Returns ``(registrations_scanned, reached)``, each reached entry a dict with
    ``label``, ``at``, ``span``, ``hops`` and ``via``, ordered by hop count then place."""

    def text(f, a, b):
        return "\n".join((lib.flines(repo, f) or [])[a - 1:b])

    v2lib.set_at(None)  # the matched definitions resolve at top level, as the calibration did
    T = set()
    for f, names in matched_defs.items():
        for nm in names:
            d = v2lib.ts_define(repo, nm, f)
            if d:
                T.add(d)
    memo = {}

    def reaches(d, depth):
        """shortest hop count from definition span d to a matched definition (0 if d is one), or None."""
        if d in T:
            return 0, [d]
        if depth >= max_hops:
            return None, []
        k = (d, depth)
        if k in memo:
            return memo[k]
        memo[k] = (None, [])
        best = (None, [])
        for nm in sorted(v2lib.ts_names_used(text(*d))):
            e = v2lib.ts_define_scoped(repo, nm, d[0], d[1])
            if not e or e == d:
                continue
            h, path = reaches(e, depth + 1)
            if h is not None and (best[0] is None or h + 1 < best[0]):
                best = (h + 1, [d] + path)
        memo[k] = best
        return best

    _, byf = v2lib.graph(repo)
    regs = []
    for f in sorted(byf):
        if lib.noise_file(f) or not f.endswith((".ts", ".tsx")):
            continue
        L = lib.flines(repo, f) or []
        for i, s in enumerate(L, 1):
            if ROUTE_OPEN.search(s):
                s = s + " ".join(x.strip() for x in L[i:i + 2])  # path on the next line (multi-line registration)
            m = ROUTE.search(s)
            c = CLI.search(s)
            if not (m or c):
                continue
            label = f"{m.group(2).upper()} {m.group(3)}" if m else f"CLI {c.group(1)}"
            a, b = stmt_span(L, i)
            h, path = reaches((f, a, b), 0)
            regs.append(dict(label=label, at=f"{f}:{i}", span=[a, b], hops=h,
                             via=[f"{os.path.basename(p[0])}:{p[1]}" for p in path[1:]]))
    hit = sorted((r for r in regs if r["hops"] is not None), key=lambda r: (r["hops"], r["at"]))
    return len(regs), hit


def describe(r):
    """One S2 line: ``POST /runs (packages/crew/src/api/routes.ts:120) via launch.ts:40 > posture.ts:12``."""
    return f"{r['label']} ({r['at']}) via {' > '.join(r['via'])}"
