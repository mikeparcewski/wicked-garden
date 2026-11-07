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
the registered checkout (never the seat-writable worktree). A store that does not RECORD a commit
(no map yet, an older wicked-core wrote no code commit, no indexed commit) re-asks nothing and says
why. A store that cannot be read, a labelled store with a map, or a recorded pair of commits the
checkout cannot compare fails the step with the cause (e2e-1105 F40): never an empty refresh of a
stale map.
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


class RefreshUnreadable(RuntimeError):
    """The store could not be read for the refresh (a missing table or column, a locked or
    corrupt file). Said as such and fails the step: never read as "no commit recorded"
    (e2e-1105 F40: a wrong column name read as "no indexed commit" and the stale map stood)."""


def _meta(con: sqlite3.Connection, key: str) -> str | None:
    """One value of estate's `meta(k, v)` table, or None when the key is absent. A value that is
    not text is unreadable, never absent (codex r1)."""
    row = con.execute("SELECT v FROM meta WHERE k = ?", (key,)).fetchone()
    if row is None:
        return None
    if not isinstance(row[0], str):
        raise RefreshUnreadable(f"the store's meta `{key}` is not text ({type(row[0]).__name__})")
    return row[0]


def indexed_commit(con: sqlite3.Connection) -> tuple[str | None, str]:
    """The commit the store is indexed at now and where it was read: estate's singular
    `repo_commit` for a store of one repository, else `repo:<label>:commit` when the store holds
    exactly one labelled repository (estate `repo_scope.rs`, "Provenance"). (None, why) when it
    cannot say which."""
    commit = (_meta(con, "repo_commit") or "").strip()
    if commit:
        return commit.lower(), "repo_commit"
    labels_raw = _meta(con, "repo_labels")
    if not labels_raw:
        return None, "the store records no indexed commit"
    try:
        labels = json.loads(labels_raw)
    except ValueError as e:
        raise RefreshUnreadable(f"the store's repo_labels is not JSON ({e})") from e
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise RefreshUnreadable("the store's repo_labels is not a list of labels")
    if len(labels) != 1:
        return None, (f"the store holds {len(labels)} labelled repositories, so which one this "
                      f"run maps cannot be told")
    commit = (_meta(con, f"repo:{labels[0]}:commit") or "").strip()
    if not commit:
        return None, f"the store records no indexed commit for repository `{labels[0]}`"
    return commit.lower(), f"repo:{labels[0]}:commit"


def build_and_base(db: str) -> tuple[str | None, str | None, str]:
    """(the commit the map was built from, the commit the store is indexed at now, where the base
    was read or why it is missing). Each commit is None when the store does not say: no build yet,
    a build by an older wicked-core, a store with no indexed commit. Raises [`RefreshUnreadable`]
    when the store cannot be read (a read that fails is never "not recorded"), and for a labelled
    store that holds a map (its node paths carry the label, which the mapping steps do not
    translate; codex r2/r3), whether or not the map recorded its commit."""
    try:
        con = _ro(db)
        try:
            row = con.execute("SELECT n.data FROM nodes n JOIN symbols s ON s.sid = n.symbol "
                              "WHERE s.sym = ?", (BUILD_SYMBOL,)).fetchone()
            built = None
            if row is not None:
                # Absent record: no map yet. A record from an older wicked-core: no code_commit.
                # Anything else that does not parse is unreadable (codex r1), never "no commit".
                try:
                    data = json.loads(row[0]) if isinstance(row[0], str) else None
                except ValueError as e:
                    raise RefreshUnreadable(f"the map's build record is not JSON ({e})") from e
                meta = data.get("metadata", {}) if isinstance(data, dict) else None
                if not isinstance(meta, dict):
                    raise RefreshUnreadable("the map's build record has no metadata object")
                c = meta.get("code_commit")
                if c is not None and not isinstance(c, str):
                    raise RefreshUnreadable(f"the map's build record names a code commit that "
                                            f"is not text ({type(c).__name__})")
                built = c.strip().lower() if c and c.strip() else None
            base, why = indexed_commit(con)
            labelled = why.startswith("repo:") or bool(_meta(con, "repo_labels"))
            if row is not None and labelled:
                raise RefreshUnreadable("the store is labelled: Refresh map reads a store of one "
                                        "un-labelled repository, as wicked-crew registers them")
        finally:
            con.close()
    except sqlite3.Error as e:
        raise RefreshUnreadable(f"the store {db} could not be read ({e})") from e
    if built is not None and not _HEX.match(built):
        raise RefreshUnreadable(f"the map's build record names {built!r}, not a commit")
    if base is not None and not _HEX.match(base):
        raise RefreshUnreadable(f"the store's indexed commit is {base!r}, not a commit")
    return built, base, why


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
        if "requirement" not in cols or "requirement_validated" not in cols or not has_ann:
            # Every estate store wicked-garden maps carries these: one that does not is not read
            # as "nothing mapped" (e2e-1105 F40).
            raise RefreshUnreadable(f"the store {db} has no requirement columns or annotations "
                                    f"table (columns: {sorted(cols)})")
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


def rule_keys(db: str, symbol_id: str) -> list[str]:
    """The keys of the business rules `symbol_id` holds now (host read, read-only)."""
    con = _ro(db)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                           "name = 'annotations'").fetchone():
            return []  # a store that keeps no annotations holds no rule rows
        # Every key (codex r2): a row left out would keep its obsolete statement in the graph.
        rows = con.execute("SELECT DISTINCT a.key FROM annotations a JOIN symbols s ON "
                           "s.sid = a.node_sym WHERE s.sym = ? AND a.type = 'business_rule' "
                           "ORDER BY a.key", (symbol_id,)).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows if isinstance(r[0], str)]


def changed_units(db: str, repo_root: str, tracked: set[str],
                  exclude: set[str]) -> tuple[list[dict], str]:
    """The mapped behaviours in product files changed since the map was built, as coverage-style
    nodes (`symbol_id`, `name`, `file`, `kind`) plus `prior` (the earlier statement), and a line
    saying what was compared. `exclude`: units already framed for another reason (unmapped,
    placeholders). A store that does not RECORD a commit re-asks nothing and says why; a store
    that cannot be READ, a labelled store with a map, or a recorded pair of commits the checkout
    cannot compare raises [`RefreshUnreadable`]."""
    built, base, why = build_and_base(db)
    if built is None:
        return [], ("no build commit recorded (no map yet, or a map built by an older "
                    "wicked-core): changed behaviours are not re-asked")
    if base is None:
        return [], f"{why}: changed behaviours are not re-asked"
    if built == base:
        return [], f"code unchanged since the map was built ({built[:12]})"
    try:
        files = changed_files(repo_root, built, base)
    except RuntimeError as e:
        # Both commits are recorded, so the comparison must run (codex r2): a checkout that cannot
        # make it (a shallow clone, a rewritten history) fails the step, never re-asks nothing.
        raise RefreshUnreadable(f"the files changed since the map was built "
                                f"({built[:12]}..{base[:12]}) could not be read in "
                                f"{repo_root}: {e}") from e
    files = sorted(f for f in files if f in tracked)
    try:
        rows = _mapped_in(db, files) if files else []
    except sqlite3.Error as e:
        raise RefreshUnreadable(f"the mapped behaviours could not be read from {db} ({e})") from e
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
