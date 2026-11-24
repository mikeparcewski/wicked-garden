# Ported from the J6 v3 proof (proof-v3/cal/cobol_flow.py, sha256 f4038366...): a copybook resolves by name in
# the run's tree (defs.copybook_path: beside the program, else the one copybook of that name), not at CardDemo's
# fixed app/cpy/. The gate rules are unchanged.
"""Fail-closed completeness for R's COBOL context (coord delta check 2026-11-24, F1-F3). Text only, 0 model calls.

A clear may rest on ENTRY / PATH / WRITERS only when this module PROVES the program uses no control-flow or data-flow
form outside the ones it models. Everything else answers "incomplete", and `decide` then keeps the flag.

Modelled control flow: paragraphs (header period on the same or next line); `PERFORM p`; `PERFORM a THRU|THROUGH b`
where b is a or the paragraph right after a (the X / X-EXIT idiom: no interior paragraph); `GO TO p`; an unnamed batch
main before the first paragraph; sequential fall-through, transitively; an Area-A procedure `COPY` whose copybook only
PERFORMs / GOes TO its own paragraphs (the paragraph holding it never counts as ending in a transfer).
Refused (program incomplete): ALTER; GO TO ... DEPENDING; GO TO with no name; a SECTION header or DECLARATIVES; a
PERFORM / GO TO whose paragraph name is on the next line; a THRU range with an interior paragraph; an Area-B procedure
COPY; any other Area-A text; a RECEIVE MAP without INTO; (delta2 G2) ENTRY, EXEC SQL WHENEVER, SORT/MERGE INPUT/OUTPUT
PROCEDURE, EXIT PARAGRAPH, GO without TO, GO TO into a copybook paragraph, lowercase code, and any of these forms or
EXEC CICS HANDLE inside a procedure copybook. A paragraph named by EXEC CICS HANDLE ... (x) is an implicit entry:
an anchor reached from it, or by fall-through from it, is "incomplete". This list is what is modelled and refused;
it is NOT proved to cover every COBOL form (delta2 G5): a form outside both lists is a known gap, not a proof.
Implicit writers (delta2 C-G1, time-boxed ruling): a name whose closure holds a FILE STATUS item, a name written inside
a procedure copybook, or a platform-written name (SQL*, EIB* except EIBCALEN, RETURN-CODE, SORT-RETURN, TALLY, DFH*)
makes writers_complete answer "incomplete", so no UNREACHABLE clear rests on it.
Modelled writes (WRITERS, the statements this module recognises; not a proved superset): MOVE/SET/INITIALIZE/COMPUTE/ACCEPT/ADD/SUBTRACT/MULTIPLY/DIVIDE/STRING/UNSTRING
receivers, READ ... INTO, PERFORM VARYING/AFTER, EXEC INTO()/RESP()/RESP2()/SET()/LENGTH()/RIDFLD()/:host after INTO,
WRITE/REWRITE rec FROM; every name in CALL/INSPECT/SEARCH/SORT/MERGE/RELEASE/RETURN/START/DELETE is listed as a
possible writer; a READ/RETURN of a file without INTO writes that file's record. The closure adds descendants and
REDEFINES aliases to v3's name / 88 / group-ancestor set."""
import re
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import cobol_ctx as cx  # noqa: E402
defs = cx.defs

VERBS = {"ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY", "DIVIDE",
         "ELSE", "EVALUATE", "EXEC", "EXIT", "GO", "GOBACK", "IF", "INITIALIZE", "INSPECT", "MERGE", "MOVE", "MULTIPLY",
         "NEXT", "OPEN", "PERFORM", "READ", "RELEASE", "RETURN", "REWRITE", "SEARCH", "SET", "SORT", "START", "STOP",
         "STRING", "SUBTRACT", "UNSTRING", "WHEN", "WRITE"}
INLINE_KW = {"UNTIL", "VARYING", "WITH", "TEST", "TIMES"} | VERBS
_LIT = re.compile(r"'[^']*'|\"[^\"]*\"")
_cache = {}
defs.on_reset(_cache.clear)  # keyed by path: a new tree starts empty


