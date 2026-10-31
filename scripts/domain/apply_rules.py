#!/usr/bin/env python3
"""apply_rules.py — HOST step `extract-apply` of domain-extraction (wicked-garden#1362).

The seat container's extract step stated its rules into the RULES file in the run's worktree
(`wicked-garden/domain-rules@1`, `rules_file.py`); it cannot write the store. This step, on the
daemon host, is the only writer, and it trusts nothing the seat could have touched:

  * the file must be inside the schema: a document outside it (wrong tag, unknown key, a bad
    seat name, too many entries, not JSON, a symlink) is refused whole and nothing is written;
    an entry outside it is refused and listed;
  * every entry must name a behaviour the store has and that `wicked-core coverage`, run here,
    reports unmapped, in a file `git ls-files` tracks in the registered repository — anything
    else is refused and listed;
  * what passes is judged and written exactly as the extraction harness writes its own model's
    rules (`extract_loop.decide_and_write`: the rule validator, confidence x community
    cohesion >= 0.75 to resolve, the RISK floor, a read-back per write), authored
    `extract-loop` — the seat a file names is the seat's own claim, so it is only reported;
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


def _mapped_since(db: str, symbol_id: str, before: str) -> bool:
    """Whether another writer changed `symbol_id`'s requirement since this step read the store
    (`before`): a fresh read, compared. False when the store cannot say (an older schema)."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT n.requirement FROM nodes n JOIN symbols s ON s.sid = n.symbol "
                              "WHERE s.sym = ?", (symbol_id,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return ((row[0] if row else None) or "") != (before or "")


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

    # The store as it stands BEFORE the coverage snapshot: a requirement that differs from it at
    # write time was written by someone else meanwhile (and it guards a floor over a statement).
    try:
        store = extract_loop._DirectStore(db)
    except Exception as e:
        print(f"[extract-apply] direct store unavailable ({e})", file=sys.stderr)
        store = None
    with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
        before = core.coverage(db, str(Path(tmp) / "coverage.json"))
    unmapped = {n["symbol_id"]: n for n in _clients.unaccounted_nodes(before)
                if isinstance(n, dict) and isinstance(n.get("symbol_id"), str)}
    tracked = rules_file.tracked_files(repo_root)

    eligible: list[dict] = []
    for entry in accepted:
        sid = entry["symbol_id"]
        node = unmapped.get(sid)
        if node is None:
            why = "is not an unmapped behaviour in the store"
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
    ids = {e["symbol_id"] for e in eligible}
    outcomes = {"resolved": 0, "risk": 0, "kept": 0}
    try:
        for entry in eligible:
            sid = entry["symbol_id"]
            if _mapped_since(db, sid, store.requirement_of(sid) if store is not None else ""):
                # Another writer mapped it after the coverage snapshot: theirs stands. (This narrows
                # the window to one read before the write; the store has no conditional write.)
                refused.append({"index": None, "symbol_id": rules_file._shown(sid),
                                "why": "was mapped by another writer while this step ran"})
                continue
            outcome = extract_loop.decide_and_write(estate, store, sid,
                                                    unmapped[sid].get("name", ""), entry, ids, nc,
                                                    sizes, seat=author)
            outcomes[outcome] += 1

        # The report is computed in a host temp directory and published through the safe writer
        # (core writes its --out in place, which would follow a planted link or hard link).
        with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
            after, met, line = core.coverage_against_minimum(db, str(Path(tmp) / "coverage.json"))
        rules_file.write_json_file(base, coverage_rel, after)
    except (rules_file.RulesFileRefused, RuntimeError, OSError) as e:
        done = sum(outcomes.values())
        raise AppliedThenFailed(f"{done} rule(s) were written to the store before this failed: "
                                f"{e}") from e

    report = {
        "declared_seat": seat,
        "author": author,
        "entries": len(doc.get("rules") or []),
        "applied": outcomes,
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
        raise AppliedThenFailed(f"{sum(outcomes.values())} rule(s) were written to the store and "
                                f"{coverage_rel} was written, but the report was not: {e}") from e
    for r in refused[:20]:
        print(f"[extract-apply] refused {r['symbol_id'] or '#' + str(r['index'])}: {r['why']}",
              file=sys.stderr)
    print(f"[extract-apply] {rules_rel} (declared seat {seat or '-'}): {outcomes['resolved']} resolved, "
          f"{outcomes['risk']} RISK-flagged, {outcomes['kept']} kept, {len(refused)} refused "
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
