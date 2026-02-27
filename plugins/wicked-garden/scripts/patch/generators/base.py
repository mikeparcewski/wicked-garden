"""
Base generator interface and registry for language-agnostic code generation.

Generators are the symmetric counterpart to adapters. While adapters extract
symbols from code, generators create patches to modify code based on change
specifications and the symbol graph.

Architecture:
    ChangeSpec -> Generator.generate() -> Patch/PatchSet

The propagation engine uses lineage paths to coordinate generators:
    1. User specifies a change to a symbol (e.g., add field to entity)
    2. Lineage tracer finds all dependent symbols
    3. For each affected file, the appropriate generator creates patches
    4. All patches are returned as a PatchSet for review/application
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union
import logging
import threading

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes that can be propagated."""
    ADD_FIELD = "add_field"           # Add a field to an entity/class
    REMOVE_FIELD = "remove_field"     # Remove a field
    RENAME_FIELD = "rename_field"     # Rename a field
    MODIFY_FIELD = "modify_field"     # Change field type or attributes
    ADD_VALIDATION = "add_validation" # Add validation logic
    ADD_COLUMN = "add_column"         # Add database column
    RENAME_COLUMN = "rename_column"   # Rename database column
    ADD_UI_BINDING = "add_ui_binding" # Add UI binding for field
    UPDATE_UI_BINDING = "update_ui_binding"  # Update existing UI binding


@dataclass
class FieldSpec:
    """Specification for a field/property."""
    name: str
    type: str                          # Language-agnostic type hint
    nullable: bool = True
    default: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None  # e.g., {"min": 0, "max": 100}
    annotations: List[str] = field(default_factory=list)
    column_name: Optional[str] = None  # Database column name if different
    label: Optional[str] = None        # UI label
    description: Optional[str] = None


@dataclass
class ChangeSpec:
    """
    Specification for a change to propagate.

    This is language-agnostic - the generator translates it to
    language-specific code modifications.
    """
    change_type: ChangeType
    target_symbol_id: str              # Symbol being modified
    field_spec: Optional[FieldSpec] = None  # For add/modify field
    old_name: Optional[str] = None     # For rename operations
    new_name: Optional[str] = None     # For rename operations
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.change_type, str):
            self.change_type = ChangeType(self.change_type)


@dataclass
class Patch:
    """
    A single code modification.

    Patches are expressed as line-based edits to maintain
    readability and allow for conflict detection.
    """
    file_path: str
    line_start: int                    # 1-based line number
    line_end: int                      # Inclusive end line
    old_content: str                   # Original lines (for verification)
    new_content: str                   # Replacement content
    description: str                   # Human-readable description
    symbol_id: Optional[str] = None    # Related symbol
    confidence: str = "high"           # high/medium/low

    @property
    def is_insert(self) -> bool:
        """True if this is an insertion (no lines replaced)."""
        return self.line_start > self.line_end

    @property
    def is_delete(self) -> bool:
        """True if this is a deletion (empty new content)."""
        return not self.new_content.strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "old": self.old_content,
            "new": self.new_content,
            "description": self.description,
            "symbol_id": self.symbol_id,
            "confidence": self.confidence,
        }

    def to_unified_diff(self) -> str:
        """Generate unified diff format."""
        from difflib import unified_diff
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        diff = unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm=""
        )
        return "".join(diff)


@dataclass
class PatchSet:
    """
    Collection of patches for a change propagation.

    Groups patches by file and provides aggregate statistics.
    """
    change_spec: ChangeSpec
    patches: List[Patch] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def files_affected(self) -> Set[str]:
        """Set of files that will be modified."""
        return {p.file_path for p in self.patches}

    @property
    def patch_count(self) -> int:
        return len(self.patches)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def patches_by_file(self) -> Dict[str, List[Patch]]:
        """Group patches by file path."""
        by_file: Dict[str, List[Patch]] = {}
        for patch in self.patches:
            if patch.file_path not in by_file:
                by_file[patch.file_path] = []
            by_file[patch.file_path].append(patch)
        # Sort patches within each file by line number (descending for safe application).
        # enumerate() provides a stable secondary key so same-position patches
        # preserve their original generation order after reversal.
        for patches in by_file.values():
            indexed = list(enumerate(patches))
            indexed.sort(key=lambda t: (t[1].line_start, t[0]), reverse=True)
            patches[:] = [p for _, p in indexed]
        return by_file

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_spec.change_type.value,
            "target": self.change_spec.target_symbol_id,
            "files_affected": list(self.files_affected),
            "patch_count": self.patch_count,
            "patches": [p.to_dict() for p in self.patches],
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Change: {self.change_spec.change_type.value}",
            f"Target: {self.change_spec.target_symbol_id}",
            f"Files affected: {len(self.files_affected)}",
            f"Patches: {self.patch_count}",
        ]
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        return "\n".join(lines)


