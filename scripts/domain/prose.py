"""J6 v3 business prose (DES-j6-build §5-§6): rule groups written by Claude Code from the run's Checked statements
only, checked mechanically (0 calls) and by Codex against the statements they cite, one repair, then shown or
withheld.

The writer never sees the code: its input is the Checked rule statements as the frozen renderer writes them
(``render.py``), numbered ``S1..`` in file order. Each group has a title, one RULE sentence (plain words, no code
names) and 0-4 DETAIL sentences, every sentence citing the statements it rests on. Then:

- mechanical checks: shape; every cite exists; every Checked statement is cited; no code span in a RULE (M5);
  every identifier and literal token of a backtick span in a DETAIL appears in a cited statement (M4, token level);
- the prose check (Codex, at most 40 sentences per call): SUPPORTED / OVERREACH (SCOPE, QUANTIFIER, VALUE,
  INVENTED) / WRONG; a sentence that says more than its statements is an overreach;
- one Claude Code repair for every sentence that failed either, with its objection; the repairs are checked the same
  way once more; a sentence that still fails is withheld with its reason.

The prompts are the calibrated ones (``prose-cal``: ``prose_v2`` as ``prose.txt``, check v2, repair). The writer
takes at most :data:`PER_WRITE` statements per call, whole files at a time; the calibration's runs (72 and 68
statements) were one call each. Prose never counts toward coverage, and it is never a target.
"""
import collections
import concurrent.futures as cf
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import model_calls as calls  # noqa: E402
from domain.render import render  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PER_WRITE = 80
PER_CHECK = 40


def _prompt(name):
    with open(os.path.join(HERE, "prompts", name)) as fh:
        return fh.read()


WRITE, CHECK, REPAIR = _prompt("prose.txt"), _prompt("prose_check.txt"), _prompt("prose_repair.txt")


def rows_of(statements):
    """The writer's input: the Checked rule statements, rendered, numbered ``S1..`` by file and first line."""
    ck = [s for s in statements if s.get("status") == "Checked" and s.get("kind") == "rule"]
    ck.sort(key=lambda s: (s["anchor"]["file"], s["anchor"]["lines"][0], s["id"]))
    rows = []
    for k, s in enumerate(ck, 1):
        a = s["anchor"]
        rows.append(dict(sid=f"S{k}", id=s["id"], file=a["file"], lines=a["lines"], text=render(s, s.get("name")),
                         anchor=f"{a['file']}:{a['lines'][0]}-{a['lines'][1]}"))
    return rows


def packs(rows):
    """Writer calls: whole files, at most :data:`PER_WRITE` statements each (one file over the cap is its own call)."""
    by_file = collections.OrderedDict()
    for r in rows:
        by_file.setdefault(r["file"], []).append(r)
    out, cur = [], []
    for rs in by_file.values():
        if cur and len(cur) + len(rs) > PER_WRITE:
            out.append(cur)
            cur = []
        cur += rs
    if cur:
        out.append(cur)
    return out


_TOKEN = re.compile(r"'[^']*'|\"[^\"]*\"|[\w$][\w$-]*(?:\.\d+)?")  # a COBOL name may start with digits


def _tokens(span):
    """The identifier and literal tokens of a code span (``isCouncilSize(v)`` -> ``isCouncilSize``, ``v``)."""
    return [t.rstrip("-") for t in _TOKEN.findall(span) if t.strip("'\"")]


def _has(blob, tok):
    if tok[:1] in "'\"":
        return tok in blob
    return re.search(rf"(?<![\w$-]){re.escape(tok)}(?![\w$-])", blob) is not None


def sentence_fails(s, layer, by):
    """The mechanical failures of one sentence against the statements it cites (M2, M5, M4 token rule)."""
    cites = s.get("cites") or []
    bad = [c for c in cites if c not in by]
    if not cites or bad:
        return [f"M2 cites {bad or 'none'}"]
    blob = "\n".join(by[c]["text"] for c in cites)
    spans = re.findall(r"`([^`]+)`", s.get("text") or "")
    if layer == "rule":
        return [f"M5 a RULE sentence has code: {', '.join(spans)}"] if spans else []
    return [f"M4 `{t}` is in no cited statement" for sp in spans for t in _tokens(sp) if not _has(blob, t)]


