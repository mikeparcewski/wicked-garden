"""
Vue language adapter for symbol extraction.

Extracts from Vue Single File Components:
- Components (kebab-case and PascalCase)
- v-model bindings
- v-bind/: bindings
- v-on/@ event handlers
- Form fields
"""

from typing import List
import re
import logging

from .base import LanguageAdapter, AdapterRegistry

logger = logging.getLogger(__name__)

# Conditional imports
try:
    from symbol_graph import Symbol, SymbolType
    HAS_SYMBOL_GRAPH = True
except ImportError:
    HAS_SYMBOL_GRAPH = False
    Symbol = None
    SymbolType = None


@AdapterRegistry.register
class VueAdapter(LanguageAdapter):
    """Parse Vue SFC files for components and bindings."""

    name = "vue"
    extensions = {'.vue'}

    # Class-level compiled patterns for better performance
    COMPONENT_PATTERN = re.compile(
        r'<([a-z]+-[a-z-]+|[A-Z][a-zA-Z0-9]+)(?:\s|>|/)'
    )
    V_MODEL_PATTERN = re.compile(
        r'v-model(?:\.[\w]+)*\s*=\s*["\']([^"\']+)["\']'
    )
    V_BIND_PATTERN = re.compile(
        r'(?:v-bind:|:)(\w+)\s*=\s*["\']([^"\']+)["\']'
    )
    V_ON_PATTERN = re.compile(
        r'(?:v-on:|@)(\w+)\s*=\s*["\']([^"\']+)["\']'
    )
    FORM_PATTERN = re.compile(
        r'<(input|select|textarea)\s+[^>]*'
        r'(?:name|id)\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse Vue file for components and bindings."""
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            # Extract components
            seen_components = set()
            for match in self.COMPONENT_PATTERN.finditer(content):
                component_name = match.group(1)
                if component_name in seen_components:
                    continue
                seen_components.add(component_name)

                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::<{component_name}>",
                    type=SymbolType.UI_COMPONENT,
                    name=component_name,
                    qualified_name=f"<{component_name}>",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'framework': 'vue',
                        'binding_type': 'component',
                    },
                ))

            # Extract v-model bindings
            for match in self.V_MODEL_PATTERN.finditer(content):
                binding_path = match.group(1)
                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::v-model:{binding_path}",
                    type=SymbolType.UI_BINDING,
                    name=binding_path,
                    qualified_name=f"v-model:{binding_path}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'framework': 'vue',
                        'binding_type': 'v-model',
                        'two_way': True,
                    },
                ))

            # Extract v-bind bindings
            for match in self.V_BIND_PATTERN.finditer(content):
                prop_name = match.group(1)
                binding_expr = match.group(2)
                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}:::{prop_name}={binding_expr}",
                    type=SymbolType.UI_BINDING,
                    name=f":{prop_name}",
                    qualified_name=f":{prop_name}={binding_expr}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'framework': 'vue',
                        'binding_type': 'v-bind',
                        'prop': prop_name,
                        'expression': binding_expr,
                    },
                ))

            # Extract event handlers
            for match in self.V_ON_PATTERN.finditer(content):
                event_name = match.group(1)
                handler = match.group(2)
                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::@{event_name}",
                    type=SymbolType.UI_BINDING,
                    name=f"@{event_name}",
                    qualified_name=f"@{event_name}={handler}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'framework': 'vue',
                        'binding_type': 'event',
                        'event': event_name,
                        'handler': handler,
                    },
                ))

            # Extract form fields
            for match in self.FORM_PATTERN.finditer(content):
                tag_type = match.group(1).lower()
                field_name = match.group(2)
                line = content[:match.start()].count('\n') + 1

                symbols.append(Symbol(
                    id=f"{file_path}::form.{field_name}",
                    type=SymbolType.UI_BINDING,
                    name=field_name,
                    qualified_name=f"form.{field_name}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        'framework': 'vue',
                        'tag_type': tag_type,
                        'binding_type': 'form_field',
                    },
                ))

        except Exception as e:
            logger.debug(f"Vue parsing error for {file_path}: {e}")

        return symbols
