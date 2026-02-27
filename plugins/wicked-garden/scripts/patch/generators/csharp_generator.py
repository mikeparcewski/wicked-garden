"""
C# code generator.

Generates patches for C# files including:
- Entity Framework models (add/modify properties, attributes)
- Classes (add properties)
- Records (add properties)
- DTOs (add properties)

Entity Framework attribute format: [Column("name"), Required, MaxLength(100)]
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
class CSharpGenerator(BaseGenerator):
    """Generate patches for C# files."""

    name = "csharp"
    extensions = {".cs"}
    symbol_types = {"class", "entity", "record", "dto", "model"}

    # Type mappings from generic types to C# types
    TYPE_MAP = {
        "string": "string",
        "str": "string",
        "text": "string",
        "int": "int",
        "integer": "int",
        "long": "long",
        "bigint": "long",
        "float": "float",
        "double": "double",
        "decimal": "decimal",
        "boolean": "bool",
        "bool": "bool",
        "date": "DateTime",
        "datetime": "DateTime",
        "timestamp": "DateTimeOffset",
        "time": "TimeSpan",
        "uuid": "Guid",
        "binary": "byte[]",
        "blob": "byte[]",
        "json": "string",  # Often stored as string in EF
    }

    # Namespace imports for types
    IMPORT_MAP = {
        "DateTime": "System",
        "DateTimeOffset": "System",
        "TimeSpan": "System",
        "Guid": "System",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a C# file."""
        patches = []

        if change_spec.change_type == ChangeType.ADD_FIELD:
            patches.extend(self._add_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.MODIFY_FIELD:
            patches.extend(self._modify_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.ADD_VALIDATION:
            patches.extend(self._add_validation(change_spec, symbol, file_content))

        return patches

    def _add_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add a property to a C# class."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine C# type
        csharp_type = self._map_type(field_spec.type)

        # Make nullable if needed
        if field_spec.nullable and csharp_type not in ("string", "byte[]"):
            csharp_type = f"{csharp_type}?"

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find insertion point (after last property, before methods)
        insert_line = self._find_property_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build property declaration
        property_lines = self._build_property_declaration(
            field_spec, csharp_type, indentation, symbol
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content="\n".join(property_lines),
            description=f"Add property '{field_spec.name}' ({csharp_type})",
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
        """Remove a property from a C# class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find property declaration (including attributes)
        prop_start, prop_end = self._find_property_declaration(lines, field_name)
        if prop_start >= 0:
            patches.append(Patch(
                file_path=file_path,
                line_start=prop_start + 1,
                line_end=prop_end + 1,
                old_content="\n".join(lines[prop_start:prop_end + 1]),
                new_content="",
                description=f"Remove property '{field_name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    def _rename_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename a property in a C# class."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find and rename property declaration
        for i, line in enumerate(lines):
            # Match property: public Type PropertyName { get; set; }
            pattern = rf"(public\s+\S+\??\s+){old_name}(\s*\{{)"
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
                break

        # Update Column attribute if present
        for i, line in enumerate(lines):
            if f'Column("{old_name}"' in line or f'Column("{self._to_snake_case(old_name)}"' in line:
                new_line = line.replace(
                    f'Column("{old_name}"',
                    f'Column("{new_name}"'
                ).replace(
                    f'Column("{self._to_snake_case(old_name)}"',
                    f'Column("{self._to_snake_case(new_name)}"'
                )
                if new_line != line:
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Update Column attribute for '{new_name}'",
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
        """Modify a property's type or attributes."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find property declaration
        prop_start, prop_end = self._find_property_declaration(lines, field_spec.name)
        if prop_start < 0:
            return patches

        # Build new property declaration
        indentation = self._get_indentation(lines[prop_end])
        csharp_type = self._map_type(field_spec.type)
        if field_spec.nullable and csharp_type not in ("string", "byte[]"):
            csharp_type = f"{csharp_type}?"

        new_property_lines = self._build_property_declaration(
            field_spec, csharp_type, indentation, symbol
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=prop_start + 1,
            line_end=prop_end + 1,
            old_content="\n".join(lines[prop_start:prop_end + 1]),
            new_content="\n".join(new_property_lines),
            description=f"Modify property '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _add_validation(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add validation attributes to a property."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec or not field_spec.validation:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find property declaration
        prop_start, prop_end = self._find_property_declaration(lines, field_spec.name)
        if prop_start < 0:
            return patches

        # Build validation attributes
        indentation = self._get_indentation(lines[prop_end])
        validation_lines = self._build_validation_attributes(
            field_spec.validation, indentation
        )

        if validation_lines:
            patches.append(Patch(
                file_path=file_path,
                line_start=prop_start + 1,
                line_end=prop_start,
                old_content="",
                new_content="\n".join(validation_lines),
                description=f"Add validation to '{field_spec.name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to C# type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _capitalize(self, name: str) -> str:
        """Capitalize first letter for C# property names (PascalCase)."""
        return name[0].upper() + name[1:] if name else name

    def _to_snake_case(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _find_class_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of a class body."""
        class_name = symbol.get("name", "")
        start = -1
        end = -1
        brace_count = 0
        in_class = False

        for i, line in enumerate(lines):
            if re.search(rf"class\s+{class_name}", line) or \
               re.search(rf"record\s+{class_name}", line):
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
        last_property_line = class_start + 1

        for i in range(class_start + 1, class_end):
            line = lines[i].strip()
            # Skip empty lines, comments, and attributes
            if not line or line.startswith("//") or line.startswith("["):
                continue
            # Check if this is a property (has get/set)
            if "{ get;" in line or "{ get }" in line or "=> " in line:
                last_property_line = i
            # Stop at first method (has parentheses before brace)
            elif re.match(r"(public|private|protected|internal)\s+\S+\s+\w+\s*\(", line):
                break

        return last_property_line

    def _detect_indentation(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> str:
        """Detect the indentation used in the class body."""
        for i in range(class_start + 1, class_end):
            line = lines[i]
            if line.strip() and not line.strip().startswith("//") and not line.strip().startswith("["):
                return self._get_indentation(line)
        return "        "  # Default to 8 spaces (2 levels)

    def _build_property_declaration(
        self,
        field_spec: FieldSpec,
        csharp_type: str,
        indentation: str,
        symbol: Dict[str, Any]
    ) -> List[str]:
        """Build a C# property declaration with attributes."""
        lines = []

        # Use PascalCase property name
        property_name = self._capitalize(field_spec.name)

        # Check if this is an Entity Framework entity
        metadata = symbol.get("metadata", {})
        is_entity = "Entity" in metadata.get("attributes", []) or \
                    "Table" in metadata.get("attributes", [])

        # Add Entity Framework Column attribute
        if is_entity or field_spec.column_name:
            column_name = field_spec.column_name or self._to_snake_case(field_spec.name)
            lines.append(f'{indentation}[Column("{column_name}")]')

        # Add Required attribute if not nullable
        if not field_spec.nullable:
            lines.append(f"{indentation}[Required]")

        # Add MaxLength for strings
        if field_spec.validation and "maxLength" in field_spec.validation:
            lines.append(f'{indentation}[MaxLength({field_spec.validation["maxLength"]})]')

        # Add custom annotations
        for annotation in field_spec.annotations:
            lines.append(f"{indentation}[{annotation}]")

        # Property declaration with auto-properties
        default_value = ""
        if field_spec.default:
            default_value = f" = {field_spec.default};"
        elif not field_spec.nullable and csharp_type == "string":
            default_value = ' = "";'

        if default_value:
            lines.append(f"{indentation}public {csharp_type} {property_name} {{ get; set; }}{default_value}")
        else:
            lines.append(f"{indentation}public {csharp_type} {property_name} {{ get; set; }}")

        lines.append("")  # Blank line after property

        return lines

    def _build_validation_attributes(
        self,
        validation: Dict[str, Any],
        indentation: str
    ) -> List[str]:
        """Build validation attributes from spec."""
        lines = []

        if validation.get("required"):
            lines.append(f"{indentation}[Required]")

        if "min" in validation and "max" in validation:
            lines.append(f'{indentation}[Range({validation["min"]}, {validation["max"]})]')
        elif "min" in validation:
            lines.append(f'{indentation}[Range({validation["min"]}, int.MaxValue)]')
        elif "max" in validation:
            lines.append(f'{indentation}[Range(int.MinValue, {validation["max"]})]')

        if "minLength" in validation and "maxLength" in validation:
            lines.append(f'{indentation}[StringLength({validation["maxLength"]}, MinimumLength = {validation["minLength"]})]')
        elif "maxLength" in validation:
            lines.append(f'{indentation}[MaxLength({validation["maxLength"]})]')
        elif "minLength" in validation:
            lines.append(f'{indentation}[MinLength({validation["minLength"]})]')

        if "pattern" in validation:
            lines.append(f'{indentation}[RegularExpression(@"{validation["pattern"]}")]')

        if validation.get("email"):
            lines.append(f"{indentation}[EmailAddress]")

        if validation.get("phone"):
            lines.append(f"{indentation}[Phone]")

        if validation.get("url"):
            lines.append(f"{indentation}[Url]")

        return lines

    def _find_property_declaration(
        self,
        lines: List[str],
        property_name: str
    ) -> tuple:
        """Find the start and end lines of a property declaration."""
        for i, line in enumerate(lines):
            # Match property: public Type PropertyName { get; set; }
            if re.search(rf"\s+{property_name}\s*\{{", line):
                # Check for attributes above
                start = i
                while start > 0 and lines[start - 1].strip().startswith("["):
                    start -= 1
                return start, i
        return -1, -1
