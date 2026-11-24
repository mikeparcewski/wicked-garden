"""business_domains.py — the repository's BUSINESS domains, proposed from code evidence (reqgraph Fix B).

A requirement's domain used to be its package directory (wicked-core `package_dir`), which a product
owner does not recognise: on the AutoGPT measurement only 57% of rows had a domain that fit. Here
the page's extract seat proposes the repository's business areas once (3 to 9, each named for what
the code does for its users, with a one-line purpose and the code that shows it), and every rule
picks one. The directory is evidence, never the name.

Everything crosses the seat boundary inside the rules file (`rules_file.py`), so the host trusts
none of it:

  * the catalog's shape is closed and bounded (`check_catalog_shape`);
  * every domain must cite code the host can see (`check_catalog_evidence`): files `git ls-files`
    tracks, and any named symbol must be in the store at that file; at least one item per domain
    is more than a directory, and a domain named after a directory is refused (the failure this
    fixes). Bad evidence is dropped; fewer than three grounded domains refuses the catalog;
  * once a catalog is stored for the repository it is the one every later page picks from: a page
    cannot rename or replace it (ids stay stable across pages and runs), but it may add an area the
    catalog lacks, grounded like a proposal, up to 9 in all (`check_additions`, wicked-garden#1537);
  * a pick must name a catalog id; an assignment must name a resolved requirement in product code.

The catalog is kept on the HOST beside the store (`<store dir>/domain-catalog/business-domains.json`,
like the generation records), and each picked domain is written on its node as the estate annotation
`business_domain` (value: compact JSON `{"id", "name", "purpose"}`; confidence: the pick's). That
is not an accounting type, so coverage and its denominator are unchanged. wicked-core's
`domain-graph` reads the annotation into each requirement's `business_domain` and the model's
`metadata.business_domains`; requirement keys (`<dir>::REQ-NNN`) do not change.

stdlib-only, cross-platform.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote

CATALOG_SCHEMA = "wicked-garden/business-domains@1"
DIR_NAME = "domain-catalog"
FILE_NAME = "business-domains.json"
# The estate annotation each picked domain is written as (wicked-core reads the same name).
ANN_TYPE = "business_domain"
ANN_KEY = "business_domain"
PROVENANCE = "extract-apply:business-domains"

MIN_DOMAINS = 3
MAX_DOMAINS = 9
MAX_EVIDENCE = 8
MAX_NAME = 60
MAX_PURPOSE = 200
MAX_REF = 500
# Resolved requirements with no domain yet, framed per page for the seat to assign.
MAX_ASSIGN = 1500
# Directory names shown to the seat so its own check can tell a directory-named domain.
MAX_DIRECTORY_NAMES = 4000

EVIDENCE_KINDS = frozenset({"entry-point", "route", "cli-verb", "api-noun", "directory"})
_DOMAIN_KEYS = frozenset({"id", "name", "purpose", "evidence"})
_EVIDENCE_KEYS = frozenset({"kind", "file", "symbol", "text"})
_ASSIGN_KEYS = frozenset({"symbol_id", "domain", "confidence"})
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,47}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class CatalogRefused(ValueError):
    """The proposed catalog is outside the schema or not grounded in the code."""

    def __init__(self, message: str, dropped: list[dict] | None = None):
        super().__init__(message)
        self.dropped = dropped or []


def _text(value: Any, limit: int, *, min_len: int = 1) -> str | None:
    """Why a one-line text field is unusable, or None."""
    if not isinstance(value, str):
        return f"is {type(value).__name__}, expected text"
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return "is not valid Unicode text"
    if _CONTROL_RE.search(value):
        return "holds a control character or a line break"
    if len(value.strip()) < min_len:
        return "is empty" if min_len <= 1 else f"is shorter than {min_len} characters"
    if len(value) > limit:
        return f"is longer than {limit} characters"
    if value.lstrip().startswith("-"):
        return "starts with '-' (the host passes values to the estate CLI)"
    return None


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def directory_names(tracked: Iterable[str]) -> set[str]:
    """The slug of every directory name on a tracked path (`a/b/c.py` -> {a, b})."""
    out: set[str] = set()
    for path in tracked:
        for part in path.replace("\\", "/").split("/")[:-1]:
            s = slug(part)
            if s:
                out.add(s)
    return out


def check_catalog_shape(domains: Any, directory_slugs: set[str] | None = None, *,
                        count: tuple[int, int] = (MIN_DOMAINS, MAX_DOMAINS),
                        verb: str = "propose") -> list[dict]:
    """The catalog's closed shape: 3 to 9 domains (`count`), unique ids and names, a one-line
    purpose and 1 to 8 evidence items each. With `directory_slugs`, a domain named after a
    directory is refused too. Raises CatalogRefused naming the first problem; returns the
    domains."""
    if not isinstance(domains, list):
        raise CatalogRefused(f"business_domains is {type(domains).__name__}, expected a list")
    if not count[0] <= len(domains) <= count[1]:
        raise CatalogRefused(f"business_domains has {len(domains)} domain(s); {verb} "
                             f"{count[0]} to {count[1]}")
    ids: set[str] = set()
    names: set[str] = set()
    for i, d in enumerate(domains):
        where = f"business_domains[{i}]"
        if not isinstance(d, dict):
            raise CatalogRefused(f"{where} is {type(d).__name__}, expected an object")
        extra = sorted(set(d) - _DOMAIN_KEYS)
        if extra:
            raise CatalogRefused(f"{where} has unknown key(s) {extra!r}")
        did = d.get("id")
        if not isinstance(did, str) or not _ID_RE.fullmatch(did):
            raise CatalogRefused(f"{where}.id must be a lowercase slug (a-z, 0-9, '-', 2 to 48 "
                                 f"characters, starting with a letter)")
        if did in ids:
            raise CatalogRefused(f"{where}.id {did!r} repeats an earlier domain")
        ids.add(did)
        why = _text(d.get("name"), MAX_NAME, min_len=3)
        if why:
            raise CatalogRefused(f"{where}.name {why}")
        name = d["name"].strip()
        if "/" in name or "\\" in name or "_" in name or "." in name:
            raise CatalogRefused(f"{where}.name {name!r} reads as a path or identifier; name the "
                                 "business area in words")
        if slug(name) in names:
            raise CatalogRefused(f"{where}.name {name!r} repeats an earlier domain")
        names.add(slug(name))
        if directory_slugs is not None and slug(name) in directory_slugs:
            raise CatalogRefused(
                f"{where}.name {name!r} is a directory name; name the business area for what the "
                "code does for its users (the directory is evidence, not the name)")
        why = _text(d.get("purpose"), MAX_PURPOSE, min_len=10)
        if why:
            raise CatalogRefused(f"{where}.purpose {why}")
        ev = d.get("evidence")
        if not isinstance(ev, list) or not 1 <= len(ev) <= MAX_EVIDENCE:
            raise CatalogRefused(f"{where}.evidence must list 1 to {MAX_EVIDENCE} items")
        for j, e in enumerate(ev):
            at = f"{where}.evidence[{j}]"
            if not isinstance(e, dict):
                raise CatalogRefused(f"{at} is {type(e).__name__}, expected an object")
            extra = sorted(set(e) - _EVIDENCE_KEYS)
            if extra:
                raise CatalogRefused(f"{at} has unknown key(s) {extra!r}")
            if not isinstance(e.get("kind"), str) or e["kind"] not in EVIDENCE_KINDS:
                raise CatalogRefused(f"{at}.kind must be one of {sorted(EVIDENCE_KINDS)}")
            why = _text(e.get("file"), MAX_REF)
            if why:
                raise CatalogRefused(f"{at}.file {why}")
            for key in ("symbol", "text"):
                if key in e:
                    why = _text(e[key], MAX_REF)
                    if why:
                        raise CatalogRefused(f"{at}.{key} {why}")
        if all(e["kind"] == "directory" for e in ev):
            raise CatalogRefused(f"{where} cites only directories; cite the entry points, routes, "
                                 "CLI verbs or public-API nouns that show the area")
    return domains


def check_catalog_evidence(domains: list[dict], tracked: set[str],
                           symbol_kind: Callable[[str, str], str | None],
                           read_file: Callable[[str], str | None],
                           is_product: Callable[[str, str], bool],
                           min_kept: int = MIN_DOMAINS) -> tuple[list[dict], list[dict]]:
    """Keep evidence grounded in product code and domains with a surviving symbol anchor.

    A directory item must name a tracked directory or file. Every other item must name a
    tracked product file and a symbol the graph holds there or text that occurs in it
    (codex r1: a file name alone proves nothing). A failing item is dropped with its reason;
    a domain with no remaining symbol item is dropped. Return copies and every drop; the
    whole catalog is refused only below `min_kept` (MIN_DOMAINS; 0 for added areas, each of
    which stands or falls on its own).

    The host supplies tracked files as a set and checks symbols against its graph. The seat
    passes a worktree view for file membership and directories whose symbol lookup answers
    "" (presence is the host's check).
    """
    dirs = {p.rsplit("/", 1)[0] for p in tracked if "/" in p} if isinstance(tracked, set) else None
    kept, dropped = [], []
    for d in domains:
        evidence = []
        anchored = False
        for j, e in enumerate(d["evidence"]):
            path = e["file"].strip().replace("\\", "/").rstrip("/")
            why = None
            sym = (e.get("symbol") or "").strip()
            text = (e.get("text") or "").strip()
            if e["kind"] == "directory":
                exists = (any(x == path or x.startswith(path + "/") for x in dirs)
                          or path in tracked) if dirs is not None else (
                              tracked.is_dir(path) or path in tracked)
                if not exists:
                    why = f"no file the repository tracks is under {path!r}"
            elif path not in tracked:
                why = f"{path!r} is not a file the repository tracks"
            elif not sym and not text:
                why = (f"name the symbol (or the route or verb text) in {path!r} "
                       "that shows the area")
            else:
                kind = symbol_kind(path, sym) if sym else ""
                if sym and kind is None:
                    why = f"the code graph has no symbol {sym!r} in {path!r}"
                elif not is_product(path, kind or ""):
                    why = f"{path!r} is a test, data or document file, not product code"
                elif text:
                    body = read_file(path)
                    if body is None or text not in body:
                        why = f"{text!r} does not occur in {path!r}"
            if why:
                dropped.append({"domain": d["id"], "index": j, "why": why})
            else:
                evidence.append(dict(e))
                anchored = anchored or (e["kind"] != "directory" and bool(sym))
        if anchored:
            kept.append({**d, "evidence": evidence})
        else:
            dropped.append({"domain": d["id"], "index": None,
                            "why": "no remaining evidence names a symbol the code graph holds"})
    if len(kept) < min_kept:
        details = "; ".join(f"{r['domain']} evidence[{r['index']}]: {r['why']}"
                            for r in dropped[:5])
        if len(dropped) > 5:
            details += f"; and {len(dropped) - 5} more"
        raise CatalogRefused(f"only {len(kept)} business domains remain; need {MIN_DOMAINS}; "
                             f"dropped: {details}", dropped)
    return kept, dropped


def check_additions(stored: list[dict], added: Any,
                    directory_slugs: set[str] | None = None, room: int | None = None) -> list[dict]:
    """The areas a later page adds to a stored catalog (wicked-garden#1537: a catalog proposed
    from the batch programs had no area for sign-on, menus and user administration, so their
    rules were forced into the nearest one and a review could only ask to strip the picks).
    The stored domains stay as they are; each added one has a proposal's shape, a new id and a
    new name, up to MAX_DOMAINS in all. Raises CatalogRefused naming the first problem."""
    if room is None:
        room = MAX_DOMAINS - len(stored)
    if len(stored) >= MAX_DOMAINS:
        raise CatalogRefused(f"business_domains: the repository's catalog already has "
                             f"{len(stored)} domains, the most it may hold; pick from it")
    if room <= 0:
        raise CatalogRefused("business_domains: this repository's catalog takes no added area "
                             "(it was rebuilt from the code graph, with no catalog file to "
                             "extend); pick from it")
    check_catalog_shape(added, directory_slugs, count=(1, room),
                        verb="add to the stored catalog")
    ids = {d["id"] for d in stored}
    names = {slug(d["name"]) for d in stored}
    for i, d in enumerate(added):
        if d["id"] in ids:
            raise CatalogRefused(f"business_domains[{i}].id {d['id']!r} is already a domain of the "
                                 "stored catalog; a page adds areas, never changes one")
        if slug(d["name"]) in names:
            raise CatalogRefused(f"business_domains[{i}].name {d['name']!r} repeats a domain of "
                                 "the stored catalog")
    return added


def check_pick(domain: Any, confidence: Any, ids: set[str]) -> str | None:
    """Why a rule's (or an assignment's) domain pick is unusable, or None."""
    if not isinstance(domain, str) or domain not in ids:
        return f"domain {str(domain)[:60]!r} is not an id of the repository's business domains"
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
            or not 0 <= confidence <= 1 or not math.isfinite(confidence):
        return "domain_confidence is not a number in [0,1]"
    return None


def check_assignments(items: Any, ids: set[str], max_items: int = 20000
                      ) -> tuple[list[dict], list[dict]]:
    """(accepted, refused) for the seat's `assignments` list (first entry per symbol wins)."""
    if not isinstance(items, list):
        raise CatalogRefused(f"assignments is {type(items).__name__}, expected a list")
    if len(items) > max_items:
        raise CatalogRefused(f"assignments has {len(items)} entries, the limit is {max_items}")
    accepted: list[dict] = []
    refused: list[dict] = []
    seen: set[str] = set()
    for i, a in enumerate(items):
        sid = a.get("symbol_id") if isinstance(a, dict) else None
        why = None
        if not isinstance(a, dict):
            why = f"is {type(a).__name__}, expected an object"
        elif set(a) - _ASSIGN_KEYS:
            why = f"unknown key(s) {sorted(set(a) - _ASSIGN_KEYS)!r}"
        elif not isinstance(sid, str) or not sid or len(sid) > 1000:
            why = "symbol_id is not a symbol id"
        elif sid in seen:
            why = "repeats a symbol an earlier assignment already covers"
        else:
            why = check_pick(a.get("domain"), a.get("confidence"), ids)
        if why:
            refused.append({"index": i, "symbol_id": sid if isinstance(sid, str) else None,
                            "why": why})
            continue
        seen.add(sid)
        accepted.append(a)
    return accepted, refused


