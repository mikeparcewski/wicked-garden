"""
JavaScript language adapter for symbol extraction.

Extracts:
- Function declarations (named functions, arrow functions)
- ES6 class declarations and methods
- Variable declarations (const/let/var at module scope)

Handles legacy/non-module JS patterns common in enterprise apps.
Minified files (*.min.js) are excluded at the ignore handler level.
"""

from typing import List
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
class JavaScriptAdapter(LanguageAdapter):
    """Parse JavaScript files for functions, classes, and variables."""

    name = "javascript"
    extensions = {'.js', '.mjs', '.cjs'}

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse JavaScript file using tree-sitter.

        Uses javascript.scm query to extract functions, classes, and methods.
        """
        if not self.code_parser or not HAS_SYMBOL_GRAPH or not HAS_TREESITTER:
            return []

        symbols = []

        try:
            parser = self.code_parser._get_parser('.js')
            if not parser:
                return symbols

            tree = parser.parse(content.encode())

            if self.code_parser._query_loader:
                query_text = self.code_parser._query_loader.load_query('javascript')
                if query_text:
                    ts_language = get_language('javascript')
                    query = ts.Query(ts_language, query_text)
                    cursor = ts.QueryCursor(query)
                    matches = list(cursor.matches(tree.root_node))

                    seen_functions = set()
                    seen_classes = set()
                    seen_methods = set()
                    current_class = None

                    for pattern_idx, captures_dict in matches:
                        for name, nodes in captures_dict.items():
                            for node in nodes:
                                text = content[node.start_byte:node.end_byte]
                                line_start = node.start_point[0] + 1
                                line_end = node.end_point[0] + 1

                                if name == 'code_function.name' and text not in seen_functions:
                                    seen_functions.add(text)
                                    symbols.append(Symbol(
                                        id=f"{file_path}::{text}",
                                        type=SymbolType.METHOD,
                                        name=text,
                                        qualified_name=f"{file_path}::{text}",
                                        file_path=file_path,
                                        line_start=line_start,
                                        metadata={
                                            'language': 'javascript',
                                        },
                                    ))

                                elif name == 'code_class.name' and text not in seen_classes:
                                    seen_classes.add(text)
                                    current_class = text
                                    symbols.append(Symbol(
                                        id=f"{file_path}::{text}",
                                        type=SymbolType.CLASS,
                                        name=text,
                                        qualified_name=f"{file_path}::{text}",
                                        file_path=file_path,
                                        line_start=line_start,
                                        line_end=line_end,
                                        metadata={
                                            'language': 'javascript',
                                        },
                                    ))

                                elif name == 'code_method.name':
                                    qualified = f"{current_class}.{text}" if current_class else text
                                    method_key = f"{current_class or ''}:{text}:{line_start}"
                                    if method_key not in seen_methods:
                                        seen_methods.add(method_key)
                                        symbols.append(Symbol(
                                            id=f"{file_path}::{qualified}",
                                            type=SymbolType.METHOD,
                                            name=text,
                                            qualified_name=f"{file_path}::{qualified}",
                                            file_path=file_path,
                                            line_start=line_start,
                                            metadata={
                                                'language': 'javascript',
                                                'is_class_method': True,
                                            },
                                        ))

        except Exception as e:
            logger.debug(f"JavaScript parsing error for {file_path}: {e}")

        return symbols
