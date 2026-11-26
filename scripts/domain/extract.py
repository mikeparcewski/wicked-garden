"""J6 v3 extract (DES-j6-build §2; DES-j6-v2 contract v2): one Claude Code call per batch, the machine checks
M1 / M2 / M4' / M7 on every statement and not-rule, the derived kind, and at most one M-repair call per batch.

Ported from the J6 v3 proof (``proof-v3/scripts/extract.py``). The checks and the prompts are unchanged. Three
changes, none to a rule: (1) the proof read its repository, scope and calls at import; the port takes them as
arguments (:func:`extract_all`). (2) The proof's COBOL / generic switch was the repository (CardDemo = COBOL); the
port takes it from the target's file (``lookup.lang_of``), which is the same split on both proof repositories and
lets one run hold both. (3) The proof raised its own CLI's output cap (``CLAUDE_CODE_MAX_OUTPUT_TOKENS``); a seat
call runs the signed-in seat as the daemon launches it (the proof's largest extract answer was about 39 KB).
"""
import collections
import concurrent.futures as cf
import itertools
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import defs  # noqa: E402
from domain import graph as lib  # noqa: E402
from domain import lookup as v2lib  # noqa: E402
from domain import model_calls as calls  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _text(*parts):
    with open(os.path.join(HERE, *parts)) as fh:
        return fh.read()


CARDS = {"cobol": _text("cards", "cobol.md"), "generic": _text("cards", "generic.md")}
XP = _text("prompts", "extract.txt")
RM = _text("prompts", "repair_m.txt")
REJECTED = ("\n\n=== REJECTED BY A PERSON ===\nA person read these statements of the targets above and rejected them; the "
            "note says what is wrong. Do not state them again as they were: state the decision in those lines correctly, "
            "or account for the lines as a not-rule.\n")
TYPES = {"trigger", "condition", "effect", "else", "value"}
REASONS = {"exit", "io-wrapper", "control-only", "display-format"}
COBKW = set("""AND OR NOT IF TO OF IS THEN TRUE FALSE ELSE END-IF MOVE PERFORM UNTIL THRU THROUGH VARYING BY FROM INTO GIVING
WHEN OTHER EVALUATE SET DISPLAY CALL USING READ WRITE REWRITE OPEN CLOSE INPUT OUTPUT I-O EXTEND AT END INVALID KEY NEXT SENTENCE
GO COMPUTE ADD SUBTRACT MULTIPLY DIVIDE ROUNDED ZERO ZEROS ZEROES SPACE SPACES HIGH-VALUES LOW-VALUES EQUAL GREATER LESS THAN
EXIT GOBACK STOP RUN CONTINUE INITIALIZE STRING DELIMITED SIZE ON ERROR EXEC END-EXEC PGM DD DSN DISP SORT FIELDS INCLUDE COND
RECORD FILE STATUS CEE3ABD WITH TEST BEFORE AFTER ALSO NUMERIC ALPHABETIC REPLACING ALL LEADING TRAILING INSPECT TALLYING FOR""".split())
CONFIRMED = ("\n\n=== CONFIRMED BY A PERSON ===\nA person confirmed these statements of the targets above. They stand as "
             "they are and account for their anchor lines: do not state them again.\n")


def person_section(ts):
    """What a person ruled on these targets (``run.rulings``), for the writer: the statements they rejected, with their
    note, and the ones they confirmed. Empty when they ruled on none, so such a batch sends the frozen prompt as is."""
    rej = [dict(target=t["id"], statement=r["statement"], note=r["note"]) for t in ts for r in t.get("rejected") or []]
    con = [dict(target=t["id"], statement=c["statement"], lines=(c.get("anchor") or {}).get("lines"))
           for t in ts for c in t.get("confirmed") or []]
    out = ""
    if rej:
        out += REJECTED + json.dumps(rej, indent=0, ensure_ascii=False)
    if con:
        out += CONFIRMED + json.dumps(con, indent=0, ensure_ascii=False)
    return out


def is_cobol(f):
    return v2lib.lang_of(f) == "cobol"


def pref(r):
    return v2lib.pref(r)


