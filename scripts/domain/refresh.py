"""refresh.py — which MAPPED behaviours changed since the requirements map was built (wicked-garden#1425).

A Refresh map run (the requirements page's "Built from code N commits old") re-indexes the
repository at the run's base and maps what is new. A behaviour that was already mapped and whose
code has changed since must be asked again too, or it keeps its old statement and any old
"code doesn't meet it" finding while the page reads as current.

The map's build record (wicked-core#1327, `requirements-graph/build` in the store) names the code
commit the map was built from; the store's `repo_commit` names the commit it is indexed at now (the
run's base, after the engine's D8 index). The files git reports changed between the two, in the
registered checkout, are the files whose mapped behaviours are asked again.

Everything here is a read: the store through a read-only connection, git with fixed arguments in
the registered checkout (never the seat-writable worktree). A store or a build that cannot say
(an older wicked-core wrote no code commit, a commit the checkout does not hold) re-asks nothing
and says why.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from urllib.parse import quote

from domain import extract_loop, rules_file

BUILD_SYMBOL = "wicked-apps synthetic requirements-graph/build:"
_HEX = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_GIT_TIMEOUT = 30
PRIOR_LIMIT = 500  # characters of the earlier statement the worklist carries
_CHUNK = 400  # file names per IN (...) query


def _ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)


def build_and_base(db: str) -> tuple[str | None, str | None]:
    """(the commit the map was built from, the commit the store is indexed at now), each None when
    the store does not say (no build yet, a build by an older wicked-core, an older store)."""
    built = base = None
    try:
        con = _ro(db)
        try:
            try:
                row = con.execute("SELECT n.data FROM nodes n JOIN symbols s ON s.sid = n.symbol "
                                  "WHERE s.sym = ?", (BUILD_SYMBOL,)).fetchone()
            except sqlite3.OperationalError:
                row = None
            if row is not None:
                try:
                    meta = json.loads(row[0] or "{}").get("metadata") or {}
                except (TypeError, ValueError, AttributeError):
                    meta = {}
                c = meta.get("code_commit") if isinstance(meta, dict) else None
                built = c.strip().lower() if isinstance(c, str) else None
            try:
                row = con.execute("SELECT value FROM meta WHERE key = 'repo_commit'").fetchone()
            except sqlite3.OperationalError:
                row = None
            if row is not None and isinstance(row[0], str):
                base = row[0].strip().lower()
        finally:
            con.close()
    except sqlite3.Error:
        return None, None
    return (built if built and _HEX.match(built) else None,
            base if base and _HEX.match(base) else None)


def changed_files(repo_root: str, built: str, base: str) -> set[str]:
    """Files git reports changed from `built` to `base` in the registered checkout. Raises
    RuntimeError when git cannot say (a commit the checkout does not hold, git missing)."""
    git = rules_file.trusted_executable("git")
    if git is None:
        raise RuntimeError("git is not on PATH")
    argv = [git, "-c", "core.fsmonitor=false", "-C", str(repo_root), "diff", "--no-ext-diff",
            "--no-textconv", "--name-only", "-z", built, base, "--"]
    try:
        proc = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=_GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"git diff could not run: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"git diff exited {proc.returncode}: "
                           f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return {p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p}


def _mapped_in(db: str, files: list[str]) -> list[tuple[str, str, str, str, str]]:
    """(symbol id, name, file, data, earlier statement) of each MAPPED behaviour in `files`: a
    node holding a business rule or a validated requirement."""
    out = []
    con = _ro(db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(nodes)")}
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        has_ann = "annotations" in tables
        conds = []
        if "requirement_validated" in cols:
            conds.append("n.requirement_validated = 1")
        if has_ann:
            conds.append("EXISTS (SELECT 1 FROM annotations a WHERE a.node_sym = n.symbol "
                         "AND a.type = 'business_rule' AND trim(a.value) != '')")
        if not conds or "requirement" not in cols:
            return []
        prior = ("COALESCE((SELECT a.value FROM annotations a WHERE a.node_sym = n.symbol AND "
                 "a.type = 'business_rule' AND trim(a.value) != '' ORDER BY a.ts DESC, a.id DESC "
                 "LIMIT 1), n.requirement, '')" if has_ann else "COALESCE(n.requirement, '')")
        for i in range(0, len(files), _CHUNK):
            part = files[i:i + _CHUNK]
            marks = ",".join("?" * len(part))
            out += con.execute(
                f"SELECT s.sym, n.name, n.file, n.data, {prior} FROM nodes n JOIN symbols s ON "
                f"s.sid = n.symbol WHERE n.file IN ({marks}) AND ({' OR '.join(conds)})",
                part).fetchall()
    finally:
        con.close()
    return out


RULE_KEYS_LIMIT = 16  # earlier rule rows one restatement supersedes


def rule_keys(db: str, symbol_id: str) -> list[str]:
    """The keys of the business rules `symbol_id` holds now (host read, read-only)."""
    con = _ro(db)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                           "name = 'annotations'").fetchone():
            return []  # a store that keeps no annotations holds no rule rows
        rows = con.execute("SELECT DISTINCT a.key FROM annotations a JOIN symbols s ON "
                           "s.sid = a.node_sym WHERE s.sym = ? AND a.type = 'business_rule' "
                           "ORDER BY a.key LIMIT ?", (symbol_id, RULE_KEYS_LIMIT)).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows if isinstance(r[0], str)]


def changed_units(db: str, repo_root: str, tracked: set[str],
                  exclude: set[str]) -> tuple[list[dict], str]:
    """The mapped behaviours in product files changed since the map was built, as coverage-style
    nodes (`symbol_id`, `name`, `file`, `kind`) plus `prior` (the earlier statement), and a line
    saying what was compared. `exclude`: units already framed for another reason (unmapped,
    placeholders). Never raises: a store or checkout that cannot say re-asks nothing."""
    built, base = build_and_base(db)
    if built is None:
        return [], ("no build commit recorded (no map yet, or a map built by an older "
                    "wicked-core): changed behaviours are not re-asked")
    if base is None:
        return [], "the store records no indexed commit: changed behaviours are not re-asked"
    if built == base:
        return [], f"code unchanged since the map was built ({built[:12]})"
    try:
        files = changed_files(repo_root, built, base)
    except RuntimeError as e:
        return [], (f"the files changed since the map was built ({built[:12]}..{base[:12]}) "
                    f"could not be read ({e}): changed behaviours are not re-asked")
    files = sorted(f for f in files if f in tracked)
    try:
        rows = _mapped_in(db, files) if files else []
    except sqlite3.Error as e:
        return [], f"the mapped behaviours could not be read ({e}): none re-asked"
    units = []
    for sym, name, file, data, prior in rows:
        if sym in exclude:
            continue
        kind = extract_loop.kind_of_row((name, file, data))
        if extract_loop.unconfirmed_reason(file, True, kind):  # tests, data files: not product code
            continue
        units.append({"symbol_id": sym, "name": name or "", "file": file, "kind": kind,
                      "prior": str(prior or "")[:PRIOR_LIMIT]})
    units.sort(key=lambda u: u["symbol_id"])
    return units, (f"{len(units)} mapped behaviour(s) in {len(files)} file(s) changed since the "
                   f"map was built ({built[:12]}..{base[:12]})")