def mcheck(groups, rows):
    """Shape and M checks over every group (ids assigned here): ({sentence id: [failures]}, uncited sids)."""
    by = {r["sid"]: r for r in rows}
    fails, cited = {}, set()
    for g in groups:
        if not isinstance(g, dict) or g.get("kind") not in ("business", "housekeeping") or not isinstance(g.get("rule"), dict):
            fails[f"g{g.get('g') if isinstance(g, dict) else '?'}"] = ["M1 shape"]
            continue
        for tag, s in [("r", g["rule"])] + [(f"d{k}", d) for k, d in enumerate(g.get("details") or [], 1)]:
            s["id"], s["layer"] = f"g{g['g']}.{tag}", ("rule" if tag == "r" else "detail")
            cited.update(c for c in s.get("cites") or [] if c in by)
            f = sentence_fails(s, s["layer"], by)
            if f:
                fails[s["id"]] = f
    return fails, [r["sid"] for r in rows if r["sid"] not in cited]


def sentences(groups):
    return [dict(g=g["g"], title=g["title"], kind=g["kind"], **s) for g in groups if isinstance(g, dict) and isinstance(g.get("rule"), dict)
            for s in [g["rule"]] + [d for d in g.get("details") or [] if isinstance(d, dict)]]


def check(sents, by, step):
    """The prose check: at most :data:`PER_CHECK` sentences per Codex call. Returns {sentence id: verdict row}."""
    chunks = [sents[i:i + PER_CHECK] for i in range(0, len(sents), PER_CHECK)]

    def one(k):
        ch = chunks[k]
        need = sorted({c for s in ch for c in s["cites"] if c in by}, key=lambda x: int(x[1:]))
        p = CHECK.replace("{{SENTENCES}}", "\n".join(f"[{s['id']}] (cites {', '.join(s['cites'])}) {s['text']}" for s in ch))
        p = p.replace("{{STATEMENTS}}", "\n\n".join(f"[{c}]\n{by[c]['text']}" for c in need))
        out, rc = calls.codex(step, f"c{k}", p)
        return (calls.parse_json(out) or {}).get("verdicts") or []

    with cf.ThreadPoolExecutor(4) as ex:
        got = list(ex.map(one, range(len(chunks))))
    return {x["id"]: x for vs in got for x in vs if isinstance(x, dict) and x.get("id")}


def _objection(v, mf):
    if v and v.get("verdict") != "SUPPORTED":
        return f"{v.get('verdict')} {v.get('case', '')}: {v.get('reason', '')}"
    if not v:
        return "the checker returned no verdict"
    return "; ".join(mf)


def write_all(rows, desc):
    """One writer call per pack; group numbers run on across packs."""
    groups, gmax = [], 0
    for k, pk in enumerate(packs(rows)):
        body = "\n\n".join(f"[{r['sid']}]\n{r['text']}" for r in pk)
        out, rc = calls.claude("prose", f"w{k}", WRITE.replace("{{REPO_DESC}}", desc).replace("{{STATEMENTS}}", body), timeout=1500)
        if rc != 0:
            raise calls.CallFailed(f"the prose writer's call w{k} did not answer (exit {rc}); nothing was stored")
        got = [g for g in (calls.parse_json(out) or {}).get("groups") or [] if isinstance(g, dict)]
        nums = [g.get("g") for g in got]
        if not all(isinstance(n, int) for n in nums) or len(set(nums)) != len(nums):
            # numbered twice (or not at all): the host numbers them, so no two sentences share an id or a verdict
            for n, g in enumerate(got, 1):
                g["g"] = n
        for g in got:
            g["g"] = gmax + g["g"]
        gmax = max([gmax] + [g["g"] for g in got])
        groups += got
    return groups