def quoted(text, cob):
    """(literals, identifiers) a claim states: quoted strings and numbers inside backticks are literals; other tokens
    inside backticks are identifiers; quoted strings outside backticks are literals too."""
    lits, ids = set(), set()
    for m in v2lib.BT.finditer(text):
        inner = m.group(1)
        for q in re.finditer(r"'([^']*)'|\"([^\"]*)\"", inner):
            s = q.group(1) if q.group(1) is not None else q.group(2)
            if s.strip():
                lits.add(s)
        rest = re.sub(r"'[^']*'|\"[^\"]*\"", " ", inner)
        for w in re.findall(r"[A-Za-z_$][\w$-]*|\b\d+(?:\.\d+)?\b", rest):
            if re.fullmatch(r"\d+(?:\.\d+)?", w):
                lits.add(w)
            elif cob and w.upper() in COBKW:
                continue
            elif not cob and w in v2lib.TSKW:
                continue
            else:
                ids.add(w.rstrip("-"))
    plain = v2lib.BT.sub(" ", text)
    for q in re.finditer(r"'([^']{2,})'|\"([^\"]{2,})\"", plain):
        lits.add(q.group(1) or q.group(2))
    return lits, ids


def lines_text(repo, refs):
    out = []
    for r in refs:
        p = pref(r)
        if p:
            L = lib.flines(repo, p[0]) or []
            out += L[max(0, p[1] - 1):min(len(L), p[2])]
    return "\n".join(out)


def resolves(repo, name, f, call):
    if is_cobol(f):
        if v2lib.cob_define(name, f) or v2lib.cob_define(name.upper(), f):
            return True
        base = {os.path.splitext(os.path.basename(x))[0].upper() for x in call["files"]}
        return name.upper() in base
    nm = name.split(".")[-1]
    return bool(v2lib.ts_define(repo, nm, f)) or any(nm in "\n".join((lib.flines(repo, x) or [])) for x in call["files"] if x == f)


def in_batch(repo, call, p):
    L = lib.flines(repo, p[0])
    if p[0] not in call["files"] or L is None or not (1 <= p[1] <= p[2] <= len(L)):
        return False
    sh = call["shown"].get(p[0])
    return sh is None or all(i in set(sh) for i in range(p[1], p[2] + 1))


def check_statement(repo, st, t, call):
    cob = is_cobol(t["file"])
    errs = []
    if not isinstance(st, dict):
        return ["M1 statement is not an object"]
    an = st.get("anchor") if isinstance(st.get("anchor"), dict) else {}
    ctx = st.get("context")
    if ctx is not None and not (isinstance(ctx, list) and all(isinstance(x, dict) and isinstance(x.get("at", ""), str)
                                                              for x in ctx)):
        errs.append("M1 context is not a list of {symbol, at}")
    # garden#1548: a concern is what the code means that its literal claims do not say; it cites batch lines like a claim
    cn = st.get("concerns")
    if cn is not None and not isinstance(cn, list):
        errs.append("M1 concerns is not a list of {text, lines}")
    for k, x in enumerate(cn if isinstance(cn, list) else []):
        refs = x.get("lines") if isinstance(x, dict) else None
        if not isinstance(x, dict) or not isinstance(x.get("text"), str) or not x["text"].strip() or not isinstance(refs, list) or not refs:
            errs.append(f"M1 concern {k} is not {{text, lines}} with a text and at least one line")
            continue
        for r in refs:
            p = pref(r) if isinstance(r, str) else None
            if not p:
                errs.append(f"M2 concern {k} line ref {r!r} is not path:N[-M]")
            elif not in_batch(repo, call, p):
                errs.append(f"M2 concern {k} line ref {r} is not inside the batch")
    cl = st.get("claims")
    if not isinstance(cl, list) or not cl:
        return ["M1 claims missing or empty"]
    idx = {}
    for k, c in enumerate(cl):
        if not isinstance(c, dict) or c.get("type") not in TYPES:
            errs.append(f"M1 claim {k} type {c.get('type') if isinstance(c, dict) else c!r} not in {sorted(TYPES)}")
            continue
        if not isinstance(c.get("text"), str):
            errs.append(f"M1 claim {k} has no text")
        i = c.setdefault("i", k)  # a claim without `i` is claim k, so the checker's table names it
        if not isinstance(i, int) or isinstance(i, bool) or i in idx:
            errs.append(f"M1 claim {k} has a missing or duplicate integer `i`")
            continue
        idx[i] = c
    conds = {i for i, c in idx.items() if c.get("type") == "condition"}
    for i, c in idx.items():
        for key in ("when", "unless"):
            v = [] if c.get(key) is None else c.get(key)
            if not isinstance(v, list) or any(not isinstance(x, int) or isinstance(x, bool) or x not in conds for x in v):
                errs.append(f"M1 claim {i} `{key}` {v} must list indices of this statement's condition claims")
        if c.get("type") == "value" and c.get("of") is not None and (not isinstance(c.get("of"), int) or c.get("of") not in idx):
            errs.append(f"M1 claim {i} `of` {c.get('of')} names no claim")
    if an.get("file") != t["file"]:
        errs.append(f"M2 anchor.file {an.get('file')} is not the target's file {t['file']}")
    ln = an.get("lines")
    if not (isinstance(ln, list) and len(ln) == 2 and all(isinstance(x, int) for x in ln)):
        errs.append(f"M2 anchor.lines {ln} is not [start, end]")
    elif not (t["lines"][0] <= ln[0] <= ln[1] <= t["lines"][1]):
        errs.append(f"M2 anchor.lines {ln} not inside the target lines {t['lines']}")
    for i, c in idx.items():
        refs = c.get("lines") or []
        if not isinstance(refs, list):
            errs.append(f"M2 claim {i} lines {refs!r} is not a list of path:N[-M]")
            continue
        if not refs:
            errs.append(f"M2 claim {i} cites no lines")
        for r in refs:
            p = pref(r)
            if not p:
                errs.append(f"M2 claim {i} line ref {r!r} is not path:N[-M]")
            elif not in_batch(repo, call, p):
                errs.append(f"M2 claim {i} line ref {r} is not inside the batch")
        hay = lines_text(repo, refs)
        lits, ids = quoted(c.get("text") if isinstance(c.get("text"), str) else "", cob)
        for s in sorted(lits):  # sorted: a set's order moves with the hash seed, and a re-run must send the same prompt
            ok = (s.lower() in hay.lower()) if cob else (s in hay)
            if not ok:
                errs.append(f"M4' claim {i} quotes the literal `{s}`, which is not on its cited lines")
        for s in sorted(ids):
            on = (s.lower() in hay.lower()) if cob else (s in hay)
            if not on and not resolves(repo, s, t["file"], call):
                errs.append(f"M4' claim {i} names `{s}`, which is not on its cited lines and does not resolve to a definition")
    return errs