def _strip(t):
    return _LIT.sub(" '' ", t)


def _tok_lines(L, start):
    out = []
    for i in range(start, len(L) + 1):
        c = _strip(cx.code(L[i - 1]))
        for m in re.finditer(r"[A-Z0-9][A-Z0-9-]*(?:\([^)]*\))?|[A-Z0-9]+|\.(?=\s|$)|=|:[A-Z0-9-]+|\(|\)|''", c.replace("(", " ( ").replace(")", " ) ")):
            out.append((i, m.group(0)))
    return out


def tokens(f):
    """[(line, token)] over the PROCEDURE DIVISION code text, literals blanked, periods as their own token."""
    if f in _cache:
        return _cache[f]
    ps = cx.proc_start(f)
    out = _tok_lines(defs.flines(f), ps + 1) if ps else []
    _cache[f] = out
    return out


def copy_tokens(f, name):
    """[(line, token)] over the text of the procedure copybook program ``f`` COPYs as ``name``."""
    return _tok_lines(defs.flines(defs.copybook_path(f, name) or "") or [], 1)


def proc_copies(f):
    """[(line, copybook name)] for every Area-A procedure COPY (Area-B ones are refused)."""
    L = defs.flines(f)
    ps = cx.proc_start(f) or 1
    out = []
    for i in range(ps + 1, len(L) + 1):
        m = re.match(r"COPY\s+'?([A-Z0-9-]+)'?", cx.code(L[i - 1]).strip())
        if m:
            out.append((i, m.group(1)))
    return out


def _flow_refusal(T, names, ext, where):
    """the token-level checks, shared by the program and its procedure copybooks."""
    tv = [t for _, t in T]
    for k, (ln, t) in enumerate(T):
        if t == "ALTER":
            return f"ALTER at {where}{ln}"
        if t == "DEPENDING":
            return f"GO TO ... DEPENDING at {where}{ln}"
        if t == "ENTRY":
            return f"ENTRY (alternate entry point) at {where}{ln}"
        if t == "HANDLE" and k and tv[k - 1] == "CICS" and where:
            return f"EXEC CICS HANDLE (implicit jump targets) at {where}{ln}"
        if t == "WHENEVER":
            return f"EXEC SQL WHENEVER (implicit jump targets) at {where}{ln}"
        if t == "PROCEDURE" and k + 1 < len(T) and T[k - 1][1] in ("INPUT", "OUTPUT"):
            return f"SORT / MERGE INPUT / OUTPUT PROCEDURE at {where}{ln}"
        if t in ("PARAGRAPH",) and k and tv[k - 1] == "EXIT":
            return f"EXIT PARAGRAPH at {where}{ln}"
        if t == "GO" and (k + 1 >= len(T) or T[k + 1][1] != "TO"):
            return f"GO without TO at {where}{ln}"
        if t == "TO" and k and tv[k - 1] == "GO":
            nx = T[k + 1] if k + 1 < len(T) else (ln, ".")
            if nx[1] not in names and nx[1] not in ext:
                return f"GO TO with no known paragraph name at {where}{ln}"
            if nx[1] in ext and where == "":
                return f"GO TO into a copybook paragraph at {ln}"
            if nx[0] != ln:
                return f"GO TO with its paragraph name on the next line at {where}{ln}"
    return ""


def _area_a(s):
    """first non-blank code column is in Area A (cols 8-11)."""
    if len(s) <= 7 or s[6] in "*/":
        return False
    body = s[7:72]
    st = len(body) - len(body.lstrip())
    return body.strip() != "" and st < 4


