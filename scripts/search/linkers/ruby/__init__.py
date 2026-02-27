"""
Ruby ORM linkers for wicked-search.

Handles:
- ActiveRecord models → database column mappings
"""

from .orm_linker import RubyORMLinker

__all__ = ['RubyORMLinker']
