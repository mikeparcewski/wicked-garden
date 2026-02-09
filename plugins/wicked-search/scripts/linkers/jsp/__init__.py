"""
JSP-specific linkers for wicked-search.

Handles:
- EL expression → Java bean resolution
- Form binding → constant → bean property chain
- JSP include relationships
"""

from .el_resolver import ElPathResolver
from .form_binding_linker import FormBindingLinker

__all__ = ['ElPathResolver', 'FormBindingLinker']
