"""J6 v3 checker (DES-j6-build §2; DES-j6-v3 §1-§2, §6): TWO independent C6 passes (Codex), each with its own fetch
round; the union; then R (``r_stage``: SCOPE findings of COBOL statements, behind the fail-closed gate). A statement
still flagged after R gets ONE Claude Code repair with every flagged finding of both passes; the M checks run on the
repair; the re-check is two passes (no new fetch, plus the round-1 fetched text) + union + R -> Checked or open.

Ported from the J6 v3 proof: ``proof-v3/scripts/check3.py`` and the v2 functions it imports from
``proof-v3/scripts/check.py`` (``check_round``, ``fetch_spans``, ``merge``, ``status_of``'s helpers), unchanged in
their rules. The changes are the run's inputs and the language switch: the proof read its repository at import and
switched COBOL / TypeScript on the repository's name; the port takes the run's tree, scope, batches and after-M
result as arguments (:func:`check_all`) and switches on each statement's file (``lookup.lang_of``). C6 chunks are
built per language (one card's facts per prompt), which is the proof's chunking on a one-language repository.
"""
import collections
import concurrent.futures as cf
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import extract as X  # noqa: E402
from domain import graph as lib  # noqa: E402
from domain import lookup as v2lib  # noqa: E402
from domain import model_calls as calls  # noqa: E402
from domain import r_stage as RS  # noqa: E402
from domain import union as UN  # noqa: E402

T6 = X._text("prompts", "check_C6.txt")
RP = X._text("prompts", "repair.txt")
FLAG = ("OVERREACH", "WRONG")
W = int(os.environ.get("CW", "4"))


def facts(f):
    return v2lib.card_facts(None, f)


def is_cobol_program(f):
    """R runs on COBOL program statements (the proof's ``check3.is_cobol``)."""
    return f.lower().endswith((".cbl", ".cob"))


# garden#1548: concern k of a statement goes to the checker as claim ``concern_ids(st)[k]``, one question each, numbered
# above every claim id the statement has (so no claim shares one), and its verdicts are taken out of the claims' before
# the union (:func:`split_concerns`): a concern never changes a statement's status.
CONCERN_I = 1000


def concerns_of(st):
    cs = st.get("concerns")
    return [c for c in cs if isinstance(c, dict)] if isinstance(cs, list) else []


def concern_ids(st):
    ids = [c.get("i") for c in st.get("claims") or [] if isinstance(c, dict) and isinstance(c.get("i"), int)]
    base = max([CONCERN_I] + [i + 1 for i in ids])
    return [base + k for k in range(len(concerns_of(st)))]


def table(st):
    return ([{k: c.get(k) for k in ("i", "type", "text", "when", "unless", "lines") if k in c} for c in st["claims"]]
            + [{"i": i, "type": "concern", "text": c.get("text"), "lines": c.get("lines") or []}
               for i, c in zip(concern_ids(st), concerns_of(st))])


def split_concerns(res, sts):
    """Take each statement's concern verdicts out of one pass's result ``res`` ({id: result}, changed in place):
    returns {id: {concern index: verdict row}}. Only the ids :func:`concern_ids` gave the concerns are taken."""
    out = {}
    for s in sts:
        r = res.get(s["id"])
        cs = (r or {}).get("claims")
        if not isinstance(cs, list):
            continue
        ids = {i: k for k, i in enumerate(concern_ids(s))}
        out[s["id"]] = {ids[c["i"]]: c for c in cs if isinstance(c, dict) and c.get("i") in ids}
        r["claims"] = [c for c in cs if not (isinstance(c, dict) and c.get("i") in ids)]
    return out


def inherited_concerns(x, s):
    """A repaired statement's concerns: the flagged statement's, then any new one the repair gave (same text: once),
    unjudged and one copy per child, so judging one child never changes another's and a repair never drops one."""
    new = x.get("concerns") if isinstance(x.get("concerns"), list) else []
    out, seen = [], set()
    for c in json.loads(json.dumps(concerns_of(s) + [c for c in new if isinstance(c, dict)])):
        key = c.get("text") if isinstance(c.get("text"), str) else json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append({k: v for k, v in c.items() if k not in ("checked", "reason")})
    return out


