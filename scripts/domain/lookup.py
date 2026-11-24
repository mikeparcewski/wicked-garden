"""J6 v3 lookup mechanics shared by batches / extract / check (DES-j6-build §2): go-to-definition on the floor
(COBOL: ``defs.py``; TS: the verified name lookup, lexical scope first), refs, and the checker's code context.

Ported from the J6 v3 proof (``proof-v3/scripts/v2lib.py``). The proof branched on the repository's name
(CardDemo = COBOL, crew = TypeScript); the port branches on the file's language (:func:`lang_of`), which is the
same split on both proof repositories. The card text is read from ``cards/`` beside this file.
"""
import collections, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import defs  # noqa: E402
from domain import graph as lib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COBOL_FAMILY = lib.COBOL_EXT + lib.JCL_EXT + (".bms",)


def lang_of(f):
    """``cobol`` (COBOL, copybooks, JCL, BMS), ``ts`` (TypeScript / JavaScript) or ``other``."""
    e = lib.ext(f or "")
    return "cobol" if e in COBOL_FAMILY else ("ts" if e in lib.JS else "other")


def use_repo(repo):
    """Point the COBOL lookup at this run's tree and its snapshot (a new run, even on the same tree, starts clean)."""
    if defs.OWNER is not repo:
        defs.set_root(repo.root, reader=lambda f: lib.fbytes(repo, f), owner=repo)

REF = re.compile(r"^\s*([^\s:]+):(\d+)(?:\s*-\s*(\d+))?\s*$")


def pref(r):
    m = REF.match(r or "") if isinstance(r, str) else None
    if not m:
        return None
    a, b = int(m.group(2)), int(m.group(3) or m.group(2))
    return (m.group(1), min(a, b), max(a, b))


def ref_lines(refs):
    out = set()
    for r in refs or []:
        p = pref(r)
        if p:
            out.update((p[0], i) for i in range(p[1], p[2] + 1))
    return out


def card_facts(repo, f=None):
    with open(os.path.join(HERE, "cards", f"{'cobol' if lang_of(f) == 'cobol' else 'generic'}.md")) as fh:
        t = fh.read()
    return re.search(r"^CARD FACTS .*$", t, re.M).group(0)


# ---------------- TS verified name lookup ----------------
_G = {}
DEFK = ("function", "method", "class", "interface", "type_alias", "constant", "variable", "struct", "enum")
BODYK = ("function", "method", "class")


def graph(repo):
    if repo not in _G:
        use_repo(repo)
        g = lib.load(repo)
        byf = collections.defaultdict(list)
        for n in g.nodes.values():
            if n["file"]:
                byf[n["file"]].append(n)
        _G[repo] = (g, byf)
    return _G[repo]


def _top_level(repo, n):
    _, byf = graph(repo)
    a, b = lib.span1(n)
    for m in byf[n["file"]]:
        if m is n or m["kind"] not in BODYK:
            continue
        ma, mb = lib.span1(m)
        if ma <= a and b <= mb and (ma, mb) != (a, b) and not (n["kind"] == "method" and m["kind"] == "class"):
            return False
    return True


_imp = {}


