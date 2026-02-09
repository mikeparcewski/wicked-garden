"""
Ruby language adapter for symbol extraction.

Extracts:
- ActiveRecord models (classes inheriting from ApplicationRecord or ActiveRecord::Base)
- Rails model associations (belongs_to, has_many, has_one)
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


# ActiveRecord association methods
ACTIVERECORD_ASSOCIATIONS = {
    'belongs_to', 'has_one', 'has_many', 'has_and_belongs_to_many',
}


@AdapterRegistry.register
class RubyAdapter(LanguageAdapter):
    """Parse Ruby files for ActiveRecord models."""

    name = "ruby"
    extensions = {'.rb'}

    # Class-level compiled patterns for better performance
    CLASS_PATTERN = re.compile(
        r'^class\s+(\w+)\s*<\s*(ApplicationRecord|ActiveRecord::Base)',
        re.MULTILINE
    )
    TABLE_PATTERN = re.compile(
        r'self\.table_name\s*=\s*["\'](\w+)["\']',
        re.MULTILINE
    )
    ASSOC_PATTERN = re.compile(
        r'^\s*(belongs_to|has_one|has_many|has_and_belongs_to_many)\s*:(\w+)(?:\s*,\s*(.+))?',
        re.MULTILINE
    )
    ATTR_PATTERN = re.compile(
        r'^\s*(?:validates|attribute)\s*:(\w+)',
        re.MULTILINE
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse Ruby file for ActiveRecord entities.

        Uses regex patterns to detect Rails model conventions.
        """
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            symbols = self._parse_activerecord_models(content, file_path)
        except Exception as e:
            logger.debug(f"Ruby parsing error for {file_path}: {e}")

        return symbols

    def _parse_activerecord_models(
        self,
        content: str,
        file_path: str
    ) -> List["Symbol"]:
        """Parse ActiveRecord model classes."""
        symbols = []

        for class_match in self.CLASS_PATTERN.finditer(content):
            class_name = class_match.group(1)
            base_class = class_match.group(2)
            class_start = class_match.start()
            line_start = content[:class_start].count('\n') + 1

            # Find end of class
            next_class = re.search(r'\nclass\s', content[class_match.end():])
            end_pattern = re.search(r'^end\s*$', content[class_match.end():], re.MULTILINE)

            if end_pattern:
                class_end = class_match.end() + end_pattern.end()
            elif next_class:
                class_end = class_match.end() + next_class.start()
            else:
                class_end = len(content)

            class_content = content[class_start:class_end]
            line_end = content[:class_end].count('\n') + 1

            # Derive table name (Rails convention: pluralized snake_case)
            table_name = self._tableize(class_name)

            # Check for custom table name
            table_match = self.TABLE_PATTERN.search(class_content)
            if table_match:
                table_name = table_match.group(1)

            # Create ENTITY symbol
            symbols.append(Symbol(
                id=f"{file_path}::{class_name}",
                type=SymbolType.ENTITY,
                name=class_name,
                qualified_name=f"{file_path}::{class_name}",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                metadata={
                    'table_name': table_name,
                    'orm_type': 'activerecord',
                    'base_class': base_class,
                },
            ))

            # Parse associations
            for assoc_match in self.ASSOC_PATTERN.finditer(class_content):
                assoc_type = assoc_match.group(1)
                assoc_name = assoc_match.group(2)
                assoc_options = assoc_match.group(3) or ''

                assoc_line = line_start + class_content[:assoc_match.start()].count('\n')

                # For belongs_to, the foreign key is typically name_id
                if assoc_type == 'belongs_to':
                    column_name = f"{assoc_name}_id"
                else:
                    column_name = None  # has_many/has_one don't create columns

                # Check for custom foreign_key
                fk_match = re.search(r'foreign_key:\s*["\':]+(\w+)', assoc_options)
                if fk_match:
                    column_name = fk_match.group(1)

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{assoc_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=assoc_name,
                    qualified_name=f"{class_name}.{assoc_name}",
                    file_path=file_path,
                    line_start=assoc_line,
                    metadata={
                        'field_type': assoc_type,
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': column_name,
                        'orm_type': 'activerecord',
                        'is_relationship': True,
                    },
                ))

            # Parse validated/declared attributes as potential columns
            for attr_match in self.ATTR_PATTERN.finditer(class_content):
                attr_name = attr_match.group(1)
                attr_line = line_start + class_content[:attr_match.start()].count('\n')

                # Skip if we already have this as an association
                existing = any(
                    s.name == attr_name and s.metadata.get('entity') == class_name
                    for s in symbols
                    if s.type == SymbolType.ENTITY_FIELD
                )
                if existing:
                    continue

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{attr_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=attr_name,
                    qualified_name=f"{class_name}.{attr_name}",
                    file_path=file_path,
                    line_start=attr_line,
                    metadata={
                        'field_type': 'column',
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': attr_name,
                        'orm_type': 'activerecord',
                        'is_relationship': False,
                    },
                ))

        return symbols

    def _tableize(self, class_name: str) -> str:
        """Convert CamelCase class name to Rails table name (pluralized snake_case)."""
        return NamingUtils.tableize(class_name)