def judge_concerns(s, ca, cb):
    """Each concern of ``s`` gets its two passes' verdict: WRONG when both flag it (it is dropped from the follow-ups),
    SUPPORTED when one supports it and neither flags it, else UNVERIFIABLE (shown, said as not confirmed). Its reason
    is the one a pass that gave that verdict wrote."""
    for k, c in enumerate(concerns_of(s)):
        vs = [x for x in ((ca or {}).get(k), (cb or {}).get(k)) if x]
        up = [(x.get("verdict") or "").upper() for x in vs]
        if len(up) == 2 and all(v in FLAG for v in up):
            c["checked"], why = "WRONG", vs
        elif "SUPPORTED" in up and not any(v in FLAG for v in up):
            c["checked"], why = "SUPPORTED", [x for x, v in zip(vs, up) if v == "SUPPORTED"]
        else:
            c["checked"], why = "UNVERIFIABLE", vs
        c["reason"] = next(((x.get("reason") or "").strip() for x in why if (x.get("reason") or "").strip()), "")


def item(n, st):
    return {"n": n, "routine": "%s:%d-%d" % (st["anchor"]["file"], *st["anchor"]["lines"]), "claims": table(st)}


def verdicts(r):
    return [(c.get("verdict") or "").upper() for c in (r or {}).get("claims", [])]


def check_round(repo, step, sts, extra_of=None, chunk=10, shown=None):
    """One C6 round over ``sts``: chunks of ``chunk`` statements in file order, per language. Returns {id: result}.
    ``shown`` (when given) gains, per statement, every file its chunk's prompt showed: a verdict may rest on any of them."""
    order = sorted(sts, key=lambda s: (s["anchor"]["file"], s["anchor"]["lines"][0], s["id"]))
    chunks = []
    for cob in (True, False):
        mine = [s for s in order if X.is_cobol(s["anchor"]["file"]) == cob]
        chunks += [mine[i:i + chunk] for i in range(0, len(mine), chunk)]

    def run(k):
        ss = chunks[k]
        w = collections.defaultdict(set)
        for j, s in enumerate(ss, 1):
            for f, v in v2lib.want(repo, s, (extra_of or {}).get(s["id"])).items():
                w[f] |= v
        items = "\n".join(json.dumps(item(j, s)) for j, s in enumerate(ss, 1))
        code = facts(ss[0]["anchor"]["file"]) + "\n" + v2lib.render_code(repo, w)
        out, rc = calls.codex(step, f"c{k}", T6.replace("{{ITEMS}}", items).replace("{{CODE}}", code))
        j = calls.parse_json(out) or {}
        byn = {r.get("n"): r for r in j.get("results", []) if isinstance(r, dict)}
        return ({s["id"]: byn.get(n) for n, s in enumerate(ss, 1)}, set(w)), out, rc

    # a pass in which not one call answered is sent once more, then stops the run (calls.checker_pass); a call that
    # fails among answered ones leaves its statements open (a follow-up each), checked again on the next run
    res = {}
    for (r, files), _ in calls.checker_pass(step, len(chunks), run, W):
        res.update(r)
        if shown is not None:
            for sid in r:
                shown.setdefault(sid, set()).update(files)
    return res


def fetch_spans(repo, st, r):
    f = st["anchor"]["file"]
    cob = X.is_cobol(f)
    names, spans = set(), []
    for c in (r or {}).get("claims", []):
        if (c.get("verdict") or "").upper() != "UNVERIFIABLE":
            continue
        txt = (c.get("need") or "") + " " + (c.get("reason") or "")
        for m in re.finditer(r"([\w./-]+\.\w+):(\d+)(?:-(\d+))?", txt):
            p = v2lib.pref(m.group(0))
            if p and lib.flines(repo, p[0]):
                spans.append((p[0], p[1], min(p[2], p[1] + 59)))
        names |= set(v2lib.defs.COBID.findall(txt)) if cob else set(re.findall(r"[A-Za-z_$][\w$]{2,}", txt))
    got = []
    for nm in sorted(names):
        d = v2lib.define(repo, nm, f, cap=60)
        if not d and not cob and nm not in v2lib.TSKW:
            d = v2lib.ts_define_anywhere(repo, nm)
            d = (d[0], d[1], min(d[2], d[1] + 59)) if d else None
        if d:
            spans.append(d)
            got.append(nm)
    return spans, got


