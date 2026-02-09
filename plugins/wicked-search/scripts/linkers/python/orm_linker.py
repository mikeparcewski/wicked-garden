"""
Python ORM Linker.

Creates MAPS_TO relationships between Python ORM models and database columns.
Supports:
- SQLAlchemy (Column, mapped_column, relationship)
- Django ORM (models.CharField, models.ForeignKey, etc.)
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

# Django field types that map to database columns
DJANGO_COLUMN_FIELDS = {
    'AutoField', 'BigAutoField', 'SmallAutoField',
    'CharField', 'TextField', 'EmailField', 'URLField', 'SlugField',
    'IntegerField', 'BigIntegerField', 'SmallIntegerField', 'PositiveIntegerField',
    'FloatField', 'DecimalField',
    'BooleanField', 'NullBooleanField',
    'DateField', 'DateTimeField', 'TimeField', 'DurationField',
    'BinaryField', 'FileField', 'ImageField',
    'UUIDField', 'GenericIPAddressField',
}

# Django relationship fields
DJANGO_RELATIONSHIP_FIELDS = {
    'ForeignKey', 'OneToOneField', 'ManyToManyField',
}


@register_linker
class PythonORMLinker(BaseLinker):
    """Links Python ORM models to database columns."""

    # Linker metadata
    name = "python_orm"
    description = "Links SQLAlchemy/Django models to database columns"
    priority = 20  # Run early to create COLUMN symbols

    def __init__(self, graph: SymbolGraph):
        super().__init__(graph)
        self._created_columns: Set[str] = set()

    def link_all(self) -> int:
        """
        Link all Python ORM model fields to their columns.

        Returns:
            Number of links created
        """
        links_created = 0

        # Find all entity fields (Python ORM fields are also stored as ENTITY_FIELD)
        entity_fields = self.graph.find_by_type(SymbolType.ENTITY_FIELD)

        for field in entity_fields:
            # Check if this is a Python file
            if not field.file_path or not field.file_path.endswith('.py'):
                continue

            try:
                refs = self._link_field_to_column(field)
                for ref in refs:
                    self.graph.add_reference(ref)
                links_created += len(refs)
            except Exception as e:
                logger.warning(f"Failed to link Python field {field.id}: {e}")

        logger.info(
            f"Created {links_created} Python ORM links, "
            f"{len(self._created_columns)} column symbols"
        )
        return links_created

    def _link_field_to_column(self, field: Symbol) -> List[Reference]:
        """
        Link a Python ORM field to its database column.

        Args:
            field: Entity field symbol

        Returns:
            List of references created
        """
        references = []
        metadata = field.metadata or {}

        # Get ORM type (sqlalchemy, django)
        orm_type = metadata.get("orm_type", "unknown")

        # Get column name from metadata
        column_name = metadata.get("column_name")
        if not column_name:
            # Default to field name (snake_case is common in Python)
            column_name = field.name

        # Get table name
        table_name = metadata.get("table_name")
        entity_name = metadata.get("entity")

        if not table_name and entity_name:
            # Default: snake_case of class name (common convention)
            table_name = self._to_snake_case(entity_name)

        # Create column symbol
        column_id = self._create_column_symbol(
            column_name=column_name,
            table_name=table_name,
            field=field,
        )

        # Determine confidence
        field_type = metadata.get("field_type", "")
        is_relationship = metadata.get("is_relationship", False)

        if is_relationship:
            # Relationship fields get HIGH confidence
            confidence = Confidence.HIGH
        elif metadata.get("has_explicit_column"):
            # Explicit db_column or name= argument
            confidence = Confidence.HIGH
        elif orm_type == "django" and field_type in DJANGO_COLUMN_FIELDS:
            # Django field types are well-defined
            confidence = Confidence.MEDIUM
        elif orm_type == "sqlalchemy":
            # SQLAlchemy Column() calls are explicit
            confidence = Confidence.MEDIUM
        else:
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
                "orm_type": orm_type,
                "field_type": field_type,
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
                        "orm_type": metadata.get("orm_type"),
                        "python_type": metadata.get("field_type"),
                        "source_entity": metadata.get("entity"),
                        "source_field": field.name,
                    },
                )
                self.graph.add_symbol(column_symbol)

        return column_id

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        # Insert underscore before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
