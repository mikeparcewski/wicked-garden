"""Frozen renderer (DES-j6-v2 §2 S4, §3 claim contract v2): the model never writes prose. Claims render in execution
order (by first cited line); each effect / else / value sits under its OWN `when` / `unless`, never under another
claim's. A condition no effect refers to renders as a plain "Tests:" line, so nothing the table states is dropped. The
statement's ``context`` (the definitions it relies on, with their lines) renders as one "Uses:" row under "Runs:"."""
import os
import re


def _first(c):
    for r in c.get("lines") or []:
        m = re.match(r"^\s*([^\s:]+):(\d+)", r or "")
        if m:
            return (m.group(1), int(m.group(2)))
    return ("~", 10 ** 9)


def _cite(c, anchor_file):
    out = []
    for r in c.get("lines") or []:
        m = re.match(r"^\s*([^\s:]+):(\d+(?:\s*-\s*\d+)?)\s*$", r or "")
        if not m:
            continue
        f, ln = m.group(1), m.group(2).replace(" ", "")
        out.append(ln if f == anchor_file else f"{os.path.basename(f)}:{ln}")
    return ", ".join(out)


def _txt(c):
    return (c.get("text") or "").strip().rstrip(".")


def render(st, name=None):
    a = st.get("anchor") or {}
    f = a.get("file") or ""
    ln = a.get("lines") or [0, 0]
    claims = [c for c in st.get("claims") or [] if isinstance(c, dict)]
    by_i = {c.get("i", k): c for k, c in enumerate(claims)}
    order = sorted(claims, key=_first)
    used = set()
    for c in claims:
        used.update(c.get("when") or [])
        used.update(c.get("unless") or [])
    rows = [f"Runs: {name or a.get('symbol_id') or '?'} ({f}:{ln[0]}-{ln[1]})"]
    # the definitions the statement relies on (its ``context``: a copybook field's line, garden#1548), so the text a
    # person reads names the copybook it uses, not only its cited lines (garden#1604)
    uses = []
    for x in st.get("context") if isinstance(st.get("context"), list) else []:
        if isinstance(x, dict) and isinstance(x.get("symbol"), str) and isinstance(x.get("at"), str) and x["at"].strip():
            u = f"`{x['symbol'].strip()}` ({x['at'].strip()})"
            if u not in uses:
                uses.append(u)
    if uses:
        rows.append("- Uses: " + ", ".join(uses))
    for c in order:
        t = c.get("type")
        cite = _cite(c, f)
        if t == "trigger":
            rows.append(f"- Triggered by: {_txt(c)} [{cite}]")
            continue
        if t == "condition":
            if c.get("i") not in used:
                rows.append(f"- Tests: {_txt(c)} [{cite}]")
            continue
        w = [_txt(by_i[k]) for k in c.get("when") or [] if k in by_i]
        u = [_txt(by_i[k]) for k in c.get("unless") or [] if k in by_i]
        head = []
        if w:
            head.append("When " + " and ".join(w))
        if u:
            head.append(("unless " if w else "Unless ") + " or ".join(u))
        guard = ", ".join(head) if head else "Always"
        if t == "value":
            of = by_i.get(c.get("of")) if c.get("of") is not None else None
            lead = f"Value (of: {_txt(of)})" if of else "Value"
            rows.append(f"- {lead}{'' if guard == 'Always' else ' — ' + guard}: {_txt(c)} [{cite}]")
        else:
            rows.append(f"- {guard}: {_txt(c)} [{cite}]")
    return "\n".join(rows)
