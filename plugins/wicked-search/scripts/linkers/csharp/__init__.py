"""
C# ORM linkers for wicked-search.

Handles:
- Entity Framework models → database column mappings
"""

from .orm_linker import CSharpORMLinker

__all__ = ['CSharpORMLinker']