def merge(prior, new):
    """only UNVERIFIABLE claims of the prior result take the new verdict."""
    if not prior:
        return new
    r2 = {c.get("i"): c for c in (new or {}).get("claims", [])}
    for c in prior.get("claims", []):
        if (c.get("verdict") or "").upper() == "UNVERIFIABLE" and c.get("i") in r2:
            c.update({k: r2[c["i"]].get(k) for k in ("verdict", "case", "evidence", "reason", "need", "witness")}, fetched=True)
    return prior


def one_pass(repo, tag, sts, extra_of=None, fetch=True, shown=None):
    """one C6 pass (+ its own fetch round when fetch). Returns ({id: result}, {id: fetched spans}, {id: names})."""
    r1 = check_round(repo, tag, sts, extra_of=extra_of, shown=shown)
    ext, flog = {}, {}
    if fetch:
        todo = [s for s in sts if any(v == "UNVERIFIABLE" for v in verdicts(r1.get(s["id"])))]
        for s in todo:
            # DES-j6-v3 §4 lookup at the anchor (TypeScript); COBOL resolves on the floor
            v2lib.set_at(None if X.is_cobol(s["anchor"]["file"]) else s["anchor"]["lines"][0])
            sp, got = fetch_spans(repo, s, r1.get(s["id"]))
            ext[s["id"]], flog[s["id"]] = sp, got
        v2lib.set_at(None)
        if todo:
            rf = check_round(repo, f"{tag}-fetch", todo, extra_of={k: (extra_of or {}).get(k, []) + v for k, v in ext.items()}, chunk=6,
                             shown=shown)
            for s in todo:
                r1[s["id"]] = merge(r1.get(s["id"]), rf.get(s["id"]))
    return r1, ext, flog


def union_of(out_dir, tag, sts, ra, rb):
    """``union.union`` on the two passes, keyed by a global n; the passes and the union are kept under out_dir."""
    num = {s["id"]: str(k) for k, s in enumerate(sts, 1)}
    pa = dict(raw={num[s["id"]]: ra.get(s["id"]) for s in sts if ra.get(s["id"])})
    pb = dict(raw={num[s["id"]]: rb.get(s["id"]) for s in sts if rb.get(s["id"])})
    # through JSON, as the proof's file-in, file-out union saw them (keys as strings, no shared objects)
    pa, pb = json.loads(json.dumps(pa)), json.loads(json.dumps(pb))
    U = UN.union(pa, pb)
    for x, rec in (("a", pa), ("b", pb), ("U", dict(passes=[f"{tag}_a.json", f"{tag}_b.json"], **U))):
        lib.jdump(rec, os.path.join(out_dir, f"{tag}_{x}.json"))
    return json.loads(json.dumps(U)), num


R_PER = 3  # statements per R prompt


