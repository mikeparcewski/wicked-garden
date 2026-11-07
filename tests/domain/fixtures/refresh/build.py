#!/usr/bin/env python3
"""Build the Refresh-map fixture from REAL wicked-estate and wicked-core binaries (wicked-garden e2e
F40: the first refresh tests ran on a hand-built store whose `meta` table had the wrong columns, so
the code that read the real store's `meta(k, v)` was never exercised).

What it records, in this directory:
  * `repo.bundle` — a two-commit git repository: `src/math.js` with a `sum` that skips the first
    element (commit "map"), then the fix (commit "fix"); `src/other.js` is untouched.
  * `estate.db` — the repository's estate store as the engine leaves it before a Refresh run:
    indexed at "map", mapped (sum and mean resolved, sum with a code mismatch, clamp resolved),
    the requirements graph built by `wicked-core domain-graph` (its build record names "map"),
    then re-indexed at "fix" (the engine's D8 base index of the Refresh run).
  * `labelled.db` — the same repository indexed at "map" under a label (`--repo tm`), so the
    labelled `repo:<label>:commit` meta form is read from a real store too.
  * `manifest.json` — the two commits and the binaries' versions.

Usage: build.py --estate <wicked-estate> --core <wicked-core>   (rebuilds the files in place)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "scripts"))

from domain import _clients  # noqa: E402

BUGGY = ("/** The sum of every element. @returns {number} */\n"
         "export function sum(xs) { let t = 0; for (let i = 1; i < xs.length; i++) t += xs[i]; "
         "return t; }\n"
         "/** The arithmetic mean. @returns {number} */\n"
         "export function mean(xs) { return sum(xs) / xs.length; }\n")
FIXED = BUGGY.replace("let i = 1", "let i = 0")
OTHER = ("/** Holds n within [lo, hi]. @returns {number} */\n"
         "export function clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }\n")


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-10-16T12:00:00Z",
               GIT_COMMITTER_DATE="2026-10-16T12:00:00Z")
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "core.fsmonitor=false", *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estate", required=True)
    ap.add_argument("--core", required=True)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "tm"
        (repo / "src").mkdir(parents=True)
        git(tmp, "init", "-q", "-b", "main", str(repo))
        (repo / "src" / "math.js").write_text(BUGGY)
        (repo / "src" / "other.js").write_text(OTHER)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "map")
        built = git(repo, "rev-parse", "HEAD")
        db = Path(tmp) / "estate.db"
        subprocess.run([a.estate, "index", str(repo), "--db", str(db)], check=True,
                       capture_output=True)
        estate = _clients.CliEstateClient([a.estate], str(db))
        ids = {}
        for name in ("sum", "mean", "clamp"):
            hits = estate.resolve(name)
            assert len(hits) == 1, (name, hits)
            ids[name] = hits[0]
        rules = {"sum": "The sum of numbers must include every element.",
                 "mean": "The mean is the sum of every element over the count.",
                 "clamp": "A value is held within [lo, hi]."}
        for name, stmt in rules.items():
            sid = ids[name]
            if name == "sum":
                estate.annotate(sid, type="code_mismatch", key=f"RULE-{name}:mismatch",
                                value="the loop starts at index 1, so the first element is skipped",
                                confidence=0.9, author="extract-loop")
            estate.annotate(sid, type="business_rule", key=f"RULE-{name}", value=stmt,
                            confidence=0.9, author="extract-loop")
            estate.set_requirement(sid, stmt, True)
        env = dict(os.environ, WICKED_REQUIREMENTS_MIN_COVERAGE_PCT="1")
        out = Path(tmp) / "graph.json"
        subprocess.run([a.core, "domain-graph", "--db", str(db), "--out", str(out)], check=True,
                       capture_output=True, env=env)
        (repo / "src" / "math.js").write_text(FIXED)
        git(repo, "commit", "-q", "-am", "fix")
        base = git(repo, "rev-parse", "HEAD")
        subprocess.run([a.estate, "index", str(repo), "--db", str(db)], check=True,
                       capture_output=True)
        labelled = Path(tmp) / "labelled.db"
        subprocess.run([a.estate, "index", str(repo), "--db", str(labelled), "--repo", "tm"],
                       check=True, capture_output=True)
        git(repo, "bundle", "create", str(HERE / "repo.bundle"), "--all")
        for f in (db, labelled):
            copy = HERE / f.name
            copy.unlink(missing_ok=True)
            subprocess.run(["sqlite3", str(f), f".backup '{copy}'"], check=True)
            # The build machine's temp path is not part of the fixture: the roots read neutral.
            import sqlite3
            con = sqlite3.connect(copy)
            con.execute("UPDATE meta SET v = '/fixture/tm' WHERE k = 'indexed_root' "
                        "OR k LIKE 'repo:%:root'")
            con.commit()
            con.execute("VACUUM")
            con.close()
        version = subprocess.run([a.estate, "--version"], capture_output=True, text=True).stdout
        manifest = {"built": built, "base": base, "symbols": ids,
                    "estate": version.strip(), "core": Path(a.core).name}
        (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
