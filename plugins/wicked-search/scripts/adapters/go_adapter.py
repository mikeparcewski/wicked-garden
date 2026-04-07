"""
Go language adapter for symbol extraction.

Extracts:
- GORM models (structs with gorm tags)
- SQLx/SQLBoiler model definitions
"""

from typing import List, Set, Dict, Any
import re
import logging

from .base import LanguageAdapter, AdapterRegistry
from .utils import NamingUtils

logger = logging.getLogger(__name__)

# Conditional imports
try:
    from symbol_graph import Symbol, SymbolType
    HAS_SYMBOL_GRAPH = True
except ImportError:
    HAS_SYMBOL_GRAPH = False
    Symbol = None
    SymbolType = None


@AdapterRegistry.register
class GoAdapter(LanguageAdapter):
    """Parse Go files for GORM and other ORM models."""

    name = "go"
    extensions = {'.go'}

    # Class-level compiled patterns for better performance
    STRUCT_PATTERN = re.compile(
        r'type\s+(\w+)\s+struct\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    FIELD_PATTERN = re.compile(
        r'^\s*(\w+)\s+(\S+)(?:\s+`([^`]+)`)?',
        re.MULTILINE
    )
    GORM_MODEL_PATTERN = re.compile(r'gorm\.Model')
    GORM_TAG_PATTERN = re.compile(r'gorm:"([^"]*)"')
    COLUMN_PATTERN = re.compile(r'column:(\w+)')

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse Go file for GORM entities.

        Uses regex patterns to detect struct tags with gorm directives.
        """
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            symbols = self._parse_gorm_models(content, file_path)
        except Exception as e:
            logger.debug(f"Go parsing error for {file_path}: {e}")

        return symbols

    def _parse_gorm_models(
        self,
        content: str,
        file_path: str
    ) -> List["Symbol"]:
        """Parse GORM model structs."""
        symbols = []

        for struct_match in self.STRUCT_PATTERN.finditer(content):
            struct_name = struct_match.group(1)
            struct_body = struct_match.group(2)
            struct_start = struct_match.start()
            line_start = content[:struct_start].count('\n') + 1
            line_end = content[:struct_match.end()].count('\n') + 1

            # Check if this looks like a GORM model
            has_gorm_tags = 'gorm:' in struct_body
            has_gorm_model = bool(self.GORM_MODEL_PATTERN.search(struct_body))

            if not has_gorm_tags and not has_gorm_model:
                continue

            # Derive table name (GORM convention: pluralized snake_case)
            table_name = self._tableize(struct_name)

            # Check for TableName() method override (would need more context)
            # For now, use convention

            # Create ENTITY symbol
            symbols.append(Symbol(
                id=f"{file_path}::{struct_name}",
                type=SymbolType.ENTITY,
                name=struct_name,
                qualified_name=f"{file_path}::{struct_name}",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                metadata={
                    'table_name': table_name,
                    'orm_type': 'gorm',
                    'embeds_gorm_model': has_gorm_model,
                },
            ))

            # Parse fields
            for field_match in self.FIELD_PATTERN.finditer(struct_body):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                field_tags = field_match.group(3) or ''

                # Skip embedded types
                if field_name == field_type or field_type == 'gorm.Model':
                    continue

                field_line = line_start + struct_body[:field_match.start()].count('\n')

                # Parse gorm tag
                gorm_tag = ''
                gorm_match = self.GORM_TAG_PATTERN.search(field_tags)
                if gorm_match:
                    gorm_tag = gorm_match.group(1)

                # Extract column name from tag or derive from field name
                column_name = self._to_snake_case(field_name)
                col_match = self.COLUMN_PATTERN.search(gorm_tag)
                if col_match:
                    column_name = col_match.group(1)

                # Check for special gorm directives
                is_primary_key = 'primaryKey' in gorm_tag or 'primary_key' in gorm_tag
                is_foreign_key = 'foreignKey' in gorm_tag or 'foreign_key' in gorm_tag
                is_relationship = (
                    field_type.startswith('[]') or
                    field_type.startswith('*') or
                    'references' in gorm_tag or
                    'many2many' in gorm_tag or
                    'foreignKey' in gorm_tag
                )

                symbols.append(Symbol(
                    id=f"{file_path}::{struct_name}.{field_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=field_name,
                    qualified_name=f"{struct_name}.{field_name}",
                    file_path=file_path,
                    line_start=field_line,
                    metadata={
                        'field_type': field_type,
                        'entity': struct_name,
                        'table_name': table_name,
                        'column_name': column_name,
                        'orm_type': 'gorm',
                        'gorm_tag': gorm_tag,
                        'is_relationship': is_relationship,
                        'is_primary_key': is_primary_key,
                        'is_foreign_key': is_foreign_key,
                    },
                ))

        return symbols

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        return NamingUtils.to_snake_case(name)

    def _tableize(self, name: str) -> str:
        """Convert struct name to GORM table name (pluralized snake_case)."""
        return NamingUtils.tableize(name)
