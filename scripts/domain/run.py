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
``--out`` defaults to a new ``.wicked/domain/runs/<UTC time>-<random>`` per run (a re-run in the same directory reuses its
completed calls, so a retry of one run costs nothing; a new run never collides with an earlier run's evidence).
``scope.json`` is ``{"intent": "...", "phrases": [...]?, "scope_hash": "..."?, "description": "..."?}``, checked by
``read_scope`` (anything else is refused, exit 3); the shipped step passes the file core wrote
(``WICKED_DOMAIN_SCOPE``). With a ``scope_hash`` (Start carries the preview's), a scope that no longer hashes the
same is refused (exit 3).
Progress goes to stdout one line at a time; the run's summary is ``<out>/summary.json``.
Exit: 0 done, 2 the store write failed, 3 refused before any call, 4 a writer call did not answer (nothing stored).
"""
import argparse
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path
from domain import batches, check, extract, followups, prose, scope, store  # noqa: E402
from domain import graph as lib  # noqa: E402
from domain import model_calls as calls  # noqa: E402
from domain.render import render  # noqa: E402

STALE_SCOPE = "the code changed since the preview; review the scope again"
EMPTY_SCOPE = "nothing in the code matches the scope: name a program, file or function"
RESET = ("check", "r", "status1", "repair", "sentence")


class Refused(Exception):
    pass


SCOPE_KEYS = {"intent", "phrases", "scope_hash", "description"}
SCOPE_MAX_BYTES = 64 * 1024


def read_scope(path):
    """The scope Start carries (core C1 writes it to the step's private channel directory and passes its path as
    ``WICKED_DOMAIN_SCOPE``), checked before anything runs: a JSON object of the known keys only, ``intent`` a non-empty
    string, ``phrases`` a list of non-empty strings, ``scope_hash`` and ``description`` strings. Anything else is
    refused by name (exit 3), never guessed at."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(SCOPE_MAX_BYTES + 1)
    except OSError as e:
        raise Refused(f"the scope could not be read: {e}")
    if len(raw) > SCOPE_MAX_BYTES:
        raise Refused(f"the scope is over {SCOPE_MAX_BYTES} bytes")
    def unique(pairs):
        keys = [k for k, _ in pairs]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:
            raise ValueError(f"a key appears twice: {', '.join(twice)}")
        return dict(pairs)

    def no_constant(name):
        raise ValueError(f"{name} is not JSON")

    try:
        sc = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=no_constant)
        # a lone surrogate (an escaped "\ud800") decodes, then fails the first time it is written out
        json.dumps(sc, ensure_ascii=False).encode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError, RecursionError) as e:
        raise Refused(f"the scope is not JSON: {type(e).__name__}: {e}")
    if not isinstance(sc, dict):
        raise Refused("the scope is not a JSON object")
    extra = sorted(set(sc) - SCOPE_KEYS)
    if extra:
        raise Refused(f"the scope has unknown keys: {', '.join(extra)}")
    if not isinstance(sc.get("intent"), str) or not sc["intent"].strip():
        raise Refused("the scope has no intent (a non-empty string)")
    # a key that is present is checked whatever its value: `null` is not an absent key
    ph = sc.get("phrases")
    if "phrases" in sc and (not isinstance(ph, list) or not all(isinstance(p, str) and p.strip() for p in ph)):
        raise Refused("the scope's phrases are not a list of non-empty strings")
    for k in ("scope_hash", "description"):
        if k in sc and not isinstance(sc[k], str):
            raise Refused(f"the scope's {k} is not a string")
    return sc


def say(log, text):
    log(text)


def _settled(s):
    """A prior statement that can stand unchanged: Checked, or open on a verdict (flagged or UNVERIFIABLE). One open
    on a failed or incomplete check (``noresult``) is checked again; one that failed the M checks is extracted again."""
    return s.get("status") == "Checked" or s.get("status1") in ("flagged", "unverifiable")


def _move_not_rule(n, moves):
    r, ok = store._move_ref(n.get("lines") or "", moves)
    return dict(n, lines=r) if ok else None


def rulings(prior, rec, sts, d):
    """What a person ruled on this prior target that still applies (DES-C2 §8): only on unchanged code (``carry``), and
    a statement ruling only on the statement it was made on (``store.live_ruling``). Returns the ids of the open
    statements they confirmed (each carried as it stands, never checked again), the rejected ones with their text and
    note (the target is extracted again), and whether they confirmed an unaccounted target's lines."""
    if not rec or d != "carry":
        return set(), [], False
    th, confirmed, rejected = rec.get("target_hash"), set(), []
    for s in sts:
        if s.get("status") != "open":
            continue  # only an open statement takes a ruling
        r = store.live_ruling(prior, "statement", s.get("id"), th, s)
        if r and r["action"] == "confirm":
            confirmed.add(s["id"])
        elif r:
            text = ((prior.get(store.RULE) or {}).get(s["id"]) or {}).get("statement")
            rejected.append(dict(statement=text, note=r.get("note") or ""))
    tr = store.live_ruling(prior, "target", rec.get("target"), th)
    unaccounted = bool((rec.get("state") or {}).get("unaccounted"))
    return confirmed, rejected, bool(tr and tr["action"] == "confirm" and unaccounted)


