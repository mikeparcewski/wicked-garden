#!/usr/bin/env python3
"""inject_edges.py — materialize wicked-garden's INJECTED relationships into the
codegraph symbol graph.

codegraph (the adopted static engine) resolves literal references — imports,
calls, instantiations. But this plugin's load-bearing relationships are
*injected*: wired by a shared string through a registry, never by a literal
symbol reference, so neither grep nor a static call-graph can see them:

  - **bus**: a producer ``emit_event("wicked.gate.decided")`` and a consumer that
    subscribes to ``wicked.gate.decided`` in ``_bus_consumers.json`` never
    reference each other — the event string is the only link.
  - (next: command→agent via ``subagent_type``; agent→tool via tool-capabilities.)

This reads codegraph's SQLite graph + the plugin's wiring registries, computes
the producer→consumer edges, and INSERTs them with ``provenance='injected:bus'``
so blast-radius/impact traversals (which walk incoming edges) surface the
consumer as a dependent of the producer. The codegraph engine + this extractor
together are the relationship graph blast-radius/lineage/patch consume.

Stdlib-only. Idempotent (re-run replaces injected edges). Read-the-registry, not
the LLM — deterministic.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

_REPO = Path(__file__).resolve().parents[2]
_CONSUMERS = _REPO / "scripts" / "_bus_consumers.json"
_EVENT_RE = re.compile(r"""["']((?:wicked|wg)\.[a-z0-9_]+(?:\.[a-z0-9_]+)+)["']""")
_INJECTED_PROVENANCE = "injected:bus"


def _consumers() -> List[Tuple[str, str]]:
    """[(event_filter, consumer_module_relpath), ...] from the registry."""
    if not _CONSUMERS.exists():
        return []
    data = json.loads(_CONSUMERS.read_text(encoding="utf-8"))
    out = []
    for c in data.get("consumers", []):
        ev, mod = c.get("event_filter"), c.get("module")
        if ev and mod:
            out.append((ev, mod))
    return out


def _producers_for(events: Set[str]) -> Dict[str, Set[str]]:
    """event -> {producer file relpaths}. A producer is any .py under scripts/
    that uses the literal event string and is NOT the consumer-registry plumbing
    (so the edge is producer→consumer, not registry→itself)."""
    by_event: Dict[str, Set[str]] = {e: set() for e in events}
    for py in (_REPO / "scripts").rglob("*.py"):
        if "__pycache__" in py.parts or py.name.endswith("_bus_consumers.py"):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = py.relative_to(_REPO).as_posix()
        for ev in _EVENT_RE.findall(text):
            if ev in by_event:
                by_event[ev].add(rel)
    return by_event


def _file_node_id(conn: sqlite3.Connection, relpath: str) -> str | None:
    """codegraph file node ids are 'file:<relpath>'. Confirm it exists."""
    nid = f"file:{relpath}"
    row = conn.execute("SELECT 1 FROM nodes WHERE id = ?", (nid,)).fetchone()
    return nid if row else None


def inject(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        # idempotent: clear prior injected bus edges
        conn.execute("DELETE FROM edges WHERE provenance = ?", (_INJECTED_PROVENANCE,))
        consumers = _consumers()
        events = {ev for ev, _ in consumers}
        producers = _producers_for(events)
        added, skipped = 0, 0
        for ev, consumer_mod in consumers:
            tgt = _file_node_id(conn, consumer_mod)
            if tgt is None:
                skipped += 1
                continue
            for prod in sorted(producers.get(ev, set())):
                if prod == consumer_mod:
                    continue
                src = _file_node_id(conn, prod)
                if src is None:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO edges (source, target, kind, metadata, provenance) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (src, tgt, "references",
                     json.dumps({"injected": "bus", "event": ev}),
                     _INJECTED_PROVENANCE),
                )
                added += 1
        conn.commit()
        return {"edges_added": added, "skipped": skipped, "consumers": len(consumers)}
    finally:
        conn.close()


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else _REPO / ".codegraph" / "codegraph.db"
    if not db.exists():
        print(json.dumps({"error": f"codegraph db not found at {db}; run `codegraph index` first"}))
        return 1
    print(json.dumps(inject(db), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
