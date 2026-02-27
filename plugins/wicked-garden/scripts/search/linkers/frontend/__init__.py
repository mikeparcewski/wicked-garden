"""
Frontend-specific linkers for wicked-search.

Handles:
- React component → prop/state relationships
- Vue component → data binding
- Angular component → service injection
"""

from .frontend_resolver import FrontendBindingResolver

__all__ = ['FrontendBindingResolver']