def is_rule(st, repo=None):
    """A rule has a condition, else or value claim. With ``repo`` (garden#1548), an effect that cites a record update
    (``graph.updates_records``) also makes one: a bare WRITE has no value to state, and without this its statement
    would be derived into a not-rule that the M7 record-update check then refuses, leaving the target unaccounted."""
    claims = [c for c in st.get("claims") or [] if isinstance(c, dict)]
    if {c.get("type") for c in claims} & {"condition", "else", "value"}:
        return True
    return repo is not None and any(
        p and lib.updates_records(repo, p[0], range(p[1], p[2] + 1))
        for c in claims if c.get("type") == "effect"
        for p in (pref(r) if isinstance(r, str) else None for r in c.get("lines") or []))


def cite_copybooks(st):
    """garden#1548: every field a claim names in backticks (outside a quoted literal) that exactly one of its program's
    copybooks defines goes in the statement's ``context`` with the copybook line (``app/cpy/CVACT01Y.cpy:7``), so the
    statement says which copybook it reads. A name the program defines itself, or its copybooks define twice, is left out
    (the claim's qualification is not resolved here). 0 model calls; a field the model already placed keeps its entry;
    a statement the M checks refused keeps whatever shape it has. Not COBOL: unchanged."""
    f = (st.get("anchor") or {}).get("file") if isinstance(st.get("anchor"), dict) else None
    if not isinstance(f, str) or not is_cobol(f) or not isinstance(st.get("claims"), list):
        return st
    ctx = st.get("context")
    if ctx is None:
        ctx = []
    if not isinstance(ctx, list):
        return st
    # a field the model placed with a reference keeps it; one it named with no reference gets the copybook line
    have = {x.get("symbol") for x in ctx if isinstance(x, dict) and isinstance(x.get("symbol"), str) and isinstance(x.get("at"), str) and x["at"]}
    bare = {x["symbol"]: x for x in ctx if isinstance(x, dict) and isinstance(x.get("symbol"), str) and x["symbol"] not in have}
    in_program = lambda n: (defs.define(n, [f]) or ("",))[0] == f  # noqa: E731
    books = defs.copybooks(f)
    for c in st["claims"]:
        if not isinstance(c, dict) or not isinstance(c.get("text"), str):
            continue
        for span in re.findall(r"`([^`]+)`", c["text"]):
            for name in defs.COBID.findall(re.sub(r"'[^']*'|\"[^\"]*\"", " ", span).upper()):
                if name in have or name in COBKW or in_program(name):
                    continue
                hits = [d for d in (defs.define(name, [cp]) for cp in books) if d]
                many = sum(1 for cp in books for s in defs.flines(cp) if len(s) > 7 and s[6] not in "*/"
                           and (defs.level(s) or (0, ""))[1] == name)
                if len(hits) == 1 and many == 1:  # one definition in all its copybooks
                    if name in bare:
                        bare[name]["at"] = f"{hits[0][0]}:{hits[0][1]}"
                    else:
                        ctx.append(dict(symbol=name, at=f"{hits[0][0]}:{hits[0][1]}"))
                    have.add(name)
    st["context"] = ctx
    return st