def ts_imports(repo, f):
    """local name -> (resolved file, exported name) for relative imports of f."""
    if (repo, f) in _imp:
        return _imp[(repo, f)]
    root = lib.repo_root(repo)
    text = "\n".join(lib.flines(repo, f) or [])
    out = {}
    for m in re.finditer(r"import\s+(type\s+)?([\s\S]*?)\s+from\s+['\"](\.{1,2}/[^'\"]+)['\"]", text):
        spec, mod = m.group(2), m.group(3)
        p = os.path.normpath(os.path.join(os.path.dirname(f), mod))
        tgt = None
        for ext in ("", ".ts", ".tsx", "/index.ts"):
            q = re.sub(r"\.js$", "", p) + ext if ext else p
            if ext == "" and not re.search(r"\.tsx?$", q):
                continue
            if lib.inside(root, q) and os.path.isfile(os.path.join(root, q)):
                tgt = q
                break
        if not tgt:
            continue
        br = re.search(r"\{([\s\S]*)\}", spec)
        if br:
            for part in br.group(1).split(","):
                part = re.sub(r"^\s*type\s+", "", part.strip())
                if not part:
                    continue
                mm = re.match(r"([\w$]+)(?:\s+as\s+([\w$]+))?", part)
                if mm:
                    out[mm.group(2) or mm.group(1)] = (tgt, mm.group(1))
        dm = re.match(r"\s*([\w$]+)\s*(,|$)", spec)
        if dm and not spec.strip().startswith(("{", "*")):
            out[dm.group(1)] = (tgt, "default")
    _imp[(repo, f)] = out
    return out


def _defs_named(repo, f, name, top=True):
    _, byf = graph(repo)
    c = [n for n in byf.get(f, []) if n["name"] == name and n["kind"] in DEFK and n["eb"] > n["sb"]]
    if top:
        c = [n for n in c if _top_level(repo, n)]
    c = [n for n in c if not (n["kind"] == "variable" and lib.span1(n)[1] - lib.span1(n)[0] > 200)]
    if not c:
        return None
    n = max(c, key=lambda n: lib.span1(n)[1] - lib.span1(n)[0])
    a, b = lib.span1(n)
    txt = "\n".join((lib.flines(repo, f) or [])[a - 1:b])
    return (f, a, b) if name in txt else None


import threading
_AT = threading.local()  # DES-j6-v3 §4: the line the identifier is used at; set by batches.py (target start) and want (anchor start)


def set_at(line):
    _AT.line = line


def _container3(repo, n):
    _, byf = graph(repo)
    a, b = lib.span1(n)
    best = None
    for m in byf[n["file"]]:
        if m is n or m["kind"] not in BODYK:
            continue
        ma, mb = lib.span1(m)
        if ma <= a and b <= mb and (ma, mb) != (a, b):
            if best is None or (mb - ma) < (best[1] - best[0]):
                best = (ma, mb)
    return best


def _ok3(repo, n):
    a, b = lib.span1(n)
    if n["kind"] == "variable" and b - a > 200:
        return None
    txt = "\n".join((lib.flines(repo, n["file"]) or [])[a - 1:b])
    return (n["file"], a, b) if n["name"] in txt else None


def ts_define_scoped(repo, name, f, line):
    """design-v3 cal/lookup3.py, verbatim rule: (1) innermost same-file definition whose enclosing function / method /
    class contains the line, (2) else top-level in f, (3) else the relative import's definition."""
    _, byf = graph(repo)
    cands = [n for n in byf.get(f, []) if n["name"] == name and n["kind"] in DEFK and n["eb"] > n["sb"]]
    vis = []
    for n in cands:
        c = _container3(repo, n)
        if c is None:
            vis.append((10 ** 9, n))
        elif c[0] <= line <= c[1] and n["kind"] != "method":
            vis.append((c[1] - c[0], n))
    for _, n in sorted(vis, key=lambda x: x[0]):
        d = _ok3(repo, n)
        if d:
            return d
    imp = ts_imports(repo, f).get(name)
    if imp and imp[1] != "default":
        return _defs_named(repo, imp[0], imp[1])
    return None


def ts_define(repo, name, f):
    at = getattr(_AT, "line", None)
    if at is not None:
        return ts_define_scoped(repo, name, f, at)
    d = _defs_named(repo, f, name)
    if d:
        return d
    imp = ts_imports(repo, f).get(name)
    if imp:
        tf, ex = imp
        if ex != "default":
            d = _defs_named(repo, tf, ex)
            if d:
                return d
    return None


_uniq = {}


