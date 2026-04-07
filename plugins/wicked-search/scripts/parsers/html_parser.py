"""
HTML/Frontend Parser for React, Vue, Angular, and plain HTML.

Extracts:
- Components (PascalCase tags, app-* tags)
- Data bindings (v-model, [(ngModel)], {state})
- Form fields (input, select, textarea)
- Event handlers (@click, onClick, (click))
"""

import re
from typing import Any, Dict, List, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbol_graph import Symbol, SymbolType
from .base import register_parser


@register_parser('.html', '.htm', '.vue', '.jsx', '.tsx')
class HtmlFrontendParser:
    """Parse HTML and detect frontend framework patterns."""

    def __init__(self):
        # Framework-specific patterns
        self.patterns = {
            "react": {
                "component": re.compile(r'<([A-Z][a-zA-Z0-9]+)(?:\s|>|/)'),
                "binding": re.compile(r'\{([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\}'),
                "event": re.compile(r'on[A-Z]\w+\s*=\s*\{([^}]+)\}'),
                "state": re.compile(r'useState\s*[<(]'),
            },
            "vue": {
                "component": re.compile(r'<([a-z]+-[a-z-]+|[A-Z][a-zA-Z0-9]+)(?:\s|>|/)'),
                "binding": re.compile(r'(?:v-bind:|:)(\w+)\s*=\s*["\']([^"\']+)["\']'),
                "model": re.compile(r'v-model(?:\.[\w]+)*\s*=\s*["\']([^"\']+)["\']'),
                "event": re.compile(r'(?:v-on:|@)(\w+)\s*=\s*["\']([^"\']+)["\']'),
            },
            "angular": {
                "component": re.compile(r'<(app-[a-z-]+)(?:\s|>|/)'),
                "binding": re.compile(r'\[(\w+)\]\s*=\s*["\']([^"\']+)["\']'),
                "model": re.compile(r'\[\(ngModel\)\]\s*=\s*["\']([^"\']+)["\']'),
                "event": re.compile(r'\((\w+)\)\s*=\s*["\']([^"\']+)["\']'),
            },
        }

        # HTML form patterns
        self.form_pattern = re.compile(
            r'<(input|select|textarea|button)\s+[^>]*'
            r'(?:name|id)\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        self.id_pattern = re.compile(
            r'<(\w+)[^>]*\s+id\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

    def parse(self, content: str, file_path: str) -> List[Symbol]:
        """
        Parse HTML/frontend content and extract symbols.

        Args:
            content: File content
            file_path: Path to the file

        Returns:
            List of symbols
        """
        symbols = []

        # Detect framework
        framework = self._detect_framework(content, file_path)

        # Add page symbol
        page_type = SymbolType.HTML_PAGE
        symbols.append(Symbol(
            id=f"html:{file_path}",
            type=page_type,
            name=Path(file_path).name,
            qualified_name=file_path,
            file_path=file_path,
            line_start=1,
            metadata={"framework": framework},
        ))

        # Parse based on framework
        symbols.extend(self._parse_components(content, file_path, framework))
        symbols.extend(self._parse_data_bindings(content, file_path, framework))
        symbols.extend(self._parse_form_fields(content, file_path))
        symbols.extend(self._parse_event_handlers(content, file_path, framework))

        return symbols

    def _find_line(self, content: str, pos: int) -> int:
        """Find line number for byte position."""
        return content[:pos].count('\n') + 1

    def _detect_framework(self, content: str, file_path: str) -> str:
        """Detect frontend framework from content and file extension."""
        ext = Path(file_path).suffix.lower()

        # Extension-based detection
        if ext == ".vue":
            return "vue"
        elif ext in (".jsx", ".tsx"):
            return "react"

        # Content-based detection
        if "v-model" in content or "v-bind" in content or "@click" in content:
            return "vue"
        if re.search(r'className\s*=', content) or "useState" in content or "useEffect" in content:
            return "react"
        if "[(ngModel)]" in content or "*ngFor" in content or "@Component" in content:
            return "angular"
        if "angular" in file_path.lower():
            return "angular"

        return "html"

    def _parse_components(self, content: str, file_path: str, framework: str) -> List[Symbol]:
        """Extract component usages."""
        symbols = []
        seen = set()

        # PascalCase components (React, Vue)
        pattern = re.compile(r'<([A-Z][a-zA-Z0-9]+)(?:\s|>|/)')
        for match in pattern.finditer(content):
            name = match.group(1)
            line = self._find_line(content, match.start())
            key = f"{name}:{line}"

            if key not in seen:
                seen.add(key)
                symbols.append(Symbol(
                    id=f"component:{file_path}:{name}:{line}",
                    type=SymbolType.COMPONENT,
                    name=name,
                    qualified_name=f"{file_path}#{name}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": framework,
                        "component_type": "usage",
                    },
                ))

        # kebab-case components (Vue, Angular)
        if framework in ("vue", "angular"):
            pattern = re.compile(r'<([a-z]+-[a-z-]+)(?:\s|>|/)')
            for match in pattern.finditer(content):
                name = match.group(1)
                line = self._find_line(content, match.start())
                key = f"{name}:{line}"

                # Skip common HTML tags
                if name in ("my-app", "base-layout") or name.startswith("app-"):
                    if key not in seen:
                        seen.add(key)
                        symbols.append(Symbol(
                            id=f"component:{file_path}:{name}:{line}",
                            type=SymbolType.COMPONENT,
                            name=name,
                            qualified_name=f"{file_path}#{name}",
                            file_path=file_path,
                            line_start=line,
                            metadata={
                                "framework": framework,
                                "component_type": "usage",
                            },
                        ))

        return symbols

    def _parse_data_bindings(self, content: str, file_path: str, framework: str) -> List[Symbol]:
        """Extract data binding expressions."""
        symbols = []

        if framework == "vue":
            # v-model bindings
            pattern = re.compile(r'v-model(?:\.[\w]+)*\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                binding = match.group(1)
                line = self._find_line(content, match.start())
                segments = binding.split('.')

                symbols.append(Symbol(
                    id=f"binding:{file_path}:{line}:{binding}",
                    type=SymbolType.DATA_BINDING,
                    name=binding,
                    qualified_name=f"{file_path}#binding:{binding}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "vue",
                        "binding_type": "v-model",
                        "path_segments": segments,
                        "root": segments[0] if segments else "",
                    },
                ))

            # :prop bindings (v-bind shorthand)
            pattern = re.compile(r':(\w+)\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                prop = match.group(1)
                value = match.group(2)
                line = self._find_line(content, match.start())

                # Skip class and style bindings
                if prop not in ("class", "style", "key"):
                    segments = value.split('.')
                    symbols.append(Symbol(
                        id=f"binding:{file_path}:{line}:{prop}",
                        type=SymbolType.DATA_BINDING,
                        name=f"{prop}={value}",
                        qualified_name=f"{file_path}#bind:{prop}",
                        file_path=file_path,
                        line_start=line,
                        metadata={
                            "framework": "vue",
                            "binding_type": "v-bind",
                            "prop": prop,
                            "value": value,
                            "path_segments": segments,
                            "root": segments[0] if segments else "",
                        },
                    ))

        elif framework == "react":
            # JSX expressions {variable.path}
            pattern = re.compile(r'\{([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\}')
            for match in pattern.finditer(content):
                binding = match.group(1)
                line = self._find_line(content, match.start())
                segments = binding.split('.')

                symbols.append(Symbol(
                    id=f"binding:{file_path}:{line}:{binding}",
                    type=SymbolType.DATA_BINDING,
                    name=binding,
                    qualified_name=f"{file_path}#jsx:{binding}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "react",
                        "binding_type": "jsx",
                        "path_segments": segments,
                        "root": segments[0] if segments else "",
                    },
                ))

        elif framework == "angular":
            # [(ngModel)] two-way binding
            pattern = re.compile(r'\[\(ngModel\)\]\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                binding = match.group(1)
                line = self._find_line(content, match.start())
                segments = binding.split('.')

                symbols.append(Symbol(
                    id=f"binding:{file_path}:{line}:{binding}",
                    type=SymbolType.DATA_BINDING,
                    name=binding,
                    qualified_name=f"{file_path}#ngModel:{binding}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "angular",
                        "binding_type": "ngModel",
                        "path_segments": segments,
                        "root": segments[0] if segments else "",
                    },
                ))

            # [property] one-way binding
            pattern = re.compile(r'\[(\w+)\]\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                prop = match.group(1)
                value = match.group(2)
                line = self._find_line(content, match.start())

                # Skip ngClass, ngStyle
                if prop not in ("ngClass", "ngStyle", "ngIf", "ngFor"):
                    segments = value.split('.')
                    symbols.append(Symbol(
                        id=f"binding:{file_path}:{line}:{prop}",
                        type=SymbolType.DATA_BINDING,
                        name=f"{prop}={value}",
                        qualified_name=f"{file_path}#prop:{prop}",
                        file_path=file_path,
                        line_start=line,
                        metadata={
                            "framework": "angular",
                            "binding_type": "property",
                            "prop": prop,
                            "value": value,
                            "path_segments": segments,
                            "root": segments[0] if segments else "",
                        },
                    ))

        return symbols

    def _parse_form_fields(self, content: str, file_path: str) -> List[Symbol]:
        """Extract HTML form field elements."""
        symbols = []
        seen = set()

        for match in self.form_pattern.finditer(content):
            tag = match.group(1).lower()
            name = match.group(2)
            line = self._find_line(content, match.start())
            key = f"{name}:{line}"

            if key not in seen:
                seen.add(key)
                symbols.append(Symbol(
                    id=f"field:{file_path}:{name}:{line}",
                    type=SymbolType.FORM_FIELD,
                    name=name,
                    qualified_name=f"{file_path}#field:{name}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "tag": tag,
                    },
                ))

        return symbols

    def _parse_event_handlers(self, content: str, file_path: str, framework: str) -> List[Symbol]:
        """Extract event handler definitions."""
        symbols = []

        if framework == "vue":
            # @event or v-on:event
            pattern = re.compile(r'(?:v-on:|@)(\w+)\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                event = match.group(1)
                handler = match.group(2)
                line = self._find_line(content, match.start())

                symbols.append(Symbol(
                    id=f"event:{file_path}:{line}:{event}",
                    type=SymbolType.EVENT_HANDLER,
                    name=f"@{event}",
                    qualified_name=f"{file_path}#event:{event}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "vue",
                        "event": event,
                        "handler": handler,
                    },
                ))

        elif framework == "react":
            # onClick={handler}
            pattern = re.compile(r'(on[A-Z]\w+)\s*=\s*\{([^}]+)\}')
            for match in pattern.finditer(content):
                event = match.group(1)
                handler = match.group(2)
                line = self._find_line(content, match.start())

                symbols.append(Symbol(
                    id=f"event:{file_path}:{line}:{event}",
                    type=SymbolType.EVENT_HANDLER,
                    name=event,
                    qualified_name=f"{file_path}#event:{event}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "react",
                        "event": event,
                        "handler": handler,
                    },
                ))

        elif framework == "angular":
            # (event)="handler"
            pattern = re.compile(r'\((\w+)\)\s*=\s*["\']([^"\']+)["\']')
            for match in pattern.finditer(content):
                event = match.group(1)
                handler = match.group(2)
                line = self._find_line(content, match.start())

                symbols.append(Symbol(
                    id=f"event:{file_path}:{line}:{event}",
                    type=SymbolType.EVENT_HANDLER,
                    name=f"({event})",
                    qualified_name=f"{file_path}#event:{event}",
                    file_path=file_path,
                    line_start=line,
                    metadata={
                        "framework": "angular",
                        "event": event,
                        "handler": handler,
                    },
                ))

        return symbols
