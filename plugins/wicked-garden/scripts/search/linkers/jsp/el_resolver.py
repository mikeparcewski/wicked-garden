"""
EL Expression Path Resolver.

Resolves EL expression paths like ${person.address.city} by:
1. Finding the form bean or model attribute (person)
2. Tracing through nested fields (address.city)
3. Linking to entity fields and eventually database columns

Based on Ohio team's implementation.
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
class ElPathResolver(BaseLinker):
    """Resolves EL expression paths to their data sources."""

    # Linker metadata
    name = "el_resolver"
    description = "Resolves EL expressions (${bean.field}) to entity fields"
    priority = 20  # Run early, after entities are indexed

    # Implicit EL objects to skip
    SKIP_BEANS = {
        "pagecontext", "request", "response", "session", "application",
        "param", "paramvalues", "header", "headervalues", "cookie",
        "initparam", "actionurl", "imageurl", "empty", "not",
        "true", "false", "null",
    }

    def __init__(self, graph: SymbolGraph):
        """
        Initialize resolver.

        Args:
            graph: Symbol graph to work with
        """
        super().__init__(graph)
        self._build_entity_index()

    def _build_entity_index(self) -> None:
        """Build lookup indexes for entities by bean naming conventions."""
        self.entity_by_name: Dict[str, Symbol] = {}
        self.entity_by_bean_name: Dict[str, Symbol] = {}

        for entity in self.graph.find_by_type(SymbolType.ENTITY):
            name = entity.name
            self.entity_by_name[name.lower()] = entity

            # Common bean naming conventions:
            # Person -> person, personBean, personForm
            bean_names = [
                name[0].lower() + name[1:] if name else "",  # Person -> person
                (name[0].lower() + name[1:] + "Bean") if name else "",
                (name[0].lower() + name[1:] + "Form") if name else "",
                name.lower(),
            ]
            for bn in bean_names:
                if bn:
                    self.entity_by_bean_name[bn.lower()] = entity

        logger.debug(f"Built entity index with {len(self.entity_by_name)} entities")

    def link_all(self) -> int:
        """
        Resolve all EL expressions in the graph.

        Returns:
            Number of references created
        """
        el_expressions = self.graph.find_by_type(SymbolType.EL_EXPRESSION)
        ref_count = 0

        for el_expr in el_expressions:
            refs = self.resolve(el_expr)
            for ref in refs:
                self.graph.add_reference(ref)
                ref_count += 1

        logger.info(f"Created {ref_count} EL expression references")
        return ref_count

    # Alias for backwards compatibility
    def resolve_all(self) -> int:
        """Alias for link_all()."""
        return self.link_all()

    def resolve(self, el_expression: Symbol) -> List[Reference]:
        """
        Resolve an EL expression to its data source.

        Args:
            el_expression: EL expression symbol to resolve

        Returns:
            List of references created
        """
        references = []

        # Get the root bean from metadata
        root_bean = el_expression.metadata.get("root_bean", "")
        if not root_bean:
            # Try to parse from the raw expression
            raw = el_expression.metadata.get("raw", "") or el_expression.name
            if raw:
                # Extract first segment: ${bean.field} -> bean
                match = re.search(r'[$#]\{([a-zA-Z_][a-zA-Z0-9_]*)', raw)
                if match:
                    root_bean = match.group(1)

        if not root_bean:
            return references

        # Skip implicit objects
        if root_bean.lower() in self.SKIP_BEANS:
            return references

        # Get path segments
        path_segments = el_expression.metadata.get("path_segments", [])
        if not path_segments:
            # Try to parse from raw
            raw = el_expression.metadata.get("raw", "") or el_expression.name
            if raw:
                match = re.search(r'[$#]\{([^}]+)\}', raw)
                if match:
                    path = match.group(1)
                    # Remove method calls and array access
                    path = re.sub(r'\[.*?\]', '', path)
                    path = re.sub(r'\(.*?\)', '', path)
                    path_segments = path.split('.')

        # Try to find entity by bean name convention
        entity = self._find_entity_by_bean_name(root_bean)

        if entity:
            # Link EL to entity
            references.append(Reference(
                source_id=el_expression.id,
                target_id=entity.id,
                ref_type=ReferenceType.BINDS_TO,
                confidence=Confidence.MEDIUM,
                evidence={"root_bean": root_bean, "match": "bean_convention"},
            ))

            # Trace through entity fields (skip first segment which is the bean name)
            if len(path_segments) > 1:
                field_refs = self._trace_field_path(
                    el_expression, entity, path_segments[1:]
                )
                references.extend(field_refs)

        return references

    def _find_entity_by_bean_name(self, bean_name: str) -> Optional[Symbol]:
        """
        Find an entity by bean naming convention.

        Args:
            bean_name: Bean name like 'personBean', 'childcareAuthorizationBean'

        Returns:
            Entity symbol or None
        """
        name = bean_name.lower()

        # Direct lookup
        if name in self.entity_by_bean_name:
            return self.entity_by_bean_name[name]

        # Try stripping common suffixes
        for suffix in ["bean", "form", "command", "vo", "dto"]:
            if name.endswith(suffix):
                stripped = name[:-len(suffix)]
                if stripped in self.entity_by_name:
                    return self.entity_by_name[stripped]
                if stripped in self.entity_by_bean_name:
                    return self.entity_by_bean_name[stripped]

        # Try fuzzy match (entity name contains or is contained in bean name)
        for entity_name, entity in self.entity_by_name.items():
            if entity_name in name or name in entity_name:
                return entity

        return None

    def _trace_field_path(
        self, el_expr: Symbol, entity: Symbol, path_segments: List[str]
    ) -> List[Reference]:
        """
        Trace a field path through nested objects.

        Args:
            el_expr: The EL expression being resolved
            entity: Starting entity
            path_segments: Field names to traverse

        Returns:
            List of references created
        """
        references = []
        current = entity

        for segment in path_segments:
            # Skip empty segments or method calls
            if not segment or segment.endswith(')'):
                continue

            # Find field in current entity
            field = self._find_field(current, segment)

            if field:
                # Create reference from EL to field
                references.append(Reference(
                    source_id=el_expr.id,
                    target_id=field.id,
                    ref_type=ReferenceType.BINDS_TO,
                    confidence=Confidence.HIGH,
                    evidence={"field": segment, "entity": current.name},
                ))

                # If field has a nested type, continue tracing
                field_type = field.metadata.get("field_type") or field.metadata.get("java_type")
                if field_type:
                    nested = self._find_entity_by_name(field_type)
                    if nested:
                        current = nested
                        continue

                # Found final field
                break
            else:
                logger.debug(f"Field '{segment}' not found in {current.id}")
                break

        return references

    def _find_field(self, entity: Symbol, field_name: str) -> Optional[Symbol]:
        """
        Find a field within an entity.

        Args:
            entity: Parent entity
            field_name: Field name to find

        Returns:
            Field symbol or None
        """
        # Try exact ID match
        expected_id = f"{entity.id}.{field_name}"
        field = self.graph.get_symbol(expected_id)
        if field:
            return field

        # Try case-insensitive search
        field_name_lower = field_name.lower()
        entity_id_prefix = entity.id + "."

        for sym in self.graph.symbols.values():
            if sym.type == SymbolType.ENTITY_FIELD and sym.id.startswith(entity_id_prefix):
                if sym.name.lower() == field_name_lower:
                    return sym

        return None

    def _find_entity_by_name(self, name: str) -> Optional[Symbol]:
        """Find an entity by type name."""
        if name.lower() in self.entity_by_name:
            return self.entity_by_name[name.lower()]

        entities = self.graph.find_by_name(name, SymbolType.ENTITY)
        if entities:
            return entities[0]

        return None
