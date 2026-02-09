"""
Python language adapter for symbol extraction.

Extracts:
- SQLAlchemy models (classes with __tablename__ or Column/mapped_column)
- Django models (classes using models.CharField, models.ForeignKey, etc.)
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

try:
    import tree_sitter as ts
    from tree_sitter_language_pack import get_language
    HAS_TREESITTER = True
except ImportError:
    HAS_TREESITTER = False


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

# SQLAlchemy column functions
SQLALCHEMY_COLUMN_FUNCS = {
    'Column', 'mapped_column',
}

# SQLAlchemy relationship functions
SQLALCHEMY_RELATIONSHIP_FUNCS = {
    'relationship', 'Relationship',
}


@AdapterRegistry.register
class PythonAdapter(LanguageAdapter):
    """Parse Python files for SQLAlchemy and Django ORM models."""

    name = "python"
    extensions = {'.py'}

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse Python file using tree-sitter.

        Uses python.scm query to detect ORM patterns.
        """
        if not self.code_parser or not HAS_SYMBOL_GRAPH or not HAS_TREESITTER:
            return []

        symbols = []

        try:
            parser = self.code_parser._get_parser('.py')
            if not parser:
                return symbols

            tree = parser.parse(content.encode())

            if self.code_parser._query_loader:
                query_text = self.code_parser._query_loader.load_query('python')
                if query_text:
                    ts_language = get_language('python')
                    query = ts.Query(ts_language, query_text)
                    cursor = ts.QueryCursor(query)
                    matches = list(cursor.matches(tree.root_node))

                    # Track models and their fields
                    models = {}
                    current_class = None
                    current_class_name = None

                    for pattern_idx, captures_dict in matches:
                        for name, nodes in captures_dict.items():
                            for node in nodes:
                                text = content[node.start_byte:node.end_byte]
                                line = node.start_point[0] + 1

                                # Track class definitions
                                if name == 'code_class.def':
                                    current_class = {
                                        'name': None,
                                        'bases': [],
                                        'line_start': line,
                                        'line_end': node.end_point[0] + 1,
                                        'table_name': None,
                                        'orm_type': None,
                                        'fields': [],
                                    }
                                elif name == 'code_class.name' and current_class:
                                    current_class['name'] = text
                                    current_class_name = text
                                    models[text] = current_class
                                elif name == 'code_class.base' and current_class:
                                    current_class['bases'].append(text)
                                    if text == 'Model':
                                        current_class['orm_type'] = 'django'
                                    elif text in ('Base', 'DeclarativeBase', 'DeclarativeMeta'):
                                        current_class['orm_type'] = 'sqlalchemy'

                                # SQLAlchemy __tablename__
                                elif name == 'orm_sqlalchemy.tablename_value':
                                    if current_class:
                                        current_class['table_name'] = text.strip('"\'')
                                        current_class['orm_type'] = 'sqlalchemy'

                                # SQLAlchemy Column/mapped_column fields
                                elif name == 'orm_sqlalchemy.field_name':
                                    if current_class and text not in ('__tablename__',):
                                        current_class['_pending_field'] = {
                                            'name': text,
                                            'line': line,
                                            'orm_type': 'sqlalchemy',
                                        }
                                elif name == 'orm_sqlalchemy.column_func':
                                    if current_class and text in SQLALCHEMY_COLUMN_FUNCS:
                                        pending = current_class.get('_pending_field')
                                        if pending:
                                            pending['field_type'] = text
                                            pending['is_relationship'] = False
                                            current_class['fields'].append(pending)
                                            current_class['_pending_field'] = None
                                            current_class['orm_type'] = 'sqlalchemy'
                                elif name == 'orm_sqlalchemy.mapped_func':
                                    if current_class and text == 'mapped_column':
                                        pending = current_class.get('_pending_field')
                                        if pending:
                                            pending['field_type'] = 'mapped_column'
                                            pending['is_relationship'] = False
                                            current_class['fields'].append(pending)
                                            current_class['_pending_field'] = None
                                            current_class['orm_type'] = 'sqlalchemy'

                                # SQLAlchemy relationship fields
                                elif name == 'orm_sqlalchemy.rel_name':
                                    if current_class:
                                        current_class['_pending_rel'] = {
                                            'name': text,
                                            'line': line,
                                            'orm_type': 'sqlalchemy',
                                        }
                                elif name == 'orm_sqlalchemy.rel_func':
                                    if current_class and text in SQLALCHEMY_RELATIONSHIP_FUNCS:
                                        pending = current_class.get('_pending_rel')
                                        if pending:
                                            pending['field_type'] = 'relationship'
                                            pending['is_relationship'] = True
                                            current_class['fields'].append(pending)
                                            current_class['_pending_rel'] = None

                                # Django model fields
                                elif name == 'orm_django.field_name':
                                    if current_class:
                                        current_class['_pending_django'] = {
                                            'name': text,
                                            'line': line,
                                            'orm_type': 'django',
                                        }
                                elif name == 'orm_django.field_type':
                                    if current_class:
                                        pending = current_class.get('_pending_django')
                                        if pending:
                                            pending['field_type'] = text
                                            pending['is_relationship'] = text in DJANGO_RELATIONSHIP_FIELDS
                                            current_class['fields'].append(pending)
                                            current_class['_pending_django'] = None
                                            current_class['orm_type'] = 'django'

                                # Django Meta class for db_table
                                elif name == 'orm_django.meta_key' and current_class:
                                    current_class['_meta_key'] = text
                                elif name == 'orm_django.meta_value' and current_class:
                                    if current_class.get('_meta_key') == 'db_table':
                                        current_class['table_name'] = text.strip('"\'')

                    # Build symbols for detected ORM models
                    symbols = self._build_symbols(models, file_path)

        except Exception as e:
            logger.debug(f"Python parsing error for {file_path}: {e}")

        return symbols

    def _build_symbols(
        self,
        models: Dict[str, Dict[str, Any]],
        file_path: str
    ) -> List["Symbol"]:
        """Build Symbol objects from parsed model data."""
        symbols = []

        for class_name, model in models.items():
            # Only process classes that look like ORM models
            is_orm_model = (
                model.get('orm_type') or
                model.get('table_name') or
                len(model.get('fields', [])) > 0
            )

            if not is_orm_model:
                continue

            orm_type = model.get('orm_type', 'unknown')
            bases = model.get('bases', [])
            base_class = bases[0] if bases else None

            # Derive table name if not explicit
            table_name = model.get('table_name')
            if not table_name and orm_type == 'django':
                table_name = class_name.lower()
            elif not table_name and orm_type == 'sqlalchemy':
                table_name = self._to_snake_case(class_name)

            # Create ENTITY symbol
            symbols.append(Symbol(
                id=f"{file_path}::{class_name}",
                type=SymbolType.ENTITY,
                name=class_name,
                qualified_name=f"{file_path}::{class_name}",
                file_path=file_path,
                line_start=model.get('line_start', 0),
                line_end=model.get('line_end', 0),
                metadata={
                    'base_class': base_class,
                    'table_name': table_name,
                    'orm_type': orm_type,
                },
            ))

            # Create ENTITY_FIELD symbols for each field
            for field in model.get('fields', []):
                field_name = field.get('name')
                if not field_name:
                    continue

                column_name = field.get('column_name', field_name)

                symbols.append(Symbol(
                    id=f"{file_path}::{class_name}.{field_name}",
                    type=SymbolType.ENTITY_FIELD,
                    name=field_name,
                    qualified_name=f"{class_name}.{field_name}",
                    file_path=file_path,
                    line_start=field.get('line', 0),
                    metadata={
                        'field_type': field.get('field_type'),
                        'entity': class_name,
                        'table_name': table_name,
                        'column_name': column_name,
                        'orm_type': orm_type,
                        'is_relationship': field.get('is_relationship', False),
                    },
                ))

        return symbols

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        return NamingUtils.to_snake_case(name)
