"""
Go ORM Linker.

Creates MAPS_TO relationships between GORM models and database columns.
"""

import logging
import re
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
class GoORMLinker(BaseLinker):
    """Links GORM models to database columns."""

    name = "go_orm"
    description = "Links GORM models to database columns"
    priority = 20

    def __init__(self, graph: SymbolGraph):
        super().__init__(graph)
        self._created_columns: Set[str] = set()

    def link_all(self) -> int:
        """Link all Go ORM model fields to their columns."""
        links_created = 0

        entity_fields = self.graph.find_by_type(SymbolType.ENTITY_FIELD)

        for field in entity_fields:
            if not field.file_path or not field.file_path.endswith('.go'):
                continue

            metadata = field.metadata or {}
            if metadata.get('orm_type') != 'gorm':
                continue

            try:
                refs = self._link_field_to_column(field)
                for ref in refs:
                    self.graph.add_reference(ref)
                links_created += len(refs)
            except Exception as e:
                logger.warning(f"Failed to link Go field {field.id}: {e}")

        logger.info(
            f"Created {links_created} Go ORM links, "
            f"{len(self._created_columns)} column symbols"
        )
        return links_created

    def _link_field_to_column(self, field: Symbol) -> List[Reference]:
        """Link a Go ORM field to its database column."""
        references = []
        metadata = field.metadata or {}

        column_name = metadata.get("column_name", field.name)
        table_name = metadata.get("table_name")
        gorm_tag = metadata.get("gorm_tag", "")

        column_id = self._create_column_symbol(
            column_name=column_name,
            table_name=table_name,
            field=field,
        )

        # Determine confidence from gorm tag
        is_primary_key = metadata.get("is_primary_key", False)
        has_explicit_column = 'column:' in gorm_tag

        if is_primary_key:
            confidence = Confidence.HIGH
        elif has_explicit_column:
            confidence = Confidence.HIGH
        else:
            confidence = Confidence.MEDIUM

        is_relationship = metadata.get("is_relationship", False)

        references.append(Reference(
            source_id=field.id,
            target_id=column_id,
            ref_type=ReferenceType.MAPS_TO,
            confidence=confidence,
            evidence={
                "column_name": column_name,
                "table_name": table_name,
                "orm_type": "gorm",
                "gorm_tag": gorm_tag,
                "is_relationship": is_relationship,
            },
        ))

        return references

    def _create_column_symbol(
        self,
        column_name: str,
        table_name: Optional[str],
        field: Symbol,
    ) -> str:
        """Create a COLUMN symbol if not already created."""
        if table_name:
            column_id = f"db::{table_name}.{column_name}"
        else:
            file_key = Path(field.file_path).stem if field.file_path else "unknown"
            column_id = f"db::{file_key}.{column_name}"

        if column_id not in self._created_columns:
            self._created_columns.add(column_id)

            existing = self.graph.get_symbol(column_id)
            if not existing:
                metadata = field.metadata or {}

                column_symbol = Symbol(
                    id=column_id,
                    type=SymbolType.COLUMN,
                    name=column_name,
                    qualified_name=f"{table_name}.{column_name}" if table_name else column_name,
                    file_path=field.file_path,
                    line_start=field.line_start,
                    metadata={
                        "table_name": table_name,
                        "column_name": column_name,
                        "orm_type": "gorm",
                        "source_entity": metadata.get("entity"),
                        "source_field": field.name,
                    },
                )
                self.graph.add_symbol(column_symbol)

        return column_id
