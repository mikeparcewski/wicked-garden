#!/usr/bin/env python3
"""codegraph_db.py — adapt codegraph's SQLite into the symbol-graph DB wicked-patch
expects (the `--db`).

This is the payoff of ADR 0001: codegraph builds a column-precise, multi-language
symbol+edge graph; wicked-patch needs a `--db` with a `symbols` table + reference
tables for cross-file refactor (rename/add-field/remove). Nothing produced that
`--db` before, so the patch family was dead-on-arrival. This translates
codegraph's `nodes`/`edges` into the schema `PropagationEngine` + `_resolve_symbol_id`
read, reviving the family without changing patch's engine.

Mapping (codegraph → patch):
  nodes(id,name,kind,file_path,start_line,end_line,metadata)
      -> symbols(id,name,type,file_path,line_start,line_end,metadata,layer)
  edges(source,target,kind):
      kind='references' -> symbol_refs(source_id,target_id,ref_type) + refs
      kind='calls'      -> symbol_calls(symbol_id,target_id)         + refs
      kind='imports'    -> symbol_imports(symbol_id,target_id)       + refs
      (all)             -> refs(source_id,target_id,ref_type,confidence)
  + metadata(key,value) with indexed_at (safety.py freshness check)

Stdlib-only. Deterministic. Rebuilds the patch DB from scratch each run.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# codegraph edge kind -> (patch reference table, columns)
_EDGE_TABLE = {
    "references": ("symbol_refs", ("source_id", "target_id", "ref_type")),
    "calls": ("symbol_calls", ("symbol_id", "target_id")),
    "imports": ("symbol_imports", ("symbol_id", "target_id")),
}


def build_patch_db(codegraph_db: Path, out_db: Path) -> Dict[str, int]:
    """Translate a codegraph SQLite into a patch-compatible symbol-graph DB.
    Returns counts. Rebuilds out_db from scratch (idempotent)."""
    if not Path(codegraph_db).exists():
        raise FileNotFoundError(f"codegraph db not found: {codegraph_db}; run `codegraph index` first")
    src = sqlite3.connect(f"file:{codegraph_db}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    if Path(out_db).exists():
        Path(out_db).unlink()
    dst = sqlite3.connect(str(out_db))
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
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX idx_symbols_name ON symbols(name);
            CREATE INDEX idx_symbols_file ON symbols(file_path);
            CREATE INDEX idx_refs_target ON refs(target_id);
            """
        )
        counts = {"symbols": 0, "refs": 0, "symbol_refs": 0, "symbol_calls": 0, "symbol_imports": 0}
        # codegraph nodes carry no `metadata` column. PropagationEngine does
        # json.loads(metadata) so it MUST be a JSON object (or NULL -> "{}").
        # Pack the useful codegraph fields (signature) as JSON. layer has no
        # codegraph equivalent -> NULL.
        for r in src.execute(
            "SELECT id, name, kind, file_path, start_line, end_line, signature FROM nodes"
        ):
            meta = json.dumps({"signature": r["signature"]}) if r["signature"] else None
            dst.execute(
                "INSERT OR IGNORE INTO symbols (id,name,type,file_path,line_start,line_end,metadata,layer)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (r["id"], r["name"], r["kind"], r["file_path"],
                 r["start_line"], r["end_line"], meta, None),
            )
            counts["symbols"] += 1
        for e in src.execute("SELECT source, target, kind FROM edges"):
            s, t, k = e["source"], e["target"], e["kind"]
            dst.execute("INSERT INTO refs (source_id,target_id,ref_type,confidence) VALUES (?,?,?,?)",
                        (s, t, k, 1.0))
            counts["refs"] += 1
            spec = _EDGE_TABLE.get(k)
            if spec:
                table, cols = spec
                dst.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            (s, t, k) if len(cols) == 3 else (s, t))
                counts[table] += 1
        dst.execute("INSERT INTO metadata (key,value) VALUES ('indexed_at', ?)",
                    (datetime.now(timezone.utc).isoformat(),))
        dst.execute("INSERT INTO metadata (key,value) VALUES ('source', 'codegraph')")
        dst.commit()
        return counts
    finally:
        src.close()
        dst.close()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Build a wicked-patch --db from codegraph's SQLite.")
    p.add_argument("--codegraph-db", default=".codegraph/codegraph.db")
    p.add_argument("--out", default=".wicked/patch-symbols.db")
    a = p.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        counts = build_patch_db(Path(a.codegraph_db), out)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    import json
    print(json.dumps({"out": str(out), **counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
