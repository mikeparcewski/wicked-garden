#!/usr/bin/env python3
"""
knowledge_graph.py — Typed entity + relationship layer over SQLite.

Provides a lightweight knowledge graph for tracking requirements, designs,
tasks, tests, decisions, and their traceability relationships.

Stdlib-only. Cross-platform via pathlib.

Usage (library):
    from knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    e = kg.create_entity("requirement", "Auth must use OAuth2", phase="clarify", project_id="P1")
    kg.create_relationship(e["entity_id"], other_id, "TRACES_TO")
    related = kg.get_related(e["entity_id"], direction="forward")

Usage (CLI):
    knowledge_graph.py create-entity --type requirement --name "Auth must use OAuth2" --phase clarify --project P1
    knowledge_graph.py stats
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VALID_ENTITY_TYPES = frozenset([
    "requirement", "acceptance_criteria", "design_artifact", "task",
    "test_scenario", "evidence", "decision", "incident",
])

VALID_REL_TYPES = frozenset([
    "TRACES_TO", "IMPLEMENTED_BY", "TESTED_BY", "VERIFIES",
    "DECIDED_BY", "BLOCKS", "SUPERSEDES",
])

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    phase TEXT,
    project_id TEXT,
    state TEXT DEFAULT 'DRAFT',
    metadata TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    created_at TEXT,
    created_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id);
CREATE INDEX IF NOT EXISTS idx_entities_phase ON entities(phase);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(rel_type);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_db_path() -> Path:
    from _domain_store import get_local_path
    return get_local_path("wicked-smaht", "knowledge") / "knowledge_graph.db"


class KnowledgeGraph:
    """Lightweight entity + relationship graph backed by SQLite."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or _resolve_db_path()
        self._conn: sqlite3.Connection | None = None

    # -- connection / schema ------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self._db_path), check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
        return self._conn

    # -- Entity CRUD --------------------------------------------------------

    def create_entity(
        self, entity_type: str, name: str, *,
        phase: str | None = None, project_id: str | None = None,
        state: str = "DRAFT", metadata: dict | None = None,
    ) -> dict:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type '{entity_type}'. Must be one of {sorted(VALID_ENTITY_TYPES)}")
        now = _now()
        eid = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO entities (entity_id, entity_type, name, phase, project_id, state, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, entity_type, name, phase, project_id, state, json.dumps(metadata) if metadata else None, now, now),
        )
        conn.commit()
        return self.get_entity(eid)  # type: ignore[return-value]

    def get_entity(self, entity_id: str) -> dict | None:
        row = self._get_conn().execute(
            "SELECT * FROM entities WHERE entity_id = ?", (entity_id,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def update_entity(self, entity_id: str, **fields) -> dict | None:
        allowed = {"name", "phase", "project_id", "state", "metadata", "entity_type"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_entity(entity_id)
        if "entity_type" in updates and updates["entity_type"] not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type '{updates['entity_type']}'")
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata"] = json.dumps(updates["metadata"])
        updates["updated_at"] = _now()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [entity_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE entities SET {sets} WHERE entity_id = ?", vals)
        conn.commit()
        return self.get_entity(entity_id)

    def delete_entity(self, entity_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id,))
        # Also remove dangling relationships
        conn.execute("DELETE FROM relationships WHERE source_id = ? OR target_id = ?", (entity_id, entity_id))
        conn.commit()
        return cur.rowcount > 0

    def list_entities(
        self, *, entity_type: str | None = None, phase: str | None = None,
        project_id: str | None = None, state: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str] = []
        if entity_type:
            clauses.append("entity_type = ?"); params.append(entity_type)
        if phase:
            clauses.append("phase = ?"); params.append(phase)
        if project_id:
            clauses.append("project_id = ?"); params.append(project_id)
        if state:
            clauses.append("state = ?"); params.append(state)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._get_conn().execute(f"SELECT * FROM entities{where}", params).fetchall()
        return [self._row_to_entity(r) for r in rows]

    # -- Relationship CRUD --------------------------------------------------

    def create_relationship(
        self, source_id: str, target_id: str, rel_type: str, *,
        created_by: str | None = None,
    ) -> dict:
        if rel_type not in VALID_REL_TYPES:
            raise ValueError(f"Invalid rel_type '{rel_type}'. Must be one of {sorted(VALID_REL_TYPES)}")
        rid = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO relationships (rel_id, source_id, target_id, rel_type, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rid, source_id, target_id, rel_type, _now(), created_by),
        )
        conn.commit()
        return {"rel_id": rid, "source_id": source_id, "target_id": target_id,
                "rel_type": rel_type, "created_by": created_by}

    def delete_relationship(self, rel_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM relationships WHERE rel_id = ?", (rel_id,))
        conn.commit()
        return cur.rowcount > 0

    # -- Graph queries ------------------------------------------------------

    def get_related(
        self, entity_id: str, *, rel_type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        conn = self._get_conn()
        results: list[dict] = []

        if direction in ("forward", "both"):
            q = "SELECT target_id AS eid, rel_type FROM relationships WHERE source_id = ?"
            p: list[str] = [entity_id]
            if rel_type:
                q += " AND rel_type = ?"; p.append(rel_type)
            for row in conn.execute(q, p).fetchall():
                e = self.get_entity(row["eid"])
                if e:
                    e["_rel_type"] = row["rel_type"]
                    e["_direction"] = "forward"
                    results.append(e)

        if direction in ("reverse", "both"):
            q = "SELECT source_id AS eid, rel_type FROM relationships WHERE target_id = ?"
            p = [entity_id]
            if rel_type:
                q += " AND rel_type = ?"; p.append(rel_type)
            for row in conn.execute(q, p).fetchall():
                e = self.get_entity(row["eid"])
                if e:
                    e["_rel_type"] = row["rel_type"]
                    e["_direction"] = "reverse"
                    results.append(e)

        return results

    def get_subgraph(self, entity_id: str, depth: int = 2) -> dict:
        visited_entities: dict[str, dict] = {}
        visited_rels: dict[str, dict] = {}
        queue: list[tuple[str, int]] = [(entity_id, 0)]
        conn = self._get_conn()

        while queue:
            eid, d = queue.pop(0)
            if eid in visited_entities:
                continue
            entity = self.get_entity(eid)
            if not entity:
                continue
            visited_entities[eid] = entity

            if d >= depth:
                continue

            for row in conn.execute(
                "SELECT * FROM relationships WHERE source_id = ? OR target_id = ?",
                (eid, eid),
            ).fetchall():
                rid = row["rel_id"]
                if rid not in visited_rels:
                    visited_rels[rid] = dict(row)
                neighbor = row["target_id"] if row["source_id"] == eid else row["source_id"]
                if neighbor not in visited_entities:
                    queue.append((neighbor, d + 1))

        return {
            "entities": list(visited_entities.values()),
            "relationships": list(visited_rels.values()),
        }

    # -- Utility ------------------------------------------------------------

    def stats(self) -> dict:
        conn = self._get_conn()
        entity_counts: dict[str, int] = {}
        for row in conn.execute("SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type").fetchall():
            entity_counts[row["entity_type"]] = row["cnt"]
        rel_counts: dict[str, int] = {}
        for row in conn.execute("SELECT rel_type, COUNT(*) as cnt FROM relationships GROUP BY rel_type").fetchall():
            rel_counts[row["rel_type"]] = row["cnt"]
        total_e = sum(entity_counts.values())
        total_r = sum(rel_counts.values())
        return {
            "total_entities": total_e,
            "total_relationships": total_r,
            "entities_by_type": entity_counts,
            "relationships_by_type": rel_counts,
        }

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Internal -----------------------------------------------------------

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> dict:
        d = dict(row)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(description="Knowledge graph entity + relationship store")
    sub = parser.add_subparsers(dest="command")

    # create-entity
    ce = sub.add_parser("create-entity")
    ce.add_argument("--type", required=True, dest="entity_type")
    ce.add_argument("--name", required=True)
    ce.add_argument("--phase")
    ce.add_argument("--project")
    ce.add_argument("--state", default="DRAFT")
    ce.add_argument("--metadata", help="JSON string")

    # get-entity
    ge = sub.add_parser("get-entity")
    ge.add_argument("--id", required=True, dest="entity_id")

    # list-entities
    le = sub.add_parser("list-entities")
    le.add_argument("--type", dest="entity_type")
    le.add_argument("--phase")
    le.add_argument("--project")
    le.add_argument("--state")

    # create-rel
    cr = sub.add_parser("create-rel")
    cr.add_argument("--source", required=True)
    cr.add_argument("--target", required=True)
    cr.add_argument("--type", required=True, dest="rel_type")
    cr.add_argument("--by")

    # related
    rel = sub.add_parser("related")
    rel.add_argument("--id", required=True, dest="entity_id")
    rel.add_argument("--type", dest="rel_type")
    rel.add_argument("--direction", default="both", choices=["forward", "reverse", "both"])

    # subgraph
    sg = sub.add_parser("subgraph")
    sg.add_argument("--id", required=True, dest="entity_id")
    sg.add_argument("--depth", type=int, default=2)

    # stats
    sub.add_parser("stats")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    kg = KnowledgeGraph()
    try:
        result = _dispatch(kg, args)
        sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    finally:
        kg.close()


def _dispatch(kg: KnowledgeGraph, args) -> object:
    if args.command == "create-entity":
        meta = json.loads(args.metadata) if args.metadata else None
        return kg.create_entity(
            args.entity_type, args.name,
            phase=args.phase, project_id=args.project,
            state=args.state, metadata=meta,
        )
    elif args.command == "get-entity":
        return kg.get_entity(args.entity_id)
    elif args.command == "list-entities":
        return kg.list_entities(
            entity_type=args.entity_type, phase=args.phase,
            project_id=args.project, state=args.state,
        )
    elif args.command == "create-rel":
        return kg.create_relationship(
            args.source, args.target, args.rel_type, created_by=args.by,
        )
    elif args.command == "related":
        return kg.get_related(args.entity_id, rel_type=args.rel_type, direction=args.direction)
    elif args.command == "subgraph":
        return kg.get_subgraph(args.entity_id, depth=args.depth)
    elif args.command == "stats":
        return kg.stats()
    return {"error": "Unknown command"}


if __name__ == "__main__":
    _cli()
