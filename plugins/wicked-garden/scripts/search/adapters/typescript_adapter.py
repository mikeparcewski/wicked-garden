"""
TypeScript language adapter for symbol extraction.

Extracts:
- TypeORM entities (@Entity, @Column decorators)
- React components (PascalCase JSX tags)
- React bindings ({state}, onChange handlers)
- React hooks (useState, useEffect)
"""

from typing import List, Set, Dict, Any
import re
import logging

from .base import LanguageAdapter, AdapterRegistry

logger = logging.getLogger(__name__)

# Conditional imports
try:
    from symbol_graph import Symbol, SymbolType
    HAS_SYMBOL_GRAPH = True
except ImportError:
    HAS_SYMBOL_GRAPH = False
    Symbol = None
    SymbolType = None

try:
    import tree_sitter as ts
    from tree_sitter_language_pack import get_language
    HAS_TREESITTER = True
except ImportError:
    HAS_TREESITTER = False


# TypeORM column decorators
TYPEORM_COLUMN_DECORATORS = {
    'Column', 'PrimaryColumn', 'PrimaryGeneratedColumn',
    'CreateDateColumn', 'UpdateDateColumn', 'DeleteDateColumn',
    'VersionColumn',
}

# TypeORM relationship decorators
TYPEORM_RELATIONSHIP_DECORATORS = {
    'OneToOne', 'OneToMany', 'ManyToOne', 'ManyToMany',
    'JoinColumn', 'JoinTable',
}


@AdapterRegistry.register
class TypeScriptAdapter(LanguageAdapter):
    """Parse TypeScript/TSX files for TypeORM entities and React components."""

    name = "typescript"
    extensions = {'.ts', '.tsx', '.jsx'}

    # Class-level compiled patterns for better performance
    COMPONENT_PATTERN = re.compile(r'<([A-Z][a-zA-Z0-9]+)(?:\s|>|/)')
    BINDING_PATTERN = re.compile(r'\{([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\}')
    EVENT_PATTERN = re.compile(r'on[A-Z]\w+\s*=\s*\{([^}]+)\}')
    USE_STATE_PATTERN = re.compile(
        r'(?:const|let)\s+\[(\w+),\s*set(\w+)\]\s*=\s*useState'
    )
    ENTITY_PATTERN = re.compile(
        r'@Entity\s*\(\s*(?:["\'](\w+)["\']|{[^}]*name\s*:\s*["\'](\w+)["\'][^}]*})?\s*\)\s*'
        r'(?:export\s+)?class\s+(\w+)',
        re.MULTILINE
    )
    COLUMN_PATTERN = re.compile(
        r'@(Column|PrimaryColumn|PrimaryGeneratedColumn|CreateDateColumn|UpdateDateColumn|'
        r'DeleteDateColumn|VersionColumn|OneToOne|OneToMany|ManyToOne|ManyToMany|JoinColumn)\s*'
        r'\(([^)]*)\)?\s*'
        r'(\w+)\s*[?!]?\s*:',
        re.MULTILINE
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse TypeScript/TSX file for ORM entities and React patterns.

        Extracts both TypeORM entities (for .ts files) and React
        components/bindings (for .tsx/.jsx files).
        """
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            # Parse TypeORM entities (works for all .ts/.tsx files)
            symbols.extend(self._parse_typeorm_decorators(content, file_path))

            # Parse React/JSX patterns (primarily for .tsx/.jsx)
            if file_path.endswith(('.tsx', '.jsx')) or '<' in content:
                symbols.extend(self._parse_react_patterns(content, file_path))
        except Exception as e:
            logger.debug(f"TypeScript parsing error for {file_path}: {e}")

        return symbols

    def _parse_react_patterns(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse React components, bindings, and hooks."""
        symbols = []

        # Extract React components
        seen_components = set()
        for match in self.COMPONENT_PATTERN.finditer(content):
            component_name = match.group(1)
            if component_name in seen_components:
                continue
            # Skip HTML-like names
            if component_name.lower() in ('div', 'span', 'input', 'button', 'form'):
                continue
            seen_components.add(component_name)

            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::<{component_name}>",
                type=SymbolType.UI_COMPONENT,
                name=component_name,
                qualified_name=f"<{component_name}>",
                file_path=file_path,
                line_start=line,
                metadata={
                    'framework': 'react',
                    'binding_type': 'component',
                },
            ))

        # Extract useState hooks
        for match in self.USE_STATE_PATTERN.finditer(content):
            state_name = match.group(1)
            setter_name = f"set{match.group(2)}"
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::state:{state_name}",
                type=SymbolType.UI_BINDING,
                name=state_name,
                qualified_name=f"useState:{state_name}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'framework': 'react',
                    'binding_type': 'useState',
                    'setter': setter_name,
                },
            ))

        # Extract event handlers
        seen_events = set()
        for match in self.EVENT_PATTERN.finditer(content):
            handler = match.group(1).strip()
            if handler in seen_events:
                continue
            seen_events.add(handler)

            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::handler:{handler}",
                type=SymbolType.UI_BINDING,
                name=handler,
                qualified_name=f"handler:{handler}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'framework': 'react',
                    'binding_type': 'event_handler',
                },
            ))

        return symbols

    def _parse_typeorm_decorators(
        self,
        content: str,
        file_path: str
    ) -> List["Symbol"]:
        """Parse TypeORM decorator-based entities."""
        symbols = []

        # Track entities by line for association
        entity_matches = list(self.ENTITY_PATTERN.finditer(content))

        for match in entity_matches:
            table_name = match.group(1) or match.group(2)
            class_name = match.group(3)
            entity_start = match.start()
            line_start = content[:entity_start].count('\n') + 1

            # Find end of class (next class or end of file)
            next_class = re.search(r'\nclass\s', content[match.end():])
            if next_class:
                entity_end = match.end() + next_class.start()
            else:
                entity_end = len(content)

            class_content = content[entity_start:entity_end]
            line_end = content[:entity_end].count('\n') + 1

            # Default table name to class name if not specified
            if not table_name:
                table_name = self._to_snake_case(class_name)

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
                    'orm_type': 'typeorm',
                },
            ))

            # Find columns in this class
            for col_match in self.COLUMN_PATTERN.finditer(class_content):
                decorator = col_match.group(1)
                args = col_match.group(2) or ''
                field_name = col_match.group(3)

                field_line = line_start + class_content[:col_match.start()].count('\n')

                is_relationship = decorator in TYPEORM_RELATIONSHIP_DECORATORS
                is_primary_key = decorator in ('PrimaryColumn', 'PrimaryGeneratedColumn')

                # Extract column name from decorator args
                column_name = field_name
                name_match = re.search(r'name\s*:\s*["\'](\w+)["\']', args)
                if name_match:
                    column_name = name_match.group(1)

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{field_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=field_name,
                    qualified_name=f"{class_name}.{field_name}",
                    file_path=file_path,
                    line_start=field_line,
                    metadata={
                        'field_type': decorator,
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': column_name,
                        'orm_type': 'typeorm',
                        'is_relationship': is_relationship,
                        'is_primary_key': is_primary_key,
                    },
                ))

        return symbols

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