def copy_heads(f):
    """paragraph names that the program's self-contained Area-A procedure copybooks bring in."""
    L = defs.flines(f)
    ps = cx.proc_start(f) or 1
    out = set()
    for i in range(ps + 1, len(L) + 1):
        m = re.match(r"COPY\s+'?([A-Z0-9-]+)'?", cx.code(L[i - 1]).strip())
        if m and _area_a(L[i - 1]) and cx._self_contained_copy(f, m.group(1)):
            for t in (cx._copy_text(f, m.group(1)) or "").split("\n"):
                if len(t) > 7 and t[6] not in "*/" and t[7] != " ":
                    h = cx.HEAD_ONLY.match(cx.code(t).strip().rstrip(".").strip())
                    if h:
                        out.add(h.group(1))
    return out


def program_refusal(f):
    """'' when every control-flow form in f is modelled, else the first reason found."""
    L = defs.flines(f)
    ps = cx.proc_start(f)
    pp = cx.paragraphs(f)
    if not ps or not pp:
        return "no paragraph"
    names = [p[0] for p in pp]
    heads = {a for _, a, _ in pp}
    last_head = pp[-1][1]
    for i in range(ps + 1, len(L) + 1):
        s = L[i - 1]
        c = cx.code(s).strip()
        if not c:
            continue
        if re.search(r"\bSECTION\s*\.|\bDECLARATIVES\b", c):
            return f"SECTION / DECLARATIVES at {i}"
        m = re.match(r"COPY\s+'?([A-Z0-9-]+)'?", c)
        if m:
            if not _area_a(s):
                return f"Area-B procedure COPY at {i}"
            if not cx._self_contained_copy(f, m.group(1)):
                return f"procedure COPY {m.group(1)} at {i} PERFORMs / GOes TO outside itself"
            # its line stays inside the paragraph before it, whose last statement is then `COPY`, never a transfer:
            # fall-through past the copybook is assumed whenever that paragraph can run sequentially
            continue
        if _area_a(s) and i not in heads and c != ".":
            return f"unrecognized Area-A text at {i}"
    for i in range(ps + 1, len(L) + 1):
        if re.search(r"[a-z]", _strip(cx.code(L[i - 1]))):
            return f"lowercase code at {i} (the tokenizer is uppercase-only)"
    T = tokens(f)
    tv = [t for _, t in T]
    ext = copy_heads(f)  # PERFORMed copybook paragraphs return; they PERFORM / GO TO only themselves
    why = _flow_refusal(T, names, ext, "")
    if why:
        return why
    for ln0, cp in proc_copies(f):
        why = _flow_refusal(copy_tokens(f, cp), sorted(copy_heads(f)), set(), f"{cp}.cpy:")
        if why:
            return f"in procedure copybook {cp} (COPY at {ln0}): {why}"
    for k, (ln, t) in enumerate(T):
        if t == "ALTER":
            return f"ALTER at {ln}"
        if t == "DEPENDING":
            return f"GO TO ... DEPENDING at {ln}"
        if t in ("PERFORM", "GO") or (t == "TO" and k and tv[k - 1] == "GO"):
            if t == "GO":
                continue
            nx = T[k + 1] if k + 1 < len(T) else (ln, ".")
            if t == "TO":
                if nx[1] == "." or nx[1] not in names:
                    if nx[1] in (".",) or nx[1] in VERBS:
                        return f"GO TO with no paragraph name at {ln}"
                if nx[0] != ln:
                    return f"GO TO with its paragraph name on the next line at {ln}"
                continue
            # PERFORM
            if nx[1] in ext:
                if nx[0] != ln:
                    return f"PERFORM with its paragraph name on the next line at {ln}"
                if k + 3 < len(T) and T[k + 2][1] in ("THRU", "THROUGH") and T[k + 3][1] not in ext:
                    return f"PERFORM THRU from a copybook paragraph into the program at {ln}"
                continue
            if nx[1] in names:
                if nx[0] != ln:
                    return f"PERFORM with its paragraph name on the next line at {ln}"
                if k + 2 < len(T) and T[k + 2][1] in ("THRU", "THROUGH"):
                    b = T[k + 3][1] if k + 3 < len(T) else ""
                    if b not in names:
                        return f"PERFORM THRU without a known end paragraph at {ln}"
                    ia, ib = names.index(nx[1]), names.index(b)
                    if ib - ia not in (0, 1):
                        return f"PERFORM {nx[1]} THRU {b} has interior paragraphs (at {ln})"
            elif nx[1] not in INLINE_KW and not re.match(r"^[0-9]+$", nx[1]) and re.match(r"^[A-Z0-9][A-Z0-9-]*$", nx[1]):
                # PERFORM <data-name> TIMES is inline; anything else names something that is not a paragraph
                if not (k + 2 < len(T) and T[k + 2][1] == "TIMES"):
                    return f"PERFORM of an unknown name {nx[1]} at {ln}"
    if re.search(r"\bRECEIVE\s+MAP\b(?![^.]*\bINTO\b)", " ".join(tv)):
        return "RECEIVE MAP without INTO"
    return ""


