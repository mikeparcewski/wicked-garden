#!/usr/bin/env python3
"""estate_db.py — adapt a wicked-estate SQLite store into the symbol-graph DB
wicked-patch expects (the `--db`).

ADR 0005 (retarget inventory entry A3): the code graph re-homed from wicked-brain's
codegraph artifact (`.codegraph/codegraph.db`, retired) to wicked-estate. Estate's
store IS SQLite, so this adapter reads it directly, read-only — no estate binary,
MCP server, or network needed at translation time. This replaces the brain-era
`codegraph_db.py`; the rest of the patch family (patch.py, PropagationEngine,
generators) consumes the translated `--db` and is unchanged.

Read contract (pinned by a schema probe at open — see `_REQUIRED_SCHEMA`):

  symbols(sid INTEGER PK, sym TEXT UNIQUE)     -- SymbolId intern table
  nodes(symbol -> sid, name, kind, file, data) -- `kind` is serde_json-encoded
                                               --   ('"function"' / '{"other":"x"}');
                                               -- `data` is the full Node JSON
                                               --   (location.span has 0-BASED lines)
  edges(source -> sid, target -> sid, kind, confidence)
  meta(k, v)                                   -- indexed_version / indexed_root

Schema source of truth: wicked-estate `crates/wicked-estate-store/src/schema.sql`
(the v0.12+ sid-interned shape). Crew governed runs materialize a store at
`.codegraph/estate.db`; `wicked-estate index <repo> --db <path>` builds one on demand.

Mapping (estate -> patch):

  nodes JOIN symbols -> symbols(id,name,type,file_path,line_start,line_end,metadata,layer)
    id         = patch-native "file::Name" (File nodes: the bare path). The patch
                 family's documented id scheme (`Entity.java::EntityName`) and the
                 PropagationEngine's name-based cross-language discovery both key on
                 "::", so estate's SCIP-style ids ("ts-python . . . src/app/Order#")
                 are translated rather than passed through. Collisions (same
                 file+name twice, e.g. overloads) are disambiguated deterministically
                 as "file::Name#2", "file::Name#3", ... in estate-sym order.
    name/type  = nodes.name / decoded nodes.kind ("function", "class", "import", ...)
    file_path  = nodes.file ('' -> NULL for synthetic nodes)
    line_start = data.location.span.start_line + 1   (patch contract is 1-BASED,
    line_end   = data.location.span.end_line + 1      inclusive — generators/base.py)
    metadata   = JSON {"estate_symbol", "language", "signature"?} (PropagationEngine
                 json.loads() this, so it is always a JSON object or NULL)
    layer      = NULL (no estate equivalent)

  edges -> refs(source_id, target_id, ref_type, confidence)   [ALL kinds, decoded]
    kind "calls"                  -> symbol_calls(symbol_id, target_id)
    kind "imports"                -> symbol_imports(symbol_id, target_id)
    kind "references"             -> symbol_refs(source_id, target_id, ref_type)
    kind "extends" / "implements" -> symbol_bases(symbol_id, base_id)
    Estate's edge-direction invariant (source = dependent, target = dependency)
    matches the patch tables' orientation, so no direction flip is needed.
    Endpoints with no node row (edge-only interned symbols) keep the raw estate sym.

  + metadata(key,value): indexed_at (translation time — safety.py freshness check),
    source='wicked-estate', estate_version, estate_root.

Stdlib-only. Deterministic. Rebuilds the patch DB from scratch each run.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# Discovery order for the estate store (after an explicit --estate-db):
# $WICKED_ESTATE_DB, then the crew governed-run location, then the
# wicked-estate MCP default used by scripts/_estate_client.py.
ESTATE_DB_ENV = "WICKED_ESTATE_DB"
ESTATE_DB_CANDIDATES = (".codegraph/estate.db", ".wicked-estate/graph.db")

# The pinned read contract: table -> columns this adapter selects.
_REQUIRED_SCHEMA = {
    "symbols": {"sid", "sym"},
    "nodes": {"symbol", "name", "kind", "file", "data"},
    "edges": {"source", "target", "kind", "confidence"},
    "meta": {"k", "v"},
}

# decoded estate edge kind -> (patch reference table, columns)
_EDGE_TABLE = {
    "references": ("symbol_refs", ("source_id", "target_id", "ref_type")),
    "calls": ("symbol_calls", ("symbol_id", "target_id")),
    "imports": ("symbol_imports", ("symbol_id", "target_id")),
    "extends": ("symbol_bases", ("symbol_id", "base_id")),
    "implements": ("symbol_bases", ("symbol_id", "base_id")),
}


class EstateSchemaError(RuntimeError):
    """The opened SQLite file does not satisfy the wicked-estate store read contract."""


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _probe_schema(src: sqlite3.Connection, db_path: Path) -> None:
    """Verify the estate read contract; fail loud (never a silent mistranslation)."""
    problems = []
    for table, want in _REQUIRED_SCHEMA.items():
        have = _table_columns(src, table)
        if not have:
            problems.append(f"missing table '{table}'")
        elif not want <= have:
            problems.append(f"table '{table}' lacks columns {sorted(want - have)}")
    if not problems:
        return
    contract = ", ".join(
        f"{t}({', '.join(sorted(c))})" for t, c in _REQUIRED_SCHEMA.items()
    )
    hint = ""
    if {"file_path", "start_line"} <= _table_columns(src, "nodes"):
        hint = (
            " The file looks like a brain-era codegraph.db — that surface is retired"
            " (ADR 0005). Rebuild the store with:"
            " wicked-estate index <repo> --db .codegraph/estate.db"
        )
    raise EstateSchemaError(
        f"{db_path} is not a wicked-estate store: {'; '.join(problems)}."
        f" Expected the wicked-estate SQLite store schema (v0.12+ sid-interned graph;"
        f" crates/wicked-estate-store/src/schema.sql): {contract}.{hint}"
    )


def _decode_kind(raw: str) -> str:
    """Decode estate's serde_json-encoded kind column to a plain string.

    Unit variants serialize as '"calls"'; the open Other(String) variant as
    '{"other":"<kind>"}' — injected/non-code kinds surface under their real name.
    """
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return raw  # defensive: estate always JSON-encodes, but never crash on a kind
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and len(val) == 1:
        inner = next(iter(val.values()))
        if isinstance(inner, str):
            return inner
    return raw


def _read_meta(src: sqlite3.Connection) -> Dict[str, str]:
    try:
        return {k: v for k, v in src.execute("SELECT k, v FROM meta")}
    except sqlite3.OperationalError:
        return {}


def resolve_estate_db(explicit: Optional[str] = None) -> Path:
    """Resolve the estate store path: --estate-db > $WICKED_ESTATE_DB > conventional paths.

    When no candidate exists on disk, returns the crew default (.codegraph/estate.db)
    so the caller's not-found error names the canonical location to build.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(ESTATE_DB_ENV)
    if env:
        return Path(env)
    for rel in ESTATE_DB_CANDIDATES:
        candidate = Path(rel)
        if candidate.exists():
            return candidate
    return Path(ESTATE_DB_CANDIDATES[0])


