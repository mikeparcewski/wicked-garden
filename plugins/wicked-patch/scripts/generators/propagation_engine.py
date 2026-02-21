"""
Propagation Engine for wicked-search.

Orchestrates code generation across multiple files using the lineage graph.
When a change is made to a symbol, this engine:
1. Traces all dependent symbols via lineage paths
2. Groups affected symbols by file and language
3. Invokes appropriate generators for each file
4. Aggregates patches into a unified PatchSet

This is the core of the "higher-level" approach to code changes,
automatically propagating changes across all affected code.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

from .base import (
    ChangeSpec,
    ChangeType,
    FieldSpec,
    GeneratorRegistry,
    Patch,
    PatchSet,
)

logger = logging.getLogger(__name__)


@dataclass
class AffectedSymbol:
    """A symbol affected by a change."""
    id: str
    name: str
    type: str
    file_path: str
    line_start: int
    line_end: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    impact_type: str = "direct"  # direct, upstream, downstream
    distance: int = 0  # Hops from the source of change


@dataclass
class PropagationPlan:
    """
    Plan for propagating a change.

    Contains all affected symbols organized by their relationship
    to the source of the change.
    """
    source_symbol: AffectedSymbol
    direct_impacts: List[AffectedSymbol] = field(default_factory=list)
    upstream_impacts: List[AffectedSymbol] = field(default_factory=list)
    downstream_impacts: List[AffectedSymbol] = field(default_factory=list)

    @property
    def all_affected(self) -> List[AffectedSymbol]:
        return [self.source_symbol] + self.direct_impacts + self.upstream_impacts + self.downstream_impacts

    @property
    def files_affected(self) -> Set[str]:
        return {s.file_path for s in self.all_affected if s.file_path}

    def by_file(self) -> Dict[str, List[AffectedSymbol]]:
        """Group affected symbols by file."""
        by_file: Dict[str, List[AffectedSymbol]] = defaultdict(list)
        for symbol in self.all_affected:
            if symbol.file_path:
                by_file[symbol.file_path].append(symbol)
        return dict(by_file)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Source: {self.source_symbol.name} ({self.source_symbol.type})",
            f"Direct impacts: {len(self.direct_impacts)}",
            f"Upstream impacts: {len(self.upstream_impacts)}",
            f"Downstream impacts: {len(self.downstream_impacts)}",
            f"Total files affected: {len(self.files_affected)}",
        ]
        return "\n".join(lines)


class PropagationEngine:
    """
    Engine for propagating changes across the codebase.

    Uses the symbol graph to find all affected symbols, then
    coordinates generators to produce patches for each file.
    """

    # Map change types to how they propagate.
    # include_refs: reference types to follow. Empty set means follow all types.
    # Cross-file ref types from additional tables: calls, imports, extends, uses
    PROPAGATION_RULES = {
        ChangeType.ADD_FIELD: {
            "propagate_downstream": True,   # Add to UI bindings, tests
            "propagate_upstream": False,    # Don't add to callers
            "include_refs": {"binds_to", "maps_to", "uses", "extends", "imports"},
        },
        ChangeType.REMOVE_FIELD: {
            "propagate_downstream": True,   # Remove from UI, tests
            "propagate_upstream": True,     # Update callers
            "include_refs": {"binds_to", "maps_to", "uses", "calls", "extends", "imports"},
        },
        ChangeType.RENAME_FIELD: {
            "propagate_downstream": True,
            "propagate_upstream": True,
            "include_refs": {"binds_to", "maps_to", "uses", "calls", "extends", "imports"},
        },
        ChangeType.MODIFY_FIELD: {
            "propagate_downstream": True,
            "propagate_upstream": False,
            "include_refs": {"binds_to", "maps_to", "extends"},
        },
        ChangeType.ADD_VALIDATION: {
            "propagate_downstream": True,   # Add to UI validation
            "propagate_upstream": False,
            "include_refs": {"binds_to", "extends"},
        },
        ChangeType.ADD_COLUMN: {
            "propagate_downstream": False,  # DB is the sink
            "propagate_upstream": True,     # Update entity
            "include_refs": {"maps_to", "extends"},
        },
    }

    def __init__(self, db_path: Path):
        """
        Initialize the engine.

        Args:
            db_path: Path to the wicked-search SQLite database
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

    def plan_propagation(
        self,
        change_spec: ChangeSpec,
        max_depth: int = 5,
    ) -> PropagationPlan:
        """
        Create a plan for propagating a change.

        Analyzes the symbol graph to find all affected symbols.

        Args:
            change_spec: The change to propagate
            max_depth: Maximum traversal depth

        Returns:
            PropagationPlan with all affected symbols
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get the source symbol
        source = self._get_symbol(cursor, change_spec.target_symbol_id)
        if not source:
            raise ValueError(f"Symbol not found: {change_spec.target_symbol_id}")

        source_affected = AffectedSymbol(
            id=source["id"],
            name=source["name"],
            type=source["type"],
            file_path=source["file_path"],
            line_start=source.get("line_start", 0),
            line_end=source.get("line_end"),
            metadata=json.loads(source.get("metadata") or "{}"),
            impact_type="source",
            distance=0,
        )

        plan = PropagationPlan(source_symbol=source_affected)

        # Get propagation rules
        rules = self.PROPAGATION_RULES.get(change_spec.change_type, {})
        include_refs = rules.get("include_refs", set())

        # Shared visited set to prevent duplicate symbols across all impact lists
        visited: Set[str] = {source["id"]}

        # Find direct impacts (symbols that reference or are referenced by source)
        direct_refs = self._get_direct_references(cursor, source["id"])
        # Batch-fetch all referenced symbols to avoid N+1 queries
        filtered_refs = [r for r in direct_refs if r["ref_type"] in include_refs or not include_refs]
        ref_ids = [r["related_id"] for r in filtered_refs]
        symbols_by_id = self._get_symbols_batch(cursor, ref_ids)
        for ref in filtered_refs:
            symbol = symbols_by_id.get(ref["related_id"])
            if symbol and symbol["id"] not in visited:
                visited.add(symbol["id"])
                plan.direct_impacts.append(AffectedSymbol(
                    id=symbol["id"],
                    name=symbol["name"],
                    type=symbol["type"],
                    file_path=symbol["file_path"],
                    line_start=symbol.get("line_start", 0),
                    line_end=symbol.get("line_end"),
                    metadata=json.loads(symbol.get("metadata") or "{}"),
                    impact_type="direct",
                    distance=1,
                ))

        # Trace upstream (who uses/depends on this symbol)
        if rules.get("propagate_upstream", True):
            upstream = self._trace_upstream(
                cursor, source["id"], include_refs, max_depth, visited
            )
            plan.upstream_impacts.extend(upstream)

        # Trace downstream (what this symbol flows to)
        if rules.get("propagate_downstream", True):
            downstream = self._trace_downstream(
                cursor, source["id"], include_refs, max_depth, visited
            )
            plan.downstream_impacts.extend(downstream)

        return plan

    def generate_patches(
        self,
        change_spec: ChangeSpec,
        plan: Optional[PropagationPlan] = None,
        max_depth: int = 5,
    ) -> PatchSet:
        """
        Generate patches for all affected files.

        Args:
            change_spec: The change to apply
            plan: Optional pre-computed propagation plan
            max_depth: Maximum traversal depth if plan not provided

        Returns:
            PatchSet with all generated patches
        """
        if plan is None:
            plan = self.plan_propagation(change_spec, max_depth)

        patch_set = PatchSet(change_spec=change_spec)

        # Process each affected file
        for file_path, symbols in plan.by_file().items():
            try:
                patches = self._generate_file_patches(
                    change_spec, file_path, symbols
                )
                patch_set.patches.extend(patches)
            except Exception as e:
                logger.error(f"Failed to generate patches for {file_path}: {e}")
                patch_set.errors.append(f"{file_path}: {str(e)}")

        # Add warnings for incomplete propagation
        self._add_warnings(patch_set, plan)

        return patch_set

    def propagate(
        self,
        change_spec: ChangeSpec,
        dry_run: bool = True,
        max_depth: int = 5,
    ) -> PatchSet:
        """
        Full propagation: plan, generate patches, and optionally apply.

        Args:
            change_spec: The change to propagate
            dry_run: If True, only generate patches without applying
            max_depth: Maximum traversal depth

        Returns:
            PatchSet with all changes
        """
        # Plan the propagation
        plan = self.plan_propagation(change_spec, max_depth)

        # Generate patches
        patch_set = self.generate_patches(change_spec, plan, max_depth)

        # Apply patches if not dry run
        if not dry_run and not patch_set.has_errors:
            self._apply_patches(patch_set)

        return patch_set

    # Private helper methods

    def _get_symbol(self, cursor, symbol_id: str) -> Optional[Dict[str, Any]]:
        """Get a symbol by ID."""
        cursor.execute(
            """
            SELECT id, name, type, file_path, line_start, line_end, metadata, layer
            FROM symbols
            WHERE id = ?
            """,
            (symbol_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_symbols_batch(self, cursor, symbol_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple symbols by ID in a single query.

        Returns a dict mapping symbol_id -> symbol dict.
        """
        if not symbol_ids:
            return {}
        placeholders = ",".join("?" * len(symbol_ids))
        cursor.execute(
            f"""
            SELECT id, name, type, file_path, line_start, line_end, metadata, layer
            FROM symbols
            WHERE id IN ({placeholders})
            """,
            symbol_ids,
        )
        return {row["id"]: dict(row) for row in cursor.fetchall()}

    def _get_direct_references(
        self,
        cursor,
        symbol_id: str
    ) -> List[Dict[str, Any]]:
        """Get all references to/from a symbol across all reference tables.

        Queries multiple tables to ensure cross-file references are captured:
        - refs: Primary reference table with confidence and evidence
        - symbol_refs: Unified bidirectional cross-reference table
        - symbol_calls: Call graph edges
        - symbol_imports: Import relationships
        - symbol_bases: Inheritance/extension relationships
        - symbol_dependents: Reverse dependency edges
        - derived_refs: Computed/inferred references from reasoning
        """
        results = []
        seen_pairs: Set[Tuple[str, str]] = set()

        def _add_result(related_id: str, ref_type: str, direction: str, confidence: str = "medium"):
            key = (related_id, ref_type)
            if key not in seen_pairs:
                seen_pairs.add(key)
                results.append({
                    "related_id": related_id,
                    "ref_type": ref_type,
                    "confidence": confidence,
                    "direction": direction,
                })

        # 1. Primary refs table (has confidence + evidence)
        try:
            cursor.execute(
                "SELECT target_id, ref_type, confidence FROM refs WHERE source_id = ?",
                (symbol_id,)
            )
            for row in cursor.fetchall():
                _add_result(row["target_id"], row["ref_type"], "outgoing", row["confidence"] or "medium")

            cursor.execute(
                "SELECT source_id, ref_type, confidence FROM refs WHERE target_id = ?",
                (symbol_id,)
            )
            for row in cursor.fetchall():
                _add_result(row["source_id"], row["ref_type"], "incoming", row["confidence"] or "medium")
        except sqlite3.OperationalError:
            pass  # Table may not exist in older schemas

        # 2. symbol_refs table (unified cross-reference lookup)
        for tbl_query in [
            ("SELECT target_id, ref_type FROM symbol_refs WHERE source_id = ?", "outgoing", "target_id"),
            ("SELECT source_id, ref_type FROM symbol_refs WHERE target_id = ?", "incoming", "source_id"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[tbl_query[2]], row["ref_type"], tbl_query[1])
            except sqlite3.OperationalError:
                pass  # Table may not exist in older schemas

        # 3. symbol_calls table (call graph)
        for tbl_query in [
            ("SELECT target_id FROM symbol_calls WHERE symbol_id = ?", "outgoing", "calls"),
            ("SELECT symbol_id FROM symbol_calls WHERE target_id = ?", "incoming", "calls"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[0], tbl_query[2], tbl_query[1])
            except sqlite3.OperationalError:
                pass

        # 4. symbol_imports table
        for tbl_query in [
            ("SELECT target_id FROM symbol_imports WHERE symbol_id = ?", "outgoing", "imports"),
            ("SELECT symbol_id FROM symbol_imports WHERE target_id = ?", "incoming", "imports"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[0], tbl_query[2], tbl_query[1])
            except sqlite3.OperationalError:
                pass

        # 5. symbol_bases table (inheritance)
        for tbl_query in [
            ("SELECT base_id FROM symbol_bases WHERE symbol_id = ?", "outgoing", "extends"),
            ("SELECT symbol_id FROM symbol_bases WHERE base_id = ?", "incoming", "extends"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[0], tbl_query[2], tbl_query[1])
            except sqlite3.OperationalError:
                pass

        # 6. symbol_dependents table (reverse dependencies)
        for tbl_query in [
            ("SELECT dependent_id FROM symbol_dependents WHERE symbol_id = ?", "outgoing", "uses"),
            ("SELECT symbol_id FROM symbol_dependents WHERE dependent_id = ?", "incoming", "uses"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[0], tbl_query[2], tbl_query[1])
            except sqlite3.OperationalError:
                pass

        # 7. derived_refs table (computed/inferred references)
        for tbl_query in [
            ("SELECT target_id, ref_type, confidence FROM derived_refs WHERE source_id = ?", "outgoing", "target_id"),
            ("SELECT source_id, ref_type, confidence FROM derived_refs WHERE target_id = ?", "incoming", "source_id"),
        ]:
            try:
                cursor.execute(tbl_query[0], (symbol_id,))
                for row in cursor.fetchall():
                    _add_result(row[tbl_query[2]], row["ref_type"], tbl_query[1], row["confidence"] or "medium")
            except sqlite3.OperationalError:
                pass

        # 8. Cross-language and name-based reference discovery.
        # Always runs (not just as fallback) to find:
        # a) Import nodes referencing this symbol by name
        # b) Same-name symbols across languages (Java Order <-> TypeScript Order)
        try:
            symbol_name = symbol_id.rsplit('::', 1)[-1] if '::' in symbol_id else symbol_id
            cursor.execute("SELECT file_path FROM symbols WHERE id = ?", (symbol_id,))
            sym_row = cursor.fetchone()
            sym_file = sym_row["file_path"] if sym_row else None

            if symbol_name and sym_file:
                # Derive project root — use first 4 path components (e.g., /tmp/project-name/)
                # to match across subdirectories (backend/, frontend/, tests/)
                parts = sym_file.replace("\\", "/").split("/")
                project_prefix = "/".join(parts[:min(4, len(parts) - 1)])

                # a) Find import nodes in the same project that reference this name
                cursor.execute("""
                    SELECT DISTINCT s.file_path
                    FROM symbols s
                    WHERE s.type = 'import' AND s.name LIKE ?
                      AND s.file_path LIKE ?
                      AND s.file_path != ?
                """, (f'%{symbol_name}', f'{project_prefix}%', sym_file))
                for row in cursor.fetchall():
                    cursor.execute("""
                        SELECT id FROM symbols
                        WHERE file_path = ?
                          AND type IN ('class', 'interface', 'module', 'struct')
                        LIMIT 1
                    """, (row["file_path"],))
                    class_row = cursor.fetchone()
                    if class_row:
                        _add_result(class_row["id"], "imports", "incoming", "low")

                # b) Find same-name symbols in different languages within same project
                cursor.execute("""
                    SELECT id, type, file_path FROM symbols
                    WHERE name = ?
                      AND type IN ('class', 'interface', 'struct', 'table')
                      AND file_path LIKE ?
                      AND id != ?
                """, (symbol_name, f'{project_prefix}%', symbol_id))
                for row in cursor.fetchall():
                    _add_result(row["id"], "maps_to", "outgoing", "low")

        except (sqlite3.OperationalError, TypeError):
            pass  # Graceful fallback if tables/columns missing

        return results

    def _trace_upstream(
        self,
        cursor,
        symbol_id: str,
        ref_types: Set[str],
        max_depth: int,
        visited: Optional[Set[str]] = None,
    ) -> List[AffectedSymbol]:
        """Trace upstream dependencies (who depends on this symbol).

        Queries all reference tables to ensure cross-file edges are followed.
        Uses batch symbol lookups to avoid N+1 queries.
        """
        affected = []
        if visited is None:
            visited = {symbol_id}
        else:
            visited.add(symbol_id)
        queue = [(symbol_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Collect upstream symbol IDs from all reference tables
            upstream_ids = self._find_upstream_ids(cursor, current_id)

            # Filter and batch-fetch symbols
            candidates = [
                (rid, rtype) for rid, rtype in upstream_ids
                if rid not in visited and (not ref_types or rtype in ref_types)
            ]
            if not candidates:
                continue
            batch_ids = [rid for rid, _ in candidates]
            symbols_by_id = self._get_symbols_batch(cursor, batch_ids)

            for related_id, ref_type in candidates:
                symbol = symbols_by_id.get(related_id)
                if not symbol:
                    continue

                visited.add(related_id)
                affected.append(AffectedSymbol(
                    id=symbol["id"],
                    name=symbol["name"],
                    type=symbol["type"],
                    file_path=symbol["file_path"],
                    line_start=symbol.get("line_start", 0),
                    line_end=symbol.get("line_end"),
                    metadata=json.loads(symbol.get("metadata") or "{}"),
                    impact_type="upstream",
                    distance=depth + 1,
                ))
                queue.append((related_id, depth + 1))

        return affected

    def _find_upstream_ids(
        self,
        cursor,
        symbol_id: str,
    ) -> List[Tuple[str, str]]:
        """Find all upstream symbol IDs from all reference tables.

        Returns list of (related_id, ref_type) tuples.
        """
        results = []
        seen = set()

        # Queries that find "who references this symbol" (incoming edges)
        queries = [
            # refs table
            ("SELECT source_id, ref_type FROM refs WHERE target_id = ?", "source_id"),
            # symbol_refs table
            ("SELECT source_id, ref_type FROM symbol_refs WHERE target_id = ?", "source_id"),
            # symbol_calls: who calls this
            ("SELECT symbol_id, 'calls' FROM symbol_calls WHERE target_id = ?", "symbol_id"),
            # symbol_imports: who imports this
            ("SELECT symbol_id, 'imports' FROM symbol_imports WHERE target_id = ?", "symbol_id"),
            # symbol_bases: who extends this (children)
            ("SELECT symbol_id, 'extends' FROM symbol_bases WHERE base_id = ?", "symbol_id"),
            # symbol_dependents: who depends on this
            ("SELECT dependent_id, 'uses' FROM symbol_dependents WHERE symbol_id = ?", "dependent_id"),
            # derived_refs
            ("SELECT source_id, ref_type FROM derived_refs WHERE target_id = ?", "source_id"),
        ]

        for query, id_col in queries:
            try:
                cursor.execute(query, (symbol_id,))
                for row in cursor.fetchall():
                    rid = row[0]
                    rtype = row[1] if len(row) > 1 else "uses"
                    if rid not in seen:
                        seen.add(rid)
                        results.append((rid, rtype))
            except sqlite3.OperationalError:
                pass  # Table may not exist

        return results

    def _trace_downstream(
        self,
        cursor,
        symbol_id: str,
        ref_types: Set[str],
        max_depth: int,
        visited: Optional[Set[str]] = None,
    ) -> List[AffectedSymbol]:
        """Trace downstream dependencies (what this symbol flows to).

        Queries all reference tables to ensure cross-file edges are followed.
        Uses batch symbol lookups to avoid N+1 queries.
        """
        affected = []
        if visited is None:
            visited = {symbol_id}
        else:
            visited.add(symbol_id)
        queue = [(symbol_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Collect downstream symbol IDs from all reference tables
            downstream_ids = self._find_downstream_ids(cursor, current_id)

            # Filter and batch-fetch symbols
            candidates = [
                (rid, rtype) for rid, rtype in downstream_ids
                if rid not in visited and (not ref_types or rtype in ref_types)
            ]
            if not candidates:
                continue
            batch_ids = [rid for rid, _ in candidates]
            symbols_by_id = self._get_symbols_batch(cursor, batch_ids)

            for related_id, ref_type in candidates:
                symbol = symbols_by_id.get(related_id)
                if not symbol:
                    continue

                visited.add(related_id)
                affected.append(AffectedSymbol(
                    id=symbol["id"],
                    name=symbol["name"],
                    type=symbol["type"],
                    file_path=symbol["file_path"],
                    line_start=symbol.get("line_start", 0),
                    line_end=symbol.get("line_end"),
                    metadata=json.loads(symbol.get("metadata") or "{}"),
                    impact_type="downstream",
                    distance=depth + 1,
                ))
                queue.append((related_id, depth + 1))

        return affected

    def _find_downstream_ids(
        self,
        cursor,
        symbol_id: str,
    ) -> List[Tuple[str, str]]:
        """Find all downstream symbol IDs from all reference tables.

        Returns list of (related_id, ref_type) tuples.
        """
        results = []
        seen = set()

        # Queries that find "what this symbol references" (outgoing edges)
        queries = [
            # refs table
            ("SELECT target_id, ref_type FROM refs WHERE source_id = ?", "target_id"),
            # symbol_refs table
            ("SELECT target_id, ref_type FROM symbol_refs WHERE source_id = ?", "target_id"),
            # symbol_calls: what this calls
            ("SELECT target_id, 'calls' FROM symbol_calls WHERE symbol_id = ?", "target_id"),
            # symbol_imports: what this imports
            ("SELECT target_id, 'imports' FROM symbol_imports WHERE symbol_id = ?", "target_id"),
            # symbol_bases: what this extends (parents)
            ("SELECT base_id, 'extends' FROM symbol_bases WHERE symbol_id = ?", "base_id"),
            # symbol_dependents: what this is a dependency of
            ("SELECT symbol_id, 'uses' FROM symbol_dependents WHERE dependent_id = ?", "symbol_id"),
            # derived_refs
            ("SELECT target_id, ref_type FROM derived_refs WHERE source_id = ?", "target_id"),
        ]

        for query, id_col in queries:
            try:
                cursor.execute(query, (symbol_id,))
                for row in cursor.fetchall():
                    rid = row[0]
                    rtype = row[1] if len(row) > 1 else "uses"
                    if rid not in seen:
                        seen.add(rid)
                        results.append((rid, rtype))
            except sqlite3.OperationalError:
                pass  # Table may not exist

        return results

    def _generate_file_patches(
        self,
        change_spec: ChangeSpec,
        file_path: str,
        symbols: List[AffectedSymbol],
    ) -> List[Patch]:
        """Generate patches for a single file."""
        patches = []

        # Read file content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return patches

        # Get generator for this file type
        generator = GeneratorRegistry.get_generator(file_path, self.db_path)
        if not generator:
            logger.debug(f"No generator for {file_path}")
            return patches

        # Generate patches for each affected symbol in this file
        for symbol in symbols:
            symbol_dict = {
                "id": symbol.id,
                "name": symbol.name,
                "type": symbol.type,
                "file_path": symbol.file_path,
                "line_start": symbol.line_start,
                "line_end": symbol.line_end,
                "metadata": symbol.metadata,
            }

            # Adapt the change spec for this symbol
            adapted_spec = self._adapt_change_spec(change_spec, symbol)

            try:
                symbol_patches = generator.generate(
                    adapted_spec, symbol_dict, file_content
                )
                # Update file path in patches
                for patch in symbol_patches:
                    patch.file_path = file_path
                patches.extend(symbol_patches)
            except Exception as e:
                logger.warning(f"Generator failed for {symbol.id}: {e}")

        return patches

    def _adapt_change_spec(
        self,
        original: ChangeSpec,
        symbol: AffectedSymbol,
    ) -> ChangeSpec:
        """
        Adapt a change spec for a dependent symbol.

        For example, if adding a field to an entity, the change for
        a JSP binding might become ADD_UI_BINDING instead.
        """
        # Determine the appropriate change type for this symbol type
        if original.change_type == ChangeType.ADD_FIELD:
            if symbol.type in {"ui_binding", "el_expression", "form_field"}:
                return ChangeSpec(
                    change_type=ChangeType.ADD_UI_BINDING,
                    target_symbol_id=symbol.id,
                    field_spec=original.field_spec,
                    metadata={**original.metadata, **symbol.metadata},
                )
        elif original.change_type == ChangeType.RENAME_FIELD:
            # Rename propagates as rename to all affected symbols
            return ChangeSpec(
                change_type=ChangeType.RENAME_FIELD,
                target_symbol_id=symbol.id,
                old_name=original.old_name,
                new_name=original.new_name,
                metadata={**original.metadata, **symbol.metadata},
            )

        # Default: return a copy with updated target
        return ChangeSpec(
            change_type=original.change_type,
            target_symbol_id=symbol.id,
            field_spec=original.field_spec,
            old_name=original.old_name,
            new_name=original.new_name,
            metadata={**original.metadata, **symbol.metadata},
        )

    def _add_warnings(self, patch_set: PatchSet, plan: PropagationPlan):
        """Add warnings for potential issues."""
        # Check for symbols without generators
        unsupported_extensions = set()
        for symbol in plan.all_affected:
            if symbol.file_path:
                ext = Path(symbol.file_path).suffix.lower()
                if ext not in GeneratorRegistry.supported_extensions():
                    unsupported_extensions.add(ext)

        if unsupported_extensions:
            patch_set.warnings.append(
                f"No generators for file types: {', '.join(sorted(unsupported_extensions))}"
            )

        # Check for potential test files
        test_files = [
            s.file_path for s in plan.all_affected
            if s.file_path and ("test" in s.file_path.lower() or "spec" in s.file_path.lower())
        ]
        if test_files:
            patch_set.warnings.append(
                f"Test files may need manual updates: {len(test_files)} files"
            )

    def _apply_patches(self, patch_set: PatchSet):
        """
        Apply patches to files.

        Patches are applied in reverse line order (descending by line_start)
        so that earlier patches don't shift the line numbers of later ones.
        For patches at the same line_start, inserts are applied in the order
        they were generated (stable sort preserves creation order).
        """
        for file_path, patches in patch_set.patches_by_file().items():
            try:
                file_exists = Path(file_path).exists()
                if file_exists:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.read().split("\n")
                else:
                    # New file — ensure parent directory exists
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    lines = []

                # patches_by_file() returns patches sorted descending by line_start.
                # Descending order means each patch operates on original line numbers
                # since later patches (lower lines) haven't been shifted yet.
                for patch in patches:
                    if patch.is_insert:
                        # Insert new content after line_start
                        new_lines = patch.new_content.split("\n")
                        lines = lines[:patch.line_start] + new_lines + lines[patch.line_start:]
                    elif patch.is_delete:
                        # Delete lines
                        lines = lines[:patch.line_start - 1] + lines[patch.line_end:]
                    else:
                        # Replace lines
                        new_lines = patch.new_content.split("\n")
                        lines = lines[:patch.line_start - 1] + new_lines + lines[patch.line_end:]

                # Write back
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                logger.info(f"Applied {len(patches)} patches to {file_path}")

            except Exception as e:
                logger.error(f"Failed to apply patches to {file_path}: {e}")
                patch_set.errors.append(f"Apply failed for {file_path}: {str(e)}")
