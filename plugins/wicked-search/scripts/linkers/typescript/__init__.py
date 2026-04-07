"""
TypeScript ORM linkers for wicked-search.

Handles:
- TypeORM models → database column mappings
- Prisma models → database column mappings
"""

from .orm_linker import TypeScriptORMLinker

__all__ = ['TypeScriptORMLinker']