def _sentences_of(f, a, b):
    """token list of lines a..b split at periods."""
    out, cur = [], []
    for ln, t in tokens(f):
        if a <= ln <= b:
            if t == ".":
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(t)
    if cur:
        out.append(cur)
    return out


def ends_in_transfer(f, a, b):
    """the last statement of lines a..b is an unconditional transfer (GO TO p, GOBACK, STOP RUN, EXIT PROGRAM,
    EXEC CICS RETURN / XCTL ... END-EXEC), outside any open IF / EVALUATE / conditional phrase."""
    ss = _sentences_of(f, a, b)
    ss = [s for s in ss if s not in (["EXIT"],)]
    if not ss:
        return False
    s = ss[-1]
    while s and s[-1] == "EXIT" and (len(s) < 2 or s[-2] not in ("GO", "TO")):
        s = s[:-1]
    if not s:
        return False
    # find the start of the last statement
    k = len(s) - 1
    if s[-1] == "END-EXEC":
        k = max(i for i, t in enumerate(s) if t == "EXEC")
        blk = s[k:]
        if not (len(blk) > 2 and blk[1] == "CICS" and blk[2] in ("RETURN", "XCTL")):
            return False
    elif s[-1] in ("GOBACK",):
        k = len(s) - 1
    elif len(s) >= 2 and s[-2:] in (["STOP", "RUN"], ["EXIT", "PROGRAM"]):
        k = len(s) - 2
    elif len(s) >= 3 and s[-3:-1] == ["GO", "TO"]:
        k = len(s) - 3
    else:
        return False
    before = s[:k]
    opens = before.count("IF") - before.count("END-IF") + before.count("EVALUATE") - before.count("END-EVALUATE")
    cond = {"AT", "END", "INVALID", "EXCEPTION", "OVERFLOW", "SIZE", "WHEN", "ELSE", "NEXT"} & set(before)
    return opens == 0 and not cond


def _gotos(f, a, b):
    T = [x for x in tokens(f) if a <= x[0] <= b]
    return [(T[k][0], T[k + 2][1]) for k in range(len(T) - 2) if T[k][1] == "GO" and T[k + 1][1] == "TO"]


def ranges(f):
    """[(site line, a, b)] for every PERFORM p / PERFORM a THRU b (paragraph indices)."""
    names = [p[0] for p in cx.paragraphs(f)]
    T = tokens(f)
    out = []
    for k, (ln, t) in enumerate(T):
        if t == "PERFORM" and k + 1 < len(T) and T[k + 1][1] in names:
            ia = names.index(T[k + 1][1])
            ib = ia
            if k + 3 < len(T) and T[k + 2][1] in ("THRU", "THROUGH") and T[k + 3][1] in names:
                ib = names.index(T[k + 3][1])
            out.append((ln, ia, ib))
    return out


