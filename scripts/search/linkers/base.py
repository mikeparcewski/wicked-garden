"""
Base linker class and registry for discoverable linkers.

Linkers follow a plugin pattern:
1. Inherit from BaseLinker
2. Register with @register_linker decorator
3. Discovered and executed by LinkerRegistry
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Type, Optional
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbol_graph import SymbolGraph, Reference

logger = logging.getLogger(__name__)


class BaseLinker(ABC):
    """
    Base class for all linkers.

    Linkers analyze symbols in the graph and create Reference relationships
    between them. Each linker focuses on a specific type of relationship.
    """

    # Linker metadata (override in subclasses)
    name: str = "base"
    description: str = "Base linker"
    priority: int = 50  # Lower = runs earlier (0-100)

    def __init__(self, graph: SymbolGraph):
        """
        Initialize linker.

        Args:
            graph: Symbol graph to work with
        """
        self.graph = graph

    @abstractmethod
    def link_all(self) -> int:
        """
        Run the linker on the entire graph.

        Returns:
            Number of references created
        """
        pass

    def _add_reference(self, ref: Reference) -> bool:
        """
        Add a reference to the graph (helper method).

        Args:
            ref: Reference to add

        Returns:
            True if added (not duplicate)
        """
        if ref not in self.graph.references:
            self.graph.add_reference(ref)
            return True
        return False


# Registry for linkers
_LINKER_REGISTRY: Dict[str, Type[BaseLinker]] = {}


def register_linker(cls: Type[BaseLinker]) -> Type[BaseLinker]:
    """
    Decorator to register a linker class.

    Usage:
        @register_linker
        class MyLinker(BaseLinker):
            name = "my_linker"
            ...
    """
    _LINKER_REGISTRY[cls.name] = cls
    return cls


def get_linker(name: str) -> Optional[Type[BaseLinker]]:
    """Get a linker class by name."""
    return _LINKER_REGISTRY.get(name)


def list_linkers() -> List[str]:
    """List all registered linker names."""
    return list(_LINKER_REGISTRY.keys())


class LinkerRegistry:
    """
    Registry that discovers and runs linkers.

    Linkers are run in priority order (lower priority runs first).
    """

    def __init__(self, graph: SymbolGraph):
        """
        Initialize registry.

        Args:
            graph: Symbol graph to work with
        """
        self.graph = graph
        self._linkers: List[BaseLinker] = []

    def discover(self) -> None:
        """
        Discover and instantiate all registered linkers.

        Linkers are sorted by priority.
        """
        self._linkers = []

        for name, linker_class in sorted(
            _LINKER_REGISTRY.items(),
            key=lambda x: x[1].priority
        ):
            try:
                linker = linker_class(self.graph)
                self._linkers.append(linker)
                logger.debug(f"Discovered linker: {name} (priority={linker_class.priority})")
            except Exception as e:
                logger.warning(f"Failed to instantiate linker {name}: {e}")

    def run_all(self, linker_names: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Run all (or specified) linkers.

        Args:
            linker_names: Optional list of specific linkers to run

        Returns:
            Dict of linker name -> references created
        """
        if not self._linkers:
            self.discover()

        results = {}

        for linker in self._linkers:
            # Skip if not in requested list
            if linker_names and linker.name not in linker_names:
                continue

            try:
                logger.info(f"Running linker: {linker.name}")
                count = linker.link_all()
                results[linker.name] = count
                logger.info(f"  Created {count} references")
            except Exception as e:
                logger.error(f"Linker {linker.name} failed: {e}")
                results[linker.name] = -1

        return results

    def get_stats(self) -> Dict[str, any]:
        """Get stats about registered linkers."""
        return {
            "linker_count": len(_LINKER_REGISTRY),
            "linkers": [
                {
                    "name": name,
                    "description": cls.description,
                    "priority": cls.priority,
                }
                for name, cls in sorted(
                    _LINKER_REGISTRY.items(),
                    key=lambda x: x[1].priority
                )
            ],
        }