def r_round(repo, tag, sts, U, num, extra_of, shown=None):
    """R on the union's flagged COBOL statements. Returns {id: row}. ``shown`` (when given) gains, per statement, every
    file its R prompt showed (a prompt packs :data:`R_PER` statements)."""
    us, keep, rfiles = [], {}, {}
    for s in sts:
        n = num[s["id"]]
        fs = RS.flagged_claims(U["raw"].get(n))
        if not fs:
            continue
        f = s["anchor"]["file"]
        if not is_cobol_program(f):
            keep[n] = fs  # R runs on COBOL only; these stand as found
            continue
        w = v2lib.want(repo, s, extra_of.get(s["id"]))
        code = facts(f) + "\n" + v2lib.render_code(repo, w)
        us.append(dict(n=int(n), item=item(int(n), s), finds=fs, code=code, file=f, anchor_line=s["anchor"]["lines"][0]))
        # the R prompt's reachability context reads the program's copybooks too
        rfiles[int(n)] = (s["id"], set(w) | {f} | set(v2lib.defs.copybooks(f)))
    for u in us:
        n = str(u["n"])
        keep[n] = [fd for fd in u["finds"] if (fd.get("case") or "").upper() != "SCOPE"]
        sc = collections.OrderedDict()
        for fd in u["finds"]:
            if (fd.get("case") or "").upper() == "SCOPE":
                sc.setdefault(fd.get("i"), []).append(fd)
        u["finds"] = [g[0] if len(g) == 1 else dict(g[0], witness=" | ".join(f"WITNESS {k + 1}: {x.get('witness') or ''}" for k, x in enumerate(g)),
                                                    evidence="; ".join(x.get("evidence") or "" for x in g),
                                                    reason=" | ".join(x.get("reason") or "" for x in g)) for g in sc.values()]
    sent = [u for u in us if u["finds"]]
    if shown is not None:
        for i in range(0, len(sent), R_PER):  # as run_calls packs them
            pack = [rfiles[u["n"]] for u in sent[i:i + R_PER]]
            files = set().union(*(fs for _, fs in pack))
            for sid, _ in pack:
                shown.setdefault(sid, set()).update(files)
    res = RS.run_calls(f"R-{tag}", sent, per=R_PER) if sent else {}
    rows = {}
    byn = {u["n"]: u for u in us}
    for s in sts:
        n = num[s["id"]]
        if n not in keep and int(n) not in byn:
            continue
        u = byn.get(int(n))
        d = RS.decide(u, res.get(n) or []) if u and u["finds"] else []
        d += [dict(i=fd.get("i"), case=fd.get("case") or fd.get("verdict"), decision="NOT-SENT", basis=None, lines=None, cited_ok=None,
                   stands=True, reason="non-SCOPE finding, or not COBOL: stands as found") for fd in keep.get(n, [])]
        rows[s["id"]] = dict(n=n, stands=any(x["stands"] for x in d), claims=d, no_result=bool(u and u["finds"]) and n not in res)
    return rows


def answered_all(r, s):
    """One pass's result names every claim of ``s``."""
    got = {c.get("i") for c in (r or {}).get("claims", [])}
    return bool(r) and all(c.get("i") in got for c in s["claims"])


def status3(s, U, num, rrow, both=True):
    """Checked / flagged / unverifiable / noresult from the union after R. ``both``: each of the two passes answered
    on every claim; a statement one pass did not answer is never Checked (it is noresult, checked again next run),
    though a finding the other pass made still stands."""
    r = U["raw"].get(num[s["id"]])
    if not r:
        return "noresult"
    by = collections.defaultdict(list)
    for c in r.get("claims", []):
        by[c.get("i")].append(c)
    if any(not by.get(c.get("i")) for c in s["claims"]):
        return "noresult"
    standing = {x["i"] for x in (rrow or {}).get("claims", []) if x["stands"]}
    if any(i in standing for i in by):
        return "flagged"
    vs = [(c.get("verdict") or "").upper() for i, cs in by.items() for c in cs if (c.get("verdict") or "").upper() not in FLAG]
    if any(v == "UNVERIFIABLE" for v in vs):
        return "unverifiable"
    return "Checked" if both and all(v == "SUPPORTED" for v in vs) else "noresult"