def plan_reuse(repo, S, C, prior):
    """Per target of ``S``: carry / revalidate / extract (``store.decide``), and what each brings."""
    by_prior = store.prior_targets(prior)
    call_of = {tid: c for c in C["calls"] for tid in c["targets"]}
    carried, pending, not_rules, states, decision, used = [], [], [], {}, {}, set()
    ids = {t["id"] for t in S["targets"]}
    for t in S["targets"]:
        rec = store.match_prior(by_prior, t, store.window_sha(repo, t["file"], *t["lines"]), used, ids)
        d, moves = store.decide(repo, rec) if rec else ("extract", {})
        sts = rec["_statements"] if rec else []
        nrs = list(rec.get("not_rules") or []) if rec else []
        confirmed, rejected, target_confirmed = rulings(prior, rec, sts, d)
        if any((s.get("m_fail") or s.get("status1") is None and s.get("status") == "open") and s.get("id") not in confirmed
               for s in sts):
            d = "extract"  # a statement that failed the M checks is never sent to the checker as it stood
        if rec and (rec.get("state") or {}).get("unaccounted") and not sts and not nrs and not target_confirmed:
            # the writer gave the target no answer at all: asked again. One it answered with a refused not-rule stands
            # on unchanged code (0 calls), with its follow-up for the user to settle; so does one a person confirmed.
            d = "extract"
        if rejected:
            d = "extract"  # a person said a statement is wrong: the writer states the lines again, with their note
            t["rejected"] = rejected
        if d == "carry" and not all(_settled(s) or s.get("id") in confirmed for s in sts):
            d, moves = "revalidate", None  # same code: no move; the unsettled ones are checked again
        if d == "revalidate":
            moved = sts if moves is None else [store.relocate(s, moves) for s in sts]
            nmoved = nrs if moves is None else [_move_not_rule(n, moves) for n in nrs]
            if any(m is None for m in moved + nmoved):
                d = "extract"
            else:
                for s in moved:
                    if moves is None and (_settled(s) or s.get("id") in confirmed):
                        continue
                    for k in RESET:
                        s.pop(k, None)
                    s.update(status="pending", m_fail=[], revalidated=True)
                sts, nrs = moved, nmoved
        decision[t["id"]] = d
        if d == "extract":
            continue
        used.add(rec["target"])
        if rec["target"] != t["id"]:
            # the same code under a new target id: its statements take ids of this target, so no id is shared with
            # one a target of this run extracts
            sts = [dict(s, id=f"{t['id']}#{k}", was=s.get("id")) for k, s in enumerate(sts)]
            nrs = [dict(n, id=f"{t['id']}#nr{k}") for k, n in enumerate(nrs)]
        for s in sts:
            s.update(target=t["id"], call=call_of[t["id"]]["id"])
        carried.extend(s for s in sts if s.get("status") != "pending")
        pending.extend(s for s in sts if s.get("status") == "pending")
        not_rules.extend(dict(n, target=t["id"]) for n in nrs)
        states[t["id"]] = dict(rec.get("state") or {}, call=call_of[t["id"]]["id"])
    return decision, carried, pending, not_rules, states


def extract_some(repo, S, C, tids):
    """``extract.extract_all`` on the targets in ``tids`` only; calls with none of them are not made."""
    cs = [dict(c, targets=[x for x in c["targets"] if x in tids]) for c in C["calls"]]
    cs = [c for c in cs if c["targets"]]
    if not cs:
        return dict(statements=[], not_rules=[], targets={}, m_repair_calls=0)
    return extract.extract_all(repo, S, dict(C, calls=cs))


