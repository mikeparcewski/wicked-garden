"""
XML language adapter for symbol extraction.

Extracts symbols from common XML config patterns:
- Spring XML: bean definitions, property values
- Maven POM: dependency coordinates, plugin configurations
- General XML: element names with id/name/class attributes

Uses regex for simplicity — no tree-sitter needed.
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
class XmlAdapter(LanguageAdapter):
    """Parse XML config files for bean definitions and config symbols."""

    name = "xml"
    extensions = {'.xml', '.xsd', '.xsl', '.xslt'}

    # Spring bean definitions: <bean id="..." class="..."> (multi-line safe: [^>] matches \n)
    BEAN_PATTERN = re.compile(
        r'<bean\s+[^>]*?id\s*=\s*["\']([^"\']+)["\'][^>]*?class\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    # Also match class-first order: <bean class="..." id="...">
    BEAN_PATTERN_ALT = re.compile(
        r'<bean\s+[^>]*?class\s*=\s*["\']([^"\']+)["\'][^>]*?id\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    # Maven dependency: <groupId>...</groupId> + <artifactId>...</artifactId>
    ARTIFACT_PATTERN = re.compile(
        r'<artifactId>\s*([^<]+?)\s*</artifactId>',
        re.IGNORECASE,
    )

    # XSD type definitions: <xs:complexType name="..."> or <xs:simpleType name="...">
    XSD_TYPE_PATTERN = re.compile(
        r'<(?:xs|xsd):(?:complex|simple)Type\s+[^>]*?name\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    # XSD element declarations: <xs:element name="...">
    XSD_ELEMENT_PATTERN = re.compile(
        r'<(?:xs|xsd):element\s+[^>]*?name\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    # Generic elements with id or name attribute (catches most config patterns)
    NAMED_ELEMENT_PATTERN = re.compile(
        r'<(\w[\w:-]*)\s+[^>]*?(?:id|name)\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    def parse(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse XML file for config symbols."""
        if not HAS_SYMBOL_GRAPH:
            return []

        symbols = []

        try:
            lower_path = file_path.lower()

            if lower_path.endswith('.xsd'):
                symbols.extend(self._parse_xsd(content, file_path))
            elif 'pom.xml' in lower_path:
                symbols.extend(self._parse_pom(content, file_path))
            else:
                symbols.extend(self._parse_spring_xml(content, file_path))

            # Fallback: if no specialized symbols found, extract named elements
            if not symbols:
                symbols.extend(self._parse_generic(content, file_path))

        except Exception as e:
            logger.debug(f"XML parsing error for {file_path}: {e}")

        return symbols

    def _parse_spring_xml(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse Spring XML config for bean definitions."""
        symbols = []
        seen = set()

        # Bean definitions (id first)
        for match in self.BEAN_PATTERN.finditer(content):
            bean_id = match.group(1)
            bean_class = match.group(2)
            if bean_id in seen:
                continue
            seen.add(bean_id)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::bean:{bean_id}",
                type=SymbolType.SERVICE,
                name=bean_id,
                qualified_name=f"bean:{bean_id}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'bean_class': bean_class,
                    'config_type': 'spring-xml',
                },
            ))

        # Bean definitions (class first)
        for match in self.BEAN_PATTERN_ALT.finditer(content):
            bean_class = match.group(1)
            bean_id = match.group(2)
            if bean_id in seen:
                continue
            seen.add(bean_id)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::bean:{bean_id}",
                type=SymbolType.SERVICE,
                name=bean_id,
                qualified_name=f"bean:{bean_id}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'bean_class': bean_class,
                    'config_type': 'spring-xml',
                },
            ))

        return symbols

    def _parse_pom(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse Maven POM for dependency artifacts."""
        symbols = []
        seen = set()

        for match in self.ARTIFACT_PATTERN.finditer(content):
            artifact = match.group(1).strip()
            if artifact in seen:
                continue
            seen.add(artifact)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::artifact:{artifact}",
                type=SymbolType.CLASS,
                name=artifact,
                qualified_name=f"maven:{artifact}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'config_type': 'maven-pom',
                },
            ))

        return symbols

    def _parse_xsd(self, content: str, file_path: str) -> List["Symbol"]:
        """Parse XSD for type and element definitions."""
        symbols = []
        seen = set()

        for match in self.XSD_TYPE_PATTERN.finditer(content):
            type_name = match.group(1)
            if type_name in seen:
                continue
            seen.add(type_name)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::type:{type_name}",
                type=SymbolType.CLASS,
                name=type_name,
                qualified_name=f"xsd:{type_name}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'config_type': 'xsd',
                    'symbol_kind': 'type_definition',
                },
            ))

        for match in self.XSD_ELEMENT_PATTERN.finditer(content):
            element_name = match.group(1)
            if element_name in seen:
                continue
            seen.add(element_name)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::element:{element_name}",
                type=SymbolType.CLASS,
                name=element_name,
                qualified_name=f"xsd:{element_name}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'config_type': 'xsd',
                    'symbol_kind': 'element_declaration',
                },
            ))

        return symbols

    def _parse_generic(self, content: str, file_path: str) -> List["Symbol"]:
        """Extract named elements as generic config symbols."""
        symbols = []
        seen = set()

        for match in self.NAMED_ELEMENT_PATTERN.finditer(content):
            tag_name = match.group(1)
            element_name = match.group(2)

            # Skip common noise tags
            if tag_name.lower() in ('xml', 'xmlns', '?xml'):
                continue

            key = f"{tag_name}:{element_name}"
            if key in seen:
                continue
            seen.add(key)
            line = content[:match.start()].count('\n') + 1

            symbols.append(Symbol(
                id=f"{file_path}::{tag_name}:{element_name}",
                type=SymbolType.CLASS,
                name=element_name,
                qualified_name=f"{tag_name}:{element_name}",
                file_path=file_path,
                line_start=line,
                metadata={
                    'xml_tag': tag_name,
                    'config_type': 'xml',
                },
            ))

        return symbols