@AdapterRegistry.register
class PrismaAdapter(LanguageAdapter):
    """Parse Prisma schema files for model definitions."""

    name = "prisma"
    extensions = {'.prisma'}

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse Prisma schema for models."""
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            # Pattern for model definitions
            model_pattern = re.compile(
                r'^model\s+(\w+)\s*\{([^}]+)\}',
                re.MULTILINE | re.DOTALL
            )

            # Pattern for field definitions
            field_pattern = re.compile(
                r'^\s*(\w+)\s+(\w+)(\[\])?\s*(@[^\n]+)?',
                re.MULTILINE
            )

            for model_match in model_pattern.finditer(content):
                model_name = model_match.group(1)
                model_body = model_match.group(2)
                model_start = content[:model_match.start()].count('\n') + 1
                model_end = content[:model_match.end()].count('\n') + 1

                # Prisma table name defaults to model name
                table_name = model_name

                # Check for @@map directive
                map_match = re.search(r'@@map\s*\(\s*["\'](\w+)["\']', model_body)
                if map_match:
                    table_name = map_match.group(1)

                symbols.append(Symbol(
                    id=f"{file_path}::{model_name}",
                    type=SymbolType.ENTITY,
                    name=model_name,
                    qualified_name=f"{file_path}::{model_name}",
                    file_path=file_path,
                    line_start=model_start,
                    line_end=model_end,
                    metadata={
                        'table_name': table_name,
                        'orm_type': 'prisma',
                    },
                ))

                # Parse fields
                for field_match in field_pattern.finditer(model_body):
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    is_array = bool(field_match.group(3))
                    attributes = field_match.group(4) or ''

                    # Skip @@map and other model-level attributes
                    if field_name.startswith('@@'):
                        continue

                    field_line = model_start + model_body[:field_match.start()].count('\n')

                    is_relationship = field_type[0].isupper() and field_type not in (
                        'String', 'Int', 'Float', 'Boolean', 'DateTime', 'Json', 'Bytes'
                    )
                    is_primary_key = '@id' in attributes

                    # Extract column name from @map
                    column_name = field_name
                    map_match = re.search(r'@map\s*\(\s*["\'](\w+)["\']', attributes)
                    if map_match:
                        column_name = map_match.group(1)

                    symbols.append(Symbol(
                        id=f"{file_path}::{model_name}.{field_name}",
                        type=SymbolType.ENTITY_FIELD,
                        name=field_name,
                        qualified_name=f"{model_name}.{field_name}",
                        file_path=file_path,
                        line_start=field_line,
                        metadata={
                            'field_type': field_type,
                            'entity': model_name,
                            'table_name': table_name,
                            'column_name': column_name,
                            'orm_type': 'prisma',
                            'is_relationship': is_relationship,
                            'is_primary_key': is_primary_key,
                            'is_array': is_array,
                        },
                    ))

        except Exception as e:
            logger.debug(f"Prisma parsing error for {file_path}: {e}")

        return symbols
