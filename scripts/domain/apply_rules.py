#!/usr/bin/env python3
"""apply_rules.py — HOST step `extract-apply` of domain-extraction (wicked-garden#1362).

The seat container's extract step stated its rules into the RULES file in the run's worktree
(`wicked-garden/domain-rules@1`, `rules_file.py`); it cannot write the store. This step, on the
daemon host, is the only writer, and it trusts nothing the seat could have touched:

  * the file must be inside the schema: a document outside it (wrong tag, unknown key, a bad
    seat name, too many entries, not JSON, a symlink) is refused whole and nothing is written;
    an entry outside it is refused and listed;
  * every entry must name a behaviour the store has and that `wicked-core coverage`, run here,
    reports unmapped or as a risk-flagged placeholder (not a real requirement yet), or a mapped
    behaviour this run's generation record (host-side) lists as changed since the map was built
    (wicked-garden#1425) or as framed by this run itself (a rework of a page it already applied),
    in a file `git ls-files` tracks in the registered repository — anything else is refused and
    listed; an empty statement never overwrites a placeholder's statement (the floor only fills
    blanks), and either kind of mapped behaviour is only ever restated by a rule that resolves
    (anything less keeps its rule: a real requirement is never degraded by a page);
  * what passes is judged and written exactly as the extraction harness writes its own model's
    rules (`extract_loop.decide_and_write`: the rule validator, confidence >= 0.75 to
    resolve, the RISK floor, a read-back per write), authored
    `extract-loop` — the seat a file names is the seat's own claim, so it is only reported;
  * a rule about a unit whose source the host cannot read (re-read here from the store, never
    taken from the worklist), or about a test or data file, is written unconfirmed, never
    validated;
  * binaries come from the operator and the engine (env, config, PATH), never the worktree, and
    every read and write in the worktree is descriptor-relative and refuses symlinks.

Then it writes `coverage-report.json` (checked against the configured minimum) into the
worktree, where the coverage step reads it; that step's own validator recomputes it from the
store regardless. A report of what was applied and refused goes to
`.wicked/domain/apply-report.json`.

Usage (the preset's command, run from the run's worktree):
    wicked-garden run scripts/domain/apply_rules.py --db <store> --repo-root <repo> \
        [--rules .wicked/domain/rules.json] [--coverage-out coverage-report.json]

Exit 0 when the file was applied (refused entries are listed, not fatal), or when there was
nothing to extract: the run's host-side generation record shows this pass's `extract-prepare`
framed an empty page (e2e-1105 F42: a re-map of a map that is already current finishes with "map
already current at <commit>; nothing to extract", and applies no rules file). 1 when the file is
missing for a page that framed units (or with no page in flight), refused, or a write fails.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import (_clients, _rule_extractor, business_domains, extract_loop, generation,  # noqa: E402
                    refresh, rules_file)

REPORT_REL = ".wicked/domain/apply-report.json"
# Who wrote what this step applies: the harness, on the host. Not `extract-loop:<seat>` — that
# would take a seat's identity from the seat's own file.
AUTHOR = "extract-loop"
COVERAGE_REL = "coverage-report.json"


class AppliedThenFailed(RuntimeError):
    """A failure AFTER the store changed: said as such, never as "nothing written"."""


# What coverage counts as accounting for a symbol besides its requirement (wicked-governance
# domain_model.rs: business_rule, risk, and estate's advisory types assumption / question).
_ACCOUNTING_TYPES = ("business_rule", "risk", "assumption", "question")


def _accounting(db: str, symbol_ids: list[str]) -> dict[str, tuple[str, int, int, str]]:
    """For each symbol, what accounts for it in the store right now: its requirement text, whether
    it is validated (a placeholder another writer promoted keeps its text, codex on #1375) and
    the accounting annotations (business_rule, risk, assumption, question — coverage counts any)
    it carries, by count and content. One fresh read-only connection; {} when the store cannot say (older schema)."""
    import sqlite3
    from urllib.parse import quote
    out: dict[str, tuple[str, int, int, str]] = {}
    try:
        con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
        try:
            marks = ",".join("?" * len(_ACCOUNTING_TYPES))
            for sym in symbol_ids:
                try:
                    row = con.execute("SELECT s.sid, n.requirement, n.requirement_validated FROM "
                                      "symbols s LEFT JOIN nodes n ON n.symbol = s.sid "
                                      "WHERE s.sym = ?", (sym,)).fetchone()
                except sqlite3.OperationalError:  # a store before the validated column
                    row = con.execute("SELECT s.sid, n.requirement, 0 FROM symbols s LEFT JOIN "
                                      "nodes n ON n.symbol = s.sid WHERE s.sym = ?",
                                      (sym,)).fetchone()
                if row is None:
                    continue
                # The annotations' contents too, not only their count (codex r2 on #1375): a
                # business_rule replaced at a higher confidence promotes a placeholder in place.
                anns = sorted(con.execute(f"SELECT * FROM annotations WHERE node_sym = ? AND "
                                          f"type IN ({marks})",
                                          (row[0], *_ACCOUNTING_TYPES)).fetchall(), key=repr)
                out[sym] = ((row[1] or ""), int(row[2] or 0), len(anns), repr(anns))
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    return out


def _annotation_read_back(db: str):
    """A read-back for the host's writes: does the symbol carry the annotation `key` now? One
    query over a fresh read-only connection per check (the estate CLI wrote it in its own
    process), instead of a third CLI process per rule."""
    import sqlite3
    from urllib.parse import quote

    try:  # a store without estate's tables (an injected test client) reads back as before
        con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if not {"annotations", "symbols"} <= tables:
        return None

    def check(symbol_id: str, key: str, value: str | None = None) -> bool:
        try:
            con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
            try:
                row = con.execute("SELECT 1 FROM annotations a JOIN symbols s ON "
                                  "s.sid = a.node_sym WHERE s.sym = ? AND a.key = ? "
                                  "AND (? IS NULL OR a.value = ?) LIMIT 1",
                                  (symbol_id, key, value, value)).fetchone()
            finally:
                con.close()
        except sqlite3.Error as e:  # a failed read-back is a failed write, said as one
            raise RuntimeError(f"read-back of {symbol_id} failed: {e}") from e
        return row is not None

    return check


def _record_answered(db: str, answered: list[str]) -> None:
    """Record which of the page's units this step wrote (or kept), in the run's generation
    record, so only those close with the page. Never fatal: without it the next step closes the
    units that are real requirements now, except a changed mapped unit, which stays open to be
    asked again (it was real before the page)."""
    run_id = (os.environ.get("WICKED_RUN_ID") or "").strip()
    if not run_id:  # an empty list is recorded too: "answered none" (Copilot on #1375)
        return
    try:
        generation.record_answered(db, run_id, answered)
    except (OSError, ValueError) as e:
        print(f"[extract-apply] the answered units could not be recorded ({e}); the next step "
              "closes the units that are real requirements now (a changed mapped unit stays open)",
              file=sys.stderr)


def _restatable(db: str, store) -> tuple[dict[str, dict], set[str]]:
    """The mapped behaviours a page of this run may restate, as coverage-style nodes read from the
    store, and which of them are changed since the map was built. They are:
      * those the run's generation record lists as changed since the map was built
        (`prepare_worklist.py` framed them, wicked-garden#1425);
      * those this run itself framed (`visited` or `pending`): a send-back that reworks a page this
        run already applied restates its own answer, e.g. a mismatch the review asked for
        (e2e-1105 minor: mean's inherited mismatch never reached the store because its unit was
        resolved by then and refused).
    The record is host-side, beside the store: a seat cannot add to it."""
    run_id = (os.environ.get("WICKED_RUN_ID") or "").strip()
    if not run_id or store is None:
        return {}, set()
    try:
        rec = generation.load(db, run_id)
    except (OSError, ValueError):
        return {}, set()
    changed = generation.changed(rec)
    own = generation.visited(rec) | set((rec or {}).get("pending") or [])
    out = {}
    for sid in changed | own:
        row = store.node_row.get(store.sid_of.get(sid))
        if row is not None:
            out[sid] = {"symbol_id": sid, "name": row[0] or "", "file": row[1] or "",
                        "kind": extract_loop.kind_of_row(row)}
    return out, changed


def _page_framed_nothing(db: str) -> bool:
    """Did this pass's `extract-prepare` frame an EMPTY page? Read from the run's generation record
    on the host (`generation.page_in_flight`), never from the seat-writable worklist: the seat can
    rewrite that file, but cannot write the record or make prepare frame fewer units. False outside
    a run, with no record, with no page in flight (a closed page reworked after `extract-next`), and
    for a page that framed any unit: a missing rules file is then the extract step's undone work."""
    run_id = (os.environ.get("WICKED_RUN_ID") or "").strip()
    if not run_id:
        return False
    try:
        return generation.page_in_flight(generation.load(db, run_id)) == []
    except (OSError, ValueError):
        return False


def _freshness(db: str) -> tuple[bool, str]:
    """(is the map current, what to say): current only when the store records both the commit
    the map was built from and the one it is indexed at now, and they are the same (codex r1: full
    coverage alone says nothing about whether the requirements match the code)."""
    try:
        built, at, why = refresh.build_and_base(db)
    except Exception as e:  # noqa: BLE001 - prepare already failed on an unreadable store
        return False, f"whether the map matches the code could not be read ({e!s:.200})"
    if built and at and built == at:
        return True, built[:12]
    if built and at:
        return False, (f"the code changed since the map was built ({built[:12]}..{at[:12]}) and "
                       "each changed behaviour was asked by an earlier page of this run or is not "
                       "product code")
    if built is None:
        return False, ("the store records no commit the map was built from, so whether it matches "
                       "the code could not be told")
    return False, f"{why}, so whether the map matches the code could not be told"


def _nothing_to_extract(db: str, base: Path, rules_rel: str, coverage_rel: str, core) -> dict:
    """This pass's prepare framed no units: write nothing to the store, whatever rules file the
    worktree holds (an earlier page's file left behind is not this page's answer, codex r1),
    publish the coverage and apply reports the later steps read, and say so in one honest line
    (e2e-1105 F42). "Already current" only when coverage shows nothing unmapped and no placeholder
    AND the map was built at the commit the store is indexed at."""
    rules_file.check_writable(base, coverage_rel)
    rules_file.check_writable(base, REPORT_REL)
    with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
        after, met, line = core.coverage_against_minimum(db, str(Path(tmp) / "coverage.json"))
    unmapped, held = int(after.get("unaccounted") or 0), int(after.get("risk_flagged") or 0)
    current = False
    if unmapped or held:
        what = (f"nothing to extract: this page framed no units ({unmapped} unmapped, {held} "
                "placeholder(s) left, each asked by an earlier page of this run or in a file the "
                "repository does not track)")
    else:
        current, said = _freshness(db)
        what = (f"map already current at {said}; nothing to extract (this page framed no units)"
                if current else
                f"nothing to extract: this page framed no units and every behaviour is a real "
                f"requirement, but {said}")
    ignored = os.path.lexists(base / rules_rel)
    if ignored:
        what += f"; the {rules_rel} left in the worktree was not applied"
    rules_file.write_json_file(base, coverage_rel, after)
    report = {
        "declared_seat": None,
        "author": AUTHOR,
        "entries": 0,
        "applied": {"resolved": 0, "risk": 0, "kept": 0},
        "eligible": 0,
        "changed_since_build": {"listed": 0, "restated": 0},
        "reworked": 0,
        "unsourced": 0,
        "not_product": 0,
        "refused": [],
        "refused_count": 0,
        "nothing_to_extract": True,
        "map_current": current,
        "rules_file_ignored": ignored,
        "line": what,
        "coverage": {k: after.get(k) for k in ("coverage", "behavior_bearing", "resolved",
                                                "risk_flagged", "unaccounted")},
        "minimum_met": met,
        "coverage_line": line,
    }
    rules_file.write_json_file(base, REPORT_REL, report)
    print(f"[extract-apply] {what}. {line or ''}".rstrip(), file=sys.stderr)
    return report


def _rule_keys(db: str, symbol_id: str) -> list[str]:
    try:
        return refresh.rule_keys(db, symbol_id)
    except Exception as e:  # noqa: BLE001 - a store that cannot say is a failed step, said so
        raise RuntimeError(f"the rules {symbol_id} holds could not be read: {e}") from e


def _restates(entry: dict, ids: set[str], why: str | None) -> bool:
    """Would this entry RESOLVE (a valid rule at the threshold, about product code whose source
    the host read)? A changed mapped behaviour is restated only then."""
    ok, _ = _rule_extractor.validate_rule(entry, ids)
    return ok and why is None and float(entry["confidence"]) >= extract_loop.RESOLVE_THRESHOLD


def _domain_plan(db: str, doc: dict, tracked: set[str], repo_root: str) -> dict:
    """What this page may write of its business domains (reqgraph Fix B), decided before any
    write: the catalog (the stored one, else the page's proposal when it is grounded in code the
    host can see), and the assignments that name a resolved requirement with no domain yet."""
    plan: dict = {"catalog": None, "store": False, "state": "none", "assign": [],
                  "refused": []}
    stored = business_domains.load_catalog(db)
    proposed = doc.get("business_domains")
    if stored:
        plan.update(catalog=stored, state="stored")
        if proposed is not None:
            plan["refused"].append({"index": None, "symbol_id": None,
                                    "why": "business_domains: the repository already has a "
                                           "catalog; a page picks from it, never replaces it"})
    elif proposed is not None:
        try:
            business_domains.check_catalog_shape(proposed,
                                                 business_domains.directory_names(tracked))
            business_domains.check_catalog_evidence(
                proposed, tracked, business_domains.symbol_lookup(db),
                business_domains.repo_reader(repo_root),
                lambda f: not business_domains.not_product(f))
            plan.update(catalog=proposed, store=True, state="proposed")
        except business_domains.CatalogRefused as e:
            # Refused whole: the page's rules still apply, without a domain; the next page asks
            # for a catalog again.
            plan["state"] = f"refused: {e}"
            plan["refused"].append({"index": None, "symbol_id": None,
                                    "why": f"business_domains refused: {e}"})
    ids = {d["id"] for d in plan["catalog"] or []}
    plan["ids"] = ids
    if ids and "assignments" in doc:
        try:
            ok, bad = business_domains.check_assignments(doc["assignments"], ids)
        except business_domains.CatalogRefused as e:
            ok, bad = [], [{"index": None, "symbol_id": None, "why": str(e)}]
        backfill, _ = business_domains.resolved_without_domain(
            db, tracked, extract_loop.RESOLVE_THRESHOLD, business_domains.not_product,
            limit=rules_file.MAX_RULES)
        open_ids = {r["symbol_id"] for r in backfill}
        # A unit the page states a rule for takes its domain from that rule (codex r1): never
        # from an assignment too, which would overwrite the rule's pick.
        stated = {e.get("symbol_id") for e in doc.get("rules") or [] if isinstance(e, dict)}
        plan["assign"] = [a for a in ok if a["symbol_id"] in open_ids
                          and a["symbol_id"] not in stated]
        bad += [{"index": None, "symbol_id": rules_file._shown(a["symbol_id"]),
                 "why": ("has a rule on this page, whose pick is its domain"
                         if a["symbol_id"] in stated else
                         "is not a resolved requirement in product code without a business domain")}
                for a in ok if a["symbol_id"] not in open_ids or a["symbol_id"] in stated]
        plan["refused"] += [{**b, "why": f"assignment {b['why']}"} for b in bad]
    return plan


def _write_domain(estate, by_id: dict, sid: str, did: str, conf: float, author: str) -> None:
    estate.annotate(sid, type=business_domains.ANN_TYPE, key=business_domains.ANN_KEY,
                    value=business_domains.annotation_value(by_id[did]), confidence=float(conf),
                    provenance=business_domains.PROVENANCE, replace=True, author=author)


def apply(db: str, repo_root: str, base: Path, rules_rel: str, coverage_rel: str, *,
          estate=None, core=None) -> dict:
    # Binaries from the operator and the engine only — never from the seat-writable worktree.
    core = core or _clients.host_core_client()
    estate = estate or _clients.host_estate_client(db)
    if _page_framed_nothing(db):
        # The host's record says this pass's prepare framed nothing: there is nothing to apply,
        # with or without a file. A page with units, a closed page or no record goes on below, where
        # a missing file is refused: an extract step that skipped its work fails closed.
        return _nothing_to_extract(db, base, rules_rel, coverage_rel, core)
    try:
        doc = rules_file.read_json_file(base, rules_rel)
    except FileNotFoundError:
        raise rules_file.RulesFileRefused(
            f"the extract step left no rules file at {rules_rel}") from None
    seat, accepted, refused = rules_file.check_rules_doc(doc)
    # Where the outputs go is checked BEFORE anything is written: a symlink, a non-directory on
    # the way or a directory at the leaf (the worktree is seat-writable) is refused now, not after
    # the store has changed. The writes themselves go through descriptors (rules_file).
    rules_file.check_writable(base, coverage_rel)
    rules_file.check_writable(base, REPORT_REL)

    # What accounts for each named symbol BEFORE the coverage snapshot: if that has changed at
    # write time (a requirement or an accounting annotation), someone else mapped it meanwhile.
    before_state = _accounting(db, [e["symbol_id"] for e in accepted])
    try:
        store = extract_loop._DirectStore(db)
        store.repo_root = repo_root  # sources as prepare read them (the checkout, blob-checked)
    except Exception as e:
        print(f"[extract-apply] direct store unavailable ({e}); every rule is written "
              "unconfirmed (no source can be read)", file=sys.stderr)
        store = None
    with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
        before = core.coverage(db, str(Path(tmp) / "coverage.json"))
    # Not real requirements yet: the unmapped behaviours and the risk-flagged placeholders a page
    # may revisit (wicked-core#1233). A resolved behaviour is rewritten from a page only when this
    # run framed it or found it changed, and only by a rule that resolves (`_restatable`).
    held = {n["symbol_id"] for n in _clients.placeholder_nodes(before)
            if isinstance(n.get("symbol_id"), str)}
    unmapped = {n["symbol_id"]: n for n in [*_clients.unaccounted_nodes(before),
                                            *_clients.placeholder_nodes(before)]
                if isinstance(n, dict) and isinstance(n.get("symbol_id"), str)}
    # Mapped behaviours whose code changed since the map was built: restated, never degraded.
    restatable, changed_ids = _restatable(db, store)
    restate = {sid: n for sid, n in restatable.items() if sid not in unmapped}
    nodes = {**restate, **unmapped}
    tracked = rules_file.tracked_files(repo_root)
    domains = _domain_plan(db, doc, tracked, repo_root)
    domain_by_id = {d["id"]: d for d in domains["catalog"] or []}
    picks: list[tuple[str, str, float]] = []

    eligible: list[dict] = []
    for entry in accepted:
        sid = entry["symbol_id"]
        node = nodes.get(sid)
        if node is None:
            why = ("is not an unmapped behaviour or a placeholder in the store, nor a mapped one "
                   "this run framed or found changed since the map was built")
        elif node.get("file") not in tracked:
            why = f"its file {node.get('file')!r} is not tracked in the repository"
        else:
            eligible.append(entry)
            continue
        refused.append({"index": None, "symbol_id": rules_file._shown(sid), "why": why})

    # The seat's own confidence decides (extract_loop.decide_and_write): communities frame a unit
    # on the worklist, never its verdict, so this step reads none.
    nc: dict[str, str] = {}
    sizes: dict[str, int] = {}

    # The host writes these, so the host is the author: the seat named in the file is the seat's
    # own claim (a seat-written file proves nothing about who wrote it) and is only reported.
    author = AUTHOR
    # The estate CLI writes into `db`, so its writes read back from `db` directly; any other
    # client (an injected one) reads back through itself.
    read_back = (_annotation_read_back(db) if isinstance(estate, _clients.CliEstateClient)
                 else None)
    ids = {e["symbol_id"] for e in eligible}
    outcomes = {"resolved": 0, "risk": 0, "kept": 0}
    restated = 0  # changed mapped behaviours restated (counted in "resolved" too)
    reworked = 0  # this run's own earlier answers restated on a rework (counted in "resolved" too)
    # Valid rules written unconfirmed, by why: no source read on the host, or not product code.
    unconfirmed = {extract_loop.NO_SOURCE_REASON: 0, extract_loop.NOT_PRODUCT_REASON: 0}
    in_progress = None  # the symbol whose writes have started and not finished
    answered: list[str] = []  # the page's units written (or kept): closed with the page
    try:
        for entry in eligible:
            sid = entry["symbol_id"]
            now = _accounting(db, [sid])
            if sid in before_state and sid in now and now[sid] != before_state[sid]:
                # Another writer mapped it after the coverage snapshot: theirs stands. (This narrows
                # the window to one read before the write; the store has no conditional write.)
                refused.append({"index": None, "symbol_id": rules_file._shown(sid),
                                "why": "was mapped by another writer while this step ran"})
                continue
            if sid in held and not (entry.get("statement") or "").strip():
                # An empty answer adds nothing to a placeholder and must never replace what it
                # holds (codex on #1375: without a readable store the floor guard cannot see it).
                outcomes["kept"] += 1
                answered.append(sid)
                continue
            # The source is re-read here, on the host: a rule about a unit whose code cannot be
            # read is unconfirmed whatever the seat (or its worklist file) says (#1370).
            # Tests and data files are never validated either: what they hold is evidence.
            sourced = store is not None and bool(store.source_slice(sid).strip())
            why = extract_loop.unconfirmed_reason(nodes[sid].get("file", ""), sourced,
                                                  str(nodes[sid].get("kind") or ""))
            if sid in restate and not _restates(entry, ids, why):
                # A real requirement stays one: an answer that would not resolve keeps its rule.
                outcomes["kept"] += 1
                answered.append(sid)
                continue
            in_progress = sid
            # Earlier rule rows under other keys (another seat's, an older harness's): the
            # restatement supersedes them too, or the graph keeps the obsolete statement beside
            # it (codex r1). Read before the write; the estate CLI replaces by key.
            superseded = ([k for k in _rule_keys(db, sid)
                           if k != extract_loop.rule_key(sid, author)] if sid in restate else [])
            outcome = extract_loop.decide_and_write(estate, store, sid,
                                                    nodes[sid].get("name", ""), entry, ids, nc,
                                                    sizes, seat=author, read_back=read_back,
                                                    unconfirmed=why)
            if outcome == "unconfirmed":  # a RISK write, counted apart by its reason
                unconfirmed[why] += 1
                outcome = "risk"
            for key in superseded:
                estate.annotate(sid, type="business_rule", key=key, value=entry["statement"],
                                confidence=float(entry["confidence"]),
                                provenance="extract-loop:restated", replace=True, author=author)
                if read_back is not None:
                    ok = read_back(sid, key, entry["statement"])
                else:
                    ok = any(a.get("key") == key and a.get("value") == entry["statement"]
                             for a in estate.read_annotations(sid))
                if not ok:
                    raise RuntimeError(f"write not durable: {sid} rule {key} on read-back")
            in_progress = None
            outcomes[outcome] += 1
            if "domain" in entry:
                if entry["domain"] in domain_by_id:
                    picks.append((sid, entry["domain"], float(entry["domain_confidence"])))
                else:
                    domains["refused"].append({
                        "index": None, "symbol_id": rules_file._shown(sid),
                        "why": f"domain {entry['domain']!r} is not an id of the repository's "
                               "business domains (written without one)"})
            restated += sid in restate and sid in changed_ids
            reworked += sid in restate and sid not in changed_ids
            answered.append(sid)

        _record_answered(db, answered)  # before anything that can still fail (codex r3)
        # The business domains: the catalog first (the record the next page picks from), then each
        # pick and assignment on its node. Advisory: nothing here counts toward coverage.
        if domains["store"]:
            business_domains.save_catalog(db, domains["catalog"],
                                          (os.environ.get("WICKED_RUN_ID") or "").strip())
        for sid, did, conf in picks:
            _write_domain(estate, domain_by_id, sid, did, conf, author)
        for a in domains["assign"]:
            _write_domain(estate, domain_by_id, a["symbol_id"], a["domain"], a["confidence"],
                          author)
        # The report is computed in a host temp directory and published through the safe writer
        # (core writes its --out in place, which would follow a planted link or hard link).
        with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
            after, met, line = core.coverage_against_minimum(db, str(Path(tmp) / "coverage.json"))
        rules_file.write_json_file(base, coverage_rel, after)
    except (rules_file.RulesFileRefused, RuntimeError, OSError, ValueError) as e:
        _record_answered(db, answered)  # what was written before the failure still counts
        written = outcomes["resolved"] + outcomes["risk"]
        partly = (f"; {rules_file._shown(in_progress)} may be partly written (its annotation "
                  "without its requirement)") if in_progress else ""
        if not written and not in_progress:
            if isinstance(e, rules_file.RulesFileRefused):
                raise RuntimeError(f"nothing was written to the store, then: {e}") from e
            raise  # nothing reached the store; a plain failure
        raise AppliedThenFailed(f"{written} rule(s) were written to the store{partly} before this "
                                f"failed: {e}") from e

    report = {
        "declared_seat": seat,
        "author": author,
        "entries": len(doc.get("rules") or []),
        "applied": outcomes,
        "eligible": len(eligible),
        "changed_since_build": {"listed": len(changed_ids & set(restate)), "restated": restated},
        "reworked": reworked,
        "unsourced": unconfirmed[extract_loop.NO_SOURCE_REASON],
        "not_product": unconfirmed[extract_loop.NOT_PRODUCT_REASON],
        "refused": refused[:500],
        "refused_count": len(refused),
        "business_domains": {
            "catalog": domains["state"],
            "domains": len(domain_by_id),
            "picked": len(picks),
            "assigned": len(domains["assign"]),
            "refused": domains["refused"][:200],
            "refused_count": len(domains["refused"]),
        },
        "coverage": {k: after.get(k) for k in ("coverage", "behavior_bearing", "resolved",
                                                "risk_flagged", "unaccounted")},
        "minimum_met": met,
        "coverage_line": line,
    }
    try:
        rules_file.write_json_file(base, REPORT_REL, report)
    except (rules_file.RulesFileRefused, OSError) as e:
        raise AppliedThenFailed(f"{outcomes['resolved'] + outcomes['risk']} rule(s) were written to "
                                f"the store and "
                                f"{coverage_rel} was written, but the report was not: {e}") from e
    for r in refused[:20]:
        print(f"[extract-apply] refused {r['symbol_id'] or '#' + str(r['index'])}: {r['why']}",
              file=sys.stderr)
    print(f"[extract-apply] {rules_rel} (declared seat {seat or '-'}): {outcomes['resolved']} resolved, "
          f"{outcomes['risk']} RISK-flagged (unconfirmed: "
          f"{unconfirmed[extract_loop.NO_SOURCE_REASON]} with no source, "
          f"{unconfirmed[extract_loop.NOT_PRODUCT_REASON]} not product code), "
          f"{outcomes['kept']} kept, {len(refused)} refused, {restated} of "
          f"{len(changed_ids & set(restate))} changed since the map was built restated, "
          f"{reworked} of this run's own answers reworked "
          f"(written as {author}); business domains: {domains['state']}, {len(picks)} picked, "
          f"{len(domains['assign'])} assigned, {len(domains['refused'])} refused. "
          f"{line or ''}".rstrip(), file=sys.stderr)
    for r in domains["refused"][:10]:
        print(f"[extract-apply] business domains: {r['symbol_id'] or '-'}: {r['why']}",
              file=sys.stderr)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host step: check a seat's rules file and write it.")
    ap.add_argument("--db", required=True, help="the repository's code-graph store")
    ap.add_argument("--repo-root", required=True, help="the registered repository's root")
    ap.add_argument("--rules", default=rules_file.RULES_REL,
                    help=f"rules file under the working directory (default {rules_file.RULES_REL})")
    ap.add_argument("--coverage-out", default=COVERAGE_REL,
                    help=f"coverage report under the working directory (default {COVERAGE_REL})")
    args = ap.parse_args(argv)
    try:
        apply(args.db, args.repo_root, Path.cwd(), args.rules, args.coverage_out)
    except AppliedThenFailed as e:
        print(f"[extract-apply] FAILED after writing: {e}", file=sys.stderr)
        return 1
    except rules_file.RulesFileRefused as e:
        print(f"[extract-apply] REFUSED, nothing written: {e}", file=sys.stderr)
        return 1
    except (RuntimeError, OSError) as e:
        print(f"[extract-apply] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
