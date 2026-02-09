"""
Java language adapter for symbol extraction.

Extracts:
- @Entity classes -> ENTITY with ENTITY_FIELD children
- @Controller/@RestController -> CONTROLLER
- @Service -> SERVICE
- @Repository -> DAO
- @RequestMapping methods -> CONTROLLER_METHOD
"""

from typing import List, Set
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


@AdapterRegistry.register
class JavaAdapter(LanguageAdapter):
    """Parse Java files for ORM entities, controllers, services."""

    name = "java"
    extensions = {'.java'}

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse Java file using tree-sitter.

        Uses java.scm query to detect annotations and extract symbols.
        """
        if not self.code_parser or not HAS_SYMBOL_GRAPH or not HAS_TREESITTER:
            return []

        symbols = []

        try:
            parser = self.code_parser._get_parser('.java')
            if not parser:
                return symbols

            tree = parser.parse(content.encode())

            if self.code_parser._query_loader:
                query_text = self.code_parser._query_loader.load_query('java')
                if query_text:
                    ts_language = get_language('java')
                    query = ts.Query(ts_language, query_text)
                    cursor = ts.QueryCursor(query)
                    matches = list(cursor.matches(tree.root_node))

                    # Collect class info
                    class_info = {
                        'name': None,
                        'annotations': [],
                        'annotation_args': {},
                        'extends': None,
                        'line_start': 0,
                        'line_end': 0,
                        '_current_annotation': None,
                    }
                    fields = []
                    methods = []
                    current_field = {}

                    for pattern_idx, captures_dict in matches:
                        for name, nodes in captures_dict.items():
                            for node in nodes:
                                text = content[node.start_byte:node.end_byte]
                                line = node.start_point[0] + 1

                                if name == 'code_class.def':
                                    class_info['line_start'] = node.start_point[0] + 1
                                    class_info['line_end'] = node.end_point[0] + 1
                                elif name == 'code_class.name':
                                    class_info['name'] = text
                                elif name == 'code_class.annotation':
                                    class_info['annotations'].append(text)
                                    class_info['_current_annotation'] = text
                                    if text not in class_info['annotation_args']:
                                        class_info['annotation_args'][text] = {}
                                elif name == 'code_class.annotation_key':
                                    class_info['_current_key'] = text
                                elif name == 'code_class.annotation_value':
                                    current_annotation = class_info.get('_current_annotation')
                                    current_key = class_info.get('_current_key')
                                    if current_annotation and current_key:
                                        value = text.strip('"\'')
                                        class_info['annotation_args'][current_annotation][current_key] = value
                                        class_info['_current_key'] = None
                                elif name == 'code_class.annotation_default':
                                    current_annotation = class_info.get('_current_annotation')
                                    if current_annotation:
                                        value = text.strip('"\'')
                                        class_info['annotation_args'][current_annotation]['value'] = value
                                elif name == 'code_class.extends':
                                    class_info['extends'] = text

                                elif name == 'code_field.def':
                                    if current_field.get('name'):
                                        current_field.pop('_current_annotation', None)
                                        current_field.pop('_current_key', None)
                                        fields.append(current_field)
                                    current_field = {
                                        'name': None,
                                        'type': None,
                                        'annotations': [],
                                        'annotation_args': {},
                                        'line': line,
                                        '_current_annotation': None,
                                    }
                                elif name == 'code_field.name':
                                    current_field['name'] = text
                                elif name == 'code_field.type':
                                    current_field['type'] = text
                                elif name == 'code_field.annotation':
                                    current_field['annotations'].append(text)
                                    current_field['_current_annotation'] = text
                                    if text not in current_field['annotation_args']:
                                        current_field['annotation_args'][text] = {}
                                elif name == 'code_field.annotation_key':
                                    current_field['_current_key'] = text
                                elif name == 'code_field.annotation_value':
                                    current_annotation = current_field.get('_current_annotation')
                                    current_key = current_field.get('_current_key')
                                    if current_annotation and current_key:
                                        value = text.strip('"\'')
                                        current_field['annotation_args'][current_annotation][current_key] = value
                                        current_field['_current_key'] = None
                                elif name == 'code_field.annotation_default':
                                    current_annotation = current_field.get('_current_annotation')
                                    if current_annotation:
                                        value = text.strip('"\'')
                                        current_field['annotation_args'][current_annotation]['value'] = value

                                elif name == 'code_method.def':
                                    methods.append({'name': None, 'annotations': [], 'line_start': line, 'line_end': node.end_point[0] + 1})
                                elif name == 'code_method.name':
                                    if methods:
                                        methods[-1]['name'] = text
                                elif name == 'code_method.annotation':
                                    if methods:
                                        methods[-1]['annotations'].append(text)

                    # Save last field
                    if current_field.get('name'):
                        current_field.pop('_current_annotation', None)
                        current_field.pop('_current_key', None)
                        fields.append(current_field)

                    # Build symbols
                    symbols = self._build_symbols(
                        class_info, fields, methods, file_path
                    )

        except Exception as e:
            logger.debug(f"Java parsing error for {file_path}: {e}")

        return symbols

    def _build_symbols(
        self,
        class_info: dict,
        fields: list,
        methods: list,
        file_path: str
    ) -> List["Symbol"]:
        """Build Symbol objects from parsed data."""
        symbols = []

        annotations = set(class_info['annotations'])
        is_entity = 'Entity' in annotations or 'Table' in annotations
        is_controller = 'Controller' in annotations or 'RestController' in annotations
        is_service = 'Service' in annotations
        is_repository = 'Repository' in annotations

        if class_info['name']:
            if is_entity:
                symbol_type = SymbolType.ENTITY
            elif is_controller:
                symbol_type = SymbolType.CONTROLLER
            elif is_service:
                symbol_type = SymbolType.SERVICE
            elif is_repository:
                symbol_type = SymbolType.DAO
            else:
                symbol_type = SymbolType.CLASS

            class_annotation_args = class_info.get('annotation_args', {})
            table_args = class_annotation_args.get('Table', {})
            table_name = table_args.get('name') or table_args.get('value')

            symbols.append(Symbol(
                id=f"{file_path}::{class_info['name']}",
                type=symbol_type,
                name=class_info['name'],
                qualified_name=f"{file_path}::{class_info['name']}",
                file_path=file_path,
                line_start=class_info['line_start'],
                line_end=class_info['line_end'],
                metadata={
                    'annotations': list(annotations),
                    'annotation_args': class_annotation_args,
                    'extends': class_info['extends'],
                    'table_name': table_name,
                },
            ))

            # Create field symbols for entities
            if is_entity:
                for f in fields:
                    if f.get('name') and f['name'] not in ('serialVersionUID', 'logger', 'LOG'):
                        field_annotations = f.get('annotations', [])
                        annotation_args = f.get('annotation_args', {})

                        column_args = annotation_args.get('Column', {})
                        join_column_args = annotation_args.get('JoinColumn', {})

                        column_name = (
                            column_args.get('name') or
                            column_args.get('value') or
                            join_column_args.get('name') or
                            join_column_args.get('value') or
                            f['name']
                        )

                        is_primary_key = 'Id' in field_annotations
                        is_foreign_key = bool(
                            'JoinColumn' in field_annotations or
                            'ManyToOne' in field_annotations or
                            'OneToOne' in field_annotations
                        )

                        symbols.append(Symbol(
                            id=f"{file_path}::{class_info['name']}.{f['name']}",
                            type=SymbolType.ENTITY_FIELD,
                            name=f['name'],
                            qualified_name=f"{class_info['name']}.{f['name']}",
                            file_path=file_path,
                            line_start=f.get('line', 0),
                            metadata={
                                'field_type': f.get('type'),
                                'java_type': f.get('type'),
                                'annotations': field_annotations,
                                'annotation_args': annotation_args,
                                'entity': class_info['name'],
                                'table_name': table_name,
                                'column_name': column_name,
                                'is_primary_key': is_primary_key,
                                'is_foreign_key': is_foreign_key,
                            },
                        ))

            # Create method symbols for controllers
            if is_controller:
                for m in methods:
                    if m.get('name'):
                        m_annotations = set(m.get('annotations', []))
                        is_mapping = any(a in m_annotations for a in [
                            'RequestMapping', 'GetMapping', 'PostMapping',
                            'PutMapping', 'DeleteMapping', 'PatchMapping'
                        ])
                        if is_mapping:
                            symbols.append(Symbol(
                                id=f"{file_path}::{class_info['name']}.{m['name']}",
                                type=SymbolType.CONTROLLER_METHOD,
                                name=m['name'],
                                qualified_name=f"{class_info['name']}.{m['name']}",
                                file_path=file_path,
                                line_start=m.get('line_start', 0),
                                line_end=m.get('line_end', 0),
                                metadata={
                                    'annotations': list(m_annotations),
                                    'has_mapping': True,
                                },
                            ))

        return symbols
