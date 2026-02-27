"""
TypeScript code generator.

Generates patches for TypeScript/JavaScript files including:
- TypeORM entities
- Prisma models (generates schema suggestions)
- Interfaces and types
- React components (props)
- NestJS/Express controllers
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
class TypeScriptGenerator(BaseGenerator):
    """Generate patches for TypeScript/JavaScript files."""

    name = "typescript"
    extensions = {".ts", ".tsx", ".js", ".jsx"}
    symbol_types = {"entity", "entity_field", "interface", "type", "class", "component"}

    # Type mappings from generic types to TypeScript types
    TYPE_MAP = {
        "string": "string",
        "str": "string",
        "text": "string",
        "int": "number",
        "integer": "number",
        "long": "number",
        "bigint": "bigint",
        "float": "number",
        "double": "number",
        "decimal": "number",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "Date",
        "datetime": "Date",
        "timestamp": "Date",
        "time": "string",
        "uuid": "string",
        "binary": "Buffer",
        "blob": "Buffer",
        "any": "any",
        "object": "Record<string, any>",
    }

    # TypeORM column type mappings
    TYPEORM_TYPE_MAP = {
        "string": "varchar",
        "text": "text",
        "int": "int",
        "integer": "int",
        "long": "bigint",
        "float": "float",
        "double": "double",
        "decimal": "decimal",
        "boolean": "boolean",
        "date": "date",
        "datetime": "timestamp",
        "timestamp": "timestamp",
        "uuid": "uuid",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a TypeScript file."""
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
        """Add a field to a TypeScript class/interface."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        symbol_type = symbol.get("type", "").lower()

        # Detect if this is a TypeORM entity, interface, type, or class
        construct_type = self._detect_construct_type(lines, symbol)

        # Find body
        body_start, body_end = self._find_body(lines, symbol)
        if body_start < 0:
            return patches

        # Find field insertion point
        insert_line = self._find_field_insertion_point(lines, body_start, body_end, construct_type)
        indentation = self._detect_indentation(lines, body_start, body_end)

        # Build field declaration
        if construct_type == "typeorm":
            field_lines = self._build_typeorm_field(field_spec, indentation)
        elif construct_type == "interface":
            field_lines = self._build_interface_field(field_spec, indentation)
        elif construct_type == "type":
            field_lines = self._build_type_field(field_spec, indentation)
        else:
            field_lines = self._build_class_field(field_spec, indentation)

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content="\n".join(field_lines),
            description=f"Add field '{field_spec.name}'",
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
        """Remove a field from TypeScript class/interface."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field declaration (including decorators above it)
        for i, line in enumerate(lines):
            # Match: fieldName: type or fieldName?: type
            if re.match(rf"^\s+{field_name}\??:", line):
                # Check for decorators above
                start = i
                while start > 0 and lines[start - 1].strip().startswith("@"):
                    start -= 1

                patches.append(Patch(
                    file_path=file_path,
                    line_start=start + 1,
                    line_end=i + 1,
                    old_content="\n".join(lines[start:i + 1]),
                    new_content="",
                    description=f"Remove field '{field_name}'",
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
        """Rename a field across the file."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        for i, line in enumerate(lines):
            modified = False
            new_line = line

            # Field declaration: oldName: type or oldName?: type
            if re.match(rf"^\s+{old_name}\??:", line):
                new_line = re.sub(rf"^(\s+){old_name}(\??:)", rf"\1{new_name}\2", line)
                modified = True

            # Property access: this.oldName or obj.oldName
            elif f".{old_name}" in line:
                # Be careful not to replace partial matches
                new_line = re.sub(rf"\.{old_name}([^a-zA-Z0-9_]|$)", rf".{new_name}\1", line)
                if new_line != line:
                    modified = True

            # Object destructuring: { oldName } or { oldName: alias }
            elif re.search(rf"\{{\s*[^}}]*\b{old_name}\b", line):
                new_line = re.sub(rf"\b{old_name}\b", new_name, line)
                if new_line != line:
                    modified = True

            # Object literal keys: { oldName: value }
            elif re.search(rf"[{{,]\s*{old_name}\s*:", line):
                new_line = re.sub(rf"([{{,]\s*){old_name}(\s*:)", rf"\1{new_name}\2", line)
                if new_line != line:
                    modified = True

            if modified:
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        return patches

    def _modify_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Modify a field's type."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        ts_type = self._map_type(field_spec.type)

        for i, line in enumerate(lines):
            # Match: fieldName: oldType or fieldName?: oldType
            if re.match(rf"^\s+{field_spec.name}\??:", line):
                # Replace the type
                optional = "?" if field_spec.nullable else ""
                new_line = re.sub(
                    rf"^(\s+){field_spec.name}\??:\s*\S+",
                    rf"\1{field_spec.name}{optional}: {ts_type}",
                    line
                )
                if new_line != line:
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Modify field '{field_spec.name}' type to {ts_type}",
                        symbol_id=symbol.get("id"),
                        confidence="high",
                    ))
                break

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to TypeScript type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _detect_construct_type(self, lines: List[str], symbol: Dict[str, Any]) -> str:
        """Detect if this is a TypeORM entity, interface, type, or class."""
        symbol_name = symbol.get("name", "")
        content = "\n".join(lines)

        # Check for TypeORM decorators
        if "@Entity" in content or "@Column" in content:
            return "typeorm"

        for i, line in enumerate(lines):
            # Check the declaration line
            if f"interface {symbol_name}" in line:
                return "interface"
            if f"type {symbol_name}" in line:
                return "type"
            if f"class {symbol_name}" in line:
                # Check for decorators
                if i > 0 and "@Entity" in lines[i - 1]:
                    return "typeorm"
                return "class"

        return "class"

    def _find_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of the class/interface body."""
        symbol_name = symbol.get("name", "")
        start = -1
        end = -1
        brace_count = 0

        for i, line in enumerate(lines):
            if start < 0:
                # Look for class/interface/type declaration
                if (f"class {symbol_name}" in line or
                    f"interface {symbol_name}" in line or
                    f"type {symbol_name}" in line):
                    start = i
                    brace_count = line.count("{") - line.count("}")

            elif start >= 0:
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    end = i
                    break

        return start, end

    def _find_field_insertion_point(
        self,
        lines: List[str],
        body_start: int,
        body_end: int,
        construct_type: str
    ) -> int:
        """Find where to insert a new field."""
        last_field_line = body_start

        for i in range(body_start + 1, body_end):
            line = lines[i].strip()

            # Skip empty lines, comments
            if not line or line.startswith("//") or line.startswith("/*"):
                continue

            # Check for field patterns
            if ":" in line and not line.startswith("constructor") and not "(" in line.split(":")[0]:
                last_field_line = i

            # Stop at methods (except in interfaces which don't have method bodies)
            if construct_type != "interface" and "(" in line and "{" in line:
                break

        return last_field_line

    def _detect_indentation(
        self,
        lines: List[str],
        body_start: int,
        body_end: int
    ) -> str:
        """Detect the indentation used in the body."""
        for i in range(body_start + 1, min(body_end, len(lines))):
            line = lines[i]
            if line.strip() and not line.strip().startswith("//"):
                return self._get_indentation(line)
        return "  "  # Default to 2 spaces (TypeScript convention)

    def _build_typeorm_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build TypeORM column definition."""
        lines = []
        ts_type = self._map_type(field_spec.type)
        db_type = self.TYPEORM_TYPE_MAP.get(field_spec.type.lower(), "varchar")

        # Build @Column decorator
        column_args = []
        if field_spec.column_name:
            column_args.append(f'name: "{field_spec.column_name}"')
        column_args.append(f'type: "{db_type}"')
        if not field_spec.nullable:
            column_args.append("nullable: false")
        if field_spec.default:
            column_args.append(f"default: {field_spec.default}")

        lines.append(f"{indentation}@Column({{ {', '.join(column_args)} }})")

        # Field declaration
        optional = "!" if not field_spec.nullable else "?"
        lines.append(f"{indentation}{field_spec.name}{optional}: {ts_type};")

        return lines

    def _build_interface_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build interface field definition."""
        ts_type = self._map_type(field_spec.type)
        optional = "?" if field_spec.nullable else ""
        return [f"{indentation}{field_spec.name}{optional}: {ts_type};"]

    def _build_type_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build type field definition."""
        # Same as interface for type aliases
        return self._build_interface_field(field_spec, indentation)

    def _build_class_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build class field definition."""
        ts_type = self._map_type(field_spec.type)
        optional = "?" if field_spec.nullable else "!"

        if field_spec.default is not None:
            return [f"{indentation}{field_spec.name}: {ts_type} = {field_spec.default};"]
        else:
            return [f"{indentation}{field_spec.name}{optional}: {ts_type};"]