def ts_define_anywhere(repo, name):
    """fetch round only: a unique top-level definition of that name in the product tree."""
    if repo not in _uniq:
        g, byf = graph(repo)
        idx = collections.defaultdict(list)
        for f, ns in byf.items():
            if lib.noise_file(f) or not f.endswith((".ts", ".tsx")):
                continue
            for n in ns:
                if n["kind"] in DEFK and n["eb"] > n["sb"]:
                    idx[n["name"]].append(n)
        _uniq[repo] = idx
    c = [n for n in _uniq[repo].get(name, []) if _top_level(repo, n)]
    if len({(n["file"], n["sl"]) for n in c}) != 1:
        return None
    return _defs_named(repo, c[0]["file"], name)


IDENT = re.compile(r"\b[A-Za-z_$][\w$]*\b")
TSKW = set("""const let var function return if else for while do switch case default break continue new this typeof instanceof in of
await async throw try catch finally class extends import export from as type interface enum true false null undefined void
string number boolean any unknown never object Record Promise Array Set Map Date Math JSON Object String Number Boolean Error
readonly keyof public private protected static get set yield delete super implements""".split())


def ts_names_used(text):
    return {w for w in IDENT.findall(text) if w not in TSKW and len(w) > 1}


# ---------------- COBOL ----------------
def cob_files(f):
    return [f] + defs.copybooks(f)


def cob_define(name, f):
    return defs.define(name, cob_files(f))


# ---------------- names -> definitions for a statement ----------------
BT = re.compile(r"`([^`]+)`")


def names_for(repo, st):
    f = st["anchor"]["file"]
    names = set()
    for c in st.get("claims") or []:
        txt = c.get("text") or ""
        if lang_of(f) == "cobol":
            names |= set(defs.COBID.findall(txt))
        else:
            for m in BT.finditer(txt):
                names |= ts_names_used(re.sub(r"'[^']*'|\"[^\"]*\"", " ", m.group(1)))
        for r in c.get("lines") or []:
            p = pref(r)
            if p and p[0] == f:
                L = lib.flines(repo, f) or []
                for i in range(p[1], p[2] + 1):
                    if 0 < i <= len(L):
                        names |= set(defs.COBID.findall(L[i - 1][7:72])) if lang_of(f) == "cobol" else ts_names_used(L[i - 1])
    return names


def define(repo, name, f, cap=80):
    use_repo(repo)
    d = cob_define(name, f) if f.lower().endswith((".cbl", ".cob")) else (ts_define(repo, name, f) if lang_of(f) == "ts" else None)
    if not d:
        return None
    return (d[0], d[1], min(d[2], d[1] + cap - 1))


def want(repo, st, extra=None):
    w = collections.defaultdict(set)
    f, (a, b) = st["anchor"]["file"], st["anchor"]["lines"]
    _AT.line = a if lang_of(f) == "ts" else None
    w[f].update(range(a, b + 1))
    for c in st.get("claims") or []:
        for r in c.get("lines") or []:
            p = pref(r)
            if p:
                w[p[0]].update(range(p[1] - 3, p[2] + 4))
    for c in st.get("context") or []:
        p = pref((c or {}).get("at") if isinstance(c, dict) else None)
        if p:
            w[p[0]].update(range(p[1], min(p[2], p[1] + 79) + 1))
    for nm in sorted(names_for(repo, st)):
        d = define(repo, nm, f)
        if d:
            w[d[0]].update(range(d[1], d[2] + 1))
    for fx, a2, b2 in extra or []:
        w[fx].update(range(a2, b2 + 1))
    return w


def render_code(repo, w):
    out = []
    for f in sorted(w):
        L = lib.flines(repo, f) or []
        nums = sorted(i for i in w[f] if 1 <= i <= len(L))
        if not nums:
            continue
        out.append(f"### {f}")
        prev = None
        for i in nums:
            if prev is not None and i != prev + 1:
                out.append("   ...")
            out.append(f"{i}: {L[i - 1]}")
            prev = i
    return "\n".join(out)
