"""J6 v3 graph mechanics (DES-j6-build §2): the estate graph, read-only, and the source cards.

Ported from the J6 v3 proof (``proof-v3/scripts/lib.py`` and the read-only loader it used) with the
proof's lane paths replaced by a :class:`Repo` (the store and the tree a run names). The logic is
unchanged: comment and declaration cards, definition lines, decision lines and the test / vendor
predicates. ``_BUILTIN_NAMES`` and ``is_test_path`` are copied from ``extract_loop.py`` (#1366), which
goes in G5. Stdlib only.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import sqlite3
import threading
from urllib.parse import quote

# --- #1366 pieces, copied from extract_loop.py ---
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


_TEST_DIR = re.compile(
    r"(^|/)(tests?|__tests__|__mocks__|specs?|e2e|fixtures?|testdata|"
    r"(unit|integration|functional|system|acceptance|smoke|regression|contract|component|"
    r"end[_-]to[_-]end|api|ui|perf|load|stress)[_-]tests?|"
    r"tests?[_-](utils?|helpers?|support|fixtures?|common))/", re.IGNORECASE)
_TEST_PATH = re.compile(r"\.(test|spec)\.[^/]+$|(^|/)test_[^/]+\.py$|(^|/)tests?\.py$|(^|/)conftest\.py$|"
                        r"_test\.(py|go|rs|c|cc|cpp|cxx|h|hpp)$|_spec\.rb$|"
                        r"Tests?\.(cs|java|kt|swift|scala|php)$")


def is_test_path(file: str) -> bool:
    """A test, spec or fixture file: mapped in its turn, never where a page starts."""
    norm = (file or "").replace("\\", "/")
    return bool(_TEST_DIR.search(norm) or _TEST_PATH.search(norm))


BUILTIN = _BUILTIN_NAMES

# --- the estate graph, read-only ---
def norm_kind(k):
    k = json.loads(k)
    return k if isinstance(k, str) else k.get('other', str(k))

def inside(root, f):
    """``root/f`` when it resolves inside ``root`` (symlinks followed), else None. Every source read goes through it:
    a path can come from model output (a checker's fetch request, an extractor's context reference), and nothing outside
    the run's tree is ever read or shown to a seat."""
    if not f or os.path.isabs(f):
        return None
    base = os.path.realpath(root)
    p = os.path.realpath(os.path.join(base, f))
    return p if p.startswith(base + os.sep) else None


class G:
    def __init__(self, db, root):
        self.root = root
        con = sqlite3.connect(f'file:{quote(db)}?mode=ro', uri=True)
        self.nodes = {}
        self.sym2sid = {}
        for sid, name, kind, lang, f, data in con.execute('select symbol,name,kind,language,file,data from nodes'):
            d = json.loads(data)
            sp = (d.get('location') or {}).get('span') or {}
            n = dict(sid=sid, sym=d['symbol'], name=name, kind=norm_kind(kind), lang=lang, file=f,
                     sb=sp.get('start_byte', 0), eb=sp.get('end_byte', 0),
                     sl=sp.get('start_line', 0), el=sp.get('end_line', 0), sig=d.get('signature', ''))
            self.nodes[sid] = n
            self.sym2sid[n['sym']] = sid
        self.edges = []
        for s, t, k in con.execute('select source,target,kind from edges'):
            self.edges.append((s, t, norm_kind(k)))
        con.close()
        self._text = {}

    def text(self, f):
        if f not in self._text:
            p = inside(self.root, f)
            try:
                if p is None:
                    raise OSError(f)
                with open(p, 'rb') as fh:
                    self._text[f] = fh.read().decode('utf-8', 'replace')
            except OSError:
                self._text[f] = ''
        return self._text[f]


JS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
COBOL_EXT = (".cbl", ".cob", ".cpy")
JCL_EXT = (".jcl", ".prc", ".proc")


def is_vendor(f):
    return bool(re.search(r"(^|/)(node_modules|vendor|dist|build)/|\.d\.ts$|generated", f))


def noise_file(f):
    return is_test_path(f) or is_vendor(f)


class Repo:
    """The tree a run reads and its estate store (read-only). ``repo`` in every helper below."""

    def __init__(self, root, db):
        self.root = os.path.abspath(root)
        self.db = db
        self._graph = None
        self._lines = {}
        self._bytes = {}
        self._read = threading.Lock()

    @property
    def graph(self):
        if self._graph is None:
            self._graph = G(self.db, self.root)
        return self._graph


def repo_root(repo):
    return repo.root


def load(repo):
    return repo.graph


def flines(repo, f):
    k = f
    if k not in repo._lines:
        # Build the list, then publish it: the checker's threads share this cache, and a list published before its
        # trailing "" is dropped lets another thread render one line past the end of the file.
        try:
            L = fbytes(repo, f).decode("utf-8", "replace").split("\n")
            if L and L[-1] == "":
                L.pop()
        except OSError:
            L = None
        repo._lines[k] = L
    return repo._lines[k]


