"""J6 v3 stage 1 union (DES-j6-build §2; DES-j6-v3 §1): TWO independent C6 passes (each with its own fetch round); a
claim is flagged when EITHER pass flags it, and every flagged finding of both passes is kept. The union's flagged
claims then go to R once (COBOL).

Ported from the J6 v3 proof (``proof-v3/cal/union.py``, sha256 4e69ad64...): the same rules, as a function
(:func:`union`); the proof's file-in, file-out script is :func:`main`.
Usage: union.py <out.json> <pass-a.json> <pass-b.json>
"""
import json
import sys

FLAG = ("OVERREACH", "WRONG")


def _flagged(r):
    return {n for n, v in r.items() if any((c.get("verdict") or "").upper() in FLAG for c in v.get("claims", []))}


def union(a, b):
    """``a`` and ``b`` are the two passes (``{"raw": {n: {"claims": [...]}}}``); returns the union record."""
    ra, rb = a["raw"], b["raw"]
    raw = {}
    for n in sorted(set(ra) | set(rb), key=lambda x: int(x) if str(x).isdigit() else 0):
        ca = {c.get("i"): c for c in (ra.get(n) or {}).get("claims", [])}
        cb = {c.get("i"): c for c in (rb.get(n) or {}).get("claims", [])}
        claims = []
        for i in sorted(set(ca) | set(cb), key=lambda x: (x is None, x)):
            x, y = ca.get(i), cb.get(i)
            fx = x and (x.get("verdict") or "").upper() in FLAG
            fy = y and (y.get("verdict") or "").upper() in FLAG
            if fx or fy:
                # keep EVERY flagged finding of both passes (codex-check r1: keeping one dropped pass B's objection)
                for z, tag in ((x, "a"), (y, "b")):
                    if z and (z.get("verdict") or "").upper() in FLAG:
                        claims.append(dict(z, from_pass=tag, both=bool(fx and fy)))
            else:
                # no flag: SUPPORTED from either pass wins over the other's UNVERIFIABLE (DES §1 rule 2; codex-check r2)
                pick = next((z for z in (x, y) if z and (z.get("verdict") or "").upper() == "SUPPORTED"), x or y)
                claims.append(dict(pick, from_pass="a" if pick is x else "b", both=False))
        raw[n] = {"n": n, "claims": claims}
    return dict(flagged_a=sorted(_flagged(ra), key=str), flagged_b=sorted(_flagged(rb), key=str),
                flagged_union=sorted(_flagged(raw), key=str), raw=raw)


def main(argv):
    out, pa, pb = argv
    with open(pa) as fa, open(pb) as fb:
        u = union(json.load(fa), json.load(fb))
    with open(out, "w") as fh:
        json.dump(dict(passes=[pa, pb], **u), fh, indent=1)
    print(len(u["flagged_a"]), len(u["flagged_b"]), len(u["flagged_union"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