def check3(repo, out_dir, tag, sts, extra_of=None, fetch=True, shown=None):
    """Both passes, their union and R. ``shown`` (when given) gains the files each statement's checker prompts showed."""
    sa, sb = {}, {}
    with cf.ThreadPoolExecutor(2) as ex:
        fa = ex.submit(one_pass, repo, f"{tag}-a", sts, extra_of, fetch, sa)
        fb = ex.submit(one_pass, repo, f"{tag}-b", sts, extra_of, fetch, sb)
        (ra, ea, la), (rb, eb, lb) = fa.result(), fb.result()
    ca, cb = split_concerns(ra, sts), split_concerns(rb, sts)
    for s in sts:
        judge_concerns(s, ca.get(s["id"]), cb.get(s["id"]))
    ext = {s["id"]: (extra_of or {}).get(s["id"], []) + ea.get(s["id"], []) + eb.get(s["id"], []) for s in sts}
    if shown is not None:
        for s in sts:
            shown.setdefault(s["id"], set()).update(sa.get(s["id"], set()) | sb.get(s["id"], set()))
    U, num = union_of(out_dir, tag, sts, ra, rb)
    rr = r_round(repo, tag, sts, U, num, ext, shown=shown)
    st = {s["id"]: status3(s, U, num, rr.get(s["id"]), answered_all(ra.get(s["id"]), s) and answered_all(rb.get(s["id"]), s))
          for s in sts}
    return U, num, rr, st, ext, {s["id"]: sorted(set(la.get(s["id"], []) + lb.get(s["id"], []))) for s in sts}


def repair_one(repo, tby, call, sts):
    """One Claude Code repair for a batch's still-flagged statements, with every flagged finding of both passes."""
    its = []
    for s in sts:
        fnd = [{k: c.get(k) for k in ("i", "verdict", "case", "evidence", "reason", "witness", "from_pass")}
               for c in (s["check"] or {}).get("claims", []) if (c.get("verdict") or "").upper() in FLAG]
        its.append(dict(id=s["id"], target=s["target"], target_lines=tby[s["target"]]["lines"], anchor_symbol=tby[s["target"]]["anchor_symbol"],
                        statement={k: s[k] for k in ("anchor", "claims", "context") if k in s}, findings=fnd))
    with open(call["text_file"]) as fh:
        batch = fh.read()
    card = X.card_for(call, [tby[x] for x in call["targets"]])
    p = RP.replace("{{CARD}}", card).replace("{{BATCH}}", batch).replace("{{ITEMS}}", json.dumps(its, indent=0))
    out, rc = calls.claude("repair", call["id"], p, timeout=2400, max_output_tokens=calls.WRITER_MAX_OUTPUT)
    return calls.parse_json(out) or {}


