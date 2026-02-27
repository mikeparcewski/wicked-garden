"""
Java-specific linkers for wicked-search.

Handles:
- Spring MVC controller → view mappings
- JPA entity → database column mappings
- Constants → bean property resolution
"""

from .controller_linker import ControllerLinker
from .jpa_column_linker import JpaColumnLinker

__all__ = ['ControllerLinker', 'JpaColumnLinker']
