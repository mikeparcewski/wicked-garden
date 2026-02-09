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

    # Map change types to how they propagate
    PROPAGATION_RULES = {
        ChangeType.ADD_FIELD: {
            "propagate_downstream": True,   # Add to UI bindings, tests
            "propagate_upstream": False,    # Don't add to callers
            "include_refs": {"binds_to", "maps_to", "uses"},
        },
        ChangeType.REMOVE_FIELD: {
            "propagate_downstream": True,   # Remove from UI, tests
            "propagate_upstream": True,     # Update callers
            "include_refs": {"binds_to", "maps_to", "uses", "calls"},
        },
        ChangeType.RENAME_FIELD: {
            "propagate_downstream": True,
            "propagate_upstream": True,
            "include_refs": {"binds_to", "maps_to", "uses", "calls"},
        },
        ChangeType.MODIFY_FIELD: {
            "propagate_downstream": True,
            "propagate_upstream": False,
            "include_refs": {"binds_to", "maps_to"},
        },
        ChangeType.ADD_VALIDATION: {
            "propagate_downstream": True,   # Add to UI validation
            "propagate_upstream": False,
            "include_refs": {"binds_to"},
        },
        ChangeType.ADD_COLUMN: {
            "propagate_downstream": False,  # DB is the sink
            "propagate_upstream": True,     # Update entity
            "include_refs": {"maps_to"},
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

        # Find direct impacts (symbols that reference or are referenced by source)
        direct_refs = self._get_direct_references(cursor, source["id"])
        for ref in direct_refs:
            if ref["ref_type"] in include_refs or not include_refs:
                symbol = self._get_symbol(cursor, ref["related_id"])
                if symbol:
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
                cursor, source["id"], include_refs, max_depth
            )
            plan.upstream_impacts.extend(upstream)

        # Trace downstream (what this symbol flows to)
        if rules.get("propagate_downstream", True):
            downstream = self._trace_downstream(
                cursor, source["id"], include_refs, max_depth
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

    def _get_direct_references(
        self,
        cursor,
        symbol_id: str
    ) -> List[Dict[str, Any]]:
        """Get all references to/from a symbol."""
        results = []

        # Outgoing references
        cursor.execute(
            """
            SELECT target_id as related_id, ref_type, confidence, 'outgoing' as direction
            FROM refs
            WHERE source_id = ?
            """,
            (symbol_id,)
        )
        results.extend(dict(row) for row in cursor.fetchall())

        # Incoming references
        cursor.execute(
            """
            SELECT source_id as related_id, ref_type, confidence, 'incoming' as direction
            FROM refs
            WHERE target_id = ?
            """,
            (symbol_id,)
        )
        results.extend(dict(row) for row in cursor.fetchall())

        return results

    def _trace_upstream(
        self,
        cursor,
        symbol_id: str,
        ref_types: Set[str],
        max_depth: int,
    ) -> List[AffectedSymbol]:
        """Trace upstream dependencies (who depends on this symbol)."""
        affected = []
        visited = {symbol_id}
        queue = [(symbol_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Find symbols that reference current
            cursor.execute(
                """
                SELECT r.source_id, r.ref_type, r.confidence,
                       s.id, s.name, s.type, s.file_path, s.line_start, s.line_end, s.metadata
                FROM refs r
                JOIN symbols s ON r.source_id = s.id
                WHERE r.target_id = ?
                """,
                (current_id,)
            )

            for row in cursor.fetchall():
                if row["source_id"] not in visited:
                    if not ref_types or row["ref_type"] in ref_types:
                        visited.add(row["source_id"])
                        affected.append(AffectedSymbol(
                            id=row["id"],
                            name=row["name"],
                            type=row["type"],
                            file_path=row["file_path"],
                            line_start=row.get("line_start", 0),
                            line_end=row.get("line_end"),
                            metadata=json.loads(row.get("metadata") or "{}"),
                            impact_type="upstream",
                            distance=depth + 1,
                        ))
                        queue.append((row["source_id"], depth + 1))

        return affected

    def _trace_downstream(
        self,
        cursor,
        symbol_id: str,
        ref_types: Set[str],
        max_depth: int,
    ) -> List[AffectedSymbol]:
        """Trace downstream dependencies (what this symbol flows to)."""
        affected = []
        visited = {symbol_id}
        queue = [(symbol_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Find symbols that current references
            cursor.execute(
                """
                SELECT r.target_id, r.ref_type, r.confidence,
                       s.id, s.name, s.type, s.file_path, s.line_start, s.line_end, s.metadata
                FROM refs r
                JOIN symbols s ON r.target_id = s.id
                WHERE r.source_id = ?
                """,
                (current_id,)
            )

            for row in cursor.fetchall():
                if row["target_id"] not in visited:
                    if not ref_types or row["ref_type"] in ref_types:
                        visited.add(row["target_id"])
                        affected.append(AffectedSymbol(
                            id=row["id"],
                            name=row["name"],
                            type=row["type"],
                            file_path=row["file_path"],
                            line_start=row.get("line_start", 0),
                            line_end=row.get("line_end"),
                            metadata=json.loads(row.get("metadata") or "{}"),
                            impact_type="downstream",
                            distance=depth + 1,
                        ))
                        queue.append((row["target_id"], depth + 1))

        return affected

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

        Patches are applied in reverse line order to maintain line numbers.
        """
        for file_path, patches in patch_set.patches_by_file().items():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.read().split("\n")

                # Apply patches in reverse order (highest line first)
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