def prose_all(statements, desc):
    """The run's rule groups: {rows, groups, uncited, counts}. Each sentence carries ``fate``: as written, repaired
    or withheld (then ``reason``); a group whose RULE is withheld has ``rule: None`` and lists it in ``withheld``."""
    rows = rows_of(statements)
    if not rows:
        return dict(rows=[], groups=[], uncited=[], counts={})
    by = {r["sid"]: r for r in rows}
    groups = write_all(rows, desc)
    mfail, uncited = mcheck(groups, rows)
    sents = sentences(groups)
    v1 = check(sents, by, "prose-check")
    bad = [s for s in sents if (v1.get(s["id"]) or {}).get("verdict") != "SUPPORTED" or s["id"] in mfail]
    fixed = {}
    if bad:
        need = sorted({c for s in bad for c in s["cites"] if c in by}, key=lambda x: int(x[1:]))
        body = "\n\n".join(f"[{s['id']}] layer={s['layer'].upper()} cites={','.join(s['cites'])}\nTEXT: {s['text']}\n"
                           f"OBJECTION: {_objection(v1.get(s['id']), mfail.get(s['id']) or [])}" for s in bad)
        p = REPAIR.replace("{{SENTENCES}}", body).replace("{{STATEMENTS}}", "\n\n".join(f"[{c}]\n{by[c]['text']}" for c in need))
        out, rc = calls.claude("prose-repair", "r0", p, timeout=1500)
        reps = {x["id"]: x for x in (calls.parse_json(out) or {}).get("repairs") or [] if isinstance(x, dict) and x.get("id")}
        todo = []
        for s in bad:
            r = reps.get(s["id"]) or {}
            t = (r.get("text") or "").strip()
            if not t or t == "WITHHOLD":
                fixed[s["id"]] = dict(withheld=True, reason=_objection(v1.get(s["id"]), mfail.get(s["id"]) or []))
                continue
            rs = dict(id=s["id"], layer=s["layer"], text=t, cites=[c for c in (r.get("cites") or s["cites"]) if c in by])
            mf = sentence_fails(rs, rs["layer"], by)
            if mf:
                fixed[s["id"]] = dict(withheld=True, reason="; ".join(mf))
                continue
            todo.append(rs)
        v2 = check(todo, by, "prose-recheck") if todo else {}
        for rs in todo:
            v = v2.get(rs["id"])
            fixed[rs["id"]] = (dict(withheld=False, text=rs["text"], cites=rs["cites"]) if (v or {}).get("verdict") == "SUPPORTED"
                               else dict(withheld=True, reason=_objection(v, [])))
    out_groups, fates = [], collections.Counter()
    for g in groups:
        if not isinstance(g.get("rule"), dict):
            continue
        og = dict(g=g["g"], title=g.get("title"), area=g.get("area"), kind=g["kind"], rule=None, details=[], withheld=[])
        for s in [g["rule"]] + [d for d in g.get("details") or [] if isinstance(d, dict)]:
            f = fixed.get(s["id"])
            if f and f["withheld"]:
                og["withheld"].append(dict(id=s["id"], layer=s["layer"], text=s["text"], reason=f["reason"]))
                fates["withheld"] += 1
                continue
            row = dict(id=s["id"], text=f["text"] if f else s["text"], cites=f["cites"] if f else s["cites"],
                       fate="repaired" if f else "as written")
            fates[row["fate"]] += 1
            if s["layer"] == "rule":
                og["rule"] = row
            else:
                og["details"].append(row)
        out_groups.append(og)
    return dict(rows=rows, groups=out_groups, uncited=uncited,
                counts=dict(groups=len(out_groups), sentences=len(sents), m_failed=len(mfail),
                            check_flagged=sum(1 for s in sents if (v1.get(s["id"]) or {}).get("verdict") != "SUPPORTED"), **fates))
