"""
HTML language adapter for symbol extraction.

Extracts from plain HTML files:
- Form fields (input, select, textarea)
- Element IDs
- Basic structure
"""

from typing import List
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


@AdapterRegistry.register
class HtmlAdapter(LanguageAdapter):
    """Parse HTML files for form fields and structure."""

    name = "html"
    extensions = {'.html', '.htm'}

    # Class-level compiled patterns for better performance
    FORM_PATTERN = re.compile(
        r'<(input|select|textarea|button)\s+[^>]*'
        r'(?:name|id)\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    ID_PATTERN = re.compile(
        r'<(\w+)[^>]*\s+id\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse HTML file for form fields and IDs."""
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            # Extract form fields
            for match in self.FORM_PATTERN.finditer(content):
                tag_type = match.group(1).lower()
                field_name = match.group(2)
                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::form.{field_name}",
                    type=SymbolType.UI_BINDING,
                    name=field_name,
                    qualified_name=f"form.{field_name}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'tag_type': tag_type,
                        'binding_type': 'form_field',
                    },
                ))

            # Extract significant IDs (skip form fields already captured)
            captured_names = {s.name for s in symbols}
            for match in self.ID_PATTERN.finditer(content):
                tag_type = match.group(1).lower()
                element_id = match.group(2)

                if element_id in captured_names:
                    continue

                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::#{element_id}",
                    type=SymbolType.UI_COMPONENT,
                    name=element_id,
                    qualified_name=f"#{element_id}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'tag_type': tag_type,
                        'binding_type': 'element_id',
                    },
                ))

        except Exception as e:
            logger.debug(f"HTML parsing error for {file_path}: {e}")

        return symbols
