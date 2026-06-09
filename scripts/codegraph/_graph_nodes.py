#!/usr/bin/env python3
"""_graph_nodes.py — self-noding helpers for the injected-edge extractors.

codegraph indexes *code* (it parses source with tree-sitter). wicked-garden's
load-bearing relationships, though, are wired between **markdown** files —
``commands/<d>/<c>.md`` dispatches to ``agents/<d>/<a>.md`` via a ``subagent_type``
string; an agent declares a ``capability`` in YAML. codegraph never creates nodes
for those .md files (or for a virtual capability), so an injected edge had nothing
to anchor to and every edge was skipped (issue #916).

These helpers let an extractor **self-node**: create the node it needs (idempotently)
rather than requiring codegraph to have indexed it. Real code files that codegraph
already indexed are untouched (``INSERT OR IGNORE`` is a no-op when the node exists),
so the injected graph composes with the static one in the same ``nodes``/``edges``
tables — exactly the co-location ADR 0001 specified.

Stdlib-only. The schema's NOT NULL columns are all populated (the original
capability-node insert omitted them — a latent constraint violation).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

# Every column the codegraph `nodes` table requires NOT NULL, beyond the ones we set.
_INSERT_NODE = (
    "INSERT OR IGNORE INTO nodes "
    "(id, kind, name, qualified_name, file_path, language, "
    " start_line, end_line, start_column, end_column, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)"
)


def _now_ms() -> int:
    return int(time.time() * 1000)


def ensure_file_node(conn: sqlite3.Connection, relpath: str,
                     *, language: str = "markdown") -> str:
    """Ensure a ``file:<relpath>`` node exists; return its id.

    For a .md command/agent file codegraph skipped, this creates a synthetic file
    node so dispatch/capability edges can anchor. For a real source file codegraph
    already indexed, the INSERT OR IGNORE is a no-op (the real node is preserved)."""
    nid = f"file:{relpath}"
    conn.execute(_INSERT_NODE,
                 (nid, "file", Path(relpath).name, relpath, relpath, language,
                  1, 1, _now_ms()))
    return nid


def ensure_virtual_node(conn: sqlite3.Connection, node_id: str, kind: str,
                        name: str, *, file_path: str | None = None) -> str:
    """Ensure a synthetic non-file node (e.g. ``capability:<name>``) exists; return id.

    Populates every NOT NULL column the schema demands (the original capability
    insert set only id/kind/name/file_path and would violate the constraint)."""
    conn.execute(_INSERT_NODE,
                 (node_id, kind, name, name, file_path or node_id, "virtual",
                  0, 0, _now_ms()))
    return node_id


__all__ = ["ensure_file_node", "ensure_virtual_node"]