def annotation_value(domain: dict) -> str:
    """The annotation value wicked-core reads: compact, key-sorted JSON."""
    return json.dumps({"id": domain["id"], "name": domain["name"].strip(),
                       "purpose": domain["purpose"].strip()},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def not_product(file: str, kind: str = "") -> bool:
    """A test, data or document file (wicked-core's product-file predicate, as the extraction
    harness mirrors it): never a requirement to assign, never evidence of an area."""
    from domain import extract_loop  # the harness owns the predicate; imported late (no cycle)
    return extract_loop.unconfirmed_reason(file, True, kind) is not None


def repo_reader(repo_root: str, limit: int = 4 * 1024 * 1024) -> Callable[[str], str | None]:
    """read(path) of a tracked file under the registered repository (None when it cannot be read
    as text, is a link or lies outside the root)."""
    root = Path(repo_root).resolve()

    def read(rel: str) -> str | None:
        try:
            path = (root / rel)
            if path.is_symlink():
                return None
            real = path.resolve()
            if root not in real.parents or not real.is_file() or real.stat().st_size > limit:
                return None
            return real.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            return None
    return read


# --- the catalog on the host ---------------------------------------------------------------------

def catalog_path(db: str) -> Path:
    return Path(db).resolve().parent / DIR_NAME / FILE_NAME


def catalog_file(db: str) -> list[dict] | None:
    """The catalog the host's file holds, or None (no file, unreadable, or outside its shape)."""
    try:
        doc = json.loads(catalog_path(db).read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("schema") == CATALOG_SCHEMA:
            return check_catalog_shape(doc.get("domains"))
    except (OSError, ValueError):
        pass
    return None


def room_to_add(db: str) -> int:
    """How many areas a page may add (wicked-garden#1537): the room left in the catalog FILE. A
    catalog rebuilt from the store's annotations has no evidence to keep, so it takes none
    (codex r1: prepare offered additions that apply could not store)."""
    stored = catalog_file(db)
    return max(0, MAX_DOMAINS - len(stored)) if stored else 0


def load_catalog(db: str) -> list[dict] | None:
    """The repository's stored catalog, else one rebuilt from the store's annotations (the file is
    the record; the annotations are what the graph reads), else None."""
    stored = catalog_file(db)
    if stored is not None:
        return stored
    found: dict[str, dict] = {}
    for _sid, value, _conf in _store_rows(db, ANN_TYPE):
        try:
            d = json.loads(value)
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"] not in found \
                and isinstance(d.get("name"), str) and isinstance(d.get("purpose"), str):
            found[d["id"]] = {"id": d["id"], "name": d["name"], "purpose": d["purpose"],
                              "evidence": []}
    return [found[k] for k in sorted(found)] or None


def save_catalog(db: str, domains: list[dict], run_id: str = "") -> list[dict]:
    """Store the first catalog exclusively and return the catalog that won ([] if unreadable)."""
    path = catalog_path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": CATALOG_SCHEMA, "run": run_id, "domains": domains}
    fd, tmp = tempfile.mkstemp(prefix=".catalog-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        try:
            os.link(tmp, path)
        except FileExistsError:
            return load_catalog(db) or []
        return domains
    finally:
        os.unlink(tmp)


def extend_catalog(db: str, added: list[dict], run_id: str = "") -> list[dict]:
    """Add `added` to the stored catalog file and return the catalog now stored ([] when there is
    no readable catalog file to extend). An id or name another page added meanwhile keeps that
    page's domain; past MAX_DOMAINS the rest are not added. Replaced in one rename."""
    path = catalog_path(db)
    current = catalog_file(db)
    if not current:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ids, names = {d["id"] for d in current}, {slug(d["name"]) for d in current}
    fresh = []
    for d in added:
        if d["id"] in ids or slug(d["name"]) in names or len(current) + len(fresh) >= MAX_DOMAINS:
            continue
        ids.add(d["id"])
        names.add(slug(d["name"]))
        fresh.append(d)
    if not fresh:
        return current
    catalog = current + fresh
    fd, tmp = tempfile.mkstemp(prefix=".catalog-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({**doc, "domains": catalog, "extended": run_id}, f, ensure_ascii=False,
                      indent=1)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    return catalog


# --- the store, read-only ------------------------------------------------------------------------

def _connect(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{quote(str(db))}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _store_rows(db: str, ann_type: str) -> list[tuple[str, str, float]]:
    """(symbol, value, confidence) of every annotation of `ann_type`; [] when the store has none."""
    try:
        c = _connect(db)
    except sqlite3.Error:
        return []
    try:
        rows = c.execute(
            "SELECT s.sym AS sym, a.value AS value, a.confidence AS conf FROM annotations a "
            "JOIN symbols s ON s.sid = a.node_sym WHERE a.type = ? ORDER BY a.id", (ann_type,))
        return [(r["sym"], r["value"], float(r["conf"])) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def symbol_lookup(db: str) -> Callable[[str, str], str | None]:
    """symbol_kind(file, name) over the store's nodes: the kind of a node named `name` in `file`
    ("" when the store records none), or None when there is no such node."""
    kinds: dict[tuple[str, str], str] = {}
    try:
        c = _connect(db)
        try:
            try:
                rows = c.execute("SELECT name, file, kind FROM nodes").fetchall()
            except sqlite3.OperationalError:  # a store without the kind column
                rows = c.execute("SELECT name, file, '' AS kind FROM nodes").fetchall()
            for r in rows:
                key = (str(r["file"]).replace("\\", "/"), str(r["name"]))
                kinds.setdefault(key, str(r["kind"] or "").strip('"'))
        finally:
            c.close()
    except sqlite3.Error:
        pass
    return lambda file, name: kinds.get((file, name))


def resolved_without_domain(db: str, tracked: set[str], threshold: float,
                            not_product: Callable[[str, str], bool],
                            limit: int = MAX_ASSIGN) -> tuple[list[dict], int]:
    """Resolved requirements in product code that carry no business domain yet: the backfill the
    seat assigns (an existing map's rules were stated before any catalog). Returns (the first
    `limit` in symbol order as `{symbol_id, name, file, statement}`, how many there are)."""
    from domain import extract_loop

    best: dict[str, tuple[float, str]] = {}
    for sid, value, conf in _store_rows(db, "business_rule"):
        if conf >= threshold and value.strip() and conf >= best.get(sid, (-1.0, ""))[0]:
            best[sid] = (conf, value)
    have = {sid for sid, _v, _c in _store_rows(db, ANN_TYPE)}
    nodes: dict[str, tuple[str, str, str, str | None]] = {}
    try:
        c = _connect(db)
        try:
            try:
                rows = c.execute("SELECT s.sym AS sym, n.name AS name, n.file AS file, n.kind AS "
                                 "kind, n.data AS data, n.requirement AS req, n.requirement_validated AS ok "
                                 "FROM nodes n JOIN symbols s ON s.sid = n.symbol").fetchall()
            except sqlite3.OperationalError:  # an older or test store without those columns
                rows = c.execute("SELECT s.sym AS sym, n.name AS name, n.file AS file, '' AS kind, "
                                 "NULL AS data, NULL AS req, 0 AS ok FROM nodes n "
                                 "JOIN symbols s ON s.sid = n.symbol").fetchall()
            e2e_dirs = extract_loop.e2e_test_dirs(
                r[0] for r in c.execute("SELECT DISTINCT file FROM nodes"))
            for r in rows:
                nodes[r["sym"]] = (str(r["name"]), str(r["file"]),
                                   str(r["kind"] or "").strip('"'), r["data"])
                # A validated requirement resolves a node too (core's classify_node).
                if r["ok"] and (r["req"] or "").strip() and r["sym"] not in best:
                    best[r["sym"]] = (1.0, str(r["req"]))
        finally:
            c.close()
    except sqlite3.Error:
        return [], 0
    out = []
    for sid in sorted(best):
        if sid in have or sid not in nodes:
            continue
        name, file, kind, data = nodes[sid]
        if (file not in tracked or not_product(file, kind)
                or extract_loop.not_counted(file, data, e2e_dirs)):
            continue
        out.append({"symbol_id": sid, "name": name, "file": file,
                    "statement": best[sid][1][:400]})
    return out[:limit], len(out)


def worklist_block(db: str, tracked: set[str], threshold: float,
                   not_product: Callable[[str, str], bool],
                   skip: set[str] = frozenset()) -> tuple[dict, list[dict]]:
    """The worklist's `business_domains` block and its `assign` list (less `skip`: the page's
    own units, whose rule picks their domain)."""
    catalog = load_catalog(db)
    assign, total = resolved_without_domain(db, tracked, threshold, not_product)
    assign = [a for a in assign if a["symbol_id"] not in skip]
    block = {
        "propose": catalog is None,
        "catalog": catalog,
        # How many areas a page may still add to the stored catalog (wicked-garden#1537).
        "add": room_to_add(db) if catalog else 0,
        "min": MIN_DOMAINS,
        "max": MAX_DOMAINS,
        "evidence_kinds": sorted(EVIDENCE_KINDS),
        "unassigned_resolved": total,
        "directory_names": sorted(directory_names(tracked))[:MAX_DIRECTORY_NAMES],
    }
    return block, assign
