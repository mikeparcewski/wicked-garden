"""J6 v3 follow-up list (DES-j6-build §7): what the run could not settle, as actions for the user. 0 model calls.

Sources, all from the run record: a statement still flagged after its repair (or whose repair failed the M checks),
an open statement (UNVERIFIABLE after the fetch round), a statement's concern the checker did not refute (garden#1548), an M7 refusal (a ``not_rule`` over a decision) or an
unaccounted target, and the scope's unmatched phrases. Each row says where (file and lines), what is unknown, and
what to check, made concrete for COBOL with the PERFORM / GO TO sites of the paragraph (``cobol_flow.callers``).
Rows sort by kind: flagged, open, refused, scope. The user's actions on a row (Confirm, Reject with a note) are
stored by ``store.py``.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import cobol_ctx as cx  # noqa: E402
from domain import cobol_flow as g  # noqa: E402
from domain import lookup  # noqa: E402

ORDER = {"flagged": 0, "open": 1, "refused": 2, "scope": 3}
FLAG = ("OVERREACH", "WRONG")
MAX_SITES = 12


def _claim(st, i):
    return next((c for c in st.get("claims") or [] if c.get("i") == i), {})


def sites(f, line):
    """The PERFORM / GO TO lines that reach the COBOL paragraph holding ``line`` ([] when not COBOL or none)."""
    if not f.lower().endswith((".cbl", ".cob")):
        return []
    ps = cx.paragraphs(f)
    k = next((k for k, (_, a, b) in enumerate(ps) if a <= line <= b), None)
    return [] if k is None else g.callers(f, k)


def _where(f, a, b):
    return dict(file=f, lines=[a, b])


def _sentence(text):
    """``text`` stripped and ending as a sentence (a checker's reason or a repair error carries no full stop)."""
    t = (text or "").strip()
    return t if not t or t[-1] in ".!?" else t + "."


def _check_with_sites(text, f, line):
    """What to check, one thing per sentence: ``text``, then the PERFORM / GO TO sites that reach the paragraph."""
    text = _sentence(text)
    s = sites(f, line)
    if not s:
        return text
    shown = ", ".join(f"{os.path.basename(f)}:{x}" for x in s[:MAX_SITES])
    more = f", and {len(s) - MAX_SITES} more" if len(s) > MAX_SITES else ""
    reached = f"Reached from {len(s)} site{'s' if len(s) != 1 else ''}: {shown}{more}."
    return f"{text} {reached}" if text else reached


def _anchor(st):
    """(file, first, last) of a statement's anchor; ("", 0, 0) when the model left it unusable."""
    a = st.get("anchor") if isinstance(st.get("anchor"), dict) else {}
    ln = a.get("lines")
    ok = isinstance(a.get("file"), str) and isinstance(ln, list) and len(ln) == 2 and all(isinstance(x, int) for x in ln)
    return (a["file"], ln[0], ln[1]) if ok else ("", 0, 0)


def statement_rows(statements):
    """One or more rows for every open statement: its standing finding, each UNVERIFIABLE claim, else why it is open
    (the mechanical checks it failed, or a check that returned no verdict). No open statement goes without a row."""
    rows = []
    for st in statements:
        if st.get("status") != "open":
            continue
        f, lo, hi = _anchor(st)
        before = len(rows)
        found = (st.get("check") or {}).get("claims") or []
        flagged = [c for c in found if (c.get("verdict") or "").upper() in FLAG]
        standing = {x["i"] for x in (st.get("r") or {}).get("claims") or [] if x.get("stands")}
        if st.get("status1") == "flagged":
            c = next((x for x in flagged if not standing or x.get("i") in standing), flagged[0] if flagged else {})
            repair = (st.get("repair") or {}).get("errors") or []
            what = (c.get("witness") or c.get("reason") or "").strip()
            check = f"Whether claim {c.get('i')} holds: \"{(_claim(st, c.get('i')).get('text') or '').strip()}\"."
            if repair:
                check += " " + _sentence("The automatic repair failed its checks: " + "; ".join(repair[:3]))
            rows.append(dict(kind="flagged", where=_where(f, lo, hi), statement=st["id"], target=st.get("target"),
                             case=c.get("case"), both_passes=bool(c.get("both")), unknown=what,
                             check=_check_with_sites(check, f, lo), sites=sites(f, lo)))
            continue
        for c in found:
            if (c.get("verdict") or "").upper() != "UNVERIFIABLE":
                continue
            cl = _claim(st, c.get("i"))
            unknown = (f"claim {c.get('i')} ({cl.get('type')}) \"{(cl.get('text') or '').strip()}\" could not be confirmed "
                       f"from the excerpt; the checker needs: {(c.get('need') or '').strip() or 'more of the code'}")
            rows.append(dict(kind="open", where=_where(f, lo, hi), statement=st["id"], target=st.get("target"), claim=c.get("i"),
                             unknown=unknown, check=_check_with_sites((c.get("reason") or "").strip(), f, lo), sites=sites(f, lo)))
        if len(rows) == before:
            fails = st.get("m_fail") or (st.get("repair") or {}).get("errors") or []
            unknown = ("the statement failed its mechanical checks: " + "; ".join(fails[:3]) if fails else
                       "the checker returned no verdict on every claim (its call failed or its answer was incomplete)")
            rows.append(dict(kind="open", where=_where(f, lo, hi) if f else None, statement=st["id"], target=st.get("target"),
                             unknown=unknown, check="Run the extraction again, or confirm the statement against its cited lines.",
                             sites=sites(f, lo) if f else []))
    return rows


def concern_rows(statements):
    """garden#1548: one ``flagged`` row per concern of a live statement (a branch that cannot run, an amount counted
    twice, a stub), unless both checker passes refuted it. The row names no statement: the statement states the code
    literally and may be Checked, and only an open statement takes a ruling, so the row is for reading, not ruling."""
    rows = []
    for st in statements:
        if st.get("status") not in ("Checked", "open"):
            continue
        f, lo, hi = _anchor(st)
        name = st.get("name") or (st.get("anchor") or {}).get("symbol_id") or "this routine"
        cs = st.get("concerns") if isinstance(st.get("concerns"), list) else []
        for k, c in enumerate(cs):
            # only a concern the checker judged: one on a statement the M checks refused was never asked
            if not isinstance(c, dict) or c.get("checked") not in ("SUPPORTED", "UNVERIFIABLE") \
                    or not isinstance(c.get("text"), str) or not c["text"].strip():
                continue
            p = next((q for q in (lookup.pref(r) for r in (c.get("lines") if isinstance(c.get("lines"), list) else [])) if q), None)
            cf, ca, cb = p if p else (f, lo, hi)
            unknown = f"In {name}: {_sentence(c['text'])}"
            if c.get("checked") != "SUPPORTED":
                unknown += " The checker could not confirm this from the code it was shown."
            rows.append(dict(kind="flagged", where=_where(cf, ca, cb) if cf else None, statement=None, target=st.get("target"),
                             concern_of=st.get("id"), concern=k, unknown=unknown,
                             check=_check_with_sites("Read the cited lines and confirm this; the rule states the code as written.", cf, ca)
                             if cf else "Read the statement's code and confirm this.", sites=sites(cf, ca) if cf else []))
    return rows


def refusal_rows(after_m_targets, not_rules, S):
    """An unaccounted target: its M7 refusals and unaccounted lines, once per target."""
    tby = {t["id"]: t for t in S.get("targets") or []}
    rows = []
    for tid, t in after_m_targets.items():
        if not t.get("unaccounted"):
            continue
        tgt = tby.get(tid) or {}
        f, (lo, hi) = tgt.get("file") or "", tgt.get("lines") or [0, 0]
        rows.append(dict(kind="refused", where=_where(f, lo, hi), target=tid, unknown="not extracted: " + "; ".join(t.get("tfails") or []),
                         check=_check_with_sites("State the decision in these lines as a rule, or confirm these lines make no business decision.", f, lo),
                         sites=sites(f, lo)))
    return rows


def scope_rows(S):
    return ([dict(kind="scope", where=None, unknown=f"'{p}' matches no code",
                  check="Type a file, function or screen name, or drop the phrase.") for p in S.get("unmatched_phrases") or []]
            + [dict(kind="scope", where=None, unknown=f"'{p}' names more than one program file",
                    check="Type the file to extract.") for p in S.get("ambiguous_phrases") or []])


def followups(repo, S, result):
    """The run's follow-up rows from the checker's result (``check.check_all``) and the scope."""
    lookup.use_repo(repo)
    rows = statement_rows(result["statements"]) + concern_rows(result["statements"]) + refusal_rows(result["targets"], result["not_rules"], S) + scope_rows(S)
    rows.sort(key=lambda r: (ORDER[r["kind"]], (r["where"] or {}).get("file") or "", ((r["where"] or {}).get("lines") or [0])[0]))
    for n, r in enumerate(rows, 1):
        r["n"] = n
    return rows