def sequential(f):
    """indices of paragraphs that can run outside any PERFORM (sequential context), and whether the unnamed main
    falls into the first paragraph. Transitive: entry; fall-through from a sequential paragraph that does not end in a
    transfer; GO TO from a sequential paragraph; GO TO from a performed paragraph to a target outside its range."""
    pp = cx.paragraphs(f)
    L = defs.flines(f)
    ps = cx.proc_start(f)
    main = any(cx.code(L[i - 1]).strip() not in ("", ".") and not cx.code(L[i - 1]).strip().startswith("USING")
               for i in range(ps + 1, pp[0][1]))
    names = [p[0] for p in pp]
    rg = ranges(f)
    Q = set()
    main_falls = main and not ends_in_transfer(f, ps + 1, pp[0][1] - 1)
    if main:
        for _, t in _gotos(f, ps + 1, pp[0][1] - 1):
            if t in names:
                Q.add(names.index(t))
    if not main or main_falls:
        Q.add(0)
    changed = True
    while changed:
        changed = False
        for k, (nm, a, b) in enumerate(pp):
            add = set()
            if k in Q:
                if k + 1 < len(pp) and not ends_in_transfer(f, a + 1, b):
                    add.add(k + 1)
                add |= {names.index(t) for _, t in _gotos(f, a, b) if t in names}
            else:
                mine = [(x, y) for _, x, y in rg if x <= k <= y]
                for _, t in _gotos(f, a, b):
                    if t in names and any(not (x <= names.index(t) <= y) for x, y in mine):
                        add.add(names.index(t))
            if add - Q:
                Q |= add
                changed = True
    return Q, main_falls


def callers(f, k):
    """site lines that PERFORM / GO TO paragraph k or a range containing it (one-line forms; others were refused)."""
    names = [p[0] for p in cx.paragraphs(f)]
    out = {ln for ln, a, b in ranges(f) if a <= k <= b}
    T = tokens(f)
    out |= {T[i][0] for i in range(len(T) - 2) if T[i][1] == "GO" and T[i + 1][1] == "TO" and T[i + 2][1] == names[k]}
    return sorted(out)


def handle_labels(f):
    """paragraph indexes named by EXEC CICS HANDLE ABEND LABEL(x) / CONDITION c(x) / AID k(x): implicit entries."""
    names = [p[0] for p in cx.paragraphs(f)]
    out = set()
    for verb, toks in _statements(f):
        tv = [t for _, t in toks]
        if verb == "EXEC" and "HANDLE" in tv[:3]:
            out |= {names.index(tv[i + 1]) for i in range(len(tv) - 1) if tv[i] == "(" and tv[i + 1] in names}
    return out


def path_complete(f, line, depth=4, max_sites=20):
    """(ok, reason, sites): every way into the anchor's paragraph, back to the entry, within the render's caps."""
    why = program_refusal(f)
    if why:
        return False, why, []
    pp = cx.paragraphs(f)
    ps = cx.proc_start(f)
    if ps <= line < pp[0][1]:
        return True, "", []
    po = cx.para_of(f, line)
    if not po:
        return False, "no paragraph", []
    names = [p[0] for p in pp]
    Q, main_falls = sequential(f)
    H = handle_labels(f)
    seen, frontier, sites = {names.index(po[0])}, [names.index(po[0])], []
    for _ in range(depth):
        nxt = []
        for k in frontier:
            prevk = k - 1
            if k in H:
                return False, f"{names[k]} is a HANDLE label (entered on an abend or condition)", sites
            if prevk in H and not ends_in_transfer(f, pp[prevk][1] + 1, pp[prevk][2]):
                return False, f"fall-through into {names[k]} from HANDLE label {names[prevk]}", sites
            if k == 0 and main_falls:
                return False, f"the unnamed main falls into {names[k]}", sites
            if prevk >= 0 and prevk in Q and not ends_in_transfer(f, pp[prevk][1] + 1, pp[prevk][2]):
                return False, f"fall-through into {names[k]} from {names[prevk]}", sites
            for i in callers(f, k):
                sites.append(i)
                q = cx.para_of(f, i)
                if q is None:
                    continue  # a site in the unnamed main: the entry
                qk = names.index(q[0])
                if qk not in seen:
                    seen.add(qk)
                    nxt.append(qk)
        frontier = nxt
        if not frontier:
            if len(sites) > max_sites:
                return False, f"PATH has {len(sites)} sites, more than the {max_sites} R is shown", sites
            return True, "", sites
    return False, f"caller walk not finished within depth {depth}", sites


