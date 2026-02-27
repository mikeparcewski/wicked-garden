"""
C# language adapter for symbol extraction.

Extracts:
- Entity Framework entities ([Table], [Key] attributes)
- EF Core DbContext configurations
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
class CSharpAdapter(LanguageAdapter):
    """Parse C# files for Entity Framework models."""

    name = "csharp"
    extensions = {'.cs'}

    # Class-level compiled patterns for better performance
    CLASS_PATTERN = re.compile(
        r'(?:\[Table\s*\(\s*"(\w+)"\s*\)\s*\])?\s*'
        r'(?:public\s+)?class\s+(\w+)(?:\s*:\s*(\w+))?',
        re.MULTILINE
    )
    PROP_PATTERN = re.compile(
        r'(?:\[(Key|Column|ForeignKey|Required|MaxLength)\s*(?:\([^)]*\))?\s*\]\s*)*'
        r'public\s+(?:virtual\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\{\s*get;',
        re.MULTILINE
    )
    COLUMN_ATTR_PATTERN = re.compile(r'\[Column\s*\(\s*"(\w+)"')
    NAV_PATTERN = re.compile(
        r'public\s+virtual\s+(ICollection<(\w+)>|(\w+))\s+(\w+)\s*\{',
        re.MULTILINE
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse C# file for Entity Framework entities.

        Uses regex patterns to detect EF conventions and attributes.
        """
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            symbols = self._parse_ef_entities(content, file_path)
        except Exception as e:
            logger.debug(f"C# parsing error for {file_path}: {e}")

        return symbols

    def _parse_ef_entities(
        self,
        content: str,
        file_path: str
    ) -> List["Symbol"]:
        """Parse Entity Framework model classes."""
        symbols = []

        for class_match in self.CLASS_PATTERN.finditer(content):
            table_attr = class_match.group(1)
            class_name = class_match.group(2)
            base_class = class_match.group(3)

            class_start = class_match.start()
            line_start = content[:class_start].count('\n') + 1

            # Skip non-entity classes (controllers, services, etc.)
            if any(x in class_name for x in ['Controller', 'Service', 'Repository', 'Context']):
                continue

            # Find class body
            brace_start = content.find('{', class_match.end())
            if brace_start == -1:
                continue

            # Find matching closing brace with bounds checking
            brace_count = 1
            pos = brace_start + 1
            content_len = len(content)
            max_iterations = content_len - pos  # Safety limit
            iterations = 0

            while pos < content_len and brace_count > 0 and iterations < max_iterations:
                char = content[pos]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                pos += 1
                iterations += 1

            # Skip malformed classes with unbalanced braces
            if brace_count != 0:
                logger.debug(f"Unbalanced braces in class {class_name} at {file_path}")
                continue

            class_end = pos
            class_content = content[class_start:class_end]
            line_end = content[:class_end].count('\n') + 1

            # Derive table name
            if table_attr:
                table_name = table_attr
            else:
                # EF convention: pluralized class name
                table_name = self._pluralize(class_name)

            # Check if this looks like an entity (has properties with get/set)
            has_properties = bool(self.PROP_PATTERN.search(class_content))
            if not has_properties and not table_attr:
                continue

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
                    'orm_type': 'entityframework',
                    'base_class': base_class,
                    'has_table_attribute': bool(table_attr),
                },
            ))

            # Parse properties
            for prop_match in self.PROP_PATTERN.finditer(class_content):
                prop_type = prop_match.group(2)
                prop_name = prop_match.group(3)

                prop_line = line_start + class_content[:prop_match.start()].count('\n')

                # Get attribute context
                attr_context = class_content[max(0, prop_match.start()-100):prop_match.start()]
                is_primary_key = '[Key]' in attr_context
                is_foreign_key = '[ForeignKey' in attr_context

                # Extract column name
                column_name = prop_name
                col_match = self.COLUMN_ATTR_PATTERN.search(attr_context)
                if col_match:
                    column_name = col_match.group(1)

                # Check if navigation property
                is_relationship = (
                    'ICollection<' in prop_type or
                    'IEnumerable<' in prop_type or
                    'List<' in prop_type or
                    is_foreign_key
                )

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{prop_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=prop_name,
                    qualified_name=f"{class_name}.{prop_name}",
                    file_path=file_path,
                    line_start=prop_line,
                    metadata={
                        'field_type': prop_type,
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': column_name,
                        'orm_type': 'entityframework',
                        'is_relationship': is_relationship,
                        'is_primary_key': is_primary_key,
                        'is_foreign_key': is_foreign_key,
                    },
                ))

            # Parse virtual navigation properties
            for nav_match in self.NAV_PATTERN.finditer(class_content):
                nav_type = nav_match.group(1)
                collection_type = nav_match.group(2)
                single_type = nav_match.group(3)
                nav_name = nav_match.group(4)

                nav_line = line_start + class_content[:nav_match.start()].count('\n')

                # Skip if already captured
                existing = any(
                    s.name == nav_name and s.metadata.get('entity') == class_name
                    for s in symbols
                    if s.type == SymbolType.ENTITY_FIELD
                )
                if existing:
                    continue

                related_type = collection_type or single_type

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{nav_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=nav_name,
                    qualified_name=f"{class_name}.{nav_name}",
                    file_path=file_path,
                    line_start=nav_line,
                    metadata={
                        'field_type': nav_type,
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': None,  # Navigation properties don't have columns
                        'orm_type': 'entityframework',
                        'is_relationship': True,
                        'related_entity': related_type,
                    },
                ))

        return symbols

    def _pluralize(self, name: str) -> str:
        """Pluralization for EF table naming."""
        return NamingUtils.pluralize(name)