def prose_for(statements, desc, desc_key, prior):
    """The run's rule groups (DES §5): a stored group is reused, with 0 calls, while every statement it rests on reads
    the same and the run's description is the same (``desc_key``: the scope's own, never the checkout's folder name);
    the statements no reused group rests on are written again (``prose.prose_all``). Returns (groups, meta, reused
    whole, counts, uncited): ``meta`` is what the store keeps to decide the next run's reuse."""
    rows = prose.rows_of(statements)
    text_of = {r["id"]: store.sha(r["text"].encode()) for r in rows}
    meta = dict(text_of=text_of, desc=desc_key)
    if not rows:
        return [], meta, False, {}, []
    reused, covered, left_out = [], set(), set()
    for v in prior[store.GROUP].values():
        if not isinstance(v, dict) or v.get("desc") != desc_key:
            continue
        inp = v.get("inputs") or {}
        if inp and all(text_of.get(i) == h for i, h in inp.items()):
            reused.append(v["group"])
            covered |= set(inp)
        unc = v.get("uncited")
        left_out |= {i for i, h in (unc if isinstance(unc, dict) else {}).items() if text_of.get(i) == h}
    todo = {i for i in text_of if i not in covered and i not in left_out}
    reused.sort(key=lambda g: g.get("g") or 0)
    if not todo:
        return reused, meta, True, {}, sorted(left_out)
    res = prose.prose_all([s for s in statements if s.get("id") in todo], desc,
                          start=max([0] + [g.get("g") or 0 for g in reused]))
    sid = {r["sid"]: r["id"] for r in res["rows"]}
    for g in res["groups"]:
        for x in ([g["rule"]] if g.get("rule") else []) + g.get("details", []) + g.get("withheld", []):
            x["cites"] = [sid[c] for c in x.get("cites") or [] if c in sid]
    uncited = sorted(left_out | {sid[c] for c in res.get("uncited") or [] if c in sid})
    return sorted(reused + res["groups"], key=lambda g: g.get("g") or 0), meta, False, res.get("counts") or {}, uncited


def made_calls(calls_dir):
    """The calls this run sent to a seat (answered or not); a reused completed call is not one."""
    p = os.path.join(calls_dir, "ledger.jsonl")
    if not os.path.exists(p):
        return 0
    with open(p) as fh:
        return sum(1 for ln in fh if ln.strip() and not str(json.loads(ln).get("note") or "").startswith("cache hit"))


def run(root, db, scope_in, out_dir, log=print, write=store.write):
    t0 = time.time()
    repo = lib.Repo(root, db)
    calls_dir = os.path.join(out_dir, "calls")
    calls.configure(calls_dir)
    calls.check_distinct()
    S = scope.build_scope(repo, scope_in["intent"], scope_in.get("phrases"))
    if scope_in.get("scope_hash") and scope_in["scope_hash"] != S["scope_hash"]:
        raise Refused(STALE_SCOPE)
    if not S["targets"]:
        raise Refused(EMPTY_SCOPE + "".join(f"; {q}" for q in S.get("questions") or []))
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
    groups, pmeta, prose_reused, pcounts, uncited = prose_for(live, desc, scope_in.get("description") or "", prior)
    withheld = sum(len(g.get("withheld") or []) for g in groups)
    say(log, f"prose · {len(groups)} groups · {withheld} withheld" + (f" · {len(uncited)} statements in no group" if uncited else "")
        + (" · reused" if prose_reused else ""))
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
    rows, unplaced = store.rows_for(repo, dict(statements=live), records, groups, pmeta, fu, prior,
                                    lambda s: render(s, s.get("name")), uncited=uncited)
    run_id = os.environ.get("WICKED_RUN_ID") or os.path.basename(os.path.normpath(out_dir))
    own = store.run_row(repo, records, scope_in, S["scope_hash"], run_id, int(time.time()))
    report = write(db, rows + ([own] if own else []))
    accounted = sum(1 for t in S["targets"] if not (R["targets"].get(t["id"]) or {}).get("unaccounted"))
    summary = dict(targets=len(S["targets"]), accounted=accounted, checked=sum(s["status"] == "Checked" for s in live),
                   open=sum(s["status"] == "open" for s in live), groups=len(groups), withheld=withheld,
                   followups=len(fu), reuse=n, prose_reused=prose_reused, prose_counts=pcounts, uncited=uncited,
                   model_calls=made_calls(calls_dir), unplaced=unplaced, store=report, scope_hash=S["scope_hash"],
                   wall_s=round(time.time() - t0, 1))
    lib.jdump(summary, os.path.join(out_dir, "summary.json"))
    say(log, f"stored · {summary['checked']} checked statements · {len(fu)} follow-ups · {accounted} of "
             f"{len(S['targets'])} targets accounted · {summary['model_calls']} model calls"
        + (f" · {len(unplaced)} not stored (no estate node for their file)" if unplaced else ""))
    return summary, R, groups, fu


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = os.path.join(".wicked", "domain", "runs",
                             time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
    log = lambda s: print(s, flush=True)  # noqa: E731
    try:
        scope_in = read_scope(a.scope)
        run(a.repo_root, a.db, scope_in, a.out, log=log)
    except Refused as e:
        print(f"domain-run: refused: {e}", file=sys.stderr)
        return 3
    except calls.CallFailed as e:
        print(f"domain-run: {e}", file=sys.stderr)
        return 4
    except RuntimeError as e:
        if "write-batch" in str(e):
            print(f"domain-run: {e}", file=sys.stderr)
            return 2
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
