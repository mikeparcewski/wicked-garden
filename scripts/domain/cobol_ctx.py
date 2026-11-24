# Ported from the J6 v3 proof (proof-v3/cal/cobol_ctx.py, sha256 76e57f48...): the tree is the run's
# (domain.defs.set_root) and a COPY resolves as defs.copybook_path does (beside the program, else the one copybook
# of that name in the tree), not at CardDemo's fixed app/cpy/.
"""v3 reachability context for COBOL (0 model calls): the program's ENTRY (PROCEDURE DIVISION through its first
paragraph), the PATH from the entry to the anchor routine (PERFORM / GO TO sites, transitively, by text), and the
WRITERS of every data name a finding depends on (the name, its 88-level parent and siblings, its group ancestors).
Text only, over the program and its copybooks: the same floor as v2's defs.py (no new tool)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import defs  # noqa: E402  (go-to-definition over the run's tree)

PARA = re.compile(r"^([A-Z0-9][A-Z0-9-]*)(\s+SECTION)?\.\s*$")


HEAD_ONLY = re.compile(r"^([A-Z0-9][A-Z0-9-]*)(\s+SECTION)?$")


def next_code(L, i):
    """the next non-blank, non-comment code text after line i (1-based)."""
    for s in L[i:]:
        c = code(s).strip()
        if c:
            return c
    return ""


def unparsed_area_a(f):
    """PROCEDURE DIVISION lines that start in Area A but are not a recognized paragraph header or a lone period. Any
    such line means the paragraph map (and so ENTRY / PATH) may be incomplete; R may not clear on that file."""
    L = defs.flines(f)
    ps = proc_start(f)
    if not ps:
        return []
    hs = {a for _, a, _ in paragraphs(f)}
    out = []
    for i in range(ps + 1, len(L) + 1):
        s = L[i - 1]
        if len(s) > 8 and s[6] not in "*/" and s[7] != " " and i not in hs and s[7:72].strip() not in (".", ""):
            m = re.match(r"COPY\s+'?([A-Z0-9-]+)'?", s[7:72].strip())
            if m and _self_contained_copy(f, m.group(1)):
                continue  # a procedure copybook whose PERFORM / GO TO targets are all its own paragraphs
            out.append(i)
    return out


def _copy_text(f, name):
    L = defs.flines(defs.copybook_path(f, name) or "")
    return "\n".join(L) if L else None


def _self_contained_copy(f, name):
    t = _copy_text(f, name)
    if t is None:
        return False
    own, tgt = set(), set()
    for s in t.split("\n"):
        c = code(s)
        if not c.strip():
            continue
        if len(s) > 7 and s[7] != " ":
            m = HEAD_ONLY.match(c.strip().rstrip(".").strip())
            if m:
                own.add(m.group(1))
        tgt |= set(re.findall(r"\b(?:PERFORM|GO\s+TO|THRU|THROUGH)\s+([A-Z0-9][A-Z0-9-]*)", c))
    tgt -= {"UNTIL", "VARYING", "WITH", "TEST"}
    return tgt <= own


def code(s):
    return s[7:72] if len(s) > 7 and s[6] not in "*/" else ""


def proc_start(f):
    for i, s in enumerate(defs.flines(f), 1):
        if re.search(r"\bPROCEDURE\s+DIVISION\b", code(s)):
            return i
    return None


def paragraphs(f):
    L = defs.flines(f)
    ps = proc_start(f)
    if not ps:
        return []
    heads = []
    for i in range(ps + 1, len(L) + 1):
        s = L[i - 1]
        if len(s) > 8 and s[6] not in "*/" and s[7] != " ":
            t = s[7:72].strip()
            m = PARA.match(t)
            if not m and HEAD_ONLY.match(t) and next_code(L, i).startswith("."):
                m = HEAD_ONLY.match(t)  # codex-check r3: `2000-SEND-MAP` with its period on the next line
            if m:
                heads.append((m.group(1), i))
    out = []
    for k, (nm, a) in enumerate(heads):
        b = (heads[k + 1][1] - 1) if k + 1 < len(heads) else len(L)
        out.append((nm, a, b))
    return out


def para_of(f, line):
    for nm, a, b in paragraphs(f):
        if a <= line <= b:
            return nm, a, b
    return None


def entry(f, cap=200):
    ps = proc_start(f)
    pp = paragraphs(f)
    if not ps or not pp:
        return None
    b = pp[0][2]
    return ps, min(b, ps + cap)


def performers(f, para):
    """lines that PERFORM / GO TO `para`, or PERFORM a THRU range that contains it (codex-check r3: interior too)."""
    L = defs.flines(f)
    ps = proc_start(f) or 1
    order = [x[0] for x in paragraphs(f)]
    k = order.index(para) if para in order else -1
    out = []
    pat = re.compile(rf"\b(PERFORM|GO\s+TO)\s+{re.escape(para)}(?![A-Z0-9-])")
    for i in range(ps, len(L) + 1):
        t = code(L[i - 1])
        if pat.search(t) or re.search(rf"\bTHRU\s+{re.escape(para)}(?![A-Z0-9-])", t):
            out.append(i)
            continue
        m = re.search(r"\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)\s*$", t)
        if m and k >= 0 and i < len(L):
            m2 = re.search(r"^\s*(?:THRU|THROUGH)\s+([A-Z0-9][A-Z0-9-]*)", code(L[i]))
            if m2 and m.group(1) in order and m2.group(1) in order and order.index(m.group(1)) < k < order.index(m2.group(1)):
                out.append(i)
    return out


_END = re.compile(r"\b(GO\s+TO|GOBACK|STOP\s+RUN|EXIT\s+PROGRAM|RETURN|XCTL)\b")


def ctx_complete(f, line, depth=4):
    """(ok, reason): can a REJECTED rest on the ENTRY / PATH map? Fail closed when the map may miss a path:
    an unrecognized Area-A line, a caller walk cut off by the depth cap, or a paragraph on the path that control can
    fall into from the one before it (that one is the entry or a GO TO target and does not end in a transfer)."""
    if unparsed_area_a(f):
        return False, "unrecognized Area-A line"
    pp = paragraphs(f)
    L = defs.flines(f)
    ps = proc_start(f)
    if not ps or not pp:
        return False, "no paragraph"
    # code between PROCEDURE DIVISION and the first paragraph is an unnamed main (batch): it is the entry
    main = [code(L[i - 1]).strip() for i in range(ps + 1, pp[0][1]) if code(L[i - 1]).strip() not in ("", ".")]
    main = [t for t in main if not t.startswith(("USING", "DECLARATIVES", "END DECLARATIVES"))]
    if ps <= line < pp[0][1]:
        return True, ""
    po = para_of(f, line)
    if not po:
        return False, "no paragraph"
    order = [x[0] for x in pp]
    body = " ".join(code(s) for s in L[(proc_start(f) or 1) - 1:])
    # a GO TO target that ends a PERFORM ... THRU range (the X-EXIT idiom) returns at its end; it does not fall through
    gt = set(re.findall(r"GO\s+TO\s+([A-Z0-9][A-Z0-9-]*)", body)) - set(re.findall(r"(?:THRU|THROUGH)\s+([A-Z0-9][A-Z0-9-]*)", body))
    seen, frontier = {po[0]}, [po[0]]
    for _ in range(depth + 1):
        nxt = []
        for p in frontier:
            k = order.index(p)
            if k == 0 and main and not _END.search(main[-1]):
                return False, f"fall-through from the unnamed main into {p}"
            if k > 0:
                prev = pp[k - 1]
                last = next((code(L[i - 1]).strip() for i in range(prev[2], prev[1] - 1, -1) if code(L[i - 1]).strip() not in ("", ".", "EXIT", "EXIT.")), "")
                if ((k - 1 == 0 and not main) or prev[0] in gt) and not _END.search(last):
                    return False, f"fall-through into {p}"
            for i in performers(f, p):
                q = para_of(f, i)
                if q and q[0] not in seen:
                    seen.add(q[0])
                    nxt.append(q[0])
        frontier = nxt
        if not frontier:
            return True, ""
    return False, "caller walk cut off at the depth cap"


def path_to(f, line, depth=4, cap_lines=70):
    """(performer line, its paragraph) chains from the anchor routine up to the entry paragraph."""
    po = para_of(f, line)
    if not po:
        return [], None
    first = paragraphs(f)[0][0]
    seen, frontier, sites = {po[0]}, [po[0]], []
    for _ in range(depth):
        nxt = []
        for p in frontier:
            for i in performers(f, p):
                q = para_of(f, i)
                sites.append((p, i, q[0] if q else "?"))
                if q and q[0] not in seen:
                    seen.add(q[0])
                    nxt.append(q[0])
        frontier = nxt
        if not frontier:
            break
    return sites, po


def _level_line(s):
    return defs.level(s) if len(s) > 7 and s[6] not in "*/" else None


def expanded(f):
    """the program's lines with every `COPY x.` replaced by the copybook's lines (one level, as the compiler sees
    them), each as (file, line, text). Level walks run on this, so a copybook's 01 is the parent of the items
    that follow its COPY (COCOM01Y's CARDDEMO-COMMAREA owns COUSR00C's CDEMO-CU00-INFO)."""
    out = []
    for i, s in enumerate(defs.flines(f), 1):
        m = re.match(r"^.{6}\s+COPY\s+([A-Z0-9-]+)", s) if len(s) > 7 and s[6] not in "*/" else None
        cp = defs.copybook_path(f, m.group(1)) if m else None
        if cp:
            out += [(cp, j, t) for j, t in enumerate(defs.flines(cp), 1)]
        else:
            out.append((f, i, s))
    return out


_exp = {}
defs.on_reset(_exp.clear)  # keyed by path: a new tree starts empty


def closure(name, files):
    """the data names whose writes can change `name`: itself, its 88 parent and that parent's 88s, its own 88s,
    and its group ancestors (on the COPY-expanded program text). Returns (set, def location) or (None, None) when
    `name` is not a data item."""
    f0 = files[0]
    if f0 not in _exp:
        _exp[f0] = expanded(f0)
    L = _exp[f0]
    for k, (ff, ln, s) in enumerate(L):
        lv = _level_line(s)
        if not lv or lv[1] != name:
            continue
        S = {name}
        base_k, base_lv = k, lv[0]
        if lv[0] == 88:
            for j in range(k - 1, max(-1, k - 40), -1):
                l2 = _level_line(L[j][2])
                if l2 and l2[0] != 88:
                    S.add(l2[1])
                    base_k, base_lv = j, l2[0]
                    break
        for j in range(base_k + 1, min(len(L), base_k + 60)):  # 88s of the base item
            l2 = _level_line(L[j][2])
            if not l2:
                continue
            if l2[0] != 88:
                break
            S.add(l2[1])
        cur = base_lv
        for j in range(base_k - 1, -1, -1):  # group ancestors (lower level numbers above it)
            l2 = _level_line(L[j][2])
            if not l2 or l2[0] == 88 or l2[0] in (66, 77):
                continue
            if l2[0] < cur:
                S.add(l2[1])
                cur = l2[0]
                if cur <= 1:
                    break
        S.discard("FILLER")
        return S, (ff, ln)
    return None, None


def _writes(stmt, tok):
    t = re.escape(tok)
    pats = [rf"\bSET\b[^.]*?(?<![A-Z0-9-]){t}(?![A-Z0-9-])[^.]*?\bTO\b", rf"\bTO\b[^.]*?(?<![A-Z0-9-]){t}(?![A-Z0-9-])",
            rf"\bINITIALIZE\b[^.]*?(?<![A-Z0-9-]){t}(?![A-Z0-9-])", rf"\bINTO\b[^.]*?(?<![A-Z0-9-]){t}(?![A-Z0-9-])",
            rf"\bCOMPUTE\s+{t}(?![A-Z0-9-])", rf"\bACCEPT\s+{t}(?![A-Z0-9-])", rf"\bGIVING\b[^.]*?(?<![A-Z0-9-]){t}(?![A-Z0-9-])"]
    return any(re.search(p, stmt) for p in pats)


def writers(f, name, cap=25):
    files = [f] + defs.copybooks(f)
    S, at = closure(name, files)
    if not S:
        return None
    L = defs.flines(f)
    ps = proc_start(f) or 1
    out = []
    for i in range(ps, len(L) + 1):
        t = code(L[i - 1])
        hit = [s for s in S if re.search(rf"(?<![A-Z0-9-]){re.escape(s)}(?![A-Z0-9-])", t)]
        if not hit:
            continue
        prev = code(L[i - 2]) if i >= 2 else ""
        starts = re.match(r"^\s*(MOVE|SET|INITIALIZE|READ|ADD|SUBTRACT|COMPUTE|ACCEPT|EXEC|STRING|UNSTRING|WHEN|IF|ELSE|END-|PERFORM|EVALUATE|NOT|OR|AND|GO|CALL)", t)
        stmt = t if starts else (prev + " " + t)
        if any(_writes(stmt, s) for s in hit):
            out.append(i)
    return dict(name=name, closure=sorted(S), defined=f"{at[0]}:{at[1]}", lines=out[:cap], more=max(0, len(out) - cap))


def render(f, anchor_line, names, entry_cap=200):
    """the three sections, as numbered lines."""
    L = defs.flines(f)
    out = []
    e = entry(f, entry_cap)
    if e:
        out.append(f"### PROGRAM ENTRY: the PROCEDURE DIVISION through its first paragraph ({f}:{e[0]}-{e[1]})")
        out += [f"{i}: {L[i - 1]}" for i in range(e[0], e[1] + 1)]
    from domain import cobol_flow as g  # coord delta check F1-F3: the same fail-closed walk `decide` gates on
    po = para_of(f, anchor_line)
    if po:
        ok, why, sites = g.path_complete(f, anchor_line)
        out.append(f"### PATH TO THE ROUTINE {po[0]} ({f}:{po[1]}-{po[2]}): the literal PERFORM / GO TO sites found for it, and "
                   f"for the paragraphs holding them, up to the entry (each with 2 lines around it)")
        shown = set()
        for i in sites[:20]:
            q = para_of(f, i)
            out.append(f"--- reached at line {i} (in {q[0] if q else 'the unnamed main'})")
            for j in range(max(1, i - 2), min(len(L), i + 2) + 1):
                if (j not in shown):
                    out.append(f"{j}: {L[j - 1]}")
                    shown.add(j)
        if not sites:
            out.append(f"--- no literal PERFORM / GO TO site was found for {po[0]}")
        if not ok:
            out.append(f"--- this map may be incomplete ({why})")
    seen = set()
    for nm in names:
        S, at = g.closure_plus(f, nm)
        if not S or tuple(sorted(S)) in seen:
            continue
        seen.add(tuple(sorted(S)))
        ws = g.write_lines(f, S)
        out.append(f"### WRITERS of {nm} (defined {at[0]}:{at[1]}): statements that may write any of {', '.join(sorted(S))} "
                   f"(a static list: {len(ws)} line(s){', first 25 shown' if len(ws) > 25 else ''})")
        for i in ws[:25]:
            pq = para_of(f, i)
            out.append(f"{i}: {L[i - 1]}    [in {pq[0] if pq else '?'}]")
        if not ws:
            out.append("   (no statement in the PROCEDURE DIVISION was found to write it)")
    return "\n".join(out)


def data_names(text, f):
    files = [f] + defs.copybooks(f)
    out = []
    for nm in defs.COBID.findall(text or ""):
        if nm in out:
            continue
        S, _ = closure(nm, files)
        if S:
            out.append(nm)
    return out


if __name__ == "__main__":
    f = sys.argv[1]
    ln = int(sys.argv[2])
    print(render(f, ln, sys.argv[3:]))
