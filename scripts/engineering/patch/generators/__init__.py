"""
Code generators for wicked-patch.

Generators are the code-production side of the patch pipeline:
- Input: change spec + affected symbols
- Output: concrete patches per file

Uses the symbol graph (from --db or wicked-brain once available) to
propagate changes across all affected files automatically.
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
