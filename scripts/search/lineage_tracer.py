#!/usr/bin/env python3
"""
Lineage Tracer for wicked-search.

Traces data lineage paths from source symbols to sink symbols using BFS traversal.
Supports upstream (source → sink) and downstream (sink → source) tracing.

Features:
- BFS traversal with configurable max_depth
- Cycle detection to prevent infinite loops
- Gap detection for incomplete paths
- Confidence propagation (min confidence in path)
- Multiple output formats (table, json, mermaid)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque


class Confidence(str, Enum):
    """Confidence levels for lineage paths."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFERRED = "inferred"

    @classmethod
    def min_confidence(cls, *levels: str) -> str:
        """Return the minimum confidence level."""
        order = [cls.INFERRED.value, cls.LOW.value, cls.MEDIUM.value, cls.HIGH.value]
        min_idx = len(order) - 1
        for level in levels:
            if level in order:
                idx = order.index(level)
                min_idx = min(min_idx, idx)
        return order[min_idx]


@dataclass
class LineageStep:
    """A single step in a lineage path."""
    symbol_id: str
    symbol_name: str
    symbol_type: str
    layer: str
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    ref_type: Optional[str] = None  # Reference type from previous step
    confidence: str = "medium"


@dataclass
class LineagePath:
    """A complete lineage path from source to sink."""
    id: str
    source_id: str
    sink_id: str
    steps: List[LineageStep] = field(default_factory=list)
    is_complete: bool = False
    gaps: List[str] = field(default_factory=list)

    @property
    def path_length(self) -> int:
        return len(self.steps)

    @property
    def min_confidence(self) -> str:
        if not self.steps:
            return "low"
        confidences = [s.confidence for s in self.steps if s.confidence]
        return Confidence.min_confidence(*confidences) if confidences else "medium"

    @property
    def path_nodes(self) -> List[str]:
        return [s.symbol_id for s in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "sink_id": self.sink_id,
            "path_length": self.path_length,
            "min_confidence": self.min_confidence,
            "is_complete": self.is_complete,
            "gaps": self.gaps,
            "steps": [
                {
                    "symbol_id": s.symbol_id,
                    "name": s.symbol_name,
                    "type": s.symbol_type,
                    "layer": s.layer,
                    "file": s.file_path,
                    "line": s.line_start,
                    "ref_type": s.ref_type,
                    "confidence": s.confidence,
                }
                for s in self.steps
            ],
        }


# Reference types that represent data flow (for lineage tracing)
LINEAGE_REF_TYPES = {
    "binds_to",      # UI element → data field
    "maps_to",       # Entity field → column
    "calls",         # Method invocation
    "includes",      # File includes
    "returns_view",  # Controller returns view
    "uses_model",    # Controller uses model
    "receives_prop", # Component receives prop
}

# Symbol types that represent endpoints (sinks)
SINK_TYPES = {"column", "table"}

# Symbol types that represent sources
SOURCE_TYPES = {"ui_field", "form_field", "form_binding", "el_expression", "component_prop", "data_binding"}


