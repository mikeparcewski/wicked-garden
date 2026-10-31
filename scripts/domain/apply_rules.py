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
    `extract-loop:<seat>`.

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
COVERAGE_REL = "coverage-report.json"


def apply(db: str, repo_root: str, base: Path, rules_rel: str, coverage_rel: str, *,
          estate=None, core=None) -> dict:
    core = core or _clients.core_client()
    if core is None:
        raise RuntimeError("wicked-core is not resolvable on this host (WICKED_CORE_EXE, "
                           "WICKED_CORE_BIN or PATH) — cannot tell what is unmapped")
    if estate is None:
        estate = _clients.estate_client(db=db)
        if not isinstance(estate, _clients.CliEstateClient):
            raise RuntimeError("wicked-estate is not resolvable on this host (WICKED_ESTATE_BIN "
                               "or PATH) — cannot write the store")
    try:
        doc = rules_file.read_json_file(base, rules_rel)
    except FileNotFoundError:
        raise rules_file.RulesFileRefused(
            f"the extract step left no rules file at {rules_rel}") from None
    seat, accepted, refused = rules_file.check_rules_doc(doc)
    # Where the report goes is checked BEFORE anything is written (the worktree is seat-writable).
    cov_path = rules_file.inside(base, coverage_rel)
    if cov_path.exists() and not cov_path.is_file():
        raise rules_file.RulesFileRefused(f"{coverage_rel!r} is not a regular file")
    rules_file.inside(base, REPORT_REL)

    with tempfile.TemporaryDirectory(prefix="wicked-domain-apply-") as tmp:
        before = core.coverage(db, str(Path(tmp) / "coverage.json"))
    unmapped = {n["symbol_id"]: n for n in _clients.unaccounted_nodes(before)
                if isinstance(n, dict) and isinstance(n.get("symbol_id"), str)}
    tracked = rules_file.tracked_files(repo_root)

    eligible: list[dict] = []
    for i, entry in enumerate(accepted):
        sid = entry["symbol_id"]
        node = unmapped.get(sid)
        if node is None:
            why = "is not an unmapped behaviour in the store"
        elif node.get("file") not in tracked:
            why = f"its file {node.get('file')!r} is not tracked in the repository"
        else:
            eligible.append(entry)
            continue
        refused.append({"index": None, "symbol_id": sid, "why": why})

    try:
        nc = _clients.total_node_community(estate.read_clusters(), estate.list_nodes())
    except Exception as e:  # cohesion is a quality signal; without it every node is a singleton
        print(f"[extract-apply] communities unavailable ({e}); cohesion as singletons",
              file=sys.stderr)
        nc = {}
    sizes: dict[str, int] = {}
    for label in nc.values():
        sizes[label] = sizes.get(label, 0) + 1
    try:
        store = extract_loop._DirectStore(db)
    except Exception as e:  # only guards a floor over an existing statement
        print(f"[extract-apply] direct store unavailable ({e})", file=sys.stderr)
        store = None

    author = f"extract-loop:{seat}" if seat else "extract-loop"
    ids = {e["symbol_id"] for e in eligible}
    outcomes = {"resolved": 0, "risk": 0, "kept": 0}
    for entry in eligible:
        sid = entry["symbol_id"]
        outcome = extract_loop.decide_and_write(estate, store, sid, unmapped[sid].get("name", ""),
                                                entry, ids, nc, sizes, seat=author)
        outcomes[outcome] += 1

    cov_path.parent.mkdir(parents=True, exist_ok=True)
    after, met, line = core.coverage_against_minimum(db, str(cov_path))

    report = {
        "seat": seat,
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
    rules_file.write_json_file(base, REPORT_REL, report)
    for r in refused[:20]:
        print(f"[extract-apply] refused {r['symbol_id'] or '#' + str(r['index'])}: {r['why']}",
              file=sys.stderr)
    print(f"[extract-apply] {rules_rel} from seat {seat or '-'}: {outcomes['resolved']} resolved, "
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
    except rules_file.RulesFileRefused as e:
        print(f"[extract-apply] REFUSED, nothing written: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"[extract-apply] FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
