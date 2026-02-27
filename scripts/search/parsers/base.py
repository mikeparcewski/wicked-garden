"""
Minimal parser registry for wicked-search.

Provides extensible parser discovery via @register_parser decorator.
New parsers can be added without modifying core plugin code.
"""

from pathlib import Path
from typing import Dict, Type, Optional, List


# Global registry: extension -> parser class
_PARSERS: Dict[str, Type] = {}


def register_parser(*extensions: str):
    """
    Decorator to register a parser for file extensions.

    Usage:
        @register_parser('.jsp', '.jspx', '.jspf')
        class JspParser:
            def parse(self, content: str, file_path: str) -> List[Symbol]:
                ...
    """
    def decorator(cls: Type) -> Type:
        for ext in extensions:
            _PARSERS[ext.lower()] = cls
        return cls
    return decorator


def get_parser(file_path: str) -> Optional[object]:
    """
    Get parser instance for a file based on extension.

    Args:
        file_path: Path to the file

    Returns:
        Parser instance or None if no parser registered
    """
    ext = Path(file_path).suffix.lower()
    cls = _PARSERS.get(ext)
    return cls() if cls else None


def list_parsers() -> Dict[str, str]:
    """
    List all registered parsers.

    Returns:
        Dict mapping extension to parser class name
    """
    return {ext: cls.__name__ for ext, cls in _PARSERS.items()}


def get_extensions() -> List[str]:
    """Get all registered file extensions."""
    return list(_PARSERS.keys())
