"""
Parser registry with auto-discovery for wicked-search.

Provides extensible parser architecture:
- @register_parser decorator for new parsers
- get_parser() for file-based parser lookup
- list_parsers() to see registered extensions

Built-in parsers:
- JspParser: Tree-based JSP/EL with label extraction
- HtmlFrontendParser: React, Vue, Angular, plain HTML
"""

from .base import register_parser, get_parser, list_parsers, get_extensions
from .jsp_parser import JspParser
from .html_parser import HtmlFrontendParser

__all__ = [
    'register_parser',
    'get_parser',
    'list_parsers',
    'get_extensions',
    'JspParser',
    'HtmlFrontendParser',
]