# ---------------- WRITERS (statement-level; implicit writers refuse, see writers_complete) ----------------

def _items(f):
    """[(file, line, level, name, redefines)] over the COPY-expanded program."""
    out = []
    for ff, ln, s in cx.expanded(f):
        lv = cx._level_line(s)
        if lv:
            m = re.search(r"\bREDEFINES\s+([A-Z0-9-]+)", cx.code(s))
            out.append((ff, ln, lv[0], lv[1], m.group(1) if m else None))
    return out


def closure_plus(f, name):
    S, at = cx.closure(name, [f] + defs.copybooks(f))
    if not S:
        return None, None
    it = _items(f)
    def desc(nm):
        out = set()
        for k, (_, _, lv, n, _) in enumerate(it):
            if n == nm and lv not in (66, 77, 88):
                for j in range(k + 1, len(it)):
                    if it[j][2] in (66, 77) or (it[j][2] != 88 and it[j][2] <= lv):
                        break
                    out.add(it[j][3])
                break
        return out
    base = {name} | {n for n in S if n != name and any(x[3] == name and x[2] == 88 for x in it)}  # the name, its 88 parent
    D = set()
    for nm in base:
        D |= desc(nm)
    S |= D
    for _ in range(3):
        add = set()
        for _, _, _, n, r in it:
            if r and (r in S or n in S):
                add |= {n, r} | desc(n) | desc(r)
        add.discard("FILLER")
        if add <= S:
            break
        S |= add
    return S, at


def _fd_records(f):
    """file name -> record item names (FD level 01 and below)."""
    out, cur = {}, None
    for ff, ln, s in cx.expanded(f):
        c = cx.code(s).strip()
        m = re.match(r"^(FD|SD)\s+([A-Z0-9-]+)", c)
        if m:
            cur = m.group(2)
            out[cur] = set()
            continue
        if re.search(r"\b(WORKING-STORAGE|LINKAGE|LOCAL-STORAGE)\s+SECTION\b|\bPROCEDURE\s+DIVISION\b", c):
            cur = None
        lv = cx._level_line(s)
        if cur and lv:
            out[cur].add(lv[1])
    return out


def _statements(f):
    """[(verb, [(line, token)])] over the PROCEDURE DIVISION; EXEC ... END-EXEC is one statement."""
    return _split(tokens(f))


def _split(T):
    out, cur, inexec = [], None, False
    for ln, t in T:
        if inexec:
            cur[1].append((ln, t))
            if t == "END-EXEC":
                inexec = False
            continue
        if t in VERBS or t == ".":
            if cur:
                out.append(cur)
            cur = (t, [(ln, t)]) if t != "." else None
            if t == "EXEC":
                inexec = True
            continue
        if cur:
            cur[1].append((ln, t))
    if cur:
        out.append(cur)
    return out


def _base(t):
    return re.sub(r"\(.*$", "", t)


SPECIAL = re.compile(r"^(SQL[A-Z0-9-]*|EIB(?!CALEN$)[A-Z0-9]*|RETURN-CODE|SORT-RETURN|TALLY|DFH[A-Z0-9-]*)$")


def file_status(f):
    """status item -> file name, from SELECT ... FILE STATUS IS x (program text with COPYs spliced in)."""
    txt = " ".join(_strip(cx.code(s)) for _, _, s in cx.expanded(f))
    out = {}
    for m in re.finditer(r"\bSELECT\s+(?:OPTIONAL\s+)?([A-Z0-9-]+)\b(.*?)\.(?=\s|$)", txt):
        st = re.search(r"\bFILE\s+STATUS\s+(?:IS\s+)?([A-Z0-9-]+)(?:\s+([A-Z0-9-]+))?", m.group(2))
        if st:
            out[st.group(1)] = m.group(1)
            if st.group(2) and st.group(2) not in ("ACCESS", "ORGANIZATION", "RECORD", "ALTERNATE", "LOCK", "RESERVE"):
                out[st.group(2)] = m.group(1)
    return out


