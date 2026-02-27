"""
Frontend Binding Resolver.

Resolves frontend data bindings to their sources:
- Vue: v-model, :prop bindings
- React: {state.value} expressions
- Angular: [(ngModel)], [property] bindings
"""

import logging
import re
from typing import List, Optional, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from symbol_graph import (
    SymbolGraph,
    Symbol,
    Reference,
    SymbolType,
    ReferenceType,
    Confidence,
)
from linkers.base import BaseLinker, register_linker

logger = logging.getLogger(__name__)


@register_linker
class FrontendBindingResolver(BaseLinker):
    """Resolves frontend data bindings to their sources."""

    # Linker metadata
    name = "frontend"
    description = "Resolves React/Vue/Angular bindings to data sources"
    priority = 40  # Run after controller linker

    def __init__(self, graph: SymbolGraph):
        """
        Initialize resolver.

        Args:
            graph: Symbol graph to work with
        """
        super().__init__(graph)

    def link_all(self) -> int:
        """
        Resolve all frontend bindings.

        Returns:
            Number of references created
        """
        ref_count = 0

        # Resolve data bindings
        for binding in self.graph.find_by_type(SymbolType.DATA_BINDING):
            refs = self.resolve(binding)
            for ref in refs:
                self.graph.add_reference(ref)
                ref_count += 1

        # Resolve form fields
        for field in self.graph.find_by_type(SymbolType.FORM_FIELD):
            refs = self._resolve_form_field(field)
            for ref in refs:
                self.graph.add_reference(ref)
                ref_count += 1

        logger.info(f"Created {ref_count} frontend binding references")
        return ref_count

    # Alias for backwards compatibility
    def resolve_all(self) -> int:
        """Alias for link_all()."""
        return self.link_all()

    def resolve(self, binding: Symbol) -> List[Reference]:
        """
        Resolve a data binding to its source.

        Args:
            binding: Data binding symbol

        Returns:
            List of references created
        """
        references = []

        root = binding.metadata.get("root", "")
        if not root:
            # Try to parse from name
            parts = binding.name.split('.')
            if parts:
                root = parts[0]

        if not root:
            return references

        file_path = binding.file_path
        framework = binding.metadata.get("framework", "")

        # Find component props in same file
        file_symbols = self.graph.find_by_file(file_path)

        for sym in file_symbols:
            if sym.type == SymbolType.COMPONENT_PROP:
                if sym.name.lower() == root.lower():
                    references.append(Reference(
                        source_id=binding.id,
                        target_id=sym.id,
                        ref_type=ReferenceType.BINDS_TO,
                        confidence=Confidence.HIGH,
                        evidence={"match": "prop_name", "framework": framework},
                    ))
                    break

        # If no prop found, try to find component state (for React)
        if not references and framework == "react":
            # Look for useState or class state
            state_name = root
            for sym in file_symbols:
                if sym.type == SymbolType.FUNCTION and "useState" in str(sym.metadata):
                    references.append(Reference(
                        source_id=binding.id,
                        target_id=sym.id,
                        ref_type=ReferenceType.BINDS_TO,
                        confidence=Confidence.MEDIUM,
                        evidence={"match": "state_variable", "framework": framework},
                    ))
                    break

        # Try to link to backend entities (for form bindings)
        if not references:
            entity_refs = self._try_link_to_entity(binding, root)
            references.extend(entity_refs)

        return references

    def _resolve_form_field(self, field: Symbol) -> List[Reference]:
        """
        Resolve a form field to its data source.

        Args:
            field: Form field symbol

        Returns:
            List of references created
        """
        references = []

        # Form fields might bind to API/backend fields
        field_name = field.name

        # Look for entity fields with same name
        for entity_field in self.graph.find_by_type(SymbolType.ENTITY_FIELD):
            if entity_field.name.lower() == field_name.lower():
                references.append(Reference(
                    source_id=field.id,
                    target_id=entity_field.id,
                    ref_type=ReferenceType.BINDS_TO,
                    confidence=Confidence.LOW,
                    evidence={"match": "name_convention"},
                ))
                break

        return references

    def _try_link_to_entity(self, binding: Symbol, root: str) -> List[Reference]:
        """
        Try to link a frontend binding to a backend entity.

        Args:
            binding: The binding symbol
            root: Root variable name

        Returns:
            List of references created
        """
        references = []

        # Look for entities that might match
        for entity in self.graph.find_by_type(SymbolType.ENTITY):
            # Check if entity name matches root (case insensitive)
            entity_lower = entity.name.lower()
            root_lower = root.lower()

            if entity_lower == root_lower or entity_lower in root_lower or root_lower in entity_lower:
                references.append(Reference(
                    source_id=binding.id,
                    target_id=entity.id,
                    ref_type=ReferenceType.BINDS_TO,
                    confidence=Confidence.INFERRED,
                    evidence={"match": "entity_name_similarity"},
                ))
                break

        return references