class BaseGenerator(ABC):
    """
    Base class for language-specific code generators.

    Each generator knows how to create patches for its language
    based on change specifications.
    """

    # Override in subclasses
    name: str = "base"
    extensions: Set[str] = set()  # e.g., {'.java'}
    symbol_types: Set[str] = set()  # Symbol types this generator handles

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize generator.

        Args:
            db_path: Path to symbol database for context lookup
        """
        self.db_path = db_path
        self._conn = None

    @abstractmethod
    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """
        Generate patches for a change.

        Args:
            change_spec: The change to apply
            symbol: The symbol being modified (from database)
            file_content: Current content of the file

        Returns:
            List of patches to apply
        """
        pass

    def supports_file(self, file_path: str) -> bool:
        """Check if this generator handles the given file type."""
        ext = Path(file_path).suffix.lower()
        return ext in self.extensions

    def supports_symbol(self, symbol_type: str) -> bool:
        """Check if this generator handles the given symbol type."""
        return symbol_type.lower() in {t.lower() for t in self.symbol_types}

    def _get_indentation(self, line: str) -> str:
        """Extract indentation from a line."""
        return line[:len(line) - len(line.lstrip())]

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """
        Map a generic type to a language-specific type.

        Override in subclasses for language-specific mappings.
        """
        # Default mappings
        type_map = {
            "string": "String",
            "int": "int",
            "integer": "Integer",
            "long": "Long",
            "float": "float",
            "double": "double",
            "boolean": "boolean",
            "date": "Date",
            "datetime": "LocalDateTime",
            "decimal": "BigDecimal",
        }
        return type_map.get(generic_type.lower(), generic_type)


# Registry for generators
_GENERATOR_REGISTRY: Dict[str, Type[BaseGenerator]] = {}
_instances: Dict[str, BaseGenerator] = {}
_lock = threading.Lock()


def register_generator(cls: Type[BaseGenerator]) -> Type[BaseGenerator]:
    """
    Decorator to register a generator class.

    Usage:
        @register_generator
        class JavaGenerator(BaseGenerator):
            name = "java"
            extensions = {'.java'}
            ...
    """
    for ext in cls.extensions:
        _GENERATOR_REGISTRY[ext] = cls
        logger.debug(f"Registered generator {cls.name} for {ext}")
    return cls


class GeneratorRegistry:
    """
    Registry for code generators.

    Maps file extensions and symbol types to generators.
    Thread-safe with instance caching.
    """

    @classmethod
    def get_generator(
        cls,
        file_path: str,
        db_path: Optional[Path] = None
    ) -> Optional[BaseGenerator]:
        """
        Get generator instance for a file.

        Args:
            file_path: Path to file
            db_path: Optional database path

        Returns:
            Generator instance or None
        """
        ext = Path(file_path).suffix.lower()
        generator_class = _GENERATOR_REGISTRY.get(ext)

        if not generator_class:
            return None

        # Thread-safe cache lookup
        cache_key = f"{generator_class.name}:{db_path}"
        with _lock:
            if cache_key not in _instances:
                _instances[cache_key] = generator_class(db_path)
            return _instances[cache_key]

    @classmethod
    def supported_extensions(cls) -> Set[str]:
        """Get all registered file extensions."""
        return set(_GENERATOR_REGISTRY.keys())

    @classmethod
    def list_generators(cls) -> Dict[str, Type[BaseGenerator]]:
        """List all registered generators."""
        return dict(_GENERATOR_REGISTRY)

    @classmethod
    def generate(
        cls,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        file_path: str,
        db_path: Optional[Path] = None,
    ) -> List[Patch]:
        """
        Generate patches using the appropriate generator.

        Args:
            change_spec: Change specification
            symbol: Symbol being modified
            file_content: Current file content
            file_path: Path to file
            db_path: Optional database path

        Returns:
            List of patches, empty if no generator available
        """
        generator = cls.get_generator(file_path, db_path)
        if generator:
            try:
                return generator.generate(change_spec, symbol, file_content)
            except Exception as e:
                logger.warning(f"Generator {generator.name} failed: {e}")
                return []
        return []
