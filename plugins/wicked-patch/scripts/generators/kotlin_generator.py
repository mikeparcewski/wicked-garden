"""
Kotlin code generator.

Generates patches for Kotlin files including:
- Data classes (add/modify properties)
- Classes (add properties)
- Exposed/JetBrains ORM entities
- Android Room entities

Kotlin data class format: data class User(val name: String, val email: String?)
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

from .base import (
    BaseGenerator,
    register_generator,
    ChangeSpec,
    ChangeType,
    FieldSpec,
    Patch,
)

logger = logging.getLogger(__name__)


@register_generator
class KotlinGenerator(BaseGenerator):
    """Generate patches for Kotlin files."""

    name = "kotlin"
    extensions = {".kt", ".kts"}
    symbol_types = {"class", "data_class", "entity", "object", "interface"}

    # Type mappings from generic types to Kotlin types
    TYPE_MAP = {
        "string": "String",
        "str": "String",
        "text": "String",
        "int": "Int",
        "integer": "Int",
        "long": "Long",
        "bigint": "Long",
        "float": "Float",
        "double": "Double",
        "decimal": "BigDecimal",
        "boolean": "Boolean",
        "bool": "Boolean",
        "date": "LocalDate",
        "datetime": "LocalDateTime",
        "timestamp": "Instant",
        "time": "LocalTime",
        "uuid": "UUID",
        "binary": "ByteArray",
        "blob": "ByteArray",
        "json": "String",
        "list": "List",
        "map": "Map",
    }

    # Import mappings
    IMPORT_MAP = {
        "LocalDate": "java.time.LocalDate",
        "LocalDateTime": "java.time.LocalDateTime",
        "LocalTime": "java.time.LocalTime",
        "Instant": "java.time.Instant",
        "UUID": "java.util.UUID",
        "BigDecimal": "java.math.BigDecimal",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Kotlin file."""
        patches = []

        if change_spec.change_type == ChangeType.ADD_FIELD:
            patches.extend(self._add_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.MODIFY_FIELD:
            patches.extend(self._modify_field(change_spec, symbol, file_content))

        return patches

    def _add_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add a property to a Kotlin class/data class."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine Kotlin type
        kotlin_type = self._map_type(field_spec.type)

        # Make nullable if needed
        if field_spec.nullable:
            kotlin_type = f"{kotlin_type}?"

        # Check if it's a data class (properties in constructor)
        is_data_class = self._is_data_class(lines, symbol)

        if is_data_class:
            patches.extend(self._add_data_class_property(
                field_spec, kotlin_type, lines, file_path, symbol
            ))
        else:
            patches.extend(self._add_class_property(
                field_spec, kotlin_type, lines, file_path, symbol
            ))

        # Add imports if needed
        import_patch = self._add_imports(kotlin_type, lines, file_path)
        if import_patch:
            patches.insert(0, import_patch)

        return patches

    def _add_data_class_property(
        self,
        field_spec: FieldSpec,
        kotlin_type: str,
        lines: List[str],
        file_path: str,
        symbol: Dict[str, Any]
    ) -> List[Patch]:
        """Add property to a data class constructor."""
        patches = []

        # Find data class declaration
        for i, line in enumerate(lines):
            class_name = symbol.get("name", "")
            if f"data class {class_name}" in line:
                # Find the closing parenthesis of the constructor
                paren_count = 0
                start_line = i
                for j in range(i, len(lines)):
                    paren_count += lines[j].count("(") - lines[j].count(")")
                    if paren_count == 0 and ")" in lines[j]:
                        # Found closing paren
                        end_line = j
                        break
                else:
                    return patches

                # Build the new property
                property_str = self._build_data_class_property(field_spec, kotlin_type)

                # Find where to insert (before closing paren)
                if start_line == end_line:
                    # Single line data class
                    old_line = lines[i]
                    # Insert before the closing paren
                    insert_pos = old_line.rfind(")")
                    if insert_pos > 0:
                        # Check if there are existing properties
                        if "(" in old_line and old_line.find("(") < insert_pos - 1:
                            new_line = old_line[:insert_pos] + ", " + property_str + ")"
                            if old_line.endswith(")"):
                                new_line = new_line
                            else:
                                # Handle trailing content after )
                                new_line = old_line[:insert_pos] + ", " + property_str + old_line[insert_pos:]
                        else:
                            new_line = old_line[:insert_pos] + property_str + old_line[insert_pos:]

                        patches.append(Patch(
                            file_path=file_path,
                            line_start=i + 1,
                            line_end=i + 1,
                            old_content=old_line,
                            new_content=new_line,
                            description=f"Add property '{field_spec.name}' to data class",
                            symbol_id=symbol.get("id"),
                            confidence="high",
                        ))
                else:
                    # Multi-line data class
                    # Insert before the line with closing paren
                    indent = self._detect_constructor_indentation(lines, start_line, end_line)
                    new_property_line = f"{indent}{property_str},"

                    patches.append(Patch(
                        file_path=file_path,
                        line_start=end_line,
                        line_end=end_line - 1,
                        old_content="",
                        new_content=new_property_line,
                        description=f"Add property '{field_spec.name}' to data class",
                        symbol_id=symbol.get("id"),
                        confidence="high",
                    ))

                break

        return patches

    def _add_class_property(
        self,
        field_spec: FieldSpec,
        kotlin_type: str,
        lines: List[str],
        file_path: str,
        symbol: Dict[str, Any]
    ) -> List[Patch]:
        """Add property to a regular Kotlin class."""
        patches = []

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find insertion point
        insert_line = self._find_property_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build property declaration
        property_line = self._build_class_property(field_spec, kotlin_type, indentation, symbol)

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content=property_line,
            description=f"Add property '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _remove_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Remove a property from a Kotlin class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find property declaration
        for i, line in enumerate(lines):
            if re.search(rf"\b(val|var)\s+{field_name}\s*:", line):
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content="",
                    description=f"Remove property '{field_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

        return patches

    def _rename_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename a property in a Kotlin class."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Rename property declaration
        for i, line in enumerate(lines):
            pattern = rf"(\b(?:val|var)\s+){old_name}(\s*:)"
            match = re.search(pattern, line)
            if match:
                new_line = re.sub(pattern, rf"\1{new_name}\2", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename property '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Rename usages
        for i, line in enumerate(lines):
            # Match this.property or .property or property
            if f".{old_name}" in line or f"this.{old_name}" in line:
                new_line = line.replace(f".{old_name}", f".{new_name}")
                new_line = new_line.replace(f"this.{old_name}", f"this.{new_name}")
                if new_line != line and not any(p.line_start == i + 1 for p in patches):
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Update property reference '{old_name}' to '{new_name}'",
                        symbol_id=symbol.get("id"),
                        confidence="medium",
                    ))

        return patches

    def _modify_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Modify a property's type."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        kotlin_type = self._map_type(field_spec.type)
        if field_spec.nullable:
            kotlin_type = f"{kotlin_type}?"

        # Find property
        for i, line in enumerate(lines):
            if re.search(rf"\b(val|var)\s+{field_spec.name}\s*:", line):
                # Replace the type
                pattern = rf"(\b(?:val|var)\s+{field_spec.name}\s*:\s*)\S+"
                new_line = re.sub(pattern, rf"\1{kotlin_type}", line)

                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Modify property '{field_spec.name}' type to {kotlin_type}",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Kotlin type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _is_data_class(self, lines: List[str], symbol: Dict[str, Any]) -> bool:
        """Check if the class is a data class."""
        class_name = symbol.get("name", "")
        for line in lines:
            if f"data class {class_name}" in line:
                return True
        return False

    def _find_class_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of a class body."""
        class_name = symbol.get("name", "")
        start = -1
        end = -1
        brace_count = 0
        in_class = False

        for i, line in enumerate(lines):
            if re.search(rf"class\s+{class_name}", line) and "data class" not in line:
                in_class = True
                if "{" in line:
                    brace_count = 1
                    start = i
            elif in_class:
                brace_count += line.count("{") - line.count("}")
                if brace_count == 1 and start < 0:
                    start = i
                elif brace_count == 0:
                    end = i
                    break

        return start, end

    def _find_property_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert a new property."""
        last_property = class_start + 1

        for i in range(class_start + 1, class_end):
            line = lines[i].strip()
            if line.startswith("val ") or line.startswith("var ") or \
               line.startswith("private val") or line.startswith("private var"):
                last_property = i
            elif line.startswith("fun ") or line.startswith("override fun"):
                break

        return last_property

    def _detect_indentation(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> str:
        """Detect the indentation used in the class body."""
        for i in range(class_start + 1, class_end):
            line = lines[i]
            if line.strip() and not line.strip().startswith("//"):
                return self._get_indentation(line)
        return "    "  # Default to 4 spaces

    def _detect_constructor_indentation(
        self,
        lines: List[str],
        start_line: int,
        end_line: int
    ) -> str:
        """Detect indentation in constructor parameters."""
        for i in range(start_line + 1, end_line):
            line = lines[i]
            if line.strip() and ("val " in line or "var " in line):
                return self._get_indentation(line)
        return "    "

    def _build_data_class_property(
        self,
        field_spec: FieldSpec,
        kotlin_type: str
    ) -> str:
        """Build a data class constructor property."""
        # Use camelCase for Kotlin
        prop_name = field_spec.name

        if field_spec.default:
            return f"val {prop_name}: {kotlin_type} = {field_spec.default}"
        elif field_spec.nullable:
            return f"val {prop_name}: {kotlin_type} = null"
        else:
            return f"val {prop_name}: {kotlin_type}"

    def _build_class_property(
        self,
        field_spec: FieldSpec,
        kotlin_type: str,
        indentation: str,
        symbol: Dict[str, Any]
    ) -> str:
        """Build a class property declaration."""
        prop_name = field_spec.name

        # Check for annotations
        metadata = symbol.get("metadata", {})
        annotations = metadata.get("annotations", [])

        lines = []

        # Add Column annotation for JPA/Exposed
        if "Entity" in annotations or "Table" in annotations:
            column_name = field_spec.column_name or self._to_snake_case(prop_name)
            lines.append(f'{indentation}@Column(name = "{column_name}")')

        # Build property
        if field_spec.default:
            lines.append(f"{indentation}var {prop_name}: {kotlin_type} = {field_spec.default}")
        elif field_spec.nullable:
            lines.append(f"{indentation}var {prop_name}: {kotlin_type} = null")
        else:
            # For non-nullable without default, use lateinit for non-primitive
            if kotlin_type in ("Int", "Long", "Float", "Double", "Boolean", "Byte", "Short", "Char"):
                lines.append(f"{indentation}var {prop_name}: {kotlin_type} = 0")
            else:
                lines.append(f"{indentation}lateinit var {prop_name}: {kotlin_type}")

        return "\n".join(lines)

    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _add_imports(
        self,
        kotlin_type: str,
        lines: List[str],
        file_path: str
    ) -> Optional[Patch]:
        """Add import statement if needed."""
        # Remove nullable marker
        base_type = kotlin_type.rstrip("?")
        import_pkg = self.IMPORT_MAP.get(base_type)
        if not import_pkg:
            return None

        import_line = f"import {import_pkg}"

        # Check if already imported
        for line in lines:
            if import_line in line:
                return None

        # Find import section
        for i, line in enumerate(lines):
            if line.startswith("import "):
                # Insert alphabetically
                if import_line < line.strip():
                    return Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i,
                        old_content="",
                        new_content=import_line,
                        description=f"Add import for {base_type}",
                        confidence="high",
                    )
            elif line.startswith("class ") or line.startswith("data class") or \
                 line.startswith("fun ") or line.startswith("object "):
                # Insert before class definition
                return Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i,
                    old_content="",
                    new_content=import_line + "\n",
                    description=f"Add import for {base_type}",
                    confidence="high",
                )

        return None