def fbytes(repo, f):
    """``f``'s bytes as this run first read them. One snapshot per file per run: what a model was shown and the hashes
    the run stores are of the same bytes, so a file edited while the run is going is never stored as checked."""
    with repo._read:
        if f in repo._bytes:
            return repo._bytes[f]
    p = inside(repo.root, f)
    if p is None:
        raise OSError(f"{f}: outside the tree")
    with open(p, "rb") as fh:
        b = fh.read()
    with repo._read:
        return repo._bytes.setdefault(f, b)


def ext(f):
    return os.path.splitext(f)[1].lower()


def span1(n):
    """1-based inclusive (start, end) of an estate node (stored 0-based)."""
    return n["sl"] + 1, n["el"] + 1


# ---------------- cards ----------------
def comment_lines(repo, f):
    """1-based line numbers that are comments by the card."""
    L = flines(repo, f) or []
    e = ext(f)
    out = set()
    if e in COBOL_EXT:
        for i, s in enumerate(L, 1):
            if (len(s) > 6 and s[6] in "*/") or s.lstrip().startswith("*>"):
                out.add(i)
    elif e in JCL_EXT:
        for i, s in enumerate(L, 1):
            if s.startswith("//*"):
                out.add(i)
    elif e == ".bms":
        for i, s in enumerate(L, 1):
            if s.startswith("*"):
                out.add(i)
    elif e in JS or e in (".java", ".go", ".rs", ".c", ".h", ".cpp", ".cs", ".kt", ".php"):
        inblock = False
        for i, s in enumerate(L, 1):
            t = s.strip()
            # a line is a comment only when no code stands outside its comment (`/* note */ if (x)` and
            # `*/ if (x)` are code)
            if inblock:
                if "*/" in t:
                    inblock = False
                    if t.split("*/", 1)[1].strip():
                        continue
                out.add(i)
                continue
            if t.startswith("//"):
                out.add(i)
            elif t.startswith("/*"):
                if "*/" not in t[2:]:
                    inblock = True
                    out.add(i)
                elif not t[2:].split("*/", 1)[1].strip():
                    out.add(i)
    elif e in (".py", ".sh", ".yml", ".yaml", ".toml", ".rb"):
        for i, s in enumerate(L, 1):
            if s.strip().startswith("#"):
                out.add(i)
    return out


def code_lines(repo, f):
    L = flines(repo, f) or []
    cm = comment_lines(repo, f)
    return {i for i, s in enumerate(L, 1) if s.strip() and i not in cm}


_COBOL_DECL = [re.compile(p, re.I) for p in [
    r"^\s*COPY\s", r"^\s*EXEC\s+SQL\s+INCLUDE\b", r"^\s*(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b",
    r"^\s*[A-Z0-9-]+\s+SECTION\.\s*$",
    r"^\s*(PROGRAM-ID|AUTHOR|DATE-WRITTEN|DATE-COMPILED|INSTALLATION|SECURITY|SOURCE-COMPUTER|OBJECT-COMPUTER|SPECIAL-NAMES|FILE-CONTROL|INPUT-OUTPUT|CONFIGURATION|WORKING-STORAGE|LINKAGE|LOCAL-STORAGE|FILE)\b",
    r"^\s*(SELECT|ASSIGN|ORGANIZATION|ACCESS|RECORD\s+KEY|ALTERNATE|FILE\s+STATUS|FD|SD|RECORDING|BLOCK|LABEL)\b",
    r"^\s*\d{1,2}\s+\S", r"^\s*(VALUE|PIC|PICTURE|OCCURS|REDEFINES)\b", r"^\s*(EXIT|GOBACK)\s*\.?\s*$"]]
_GEN_DECL = [re.compile(p) for p in [
    r"^\s*import\b", r"^\s*export\s+(type\s+)?(\*|\{[^}]*\}?)\s*(from\b.*)?;?\s*$", r"^\s*\}?\s*from\s+['\"].*['\"];?\s*$",
    r"^\s*export\s+default\s+\w+;?\s*$", r"^\s*(const|let|var)\s+\w+\s*=\s*require\(", r"^\s*[\"']use strict[\"'];?\s*$",
    r"^\s*(package|use|using|namespace)\b", r"^\s*#\s*include\b", r"^\s*from\s+\S+\s+import\b",
    r"^\s*[\]\)\}]+[;,]?\s*$"]]
