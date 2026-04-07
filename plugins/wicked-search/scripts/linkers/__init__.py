"""
Linker registry with language-specific organization.

Linkers create Reference relationships between symbols, enabling:
- Cross-layer tracing (JSP → Java → Database)
- Blast radius analysis
- Data dictionary generation

Structure:
- java/       - Spring MVC controllers, JPA entities
- jsp/        - EL expressions, form bindings
- frontend/   - React, Vue, Angular bindings
- python/     - SQLAlchemy, Django ORM
- typescript/ - TypeORM, Prisma
- ruby/       - ActiveRecord
- csharp/     - Entity Framework
- go/         - GORM
"""

from .base import (
    BaseLinker,
    LinkerRegistry,
    register_linker,
    get_linker,
    list_linkers,
)

# Import language-specific linkers to trigger registration
from .java import ControllerLinker, JpaColumnLinker
from .jsp import ElPathResolver, FormBindingLinker
from .frontend import FrontendBindingResolver
from .python import PythonORMLinker
from .typescript import TypeScriptORMLinker
from .ruby import RubyORMLinker
from .csharp import CSharpORMLinker
from .go import GoORMLinker

__all__ = [
    # Base
    'BaseLinker',
    'LinkerRegistry',
    'register_linker',
    'get_linker',
    'list_linkers',
    # Java
    'ControllerLinker',
    'JpaColumnLinker',
    # JSP
    'ElPathResolver',
    'FormBindingLinker',
    # Frontend
    'FrontendBindingResolver',
    # Python
    'PythonORMLinker',
    # TypeScript
    'TypeScriptORMLinker',
    # Ruby
    'RubyORMLinker',
    # C#
    'CSharpORMLinker',
    # Go
    'GoORMLinker',
]