class LineageTracer:
    """Traces lineage paths through the symbol graph."""

    def __init__(self, db_path: Path):
        """
        Initialize the tracer with a database path.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_symbol(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        """Get symbol by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, type, layer, file_path, line_start FROM symbols WHERE id = ?",
            (symbol_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_outgoing_refs(self, symbol_id: str, ref_types: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Get outgoing references from a symbol."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if ref_types:
            placeholders = ",".join("?" * len(ref_types))
            cursor.execute(
                f"""
                SELECT r.target_id, r.ref_type, r.confidence,
                       s.name, s.type, s.layer, s.file_path, s.line_start
                FROM refs r
                JOIN symbols s ON r.target_id = s.id
                WHERE r.source_id = ? AND r.ref_type IN ({placeholders})
                """,
                (symbol_id, *ref_types)
            )
        else:
            cursor.execute(
                """
                SELECT r.target_id, r.ref_type, r.confidence,
                       s.name, s.type, s.layer, s.file_path, s.line_start
                FROM refs r
                JOIN symbols s ON r.target_id = s.id
                WHERE r.source_id = ?
                """,
                (symbol_id,)
            )

        return [dict(row) for row in cursor.fetchall()]

    def get_incoming_refs(self, symbol_id: str, ref_types: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Get incoming references to a symbol."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if ref_types:
            placeholders = ",".join("?" * len(ref_types))
            cursor.execute(
                f"""
                SELECT r.source_id, r.ref_type, r.confidence,
                       s.name, s.type, s.layer, s.file_path, s.line_start
                FROM refs r
                JOIN symbols s ON r.source_id = s.id
                WHERE r.target_id = ? AND r.ref_type IN ({placeholders})
                """,
                (symbol_id, *ref_types)
            )
        else:
            cursor.execute(
                """
                SELECT r.source_id, r.ref_type, r.confidence,
                       s.name, s.type, s.layer, s.file_path, s.line_start
                FROM refs r
                JOIN symbols s ON r.source_id = s.id
                WHERE r.target_id = ?
                """,
                (symbol_id,)
            )

        return [dict(row) for row in cursor.fetchall()]

    def trace_downstream(
        self,
        source_id: str,
        max_depth: int = 10,
        ref_types: Optional[Set[str]] = None
    ) -> List[LineagePath]:
        """
        Trace lineage downstream from source to sinks.

        Args:
            source_id: Starting symbol ID
            max_depth: Maximum traversal depth
            ref_types: Reference types to follow (default: LINEAGE_REF_TYPES)

        Returns:
            List of lineage paths found
        """
        if ref_types is None:
            ref_types = LINEAGE_REF_TYPES

        source = self.get_symbol(source_id)
        if not source:
            return []

        paths: List[LineagePath] = []
        visited: Set[str] = set()

        # BFS with path tracking
        # Queue: (current_id, current_path, depth)
        queue: deque[Tuple[str, List[LineageStep], int]] = deque()

        initial_step = LineageStep(
            symbol_id=source["id"],
            symbol_name=source["name"],
            symbol_type=source["type"],
            layer=source["layer"],
            file_path=source.get("file_path"),
            line_start=source.get("line_start"),
            confidence="high"
        )
        queue.append((source_id, [initial_step], 0))

        while queue:
            current_id, path, depth = queue.popleft()

            # Cycle detection
            if current_id in visited and depth > 0:
                continue
            visited.add(current_id)

            # Check if we reached a sink
            current_step = path[-1] if path else None
            if current_step and current_step.symbol_type in SINK_TYPES:
                lineage_path = LineagePath(
                    id=f"lineage:{source_id}:{current_id}",
                    source_id=source_id,
                    sink_id=current_id,
                    steps=path,
                    is_complete=True
                )
                paths.append(lineage_path)
                continue

            # Max depth check
            if depth >= max_depth:
                # Record partial path if we hit max depth without finding sink
                if len(path) > 1:
                    lineage_path = LineagePath(
                        id=f"lineage:{source_id}:{current_id}:partial",
                        source_id=source_id,
                        sink_id=current_id,
                        steps=path,
                        is_complete=False,
                        gaps=["max_depth_reached"]
                    )
                    paths.append(lineage_path)
                continue

            # Get outgoing references
            refs = self.get_outgoing_refs(current_id, ref_types)

            if not refs and len(path) > 1:
                # Dead end - record partial path
                lineage_path = LineagePath(
                    id=f"lineage:{source_id}:{current_id}:partial",
                    source_id=source_id,
                    sink_id=current_id,
                    steps=path,
                    is_complete=False,
                    gaps=["no_outgoing_refs"]
                )
                paths.append(lineage_path)
                continue

            for ref in refs:
                target_id = ref["target_id"]
                if target_id not in visited:
                    next_step = LineageStep(
                        symbol_id=target_id,
                        symbol_name=ref["name"],
                        symbol_type=ref["type"],
                        layer=ref["layer"],
                        file_path=ref.get("file_path"),
                        line_start=ref.get("line_start"),
                        ref_type=ref["ref_type"],
                        confidence=ref.get("confidence", "medium")
                    )
                    queue.append((target_id, path + [next_step], depth + 1))

        return paths

    def trace_upstream(
        self,
        sink_id: str,
        max_depth: int = 10,
        ref_types: Optional[Set[str]] = None
    ) -> List[LineagePath]:
        """
        Trace lineage upstream from sink to sources.

        Args:
            sink_id: Ending symbol ID (e.g., database column)
            max_depth: Maximum traversal depth
            ref_types: Reference types to follow (default: LINEAGE_REF_TYPES)

        Returns:
            List of lineage paths found (reversed, source → sink)
        """
        if ref_types is None:
            ref_types = LINEAGE_REF_TYPES

        sink = self.get_symbol(sink_id)
        if not sink:
            return []

        paths: List[LineagePath] = []
        visited: Set[str] = set()

        # BFS with path tracking (following incoming refs)
        queue: deque[Tuple[str, List[LineageStep], int]] = deque()

        initial_step = LineageStep(
            symbol_id=sink["id"],
            symbol_name=sink["name"],
            symbol_type=sink["type"],
            layer=sink["layer"],
            file_path=sink.get("file_path"),
            line_start=sink.get("line_start"),
            confidence="high"
        )
        queue.append((sink_id, [initial_step], 0))

        while queue:
            current_id, path, depth = queue.popleft()

            if current_id in visited and depth > 0:
                continue
            visited.add(current_id)

            # Check if we reached a source
            current_step = path[-1] if path else None
            if current_step and current_step.symbol_type in SOURCE_TYPES:
                # Reverse path so it's source → sink
                reversed_path = list(reversed(path))
                lineage_path = LineagePath(
                    id=f"lineage:{current_id}:{sink_id}",
                    source_id=current_id,
                    sink_id=sink_id,
                    steps=reversed_path,
                    is_complete=True
                )
                paths.append(lineage_path)
                continue

            if depth >= max_depth:
                if len(path) > 1:
                    reversed_path = list(reversed(path))
                    lineage_path = LineagePath(
                        id=f"lineage:{current_id}:{sink_id}:partial",
                        source_id=current_id,
                        sink_id=sink_id,
                        steps=reversed_path,
                        is_complete=False,
                        gaps=["max_depth_reached"]
                    )
                    paths.append(lineage_path)
                continue

            # Get incoming references
            refs = self.get_incoming_refs(current_id, ref_types)

            if not refs and len(path) > 1:
                reversed_path = list(reversed(path))
                lineage_path = LineagePath(
                    id=f"lineage:{current_id}:{sink_id}:partial",
                    source_id=current_id,
                    sink_id=sink_id,
                    steps=reversed_path,
                    is_complete=False,
                    gaps=["no_incoming_refs"]
                )
                paths.append(lineage_path)
                continue

            for ref in refs:
                source_id = ref["source_id"]
                if source_id not in visited:
                    next_step = LineageStep(
                        symbol_id=source_id,
                        symbol_name=ref["name"],
                        symbol_type=ref["type"],
                        layer=ref["layer"],
                        file_path=ref.get("file_path"),
                        line_start=ref.get("line_start"),
                        ref_type=ref["ref_type"],
                        confidence=ref.get("confidence", "medium")
                    )
                    queue.append((source_id, path + [next_step], depth + 1))

        return paths

    def trace(
        self,
        symbol_id: str,
        direction: str = "downstream",
        max_depth: int = 10,
        ref_types: Optional[Set[str]] = None
    ) -> List[LineagePath]:
        """
        Trace lineage in specified direction.

        Args:
            symbol_id: Starting symbol ID
            direction: "downstream" (source→sink), "upstream" (sink→source), or "both"
            max_depth: Maximum traversal depth
            ref_types: Reference types to follow

        Returns:
            List of lineage paths found
        """
        paths = []

        if direction in ("downstream", "both"):
            paths.extend(self.trace_downstream(symbol_id, max_depth, ref_types))

        if direction in ("upstream", "both"):
            paths.extend(self.trace_upstream(symbol_id, max_depth, ref_types))

        return paths

    def save_lineage_paths(self, paths: List[LineagePath]) -> int:
        """
        Save lineage paths to the database.

        Args:
            paths: List of LineagePath objects

        Returns:
            Number of paths saved
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        saved = 0
        for path in paths:
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO lineage_paths
                    (id, source_id, sink_id, path_nodes, path_length, min_confidence, is_complete, gaps, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        path.id,
                        path.source_id,
                        path.sink_id,
                        json.dumps(path.path_nodes),
                        path.path_length,
                        path.min_confidence,
                        1 if path.is_complete else 0,
                        json.dumps(path.gaps),
                    )
                )
                saved += 1
            except Exception as e:
                print(f"Error saving path {path.id}: {e}")

        conn.commit()
        return saved


def format_table(paths: List[LineagePath]) -> str:
    """Format lineage paths as a markdown table."""
    if not paths:
        return "No lineage paths found."

    lines = ["| # | Source | Sink | Steps | Confidence | Complete |",
             "|---|--------|------|-------|------------|----------|"]

    for i, path in enumerate(paths, 1):
        source_name = path.steps[0].symbol_name if path.steps else "?"
        sink_name = path.steps[-1].symbol_name if path.steps else "?"
        complete = "✓" if path.is_complete else "✗"
        lines.append(f"| {i} | {source_name} | {sink_name} | {path.path_length} | {path.min_confidence} | {complete} |")

    return "\n".join(lines)


def format_mermaid(paths: List[LineagePath]) -> str:
    """Format lineage paths as a Mermaid flowchart."""
    if not paths:
        return "graph LR\n  empty[No paths found]"

    lines = ["graph LR"]
    seen_nodes = set()
    seen_edges = set()

    for path in paths:
        for i, step in enumerate(path.steps):
            # Add node
            node_id = step.symbol_id.replace(".", "_").replace("::", "_")
            if node_id not in seen_nodes:
                label = f"{step.symbol_name}<br/>{step.symbol_type}"
                lines.append(f"  {node_id}[\"{label}\"]")
                seen_nodes.add(node_id)

            # Add edge to next step
            if i < len(path.steps) - 1:
                next_step = path.steps[i + 1]
                next_id = next_step.symbol_id.replace(".", "_").replace("::", "_")
                edge_key = f"{node_id}->{next_id}"
                if edge_key not in seen_edges:
                    ref_type = next_step.ref_type or ""
                    lines.append(f"  {node_id} -->|{ref_type}| {next_id}")
                    seen_edges.add(edge_key)

    return "\n".join(lines)


def main():
    """CLI entry point for lineage tracing."""
    import argparse

    parser = argparse.ArgumentParser(description="Trace lineage paths through symbol graph")
    parser.add_argument("symbol_id", help="Symbol ID to trace from")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--direction", choices=["downstream", "upstream", "both"], default="downstream",
                        help="Direction to trace (default: downstream)")
    parser.add_argument("--depth", type=int, default=10, help="Maximum traversal depth (default: 10)")
    parser.add_argument("--format", choices=["table", "json", "mermaid"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--save", action="store_true", help="Save paths to database")

    args = parser.parse_args()

    tracer = LineageTracer(Path(args.db))

    try:
        paths = tracer.trace(args.symbol_id, args.direction, args.depth)

        if args.save:
            saved = tracer.save_lineage_paths(paths)
            print(f"Saved {saved} lineage paths to database.")

        if args.format == "json":
            print(json.dumps([p.to_dict() for p in paths], indent=2))
        elif args.format == "mermaid":
            print(format_mermaid(paths))
        else:
            print(format_table(paths))

            # Print detailed steps for each path
            for i, path in enumerate(paths, 1):
                print(f"\n### Path {i}: {path.source_id} → {path.sink_id}")
                print(f"Confidence: {path.min_confidence}, Complete: {path.is_complete}")
                if path.gaps:
                    print(f"Gaps: {', '.join(path.gaps)}")
                print("\nSteps:")
                for j, step in enumerate(path.steps):
                    ref_info = f" ({step.ref_type})" if step.ref_type else ""
                    loc = f" @ {step.file_path}:{step.line_start}" if step.file_path else ""
                    print(f"  {j+1}. [{step.layer}] {step.symbol_name} ({step.symbol_type}){ref_info}{loc}")

    finally:
        tracer.close()


if __name__ == "__main__":
    main()
