"""
Code generators for wicked-search.

Generators are the symmetric counterpart to adapters:
- Adapters: parse code -> extract symbols
- Generators: change spec + symbols -> generate patches

This module provides language-agnostic code generation that uses
the symbol graph and lineage paths to propagate changes across
all affected files automatically.
"""

from .base import (
    BaseGenerator,
    GeneratorRegistry,
    register_generator,
    ChangeSpec,
    ChangeType,
    FieldSpec,
    Patch,
    PatchSet,
)

# Import generators to register them
from . import java_generator
from . import jsp_generator
from . import python_generator
from . import typescript_generator
from . import sql_generator
from . import go_generator
from . import csharp_generator
from . import ruby_generator
from . import kotlin_generator
from . import rust_generator
from . import php_generator
from . import perl_generator

# Import propagation engine
from .propagation_engine import PropagationEngine, PropagationPlan, AffectedSymbol

__all__ = [
    # Base classes
    "BaseGenerator",
    "GeneratorRegistry",
    "register_generator",
    # Change specifications
    "ChangeSpec",
    "ChangeType",
    "FieldSpec",
    # Patch handling
    "Patch",
    "PatchSet",
    # Propagation
    "PropagationEngine",
    "PropagationPlan",
    "AffectedSymbol",
]