def build_patch_db(estate_db: Path, out_db: Path) -> Dict[str, int]:
    """Translate a wicked-estate SQLite store into a patch-compatible symbol-graph DB.
    Returns counts. Rebuilds out_db from scratch (idempotent)."""
    estate_db = Path(estate_db)
    if not estate_db.exists():
        raise FileNotFoundError(
            f"estate store not found: {estate_db}; build one with"
            f" `wicked-estate index <repo> --db {estate_db}`"
        )
    # POSIX separators keep the sqlite URI valid on Windows paths too.
    src = sqlite3.connect(f"file:{estate_db.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        _probe_schema(src, estate_db)
        meta = _read_meta(src)
        if Path(out_db).exists():
            Path(out_db).unlink()
        dst = sqlite3.connect(str(out_db))
    except Exception:
        src.close()
        raise
    try:
        dst.executescript(
            """
            CREATE TABLE symbols (
              id TEXT PRIMARY KEY, name TEXT, type TEXT, file_path TEXT,
              line_start INTEGER, line_end INTEGER, metadata TEXT, layer TEXT
            );
            CREATE TABLE refs (source_id TEXT, target_id TEXT, ref_type TEXT, confidence REAL);
            CREATE TABLE symbol_refs (source_id TEXT, target_id TEXT, ref_type TEXT);
            CREATE TABLE symbol_calls (symbol_id TEXT, target_id TEXT);
            CREATE TABLE symbol_imports (symbol_id TEXT, target_id TEXT);
            CREATE TABLE symbol_bases (symbol_id TEXT, base_id TEXT);
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX idx_symbols_name ON symbols(name);
            CREATE INDEX idx_symbols_file ON symbols(file_path);
            CREATE INDEX idx_refs_target ON refs(target_id);
            """
        )
        counts = {
            "symbols": 0,
            "refs": 0,
            "symbol_refs": 0,
            "symbol_calls": 0,
            "symbol_imports": 0,
            "symbol_bases": 0,
        }
        # ── nodes → symbols ─────────────────────────────────────────────────
        # Ordered by estate sym so collision disambiguators are deterministic.
        id_map: Dict[str, str] = {}  # estate sym -> patch id
        taken: Dict[str, int] = {}  # patch id base -> occurrences
        for r in src.execute(
            "SELECT s.sym AS sym, n.name AS name, n.kind AS kind,"
            "       n.file AS file, n.data AS data"
            " FROM nodes n JOIN symbols s ON s.sid = n.symbol"
            " ORDER BY s.sym"
        ):
            node_type = _decode_kind(r["kind"])
            file_path = r["file"] or None
            if node_type == "file":
                base = r["name"]
            elif file_path:
                base = f"{file_path}::{r['name']}"
            else:
                base = r["name"]  # synthetic node with no source file
            n = taken.get(base, 0) + 1
            taken[base] = n
            patch_id = base if n == 1 else f"{base}#{n}"
            id_map[r["sym"]] = patch_id

            try:
                data = json.loads(r["data"])
                span = data["location"]["span"]
                # estate spans are 0-based tree-sitter rows; the patch contract
                # (generators/base.py) is 1-based inclusive.
                line_start = int(span["start_line"]) + 1
                line_end = int(span["end_line"]) + 1
            except (ValueError, KeyError, TypeError) as exc:
                raise EstateSchemaError(
                    f"corrupt node data for {r['sym']!r} in {estate_db}: {exc}"
                ) from exc
            sym_meta = {"estate_symbol": r["sym"], "language": data.get("language")}
            if data.get("signature"):
                sym_meta["signature"] = data["signature"]
            dst.execute(
                "INSERT INTO symbols"
                " (id,name,type,file_path,line_start,line_end,metadata,layer)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    patch_id,
                    r["name"],
                    node_type,
                    file_path,
                    line_start,
                    line_end,
                    json.dumps(sym_meta),
                    None,
                ),
            )
            counts["symbols"] += 1
        # ── edges → refs (+ per-kind tables) ────────────────────────────────
        for e in src.execute(
            "SELECT ss.sym AS source_sym, ts.sym AS target_sym,"
            "       e.kind AS kind, e.confidence AS confidence"
            " FROM edges e"
            " JOIN symbols ss ON ss.sid = e.source"
            " JOIN symbols ts ON ts.sid = e.target"
            " ORDER BY ss.sym, ts.sym, e.kind"
        ):
            s = id_map.get(e["source_sym"], e["source_sym"])
            t = id_map.get(e["target_sym"], e["target_sym"])
            kind = _decode_kind(e["kind"])
            dst.execute(
                "INSERT INTO refs (source_id,target_id,ref_type,confidence)"
                " VALUES (?,?,?,?)",
                (s, t, kind, e["confidence"]),
            )
            counts["refs"] += 1
            spec = _EDGE_TABLE.get(kind)
            if spec:
                table, cols = spec
                placeholders = ",".join("?" * len(cols))
                values = (s, t, kind) if len(cols) == 3 else (s, t)
                dst.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    values,
                )
                counts[table] += 1
        # ── provenance ──────────────────────────────────────────────────────
        rows = [
            ("indexed_at", datetime.now(timezone.utc).isoformat()),
            ("source", "wicked-estate"),
            ("estate_version", meta.get("indexed_version", "unknown")),
        ]
        if meta.get("indexed_root"):
            rows.append(("estate_root", meta["indexed_root"]))
        dst.executemany("INSERT INTO metadata (key,value) VALUES (?,?)", rows)
        dst.commit()
        return counts
    finally:
        src.close()
        dst.close()


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Build a wicked-patch --db from a wicked-estate SQLite store."
    )
    p.add_argument(
        "--estate-db",
        default=None,
        help=(
            "Path to the estate store (default: $WICKED_ESTATE_DB, then"
            f" {' then '.join(ESTATE_DB_CANDIDATES)})"
        ),
    )
    p.add_argument("--out", default=".wicked/patch-symbols.db")
    a = p.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        counts = build_patch_db(resolve_estate_db(a.estate_db), out)
    except (FileNotFoundError, EstateSchemaError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps({"out": str(out), **counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
