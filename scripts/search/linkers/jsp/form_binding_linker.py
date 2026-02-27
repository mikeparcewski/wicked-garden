"""
Form Binding Linker for JSP → Java mapping.

Traces the data dictionary chain:
  Form Field (JSP) → Java Constant → Bean Property → Entity Field

This enables queries like:
- "What Java property does this form field bind to?"
- "What form fields are affected if I change this entity?"
- "Show the full data flow from UI to database"
"""

import re
from typing import Dict, List, Optional, Set
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from symbol_graph import SymbolGraph, Symbol, SymbolType, Reference, ReferenceType, Confidence
from linkers.base import BaseLinker, register_linker


@register_linker
class FormBindingLinker(BaseLinker):
    """
    Links JSP form bindings to Java constants and bean properties.

    Resolution strategy:
    1. Parse form binding name (e.g., data.citizenshipAttributeNames.INS_DOCUMENT)
    2. Find matching Java constant (e.g., DTConstants.INS_DOCUMENT_TYPE)
    3. Extract bean property from constant value (e.g., "citizenshipDocType")
    4. Link to Java bean field if found
    """

    name = "form_binding_linker"
    description = "Links JSP form bindings to Java constants and bean properties"
    priority = 30  # Run after basic parsing, before other linkers

    # Patterns for extracting field names from bindings
    ATTRIBUTE_NAME_PATTERN = re.compile(r'\.([A-Z][A-Z0-9_]+)\s*$')

    def __init__(self, graph: SymbolGraph):
        super().__init__(graph)
        self._constant_map: Dict[str, Dict] = {}  # FIELD_NAME -> {symbol, value, bean_property}
        self._bean_fields: Dict[str, Symbol] = {}  # bean_property -> Symbol

    def link_all(self) -> int:
        """Run the linker on all form bindings."""
        # Build indexes
        self._build_constant_index()
        self._build_bean_field_index()

        # Link form bindings
        count = 0
        form_bindings = self.graph.find_by_type(SymbolType.FORM_BINDING)

        for binding in form_bindings:
            refs_created = self._link_binding(binding)
            count += refs_created

        return count

    def _build_constant_index(self) -> None:
        """
        Build index of Java constants that map field names to bean properties.

        Looks for patterns like:
            public static final String INS_DOCUMENT_TYPE = "citizenshipDocType";
        """
        # Find all Java constants (fields with constant metadata)
        # For now, we look for patterns in the metadata
        for symbol in self.graph.symbols.values():
            if symbol.type == SymbolType.ENTITY_FIELD:
                metadata = symbol.metadata
                # Check if this looks like a constant definition
                if metadata.get('is_constant') or metadata.get('is_static_final'):
                    field_name = symbol.name.upper()
                    value = metadata.get('value', '')
                    if value and isinstance(value, str):
                        self._constant_map[field_name] = {
                            'symbol': symbol,
                            'value': value,
                            'bean_property': value,
                        }

    def _build_bean_field_index(self) -> None:
        """Build index of bean fields by property name."""
        for symbol in self.graph.symbols.values():
            if symbol.type == SymbolType.ENTITY_FIELD:
                # Index by field name (both as-is and camelCase variations)
                self._bean_fields[symbol.name] = symbol
                self._bean_fields[symbol.name.lower()] = symbol

    def _link_binding(self, binding: Symbol) -> int:
        """
        Link a form binding to its backend counterparts.

        Returns number of references created.
        """
        count = 0
        binding_name = binding.name

        # Extract the field name from the binding
        # e.g., "data.citizenshipAttributeNames.INS_DOCUMENT" -> "INS_DOCUMENT"
        field_name = self._extract_field_name(binding_name)
        if not field_name:
            return 0

        # Try to find matching constant
        constant_info = self._find_constant(field_name)
        if constant_info:
            # Link binding -> constant
            ref = Reference(
                source_id=binding.id,
                target_id=constant_info['symbol'].id,
                ref_type=ReferenceType.BINDS_TO,
                confidence=Confidence.HIGH,
                evidence={
                    'field_name': field_name,
                    'constant_value': constant_info['value'],
                    'resolution': 'constant_lookup',
                },
            )
            if self._add_reference(ref):
                count += 1

            # Try to link to bean property
            bean_property = constant_info['bean_property']
            bean_field = self._bean_fields.get(bean_property) or self._bean_fields.get(bean_property.lower())
            if bean_field:
                ref = Reference(
                    source_id=binding.id,
                    target_id=bean_field.id,
                    ref_type=ReferenceType.BINDS_TO,
                    confidence=Confidence.HIGH,
                    evidence={
                        'field_name': field_name,
                        'bean_property': bean_property,
                        'resolution': 'constant_to_bean',
                    },
                )
                if self._add_reference(ref):
                    count += 1

        else:
            # No constant found - try direct bean property matching
            # Convert SCREAMING_SNAKE to camelCase
            bean_property = self._to_camel_case(field_name)
            bean_field = self._bean_fields.get(bean_property) or self._bean_fields.get(bean_property.lower())

            if bean_field:
                ref = Reference(
                    source_id=binding.id,
                    target_id=bean_field.id,
                    ref_type=ReferenceType.BINDS_TO,
                    confidence=Confidence.MEDIUM,
                    evidence={
                        'field_name': field_name,
                        'bean_property': bean_property,
                        'resolution': 'name_convention',
                    },
                )
                if self._add_reference(ref):
                    count += 1

        # Also update binding metadata with resolved info
        if constant_info:
            binding.metadata['resolved_constant'] = constant_info['symbol'].qualified_name
            binding.metadata['resolved_bean_property'] = constant_info['bean_property']

        return count

    def _extract_field_name(self, binding_name: str) -> Optional[str]:
        """
        Extract the field name from a binding path.

        Examples:
        - "data.citizenshipAttributeNames.INS_DOCUMENT" -> "INS_DOCUMENT"
        - "person.firstName" -> "FIRST_NAME" (converted)
        - "INS_DOCUMENT_TYPE" -> "INS_DOCUMENT_TYPE"
        """
        # Try to find SCREAMING_SNAKE pattern at end
        match = self.ATTRIBUTE_NAME_PATTERN.search(binding_name)
        if match:
            return match.group(1)

        # Take last segment
        parts = binding_name.split('.')
        if parts:
            last = parts[-1].strip()
            # Convert camelCase to SCREAMING_SNAKE if needed
            if last and not last.isupper():
                return self._to_screaming_snake(last)
            return last

        return None

    def _find_constant(self, field_name: str) -> Optional[Dict]:
        """Find a constant matching the field name."""
        # Direct match
        if field_name in self._constant_map:
            return self._constant_map[field_name]

        # Try with common suffixes
        for suffix in ['_TYPE', '_CODE', '_ID', '_NAME', '']:
            key = field_name + suffix
            if key in self._constant_map:
                return self._constant_map[key]

        # Try without common suffixes
        for suffix in ['_TYPE', '_CODE', '_ID', '_NAME']:
            if field_name.endswith(suffix):
                key = field_name[:-len(suffix)]
                if key in self._constant_map:
                    return self._constant_map[key]

        return None

    def _to_camel_case(self, screaming_snake: str) -> str:
        """Convert SCREAMING_SNAKE_CASE to camelCase."""
        parts = screaming_snake.lower().split('_')
        if not parts:
            return screaming_snake.lower()
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _to_screaming_snake(self, camel_case: str) -> str:
        """Convert camelCase to SCREAMING_SNAKE_CASE."""
        result = re.sub(r'([a-z])([A-Z])', r'\1_\2', camel_case)
        return result.upper()
