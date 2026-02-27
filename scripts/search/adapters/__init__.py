"""
Language adapters for symbol extraction.

Each adapter handles parsing a specific language to extract ORM entities,
controllers, services, UI components, and other symbols.

Adapter Pattern Benefits:
- Uniform interface: adapter.parse(content, file_path) -> List[Symbol]
- Easy to add new languages: just implement LanguageAdapter
- Clean separation of concerns: parsing logic per language
- Auto-discovery via registry based on file extensions

Supported Languages:
- Java: JPA/Hibernate entities, Spring controllers
- Python: SQLAlchemy, Django ORM
- TypeScript/JSX: TypeORM, React components
- Prisma: Schema models
- Vue: Components, v-model bindings
- Ruby: ActiveRecord
- C#: Entity Framework
- Go: GORM
- JSP: EL expressions, form bindings
- HTML: Form fields
"""

from .base import LanguageAdapter, AdapterRegistry
from .utils import NamingUtils, safe_text, safe_line, safe_match_group
from .java_adapter import JavaAdapter
from .python_adapter import PythonAdapter
from .typescript_adapter import TypeScriptAdapter, PrismaAdapter
from .ruby_adapter import RubyAdapter
from .csharp_adapter import CSharpAdapter
from .go_adapter import GoAdapter
from .jsp_adapter import JspAdapter
from .html_adapter import HtmlAdapter
from .vue_adapter import VueAdapter

__all__ = [
    # Base
    'LanguageAdapter',
    'AdapterRegistry',
    # Utilities
    'NamingUtils',
    'safe_text',
    'safe_line',
    'safe_match_group',
    # Backend/ORM adapters
    'JavaAdapter',
    'PythonAdapter',
    'TypeScriptAdapter',
    'PrismaAdapter',
    'RubyAdapter',
    'CSharpAdapter',
    'GoAdapter',
    # Frontend/UI adapters
    'JspAdapter',
    'HtmlAdapter',
    'VueAdapter',
]
