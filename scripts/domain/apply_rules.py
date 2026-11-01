#!/usr/bin/env python3
"""apply_rules.py — HOST step `extract-apply` of domain-extraction (wicked-garden#1362).

The seat container's extract step stated its rules into the RULES file in the run's worktree
(`wicked-garden/domain-rules@1`, `rules_file.py`); it cannot write the store. This step, on the
daemon host, is the only writer, and it trusts nothing the seat could have touched:

  * the file must be inside the schema: a document outside it (wrong tag, unknown key, a bad
    seat name, too many entries, not JSON, a symlink) is refused whole and nothing is written;
    an entry outside it is refused and listed;
  * every entry must name a behaviour the store has and that `wicked-core coverage`, run here,
    reports unmapped or as a risk-flagged placeholder (not a real requirement yet), in a file
    `git ls-files` tracks in the registered repository — anything else is refused and listed; an
    empty statement never overwrites a placeholder's statement (the floor only fills blanks);
  * what passes is judged and written exactly as the extraction harness writes its own model's
    rules (`extract_loop.decide_and_write`: the rule validator, confidence x community
    cohesion >= 0.75 to resolve, the RISK floor, a read-back per write), authored
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

Exit 0 when the file was applied (refused entries are listed, not fatal); 1 when the file is
missing or refused, or a write fails.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/ on path

from domain import _clients, extract_loop, rules_file  # noqa: E402

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


def _accounting(db: str, symbol_ids: list[str]) -> dict[str, tuple[str, int]]:
    """For each symbol, what accounts for it in the store right now: its requirement text and how
    many accounting annotations (business_rule, risk, assumption, question — coverage counts any)
    it carries. One fresh read-only connection; {} when the store cannot say (older schema)."""
    import sqlite3
    from urllib.parse import quote
    out: dict[str, tuple[str, int]] = {}
    try:
        con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
        try:
            marks = ",".join("?" * len(_ACCOUNTING_TYPES))
            for sym in symbol_ids:
                row = con.execute("SELECT s.sid, n.requirement FROM symbols s LEFT JOIN nodes n "
                                  "ON n.symbol = s.sid WHERE s.sym = ?", (sym,)).fetchone()
                if row is None:
                    continue
                count = con.execute(f"SELECT count(*) FROM annotations WHERE node_sym = ? AND "
                                    f"type IN ({marks})", (row[0], *_ACCOUNTING_TYPES)).fetchone()
                out[sym] = ((row[1] or ""), int(count[0]))
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

    def check(symbol_id: str, key: str) -> bool:
        try:
            con = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
            try:
                row = con.execute("SELECT 1 FROM annotations a JOIN symbols s ON "
                                  "s.sid = a.node_sym WHERE s.sym = ? AND a.key = ? LIMIT 1",
                                  (symbol_id, key)).fetchone()
            finally:
                con.close()
        except sqlite3.Error as e:  # a failed read-back is a failed write, said as one
            raise RuntimeError(f"read-back of {symbol_id} failed: {e}") from e
        return row is not None

    return check


def apply(db: str, repo_root: str, base: Path, rules_rel: str, coverage_rel: str, *,
          estate=None, core=None) -> dict:
    # Binaries from the operator and the engine only — never from the seat-writable worktree.
    core = core or _clients.host_core_client()
    estate = estate or _clients.host_estate_client(db)
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
    # may revisit (wicked-core#1233). A resolved behaviour is never rewritten from a page.
    unmapped = {n["symbol_id"]: n for n in [*_clients.unaccounted_nodes(before),
                                            *_clients.placeholder_nodes(before)]
                if isinstance(n, dict) and isinstance(n.get("symbol_id"), str)}
    tracked = rules_file.tracked_files(repo_root)

    eligible: list[dict] = []
    for entry in accepted:
        sid = entry["symbol_id"]
        node = unmapped.get(sid)
        if node is None:
            why = "is not an unmapped behaviour or a placeholder in the store"
        elif node.get("file") not in tracked:
            why = f"its file {node.get('file')!r} is not tracked in the repository"
        else:
            eligible.append(entry)
            continue
        refused.append({"index": None, "symbol_id": rules_file._shown(sid), "why": why})

    try:
        nc = _clients.total_node_community(estate.read_clusters(), estate.list_nodes())
    except Exception as e:  # cohesion is a quality signal; without it every node is a singleton
        print(f"[extract-apply] communities unavailable ({e}); cohesion as singletons",
              file=sys.stderr)
        nc = {}
    sizes: dict[str, int] = {}
    for label in nc.values():
        sizes[label] = sizes.get(label, 0) + 1

    # The host writes these, so the host is the author: the seat named in the file is the seat's
    # own claim (a seat-written file proves nothing about who wrote it) and is only reported.
    author = AUTHOR
    # The estate CLI writes into `db`, so its writes read back from `db` directly; any other
    # client (an injected one) reads back through itself.
    read_back = (_annotation_read_back(db) if isinstance(estate, _clients.CliEstateClient)
                 else None)
    ids = {e["symbol_id"] for e in eligible}
    outcomes = {"resolved": 0, "risk": 0, "kept": 0}
    # Valid rules written unconfirmed, by why: no source read on the host, or not product code.
    unconfirmed = {extract_loop.NO_SOURCE_REASON: 0, extract_loop.NOT_PRODUCT_REASON: 0}
    in_progress = None  # the symbol whose writes have started and not finished
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
            in_progress = sid
            # The source is re-read here, on the host: a rule about a unit whose code cannot be
            # read is unconfirmed whatever the seat (or its worklist file) says (#1370).
            # Tests and data files are never validated either: what they hold is evidence.
            sourced = store is not None and bool(store.source_slice(sid).strip())
            why = extract_loop.unconfirmed_reason(unmapped[sid].get("file", ""), sourced)
            outcome = extract_loop.decide_and_write(estate, store, sid,
                                                    unmapped[sid].get("name", ""), entry, ids, nc,
                                                    sizes, seat=author, read_back=read_back,
                                                    unconfirmed=why)
            if outcome == "unconfirmed":  # a RISK write, counted apart by its reason
                unconfirmed[why] += 1
                outcome = "risk"
            in_progress = None
            outcomes[outcome] += 1

        # The report is computed in a host temp directory and published through the safe writer
        # (core writes its --out in place, which would follow a planted link or hard link).
        with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
            after, met, line = core.coverage_against_minimum(db, str(Path(tmp) / "coverage.json"))
        rules_file.write_json_file(base, coverage_rel, after)
    except (rules_file.RulesFileRefused, RuntimeError, OSError, ValueError) as e:
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
        "unsourced": unconfirmed[extract_loop.NO_SOURCE_REASON],
        "not_product": unconfirmed[extract_loop.NOT_PRODUCT_REASON],
        "refused": refused[:500],
        "refused_count": len(refused),
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
          f"{outcomes['kept']} kept, {len(refused)} refused "
          f"(written as {author}). {line or ''}".rstrip(), file=sys.stderr)
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
