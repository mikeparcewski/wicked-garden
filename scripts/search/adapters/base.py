"""
Base adapter interface for language-specific symbol extraction.

All language adapters implement this interface, enabling uniform
parsing across Java, Python, TypeScript, Ruby, C#, Go, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Type, Optional, Set, Tuple
from pathlib import Path
import logging
import threading

logger = logging.getLogger(__name__)


class LanguageAdapter(ABC):
    """
    Base class for language-specific symbol extraction.

    Each adapter knows how to parse its language and extract
    ORM entities, controllers, services, and other symbols.
    """

    # Override in subclasses
    name: str = "base"
    extensions: Set[str] = set()  # e.g., {'.py'}

    def __init__(self, code_parser=None):
        """
        Initialize adapter with optional code parser for tree-sitter.

        Args:
            code_parser: CodeParser instance with tree-sitter support
        """
        self.code_parser = code_parser

    @abstractmethod
    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """
        Parse file content and extract symbols.

        Args:
            content: File content as string
            file_path: Path to the file

        Returns:
            List of Symbol objects extracted from the file
        """
        pass

    def supports_file(self, file_path: str) -> bool:
        """Check if this adapter handles the given file type."""
        ext = Path(file_path).suffix.lower()
        return ext in self.extensions


class AdapterRegistry:
    """
    Registry for language adapters.

    Maps file extensions to adapters and provides uniform parsing interface.
    Thread-safe instance caching with error tracking.
    """

    _adapters: Dict[str, Type[LanguageAdapter]] = {}
    _instances: Dict[str, LanguageAdapter] = {}
    _lock = threading.Lock()

    # Error tracking for monitoring
    _parse_errors: int = 0
    _parse_successes: int = 0

    @classmethod
    def register(cls, adapter_class: Type[LanguageAdapter]) -> Type[LanguageAdapter]:
        """
        Register an adapter class for its extensions.

        Can be used as a decorator:
            @AdapterRegistry.register
            class MyAdapter(LanguageAdapter):
                extensions = {'.my'}
        """
        for ext in adapter_class.extensions:
            cls._adapters[ext] = adapter_class
            logger.debug(f"Registered adapter {adapter_class.name} for {ext}")
        return adapter_class

    @classmethod
    def get_adapter(cls, file_path: str, code_parser=None) -> Optional[LanguageAdapter]:
        """
        Get adapter instance for a file.

        Thread-safe with atomic cache insertion.

        Args:
            file_path: Path to file
            code_parser: Optional CodeParser for tree-sitter

        Returns:
            LanguageAdapter instance or None if no adapter registered
        """
        ext = Path(file_path).suffix.lower()
        adapter_class = cls._adapters.get(ext)

        if not adapter_class:
            return None

        # Thread-safe cache lookup with atomic insertion
        cache_key = f"{adapter_class.name}:{id(code_parser)}"
        with cls._lock:
            if cache_key not in cls._instances:
                cls._instances[cache_key] = adapter_class(code_parser)
            return cls._instances[cache_key]

    @classmethod
    def supported_extensions(cls) -> Set[str]:
        """Get all registered file extensions."""
        return set(cls._adapters.keys())

    @classmethod
    def list_adapters(cls) -> Dict[str, Type[LanguageAdapter]]:
        """List all registered adapters."""
        return dict(cls._adapters)

    @classmethod
    def parse(cls, content: str, file_path: str, code_parser=None) -> List["Symbol"]:
        """
        Parse file using the appropriate adapter.

        Args:
            content: File content
            file_path: Path to file
            code_parser: Optional CodeParser for tree-sitter

        Returns:
            List of Symbols, empty if no adapter registered
        """
        adapter = cls.get_adapter(file_path, code_parser)
        if adapter:
            try:
                result = adapter.parse(content, file_path)
                cls._parse_successes += 1
                return result
            except Exception as e:
                cls._parse_errors += 1
                logger.warning(f"Adapter {adapter.name} failed on {file_path}: {e}")
                return []
        return []

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """Get parsing statistics for monitoring."""
        return {
            "parse_successes": cls._parse_successes,
            "parse_errors": cls._parse_errors,
            "registered_adapters": len(cls._adapters),
            "cached_instances": len(cls._instances),
        }

    @classmethod
    def reset_stats(cls) -> None:
        """Reset parsing statistics."""
        cls._parse_errors = 0
        cls._parse_successes = 0