_COBOL_VERBS = set("ACCEPT ADD CALL CANCEL CLOSE COMPUTE CONTINUE DELETE DISPLAY DIVIDE ELSE EVALUATE EXIT GOBACK GO IF INITIALIZE INSPECT MERGE MOVE MULTIPLY OPEN PERFORM READ RELEASE RETURN REWRITE SEARCH SET SORT START STOP STRING SUBTRACT UNSTRING WRITE WHEN EXEC GOBACK".split())
_COBOL_DEF = re.compile(r"^([A-Z0-9][A-Z0-9-]*)(\s+SECTION)?\.\s*$", re.I)
_GEN_DEF = [re.compile(p) for p in [
    r"^\s*(export\s+)?(default\s+)?(async\s+)?function\*?\s+[\w$]+",
    r"^\s*(export\s+)?(const|let|var)\s+[\w$]+\s*(:[^=]+)?=\s*(async\s*)?(\([^)]*\)|[\w$]+)\s*(:[^=]+)?=>",
    r"^\s*(export\s+)?(const|let|var)\s+[A-Z][A-Z0-9_]+\s*(:[^=]+)?=",
    r"^\s*(export\s+)?(abstract\s+)?class\s+[\w$]+", r"^\s*(export\s+)?(interface|type|enum)\s+[\w$]+",
    r"^\s*(async\s+)?def\s+\w+", r"^func\s", r"^\s*(pub\s+)?(async\s+)?fn\s"]]


def _line(repo, f, i):
    L = flines(repo, f) or []
    return L[i - 1] if 1 <= i <= len(L) else ""


def is_decl(repo, f, i, in_proc=True):
    s = _line(repo, f, i)
    e = ext(f)
    if e in COBOL_EXT:
        body = s[7:] if len(s) > 7 else s
        pats = _COBOL_DECL if not in_proc else [p for k, p in enumerate(_COBOL_DECL) if k not in (3,)]
        return any(p.search(body) for p in pats)
    return any(p.search(s) for p in _GEN_DECL)


def is_def_line(repo, f, i):
    s = _line(repo, f, i)
    e = ext(f)
    if e in COBOL_EXT:
        if len(s) < 8 or s[6] in "*/":
            return False
        if s[7:8] == " ":  # area A starts in column 8
            return False
        m = _COBOL_DEF.match(s[7:].rstrip())
        return bool(m) and m.group(1).upper() not in _COBOL_VERBS and not m.group(1).upper().startswith("END-")
    return any(p.search(s) for p in _GEN_DEF)


def procedure_start(repo, f):
    L = flines(repo, f) or []
    for i, s in enumerate(L, 1):
        if re.search(r"PROCEDURE\s+DIVISION", s, re.I) and not (len(s) > 6 and s[6] in "*/"):
            return i
    return None


DECISION_COBOL = re.compile(r"\b(IF|ELSE|EVALUATE|WHEN|UNTIL|VARYING|AT\s+END|INVALID\s+KEY|SIZE\s+ERROR|OVERFLOW|DEPENDING|NEXT\s+SENTENCE|SEARCH|CEE3ABD|ABEND|COND=|INCLUDE\s+COND|OMIT\s+COND)\b|COND=|SET\s+\S+\s+TO\s+TRUE|'(00|10|23|02|04|35)'", re.I)
DECISION_GEN = re.compile(r"\b(if|else|switch|case|default:|throw|catch)\b|\?\?|\?\.|&&|\|\||===|!==|[^=!<>]==[^=]|!=[^=]|<=|>=|\s[<>]\s|\.(filter|find|some|every|includes|has|startsWith|endsWith|test|match|min|max|refine|default)\(|Math\.(min|max)\(|\?[^?.:]*:")


def has_decision(repo, f, lines):
    L = flines(repo, f) or []
    rx = DECISION_COBOL if (ext(f) in COBOL_EXT or ext(f) in JCL_EXT) else DECISION_GEN
    cm = comment_lines(repo, f)
    return any(rx.search(L[i - 1]) for i in lines if 1 <= i <= len(L) and i not in cm)


# ---------------- hubs (#1366 generalised, DES §3.1 E) ----------------
def build_edges(g):
    N = g.nodes
    imports_ff = collections.defaultdict(set)
    for a, b, k in g.edges:
        if k == "imports" and a in N and b in N:
            imports_ff[N[a]["file"]].add(N[b]["file"])
    infiles = collections.defaultdict(set)
    for a, b, k in g.edges:
        if k == "calls" and a in N and b in N:
            infiles[b].add(N[a]["file"])
    hub = set()
    for b, fs in infiles.items():
        fs = {f for f in fs if not noise_file(f)}
        if len(fs) >= 8:
            bare = re.split(r"[#./:]", N[b]["name"] or "")[-1].split("(", 1)[0].strip()
            builtin = N[b]["file"].endswith(JS) and bare in BUILTIN
            imp = sum(1 for f in fs if N[b]["file"] in imports_ff[f])
            if builtin or imp / len(fs) <= 0.10:
                hub.add(b)
    return imports_ff, hub


def sha(b):
    return hashlib.sha256(b).hexdigest()


def jdump(obj, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1)
