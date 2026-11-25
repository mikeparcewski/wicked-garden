"""J6 v3 stage R, the reachability confirm (DES-j6-build §2; DES-j6-v3 §2): one fresh codex call per group of COBOL
SCOPE flags that sees what C6 never sees (ENTRY, PATH and WRITERS from ``cobol_ctx``), and the fail-closed gate
(``cobol_flow``) that decides whether a rejection may clear a flag.

Ported from the J6 v3 proof (``proof-v3/cal/r_stage.py``): ``flagged_claims``, ``names_for``, ``shown_lines``,
``run_calls`` and ``decide`` unchanged; the prompt and facts are read from ``prompts/`` (byte-identical to the
proof's ``SHA256SUMS``); the calibration harness (bundles, J4 / probe / CardDemo units) stays in the proof.
"""
import json, sys, os, re, concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import cobol_ctx as cx  # noqa: E402
from domain import cobol_flow as g  # noqa: E402
from domain import model_calls as calls  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "prompts", "confirm_R.txt")) as _fh:
    T = _fh.read()
with open(os.path.join(HERE, "prompts", "facts_cobol_R.txt")) as _fh:
    FACTS = _fh.read().strip()
FLAG = ("OVERREACH", "WRONG")


def flagged_claims(r):
    return [c for c in (r or {}).get("claims", []) if (c.get("verdict") or "").upper() in FLAG]


def names_for(f, item, finds):
    cl = {c["i"]: c for c in item["claims"]}
    txt = []
    for fd in finds:
        txt += [fd.get("witness") or "", fd.get("reason") or ""]
        c = cl.get(fd.get("i")) or {}
        txt.append(c.get("text") or "")
        for k in (c.get("when") or []) + (c.get("unless") or []):
            txt.append((cl.get(k) or {}).get("text") or "")
        L = cx.defs.flines(f)
        for m in re.finditer(r"(\d+)(?:\s*-\s*(\d+))?", fd.get("evidence") or ""):
            a, b = int(m.group(1)), int(m.group(2) or m.group(1))
            if 0 < a <= len(L) and b - a < 40:
                txt += [cx.code(L[i - 1]) for i in range(a, min(b, len(L)) + 1)]
    out = cx.data_names(" ".join(txt), f)
    return out[:12]


def shown_lines(code):
    return {int(m.group(1)) for m in re.finditer(r"^(\d+): ", code, re.M)}


def run_calls(step, units, per=4, workers=4):
    """units: list of dict(n, item, finds, code, file, anchor_line). Returns {n: [decisions]}."""
    groups = [units[i:i + per] for i in range(0, len(units), per)]

    def one(k):
        us = groups[k]
        items, codes, seen = [], [], {}
        for u in us:
            items.append(json.dumps(dict(n=u["n"], routine=u["item"].get("routine") or "", claims=u["item"]["claims"],
                                         findings=[{x: fd.get(x) for x in ("i", "verdict", "case", "evidence", "reason", "witness")} for fd in u["finds"]])))
            u["names"] = names_for(u["file"], u["item"], u["finds"])
            ctx = cx.render(u["file"], u["anchor_line"], u["names"])
            u["ctx_chars"] = len(ctx)
            u["shown"] = shown_lines(u["code"]) | shown_lines(ctx)
            if u["code"] in seen:
                codes.append(f"===== code for n={u['n']}: the same code as n={seen[u['code']]} above =====\n===== reachability for n={u['n']} =====\n{ctx}")
            else:
                seen[u["code"]] = u["n"]
                codes.append(f"===== code for n={u['n']} (as the first checker saw it) =====\n{u['code']}\n===== reachability for n={u['n']} =====\n{ctx}")
        p = T.replace("{{FACTS}}", FACTS).replace("{{ITEMS}}", "\n".join(items)).replace("{{CODE}}", "\n\n".join(codes))
        out, rc = calls.codex(step, f"r{k}", p)
        j = calls.parse_json(out) or {}
        return {str(r.get("n")): r.get("findings") or [] for r in j.get("results", []) if isinstance(r, dict)}

    res = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, range(len(groups))):
            res.update(r)
    return res


def decide(u, decs):
    """per flagged claim: stands unless REJECTED with >= 1 cited line number that is in the shown code."""
    by = {d.get("i"): d for d in decs if isinstance(d, dict)}
    out = []
    for fd in u["finds"]:
        d = by.get(fd.get("i")) or {}
        dec = (d.get("decision") or "").upper()
        nums = [int(x) for x in re.findall(r"(?<![\w.])(\d{1,5})(?![\w.])", re.sub(r"^[^:]*:", "", d.get("lines") or "") + " " + " ".join(re.findall(r":([\d\-, ]+)", d.get("lines") or "")))]
        cited_ok = any(x in u["shown"] for x in nums)
        # coord delta check F1-F4: a rejection rests on ENTRY / PATH / WRITERS. It counts only when cobol_flow PROVES
        # the program uses no unmodelled control-flow form and every line that complete context needs was shown.
        ok, why, need = g.required_lines(u["file"], u["anchor_line"], u.get("names") or [])
        missing = sorted(need - u["shown"]) if ok else []
        ctx_ok = ok and not missing
        ctx_why = why or (f"{len(missing)} needed line(s) not shown, e.g. {missing[:5]}" if missing else "")
        # MISREAD and STATED rest on the claim table and the cited lines, not on the reachability map; every other
        # basis (UNREACHABLE, blank, unknown) needs the complete map
        basis = (d.get("basis") or "").upper()
        # coord delta2 G3: a MISREAD / STATED clear bypasses the map only when every cited line is in the code C6 saw
        code_only = bool(nums) and all(x in shown_lines(u["code"]) for x in nums)
        # coord delta2 C-G1: no UNREACHABLE clear may rest on a platform-written name no writer list covers
        spec = g.special_names(" ".join([d.get("reason") or "", fd.get("witness") or "", fd.get("reason") or ""]))
        if spec and ctx_ok:
            ctx_ok, ctx_why = False, f"depends on platform-written {spec[:3]}"
        rejected = dec == "REJECTED" and cited_ok and (ctx_ok or (basis in ("MISREAD", "STATED") and code_only))
        out.append(dict(i=fd.get("i"), case=fd.get("case") or fd.get("verdict"), decision=dec or "NONE", basis=d.get("basis"),
                        lines=d.get("lines"), cited_ok=cited_ok, ctx_ok=ctx_ok, ctx_why=ctx_why, stands=not rejected, reason=(d.get("reason") or "")[:300]))
    return out