def _copy_writes(f, S):
    """PERFORM / GO TO site lines of procedure-copybook paragraphs whose copybook text writes a name in S."""
    hits = set()
    heads = None
    for ln0, cp in proc_copies(f):
        T = copy_tokens(f, cp)
        if not _token_writes(T, S, f):
            continue
        heads = heads or {}
        mine = set()
        for t in (defs.flines(defs.copybook_path(f, cp) or "") or []):
            if len(t) > 7 and t[6] not in "*/" and t[7] != " ":
                h = cx.HEAD_ONLY.match(cx.code(t).strip().rstrip(".").strip())
                if h:
                    mine.add(h.group(1))
        PT = tokens(f)
        hits.add(ln0)
        hits |= {PT[k][0] for k in range(len(PT) - 1) if PT[k][1] in ("PERFORM", "TO", "THRU", "THROUGH") and PT[k + 1][1] in mine}
    return hits


def _token_writes(T, S, f):
    return bool(_write_hits(_split(T), S, f))


def write_lines(f, S):
    """lines of statements that may write any name in S, including the implicit writers: every I/O statement on the
    file whose FILE STATUS item is in S, and the PERFORM sites of a procedure copybook that writes S."""
    hits = _write_hits(_statements(f), S, f)
    fs = file_status(f)
    files = {fs[n] for n in S if n in fs}
    if files:
        fd = _fd_records(f)
        recs = set().union(*[fd.get(x, set()) for x in files])
        for verb, toks in _statements(f):
            tv = [_base(t) for _, t in toks]
            if verb in ("OPEN", "CLOSE", "READ", "WRITE", "REWRITE", "DELETE", "START", "RETURN", "RELEASE") and \
                    (set(tv[1:]) & files or (verb in ("WRITE", "REWRITE", "RELEASE") and len(tv) > 1 and tv[1] in recs)):
                hits.add(toks[0][0])
    hits |= _copy_writes(f, S)
    return sorted(hits)


def special_names(text):
    """platform-written names (SQLCA, EIB other than EIBCALEN, RETURN-CODE, ...) in a text: any UNREACHABLE clear that
    depends on one is refused, since no static writer list covers them."""
    return sorted({t for t in re.findall(r"[A-Z0-9][A-Z0-9-]*", text or "") if SPECIAL.match(t)})


