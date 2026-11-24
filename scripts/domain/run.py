#!/usr/bin/env python3
"""J6 v3 ``domain-run`` (DES-j6-build §1-§2): the one host step that turns a scope into the domain model on the estate
nodes. Scope, batches, extract (Claude Code), the two-pass check with its fetch rounds, the COBOL gate and R, the
repair and re-check (Codex), business prose, the follow-up list, then one write to the store. Every model call goes
through ``wicked-core model-call`` (``model_calls.py``).

Before any call the run takes what the store already holds (``store.py``): a target whose batch is unchanged is
carried with zero calls, one whose code moved but whose cited text is unchanged is re-validated, anything else is
extracted again; the prose is reused when its input is unchanged. An unchanged re-run therefore makes no model call
and writes the same model.

Usage: run.py --db <estate.db> --repo-root <tree> --scope <scope.json> [--out <dir>]
``scope.json`` is ``{"intent": "...", "phrases": [...]?, "scope_hash": "..."?, "description": "..."?}``. With a
``scope_hash`` (Start carries the preview's), a scope that no longer hashes the same is refused (exit 3).
Progress goes to stdout one line at a time; the run's summary is ``<out>/summary.json``.
Exit: 0 done, 2 the store write failed, 3 refused before any call.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import batches, check, extract, followups, prose, scope, store  # noqa: E402
from domain import graph as lib  # noqa: E402
from domain import model_calls as calls  # noqa: E402
from domain.render import render  # noqa: E402

STALE_SCOPE = "the code changed since the preview; review the scope again"
RESET = ("check", "r", "status1", "repair", "sentence")


class Refused(Exception):
    pass


def say(log, text):
    log(text)


def plan_reuse(repo, S, C, prior):
    """Per target of ``S``: carry / revalidate / extract (``store.decide``), and what each brings."""
    by_prior = store.prior_targets(prior)
    call_of = {tid: c for c in C["calls"] for tid in c["targets"]}
    carried, pending, not_rules, states, decision = [], [], [], {}, {}
    for t in S["targets"]:
        rec = by_prior.get((t["file"], store.window_sha(repo, t["file"], *t["lines"])))
        d, moves = store.decide(repo, rec) if rec else ("extract", {})
        sts = rec["_statements"] if rec else []
        if d == "revalidate":
            moved = [store.relocate(s, moves) for s in sts]
            if any(m is None for m in moved):
                d = "extract"
            else:
                for s in moved:
                    for k in RESET:
                        s.pop(k, None)
                    s.update(status="pending", m_fail=[], revalidated=True)
                sts = moved
        decision[t["id"]] = d
        if d == "extract":
            continue
        for s in sts:
            s.update(target=t["id"], call=call_of[t["id"]]["id"])
        (carried if d == "carry" else pending).extend(sts)
        not_rules.extend(dict(n, target=t["id"]) for n in rec.get("not_rules") or [])
        states[t["id"]] = dict(rec.get("state") or {}, call=call_of[t["id"]]["id"])
    return decision, carried, pending, not_rules, states


def extract_some(repo, S, C, tids):
    """``extract.extract_all`` on the targets in ``tids`` only; calls with none of them are not made."""
    cs = [dict(c, targets=[x for x in c["targets"] if x in tids]) for c in C["calls"]]
    cs = [c for c in cs if c["targets"]]
    if not cs:
        return dict(statements=[], not_rules=[], targets={}, m_repair_calls=0)
    return extract.extract_all(repo, S, dict(C, calls=cs))


def prose_for(statements, desc, prior):
    """The run's rule groups: the stored ones when the writer's input is unchanged, else ``prose.prose_all``."""
    rows = prose.rows_of(statements)
    rows_hash = store.sha(json.dumps([(r["sid"], r["id"], r["text"]) for r in rows]).encode())
    stored = [v for v in prior[store.GROUP].values() if v.get("rows_hash") == rows_hash]
    if rows and stored and len(stored) == len(prior[store.GROUP]):
        groups = sorted((v["group"] for v in stored), key=lambda g: g.get("g") or 0)
        return groups, rows_hash, True, {}
    if not rows:
        return [], rows_hash, False, {}
    res = prose.prose_all(statements, desc)
    sid = {r["sid"]: r["id"] for r in res["rows"]}
    for g in res["groups"]:
        for s in ([g["rule"]] if g.get("rule") else []) + g.get("details", []):
            s["cites"] = [sid[c] for c in s.get("cites") or [] if c in sid]
    return res["groups"], rows_hash, False, res.get("counts") or {}


def made_calls(calls_dir):
    p = os.path.join(calls_dir, "ledger.jsonl")
    if not os.path.exists(p):
        return 0
    with open(p) as fh:
        return sum(1 for ln in fh if ln.strip() and not json.loads(ln).get("note"))


def run(root, db, scope_in, out_dir, log=print, write=store.write):
    t0 = time.time()
    repo = lib.Repo(root, db)
    calls_dir = os.path.join(out_dir, "calls")
    calls.configure(calls_dir)
    calls.check_distinct()
    S = scope.build_scope(repo, scope_in["intent"], scope_in.get("phrases"))
    if scope_in.get("scope_hash") and scope_in["scope_hash"] != S["scope_hash"]:
        raise Refused(STALE_SCOPE)
    say(log, f"scope · {len(S['target_files'])} files · {len(S['targets'])} targets")
    C = batches.plan_batches(repo, S, os.path.join(out_dir, "batches"))
    prior = store.load_symbols(db, store.load(db))
    decision, carried, pending, nrs, states = plan_reuse(repo, S, C, prior)
    n = {d: sum(1 for v in decision.values() if v == d) for d in ("carry", "revalidate", "extract")}
    say(log, f"reuse · {n['carry']} carried · {n['revalidate']} re-validated · {n['extract']} to extract")
    A = extract_some(repo, S, C, {t for t, d in decision.items() if d == "extract"})
    for c in C["calls"]:
        if any(decision[t] == "extract" for t in c["targets"]):
            say(log, f"{c['id']} · read ✓")
    A["statements"] = carried + pending + A["statements"]
    A["not_rules"] = nrs + A["not_rules"]
    A["targets"] = dict(states, **A["targets"])
    if any(s["status"] == "pending" for s in A["statements"]):
        R = check.check_all(repo, S, C, A, os.path.join(out_dir, "check"))
    else:
        R = dict(statements=A["statements"], not_rules=A["not_rules"], targets=A["targets"])
    live = [s for s in R["statements"] if s.get("status") in ("Checked", "open")]
    for c in C["calls"]:
        mine = [s for s in live if s.get("target") in c["targets"]]
        ok = sum(1 for t in c["targets"] if not (R["targets"].get(t) or {}).get("unaccounted"))
        say(log, f"{c['id']} · checked {sum(s['status'] == 'Checked' for s in mine)}/{len(mine)} · "
                 f"{sum(s['status'] == 'open' for s in mine)} open · {ok}/{len(c['targets'])} targets accounted")
    desc = scope_in.get("description") or os.path.basename(os.path.abspath(root))
    groups, rows_hash, prose_reused, pcounts = prose_for(live, desc, prior)
    withheld = sum(len(g.get("withheld") or []) for g in groups)
    say(log, f"prose · {len(groups)} groups · {withheld} withheld" + (" · reused" if prose_reused else ""))
    fu = followups.followups(repo, S, R)
    spans = store._unit_spans(repo)
    call_of = {tid: c for c in C["calls"] for tid in c["targets"]}
    records = []
    for t in S["targets"]:
        sts = [s for s in live if s.get("target") == t["id"]]
        tn = [x for x in R["not_rules"] if x.get("target") == t["id"]]
        rec = store.target_record(repo, t, call_of[t["id"]], sts, tn, R["targets"].get(t["id"]) or {}, spans, S["targets"])
        rec["anchor_symbol"] = t.get("anchor_symbol")
        records.append(rec)
    rows, unplaced = store.rows_for(repo, dict(statements=live), records, groups, rows_hash, fu, prior,
                                    lambda s: render(s, s.get("name")))
    report = write(db, rows)
    accounted = sum(1 for t in S["targets"] if not (R["targets"].get(t["id"]) or {}).get("unaccounted"))
    summary = dict(targets=len(S["targets"]), accounted=accounted, checked=sum(s["status"] == "Checked" for s in live),
                   open=sum(s["status"] == "open" for s in live), groups=len(groups), withheld=withheld,
                   followups=len(fu), reuse=n, prose_reused=prose_reused, prose_counts=pcounts,
                   model_calls=made_calls(calls_dir), unplaced=unplaced, store=report, scope_hash=S["scope_hash"],
                   wall_s=round(time.time() - t0, 1))
    lib.jdump(summary, os.path.join(out_dir, "summary.json"))
    say(log, f"stored · {summary['checked']} checked statements · {len(fu)} follow-ups · {accounted} of "
             f"{len(S['targets'])} targets accounted · {summary['model_calls']} model calls")
    return summary, R, groups, fu


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--out", default=os.path.join(".wicked", "domain", "run"))
    a = ap.parse_args(argv)
    with open(a.scope) as fh:
        scope_in = json.load(fh)
    log = lambda s: print(s, flush=True)  # noqa: E731
    try:
        run(a.repo_root, a.db, scope_in, a.out, log=log)
    except Refused as e:
        print(f"domain-run: refused: {e}", file=sys.stderr)
        return 3
    except RuntimeError as e:
        if "write-batch" in str(e):
            print(f"domain-run: {e}", file=sys.stderr)
            return 2
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