def check_target(repo, tout, t, call):
    sts = [s for s in (tout.get("statements") or []) if isinstance(s, dict)]
    nrs = [dict(n) for n in (tout.get("not_rules") or []) if isinstance(n, dict)]
    keep, fails, tf = [], {}, []
    for st in sts:
        if not isinstance(st.get("anchor"), dict):
            st["anchor"] = {}
        an = st["anchor"]
        an["symbol_id"] = an.get("symbol_id") or t["anchor_symbol"]
        e = check_statement(repo, st, t, call)
        if not e and not is_rule(st, repo):
            ln = an["lines"]
            nrs.append(dict(lines=f"{t['file']}:{ln[0]}-{ln[1]}", reason="control-only", note="derived: no condition, else or value claim, and no record update", derived=True))
            continue
        keep.append(st)
        if e:
            fails[len(keep) - 1] = e
    rule_lines = set()
    # Every model-supplied range is cut to the file before it is expanded: only the file's code lines count, and a
    # range such as [1, 10**12] must not exhaust the host before it is refused.
    nlines = len(lib.flines(repo, t["file"]) or [])
    for st in keep + list(t.get("confirmed") or []):  # a statement a person confirmed accounts for its lines too
        an = st.get("anchor") or {}
        ln = an.get("lines")
        if an.get("file") == t["file"] and isinstance(ln, list) and len(ln) == 2 and all(isinstance(x, int) for x in ln):
            rule_lines.update(range(max(ln[0], 1), min(ln[1], nlines) + 1))
    code = lib.code_lines(repo, t["file"])
    for n in nrs:
        if n.get("reason") not in REASONS:
            n["refused"] = True
            tf.append(f"M1 not_rule {n.get('lines')} reason {n.get('reason')!r} not in {sorted(REASONS)}")
        p = pref(n.get("lines") or "")
        if not p or p[0] != t["file"]:
            n["refused"] = True
            tf.append(f"M2 not_rule lines {n.get('lines')!r} are not path:N-M in the target file")
            continue
        dl = [i for i in range(max(p[1], 1), min(p[2], nlines) + 1)
              if i in code and i not in rule_lines and lib.has_decision(repo, t["file"], [i])]
        if dl:
            n["refused"] = True
            tf.append(f"M7 not_rule {n.get('lines')} holds a decision on line(s) {dl[:6]}: state it as a statement with that test as a condition claim")
            continue
        ul = lib.updates_records(repo, t["file"], [i for i in range(max(p[1], 1), min(p[2], nlines) + 1)
                                                   if i in code and i not in rule_lines])
        if ul:
            n["refused"] = True
            tf.append(f"M7 not_rule {n.get('lines')} updates a record on line(s) {ul[:6]}: state it as a statement, one effect "
                      "claim per update in execution order")
    need = {i for i in range(t["lines"][0], t["lines"][1] + 1) if i in code}
    cov = set(rule_lines)
    for n in nrs:
        p = pref(n.get("lines") or "")
        if p and p[0] == t["file"] and not n.get("refused"):
            cov.update(range(max(p[1], 1), min(p[2], nlines) + 1))
    miss = sorted(need - cov)
    if miss:
        runs = []
        for i in miss:
            if runs and i <= runs[-1][1] + 3:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        tf.append("M7 target lines not accounted by any statement anchor or not_rule: " + ", ".join(f"{a}-{b}" for a, b in runs))
    return keep, nrs, fails, tf


def tgt_json(t):
    return dict(target=t["id"], kind=t["kind"], file=t["file"], lines=t["lines"], anchor_symbol=t["anchor_symbol"], name=t.get("anchor_name"))


def card_for(call, ts):
    """A COBOL unit's batch reads the COBOL card; every other batch reads the generic card."""
    f = call.get("unit") or (ts[0]["file"] if ts else "")
    return CARDS["cobol" if is_cobol(f) else "generic"]


