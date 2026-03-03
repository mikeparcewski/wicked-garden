"""
Python ORM linkers for wicked-search.

Handles:
- SQLAlchemy models → database column mappings
- Django ORM models → database column mappings
"""

from .orm_linker import PythonORMLinker

__all__ = ['PythonORMLinker']
