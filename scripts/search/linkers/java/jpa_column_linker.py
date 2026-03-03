"""
JPA Column Linker.

Creates MAPS_TO relationships between entity fields and database columns.
Extracts column metadata from @Column, @Id, @JoinColumn annotations.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from symbol_graph import (
    SymbolGraph,
    Symbol,
    Reference,
    SymbolType,
    ReferenceType,
    Confidence,
)
from linkers.base import BaseLinker, register_linker

logger = logging.getLogger(__name__)


@register_linker
class JpaColumnLinker(BaseLinker):
    """Links JPA entity fields to database columns."""

    # Linker metadata
    name = "jpa_column"
    description = "Links JPA entity fields to database columns"
    priority = 20  # Run early to create COLUMN symbols

    def __init__(self, graph: SymbolGraph):
        """
        Initialize linker.

        Args:
            graph: Symbol graph to work with
        """
        super().__init__(graph)
        self._created_columns: Set[str] = set()  # Track created column symbols

    def link_all(self) -> int:
        """
        Link all entity fields to their columns.

        Returns:
            Number of links created
        """
        links_created = 0

        # Find all entity fields
        entity_fields = self.graph.find_by_type(SymbolType.ENTITY_FIELD)

        for field in entity_fields:
            try:
                refs = self._link_field_to_column(field)
                for ref in refs:
                    self.graph.add_reference(ref)
                links_created += len(refs)
            except Exception as e:
                logger.warning(f"Failed to link field {field.id}: {e}")

        logger.info(
            f"Created {links_created} field-column links, "
            f"{len(self._created_columns)} column symbols"
        )
        return links_created

    def _link_field_to_column(self, field: Symbol) -> List[Reference]:
        """
        Link an entity field to its database column.

        Creates a COLUMN symbol if needed, then creates MAPS_TO reference.

        Args:
            field: Entity field symbol

        Returns:
            List of references created
        """
        references = []
        metadata = field.metadata or {}

        # Get column name from metadata (extracted from @Column annotation)
        column_name = metadata.get("column_name")
        if not column_name:
            # Default to field name if no @Column annotation
            column_name = field.name

        # Get entity name for table context
        entity_name = metadata.get("entity")
        if not entity_name:
            # Try to extract from qualified name
            if "." in field.qualified_name:
                entity_name = field.qualified_name.split(".")[0]

        # Determine table name:
        # 1. From field metadata (propagated from @Table annotation on entity)
        # 2. Fall back to looking up entity symbol
        # 3. Default to entity name (JPA convention)
        table_name = metadata.get("table_name")
        if not table_name:
            table_name = self._find_table_name(entity_name, field.file_path)

        # Create column symbol if not exists
        column_id = self._create_column_symbol(
            column_name=column_name,
            table_name=table_name,
            field=field,
        )

        # Determine confidence based on annotation presence
        annotations = metadata.get("annotations", [])
        annotation_args = metadata.get("annotation_args", {})
        column_args = annotation_args.get("Column", {})
        join_column_args = annotation_args.get("JoinColumn", {})

        # Check for explicit column name in @Column or @JoinColumn
        has_explicit_column = (
            column_args.get("name") or
            column_args.get("value") or  # @Column("FOO") single-arg
            join_column_args.get("name") or
            join_column_args.get("value")  # @JoinColumn("FOO") single-arg
        )

        if has_explicit_column:
            # Explicit @Column(name="...") or @Column("...") = HIGH confidence
            confidence = Confidence.HIGH
        elif "JoinColumn" in annotations:
            # @JoinColumn without explicit name = HIGH (uses field name convention)
            confidence = Confidence.HIGH
        elif "Id" in annotations:
            # @Id with default column name = MEDIUM
            confidence = Confidence.MEDIUM
        else:
            # No explicit annotation, using JPA naming convention = INFERRED
            confidence = Confidence.INFERRED

        # Create MAPS_TO reference
        references.append(Reference(
            source_id=field.id,
            target_id=column_id,
            ref_type=ReferenceType.MAPS_TO,
            confidence=confidence,
            evidence={
                "column_name": column_name,
                "table_name": table_name,
                "is_primary_key": metadata.get("is_primary_key", False),
                "is_foreign_key": metadata.get("is_foreign_key", False),
                "annotations": annotations,
            },
        ))

        return references

    def _find_table_name(self, entity_name: str, file_path: str) -> Optional[str]:
        """
        Find the table name for an entity.

        Looks up the entity symbol and checks for @Table annotation.

        Args:
            entity_name: Entity class name
            file_path: File containing the entity

        Returns:
            Table name or None
        """
        # Try to find the entity symbol
        entity_id = f"{file_path}::{entity_name}"
        entity = self.graph.get_symbol(entity_id)

        if entity and entity.metadata:
            # Check for explicit table name in metadata
            # (would be set from @Table(name="...") annotation)
            table_name = entity.metadata.get("table_name")
            if table_name:
                return table_name

        # Use JPA naming convention: entity name -> table name
        # PersonEntity -> PERSON_ENTITY (or person_entity)
        return entity_name

    def _create_column_symbol(
        self,
        column_name: str,
        table_name: Optional[str],
        field: Symbol,
    ) -> str:
        """
        Create a COLUMN symbol if not already created.

        Args:
            column_name: Database column name
            table_name: Database table name
            field: The entity field this column maps from

        Returns:
            Column symbol ID
        """
        # Generate column ID with file context for disambiguation
        # Format: db::{table_name}.{column_name} or db::{entity_file}::{column_name}
        if table_name:
            column_id = f"db::{table_name}.{column_name}"
        else:
            # Use file path for disambiguation when no table name
            file_key = Path(field.file_path).stem if field.file_path else "unknown"
            column_id = f"db::{file_key}.{column_name}"

        # Only create if not already done
        if column_id not in self._created_columns:
            self._created_columns.add(column_id)

            # Check if symbol already exists in graph
            existing = self.graph.get_symbol(column_id)
            if not existing:
                metadata = field.metadata or {}

                column_symbol = Symbol(
                    id=column_id,
                    type=SymbolType.COLUMN,
                    name=column_name,
                    qualified_name=f"{table_name}.{column_name}" if table_name else column_name,
                    file_path=field.file_path,  # Associate with entity file
                    line_start=field.line_start,
                    metadata={
                        "table_name": table_name,
                        "column_name": column_name,
                        "is_primary_key": metadata.get("is_primary_key", False),
                        "is_foreign_key": metadata.get("is_foreign_key", False),
                        "java_type": metadata.get("java_type"),
                        "source_entity": metadata.get("entity"),
                        "source_field": field.name,
                    },
                )
                self.graph.add_symbol(column_symbol)

        return column_id