def _write_hits(stmts, S, f):
    fd = _fd_records(f)
    hits = set()
    for verb, toks in stmts:
        tv = [_base(t) for _, t in toks]
        occ = [(ln, i) for i, (ln, t) in enumerate(toks) if _base(t) in S or t.lstrip(":") in S]
        if verb in ("READ", "RETURN") and len(tv) > 1 and tv[1] in fd and "INTO" not in tv and fd[tv[1]] & S:
            hits.add(toks[0][0])
        if not occ:
            continue
        def after(kw_set):
            ks = [i for i, t in enumerate(tv) if t in kw_set]
            return min(ks) if ks else None
        w = []
        if verb == "MOVE":
            k = max([i for i, t in enumerate(tv) if t == "TO"] or [10 ** 6])
            w = [ln for ln, i in occ if i > k]
        elif verb == "SET":
            k = after({"TO", "UP", "DOWN"})
            w = [ln for ln, i in occ if k is not None and i < k]
        elif verb in ("INITIALIZE",):
            k = after({"REPLACING", "WITH"})
            w = [ln for ln, i in occ if k is None or i < k]
        elif verb == "COMPUTE":
            k = after({"="})
            w = [ln for ln, i in occ if k is None or i < k]
        elif verb == "ACCEPT":
            w = [ln for ln, i in occ if i == 1]
        elif verb in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
            g = after({"GIVING"})
            if g is not None:
                w = [ln for ln, i in occ if i > g]
            else:
                kw = {"ADD": {"TO"}, "SUBTRACT": {"FROM"}, "MULTIPLY": {"BY"}, "DIVIDE": {"INTO"}}[verb]
                k = after(kw)
                w = [ln for ln, i in occ if k is not None and i > k]
            r = after({"REMAINDER"})
            w += [ln for ln, i in occ if r is not None and i > r]
        elif verb in ("STRING", "UNSTRING"):
            k = after({"INTO"})
            w = [ln for ln, i in occ if k is not None and i > k]
        elif verb == "READ":
            k = after({"INTO"})
            w = [ln for ln, i in occ if k is not None and i > k]
        elif verb == "PERFORM":
            for kw in ("VARYING", "AFTER"):
                for j, t in enumerate(tv):
                    if t == kw and j + 1 < len(tv):
                        w += [ln for ln, i in occ if i == j + 1]
        elif verb in ("WRITE", "REWRITE"):
            if "FROM" in tv:
                w = [ln for ln, i in occ if i == 1]
        elif verb == "EXEC":
            for ln, i in occ:
                # the option whose parentheses hold this occurrence
                d, opt = 0, None
                for j in range(i - 1, -1, -1):
                    if tv[j] == ")":
                        d += 1
                    elif tv[j] == "(":
                        if d == 0:
                            opt = tv[j - 1] if j else None
                            break
                        d -= 1
                if opt in ("INTO", "RESP", "RESP2", "SET", "LENGTH", "RIDFLD", "FLENGTH", "KEYLENGTH", "NUMITEMS", "ITEM") or \
                        (opt is None and "INTO" in tv[:i] and toks[i][1].startswith(":")):
                    w.append(ln)
                elif opt is None and toks[i][1].startswith(":"):
                    pass  # an SQL host variable outside INTO is read
                elif opt == "COMMAREA" and "LINK" in tv[:4]:
                    w.append(ln)  # a LINKed program may change the COMMAREA it is given
                elif opt not in ("FROM", "PROGRAM", "TRANSID", "MAP", "MAPSET", "DATASET", "FILE", "QUEUE", "COMMAREA"):
                    w.append(ln)  # unknown option: listed as a possible writer
        elif verb in ("CALL", "INSPECT", "SEARCH", "SORT", "MERGE", "RELEASE", "RETURN", "START", "DELETE", "UNSTRING"):
            w = [ln for ln, _ in occ]
        hits |= set(w)
    return hits


def writers_complete(f, names):
    """(ok, reason, {name: lines}) for the names R was given."""
    out = {}
    fs = file_status(f)
    for nm in names:
        if SPECIAL.match(nm):
            return False, f"{nm} is written by the platform (no writer list covers it)", out
        S, _ = closure_plus(f, nm)
        if not S:
            continue
        # coord delta2 C-G1 (time-boxed ruling): a name with implicit writers refuses the clear
        if S & set(fs):
            return False, f"{nm} overlaps the FILE STATUS item {sorted(S & set(fs))[0]} (written by every I/O on its file)", out
        cw = _copy_writes(f, S)
        if cw:
            return False, f"{nm} is written inside a procedure copybook (PERFORM / COPY at {sorted(cw)[0]})", out
        out[nm] = write_lines(f, S)
    return True, "", out


def required_lines(f, line, names, entry_cap=200):
    """(ok, reason, lines R must have been shown for a clear to rest on its context)."""
    ok, why, sites = path_complete(f, line)
    if not ok:
        return False, why, set()
    need = set(sites)
    ps = cx.proc_start(f)
    pp = cx.paragraphs(f)
    if pp[0][2] > ps + entry_cap:
        return False, f"ENTRY is {pp[0][2] - ps + 1} lines, more than the {entry_cap + 1} R is shown", set()
    need |= set(range(ps, pp[0][2] + 1))
    wok, wwhy, wl = writers_complete(f, names)
    if not wok:
        return False, wwhy, set()
    for nm, ls in wl.items():
        need |= set(ls)
    return True, "", need