def extract_call(repo, tby, call):
    ts = [tby[x] for x in call["targets"]]
    with open(call["text_file"]) as fh:
        batch = fh.read()
    p = XP.replace("{{CARD}}", card_for(call, ts)).replace("{{BATCH}}", batch).replace("{{TARGETS}}", json.dumps([tgt_json(t) for t in ts], indent=0))
    p += person_section(ts)
    out, rc = calls.claude("extract", call["id"], p, timeout=2400, max_output_tokens=calls.WRITER_MAX_OUTPUT)
    if not calls.answered(out, rc):
        raise calls.CallFailed(f"the writer's extract call {call['id']} did not answer (exit {rc}); nothing was stored")
    j = calls.parse_json(out) or {}
    res = {x.get("target"): x for x in j.get("targets", []) if isinstance(x, dict)}
    tres, fl = {}, []
    for t in ts:
        tout = res.get(t["id"]) or {"statements": [], "not_rules": []}
        keep, nrs, fails, tf = check_target(repo, tout, t, call)
        tres[t["id"]] = dict(statements=keep, not_rules=nrs, fails=fails, tfails=tf)
        if fails or tf or t["id"] not in res:
            fl.append(dict(target=t["id"], target_failures=tf + ([] if t["id"] in res else ["target missing from output"]),
                           statement_failures={str(i): e for i, e in fails.items()}))
    m_fail_causes = [e for f in fl for e in f["target_failures"] + [x for v in f["statement_failures"].values() for x in v]]
    repaired = False
    if fl:
        prev = json.dumps({"targets": [res.get(f["target"]) or {"target": f["target"], "statements": [], "not_rules": []} for f in fl]})
        rp = RM.replace("{{FAILURES}}", json.dumps(fl, indent=0)).replace("{{PREVIOUS}}", prev) + "\n\n=== CONTEXT (the same batch and targets as before) ===\n" + p
        out2, rc2 = calls.claude("mrepair", call["id"], rp, timeout=2400, max_output_tokens=calls.WRITER_MAX_OUTPUT)
        repaired = True
        failed = {f["target"] for f in fl}
        # A repair answer replaces only a target that failed: one that passed keeps its first answer.
        for x in ((calls.parse_json(out2) or {}).get("targets", []) if rc2 == 0 else []):
            if isinstance(x, dict) and x.get("target") in failed:
                t = tby[x["target"]]
                keep, nrs, fails, tf = check_target(repo, x, t, call)
                tres[t["id"]] = dict(statements=keep, not_rules=nrs, fails=fails, tfails=tf)
    return call, tres, repaired, m_fail_causes


def extract_all(repo, S, C, workers=6):
    """Run every batch of ``C`` (``batches.plan_batches``) over scope ``S``: the proof's ``after_m.json`` shape."""
    t0 = time.time()
    v2lib.use_repo(repo)
    calls.check_distinct()
    tby = {t["id"]: t for t in S["targets"]}
    with cf.ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(lambda c: extract_call(repo, tby, c), C["calls"]))
    statements, notrules, tstate, mcauses = [], [], {}, []
    for call, tres, repaired, causes in results:
        mcauses += causes
        for tid in call["targets"]:
            t, r = tby[tid], tres[tid]
            tstate[tid] = dict(call=call["id"], unaccounted=bool(r["tfails"]), tfails=r["tfails"])
            # a confirmed statement kept beside the new ones keeps its id (run.plan_reuse): new ids skip it
            # (by its base id: a repair names its statement <id>~r<k>, check.py, so a new <id> would repair onto it)
            taken = {str(c.get("id")).split("~", 1)[0] for c in t.get("confirmed") or []}
            free = (f"{tid}#{k}" for k in itertools.count() if f"{tid}#{k}" not in taken)
            for k, st in enumerate(r["statements"]):
                st.update(id=next(free), target=tid, call=call["id"], m_fail=r["fails"].get(k) or [], kind="rule", name=t.get("anchor_name"))
                cite_copybooks(st)
                st["status"] = "open" if st["m_fail"] else "pending"
                statements.append(st)
            for k, n in enumerate(r["not_rules"]):
                n.update(id=f"{tid}#nr{k}", target=tid, call=call["id"], status="refused" if n.get("refused") else "accepted")
                notrules.append(n)
    kinds = collections.Counter(re.match(r"(M\d'?)", e).group(1) if re.match(r"(M\d'?)", e) else "other" for e in mcauses)
    return dict(statements=statements, not_rules=notrules, targets=tstate, wall_s=round(time.time() - t0, 1),
                m_repair_calls=sum(1 for r in results if r[2]), m_fail_causes_first_pass=dict(kinds))
