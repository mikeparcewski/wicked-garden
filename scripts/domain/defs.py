"""Emulated COBOL go-to-definition over the run's tree (what an LSP such as the COBOL language server would return).

Ported from the J6 v3 proof (``proof-v3/frozen/defs.py``). Two changes, both paths: the tree is the run's
(:func:`set_root`), and ``COPY X`` resolves to ``<program dir>/../cpy/X.cpy`` (the proof's fixed ``app/cpy``),
else to the one ``X.cpy`` in the tree (any case), never to a BMS symbolic map (:func:`copybook_path`). The
definition rules are unchanged.
"""
import os, re
SRC = None
_fl = {}
_cpy = None
_resets = []


def _inside(root, f):
    """``root/f`` when it resolves inside ``root`` (as ``graph.inside``; this module stays import-free)."""
    if not f or os.path.isabs(f):
        return None
    base = os.path.realpath(root)
    p = os.path.realpath(os.path.join(base, f))
    return p if p.startswith(base + os.sep) else None


def on_reset(clear):
    """Register a cache, keyed by path in the current tree, that :func:`set_root` must clear."""
    _resets.append(clear)


def set_root(root):
    """Point the lookup at the run's tree (and forget the previous tree's text and every cache over it)."""
    global SRC, _cpy
    SRC = root
    _fl.clear()
    _cpy = None
    for clear in _resets:
        clear()


def _copybook_index():
    """``({NAME: [copybook paths]}, {NAME of every BMS mapset})`` over the tree, names upper-cased."""
    global _cpy
    if _cpy is None:
        idx, maps = {}, set()
        for dp, dn, fn in os.walk(SRC):
            dn[:] = sorted(d for d in dn if d not in (".git", "node_modules"))
            for f in sorted(fn):
                stem, e = os.path.splitext(f)
                if e.lower() == ".cpy":
                    idx.setdefault(stem.upper(), []).append(os.path.relpath(os.path.join(dp, f), SRC))
                elif e.lower() == ".bms":
                    maps.add(stem.upper())
        _cpy = (idx, maps)
    return _cpy


def copybook_by_name(name):
    """The one ``name.cpy`` in the tree (any case), or None (none, or more than one)."""
    hits = _copybook_index()[0].get(name.upper(), [])
    return hits[0] if len(hits) == 1 else None


def copybook_path(f, name):
    """Where ``COPY name`` in program ``f`` resolves, or None.

    A symbolic map generated from a BMS mapset in the tree (``name.bms``) is screen I/O, not program data, and is
    not resolved: the J6 v3 checker was calibrated without map fields (the proof's fixed ``app/cpy`` held none), and
    resolving them adds every screen field to the WRITERS of the group the map follows."""
    if name.upper() in _copybook_index()[1]:
        return None
    near = os.path.normpath(os.path.join(os.path.dirname(f), "..", "cpy", f"{name}.cpy"))
    if flines(near):
        return near
    return copybook_by_name(name)


def flines(f):
    if f not in _fl:
        try:
            p = _inside(SRC, f)
            if p is None:
                raise OSError(f)
            with open(p, "rb") as fh:
                _fl[f] = fh.read().decode("utf-8", "replace").split("\n")
        except OSError:
            _fl[f] = []
    return _fl[f]
COBID = re.compile(r"(?<![A-Z0-9-])([A-Z0-9]*[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|[0-9]+(?:-[A-Z0-9]+)*-[A-Z][A-Z0-9-]*|[A-Z]{4,}[0-9]*)(?![A-Z0-9-])")
def copybooks(f):
    out = []
    for s in flines(f):
        m = re.match(r"^.{6}\s+COPY\s+([A-Z0-9-]+)", s)
        if m:
            p = copybook_path(f, m.group(1))
            if p:
                out.append(p)
    return out
def level(s):
    m = re.match(r"^.{6}\s*(\d{1,2})\s+([A-Z0-9-]+)", s)
    return (int(m.group(1)), m.group(2)) if m else None
def define(name, files):
    """Emulated go-to-definition (what an LSP would return): data item (+ its 88s / group), paragraph body, SELECT clause."""
    for f in files:
        L = flines(f)
        for i, s in enumerate(L, 1):
            if len(s) < 8 or s[6] in "*/":
                continue
            body = s[7:]
            lv = level(s)
            if lv and lv[1] == name:
                a, b = i, i
                if lv[0] == 88:
                    for j in range(i - 1, max(0, i - 30), -1):
                        l2 = level(L[j - 1])
                        if l2 and l2[0] != 88:
                            a = j
                            break
                for j in range(i + 1, min(len(L), i + 40) + 1):
                    l2 = level(L[j - 1])
                    if l2 and (l2[0] <= lv[0] and l2[0] != 88) and lv[0] != 88:
                        break
                    if l2 and lv[0] == 88 and l2[0] != 88:
                        break
                    b = j
                return f, a, b
            if re.match(rf"^{re.escape(name)}\.\s*$", body.strip()) and s[7] != " ":
                b = i
                for j in range(i + 1, min(len(L), i + 40) + 1):
                    t = L[j - 1]
                    if len(t) > 8 and t[6] not in "*/" and t[7] != " " and re.match(r"^[A-Z0-9-]+\.\s*$", t[7:].strip()):
                        break
                    b = j
                return f, i, b
            if re.match(rf"^\s*SELECT\s+{re.escape(name)}\b", body):
                b = i
                while b < len(L) and "." not in L[b - 1][7:72]:
                    b += 1
                return f, i, b
    return None