def check_all(repo, S, C, A, out_dir):
    """Check the after-M result ``A`` (``extract.extract_all``): the proof's ``statements.json`` shape."""
    t0 = time.time()
    v2lib.use_repo(repo)
    os.makedirs(out_dir, exist_ok=True)
    timing = collections.OrderedDict()
    tby = {t["id"]: t for t in S["targets"]}
    callby = {c["id"]: c for c in C["calls"]}
    statements, notrules = A["statements"], A["not_rules"]
    pend = [s for s in statements if s["status"] == "pending"]
    shown = {}
    U, num, rr, st1, ext, flog = check3(repo, out_dir, "check", pend, shown=shown)
    for s in pend:
        s["check"] = U["raw"].get(num[s["id"]])
        s["r"] = rr.get(s["id"])
        s["status1"] = st1[s["id"]]
        s["fetched"] = flog[s["id"]]
        # every file the check showed (its chunks' code, the fetch rounds): store.py's batch hash covers them too, so a
        # change to any file a verdict may rest on re-checks the statement
        s["fetched_files"] = sorted({sp[0] for sp in ext.get(s["id"], [])} | shown.get(s["id"], set()))
    timing["check_s"] = round(time.time() - t0, 1)
    c1 = collections.Counter(st1.values())
    flagged_before_r = [s["id"] for s in pend if RS.flagged_claims(s["check"])]
    r_cleared = [s["id"] for s in pend if s["id"] in rr and not rr[s["id"]]["stands"]]
    t2 = time.time()
    flagged = collections.defaultdict(list)
    for s in pend:
        if s["status1"] == "flagged":
            flagged[s["call"]].append(s)
    new_sts = []
    with cf.ThreadPoolExecutor(6) as ex:
        done = list(ex.map(lambda kv: (kv[0], repair_one(repo, tby, callby[kv[0]], kv[1])), flagged.items()))
    for cid, j in done:
        got = {r.get("id"): r for r in j.get("repairs", []) if isinstance(r, dict)}
        for s in flagged[cid]:
            r = got.get(s["id"])
            t = tby[s["target"]]
            call = callby[cid]
            reps = [x for x in (r or {}).get("statements") or [] if isinstance(x, dict)]
            errs = [] if reps else ["repair returned no statement"]
            cov = set()
            for x in reps:
                if not isinstance(x.get("anchor"), dict):
                    x["anchor"] = {}
                x["anchor"]["symbol_id"] = x["anchor"].get("symbol_id") or t["anchor_symbol"]
                errs += X.check_statement(repo, x, t, call)
                if not X.is_rule(x, repo):
                    errs.append("kind: the repaired statement has no condition, else or value claim, and no record update")
                ln = x["anchor"].get("lines")
                if isinstance(ln, list) and len(ln) == 2 and all(isinstance(v, int) for v in ln):
                    cov.update(range(max(ln[0], t["lines"][0]), min(ln[1], t["lines"][1]) + 1))  # bounded: model-made
            code = lib.code_lines(repo, t["file"])
            a, b = s["anchor"]["lines"]
            lost = sorted(i for i in range(a, b + 1) if i in code and i not in cov)
            if reps and lost:
                errs.append(f"M7 the repair no longer covers anchor lines {lost[:8]}")
            s["repair"] = dict(errors=errs, n_statements=len(reps))
            if errs:
                s["status"] = "open"
                continue
            s["status"] = "replaced"
            for k, x in enumerate(reps):
                new_sts.append(X.cite_copybooks(dict(anchor=x["anchor"], claims=x["claims"], context=x.get("context") or [],
                                    concerns=inherited_concerns(x, s), id=f"{s['id']}~r{k}", target=s["target"],
                                    call=cid, kind="rule", name=s.get("name"), m_fail=[], status="pending", repaired_from=s["id"],
                                    fetched=s.get("fetched"), fetched_files=s.get("fetched_files"))))
    timing["repair_s"] = round(time.time() - t2, 1)
    t3 = time.time()
    if new_sts:
        shown2 = {}
        U2, num2, rr2, st2, _, _ = check3(repo, out_dir, "recheck", new_sts,
                                          extra_of={x["id"]: ext.get(x["repaired_from"], []) for x in new_sts}, fetch=False,
                                          shown=shown2)
        for x in new_sts:
            x["fetched_files"] = sorted(set(x.get("fetched_files") or []) | shown2.get(x["id"], set()))
            x["check"] = U2["raw"].get(num2[x["id"]])
            x["r"] = rr2.get(x["id"])
            x["status1"] = st2[x["id"]]
            x["status"] = "Checked" if st2[x["id"]] == "Checked" else "open"
    timing["recheck_s"] = round(time.time() - t3, 1)
    for s in pend:
        if s["status"] == "pending":
            s["status"] = "Checked" if s["status1"] == "Checked" else "open"
    statements += new_sts
    for s in statements:
        s["sentence"] = None
    conv = collections.Counter()
    for s in pend:
        if s["status1"] == "flagged":
            kids = [x for x in new_sts if x["repaired_from"] == s["id"]]
            conv["flagged"] += 1
            conv["repaired_all_checked"] += bool(kids) and all(x["status"] == "Checked" for x in kids)
            conv["repair_failed_m"] += s["status"] == "open"
    r_rows = [dict(id=s["id"], claims=[(c["i"], c["case"], c["decision"], c["basis"], c.get("ctx_ok"), c["stands"]) for c in s["r"]["claims"]],
                   final=s["status"]) for s in pend if s.get("r")]
    return dict(statements=statements, not_rules=notrules, targets=A["targets"], timing=timing, wall_s=round(time.time() - t0, 1),
                after_first_check=dict(c1), repair_conversion=dict(conv), flagged_before_r=flagged_before_r, r_cleared=r_cleared,
                r_cleared_checked=[i for i in r_cleared if next(s for s in pend if s["id"] == i)["status"] == "Checked"], r_rows=r_rows)
