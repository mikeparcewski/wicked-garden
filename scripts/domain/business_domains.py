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
    fixes). A catalog that fails is refused whole, and the page's rules apply without a domain;
  * once a catalog is stored for the repository it is the one every later page picks from: a page
    cannot rename or replace it (ids stay stable across pages and runs);
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


def check_catalog_shape(domains: Any, directory_slugs: set[str] | None = None) -> list[dict]:
    """The catalog's closed shape: 3 to 9 domains, unique ids and names, a one-line purpose and
    1 to 8 evidence items each. With `directory_slugs`, a domain named after a directory is
    refused too. Raises CatalogRefused naming the first problem; returns the domains."""
    if not isinstance(domains, list):
        raise CatalogRefused(f"business_domains is {type(domains).__name__}, expected a list")
    if not MIN_DOMAINS <= len(domains) <= MAX_DOMAINS:
        raise CatalogRefused(f"business_domains has {len(domains)} domain(s); propose "
                             f"{MIN_DOMAINS} to {MAX_DOMAINS}")
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
                           is_product: Callable[[str, str], bool]) -> None:
    """Every evidence item must point at code the host can see, and say something the code
    shows (codex r1: a file name alone proves nothing):

      * a `directory` item names a directory holding a file git tracks;
      * any other item names a product-code file git tracks (not a test, data or document file)
        and carries a `symbol` the code graph holds in that file or a `text` (a route, a CLI verb)
        that occurs in the file as the host reads it;
      * every domain has at least one item whose `symbol` the code graph holds.

    Whether that code is really the area's is the page review's question; this is the floor.
    Raises CatalogRefused naming the first item that fails."""
    dirs = {p.rsplit("/", 1)[0] for p in tracked if "/" in p}
    for i, d in enumerate(domains):
        anchored = False
        for j, e in enumerate(d["evidence"]):
            at = f"business_domains[{i}].evidence[{j}]"
            path = e["file"].strip().replace("\\", "/").rstrip("/")
            if e["kind"] == "directory":
                if not any(x == path or x.startswith(path + "/") for x in dirs) and path not in tracked:
                    raise CatalogRefused(f"{at}: no file the repository tracks is under {path!r}")
                continue
            if path not in tracked:
                raise CatalogRefused(f"{at}: {path!r} is not a file the repository tracks")
            sym = (e.get("symbol") or "").strip()
            text = (e.get("text") or "").strip()
            if not sym and not text:
                raise CatalogRefused(f"{at}: name the symbol (or the route or verb text) in "
                                     f"{path!r} that shows the area")
            kind = symbol_kind(path, sym) if sym else ""
            if sym and kind is None:
                raise CatalogRefused(f"{at}: the code graph has no symbol {sym!r} in {path!r}")
            # Core's product predicate, with the node's kind (an extracted `Rule` in a flow or
            # policy file is product behaviour whatever its extension; codex r2).
            if not is_product(path, kind or ""):
                raise CatalogRefused(f"{at}: {path!r} is a test, data or document file, not "
                                     "product code")
            anchored = anchored or bool(sym)
            if text:
                body = read_file(path)
                if body is None or text not in body:
                    raise CatalogRefused(f"{at}: {text!r} does not occur in {path!r}")
        if not anchored:
            raise CatalogRefused(f"business_domains[{i}] cites no symbol the code graph holds; "
                                 "name at least one entry point, handler or public-API symbol")


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


def load_catalog(db: str) -> list[dict] | None:
    """The repository's stored catalog, else one rebuilt from the store's annotations (the file is
    the record; the annotations are what the graph reads), else None."""
    try:
        doc = json.loads(catalog_path(db).read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("schema") == CATALOG_SCHEMA:
            return check_catalog_shape(doc.get("domains"))
    except (OSError, ValueError):
        pass
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


def save_catalog(db: str, domains: list[dict], run_id: str = "") -> None:
    path = catalog_path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": CATALOG_SCHEMA, "run": run_id, "domains": domains}
    fd, tmp = tempfile.mkstemp(prefix=".catalog-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    best: dict[str, tuple[float, str]] = {}
    for sid, value, conf in _store_rows(db, "business_rule"):
        if conf >= threshold and value.strip() and conf >= best.get(sid, (-1.0, ""))[0]:
            best[sid] = (conf, value)
    have = {sid for sid, _v, _c in _store_rows(db, ANN_TYPE)}
    nodes: dict[str, tuple[str, str, str]] = {}
    try:
        c = _connect(db)
        try:
            try:
                rows = c.execute("SELECT s.sym AS sym, n.name AS name, n.file AS file, n.kind AS "
                                 "kind, n.requirement AS req, n.requirement_validated AS ok "
                                 "FROM nodes n JOIN symbols s ON s.sid = n.symbol").fetchall()
            except sqlite3.OperationalError:  # an older or test store without those columns
                rows = c.execute("SELECT s.sym AS sym, n.name AS name, n.file AS file, '' AS kind, "
                                 "NULL AS req, 0 AS ok FROM nodes n "
                                 "JOIN symbols s ON s.sid = n.symbol").fetchall()
            for r in rows:
                nodes[r["sym"]] = (str(r["name"]), str(r["file"]), str(r["kind"] or "").strip('"'))
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
        name, file, kind = nodes[sid]
        if file not in tracked or not_product(file, kind):
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
        "min": MIN_DOMAINS,
        "max": MAX_DOMAINS,
        "evidence_kinds": sorted(EVIDENCE_KINDS),
        "unassigned_resolved": total,
        "directory_names": sorted(directory_names(tracked))[:MAX_DIRECTORY_NAMES],
    }
    return block, assign
