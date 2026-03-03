"""
JSP language adapter for symbol extraction.

Wraps the existing JspParser to provide:
- EL expressions (${...}, #{...})
- Spring form bindings (<form:input path="...">)
- Custom input tags with name/label attributes
- Control flow context tracking
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
    from parsers import JspParser
    HAS_JSP_PARSER = True
except ImportError:
    HAS_JSP_PARSER = False
    JspParser = None


@AdapterRegistry.register
class JspAdapter(LanguageAdapter):
    """Parse JSP files for EL expressions and form bindings."""

    name = "jsp"
    extensions = {'.jsp', '.jspx', '.jspf'}

    def __init__(self, code_parser=None):
        super().__init__(code_parser)
        self._parser = JspParser() if HAS_JSP_PARSER else None

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse JSP file using the legacy JspParser.

        Extracts UI bindings, form fields, and EL expressions.
        """
        if not HAS_SYMBOL_GRAPH or not self._parser:
            return []

        try:
            return self._parser.parse(content, file_path)
        except Exception as e:
            logger.debug(f"JSP parsing error for {file_path}: {e}")
            return []
