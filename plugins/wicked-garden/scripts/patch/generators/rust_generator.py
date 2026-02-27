"""
Rust code generator.

Generates patches for Rust files including:
- Diesel models (add/modify fields with derive macros)
- Structs (add fields)
- sqlx structs

Diesel format: #[derive(Queryable, Insertable)]
              #[diesel(table_name = users)]
              pub struct User { pub name: String, pub email: Option<String> }
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
class RustGenerator(BaseGenerator):
    """Generate patches for Rust files."""

    name = "rust"
    extensions = {".rs"}
    symbol_types = {"struct", "enum", "trait", "impl"}

    # Type mappings from generic types to Rust types
    TYPE_MAP = {
        "string": "String",
        "str": "String",
        "text": "String",
        "int": "i32",
        "integer": "i32",
        "long": "i64",
        "bigint": "i64",
        "float": "f32",
        "double": "f64",
        "decimal": "f64",
        "boolean": "bool",
        "bool": "bool",
        "date": "NaiveDate",
        "datetime": "NaiveDateTime",
        "timestamp": "DateTime<Utc>",
        "time": "NaiveTime",
        "uuid": "Uuid",
        "binary": "Vec<u8>",
        "blob": "Vec<u8>",
        "json": "serde_json::Value",
    }

    # SQL types for Diesel column definitions
    SQL_TYPE_MAP = {
        "string": "Varchar",
        "text": "Text",
        "int": "Integer",
        "integer": "Integer",
        "long": "BigInt",
        "bigint": "BigInt",
        "float": "Float",
        "double": "Double",
        "decimal": "Numeric",
        "boolean": "Bool",
        "date": "Date",
        "datetime": "Timestamp",
        "uuid": "Uuid",
        "binary": "Binary",
    }

    # Import mappings
    IMPORT_MAP = {
        "NaiveDate": "chrono::NaiveDate",
        "NaiveDateTime": "chrono::NaiveDateTime",
        "NaiveTime": "chrono::NaiveTime",
        "DateTime<Utc>": "chrono::{DateTime, Utc}",
        "Uuid": "uuid::Uuid",
        "serde_json::Value": "serde_json",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Rust file."""
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
        """Add a field to a Rust struct."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine Rust type
        rust_type = self._map_type(field_spec.type)

        # Wrap in Option if nullable
        if field_spec.nullable:
            rust_type = f"Option<{rust_type}>"

        # Find struct body
        struct_start, struct_end = self._find_struct_body(lines, symbol)
        if struct_start < 0:
            return patches

        # Check if this is a Diesel model
        is_diesel = self._is_diesel_model(lines, struct_start)

        # Find insertion point (before closing brace)
        insert_line = struct_end - 1
        indentation = self._detect_indentation(lines, struct_start, struct_end)

        # Build field declaration
        field_line = self._build_field_declaration(
            field_spec, rust_type, indentation, is_diesel
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content=field_line,
            description=f"Add field '{field_spec.name}' ({rust_type})",
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
        """Remove a field from a Rust struct."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field declaration
        for i, line in enumerate(lines):
            # Match: pub field_name: Type, or field_name: Type,
            if re.search(rf"\b{field_name}\s*:", line):
                # Check for attributes above
                start = i
                while start > 0 and lines[start - 1].strip().startswith("#["):
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
        """Rename a field in a Rust struct."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Rename field declaration
        for i, line in enumerate(lines):
            pattern = rf"(\s*(?:pub\s+)?){old_name}(\s*:)"
            match = re.search(pattern, line)
            if match:
                new_line = re.sub(pattern, rf"\1{new_name}\2", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename field '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Update serde rename attribute if present
        for i, line in enumerate(lines):
            if f'rename = "{old_name}"' in line:
                new_line = line.replace(f'rename = "{old_name}"', f'rename = "{new_name}"')
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Update serde rename for '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="medium",
                ))

        # Update usages (self.field, struct.field)
        for i, line in enumerate(lines):
            if f".{old_name}" in line or f"self.{old_name}" in line:
                new_line = line.replace(f".{old_name}", f".{new_name}")
                if new_line != line and not any(p.line_start == i + 1 for p in patches):
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Update field reference '{old_name}' to '{new_name}'",
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
        """Modify a field's type."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        rust_type = self._map_type(field_spec.type)
        if field_spec.nullable:
            rust_type = f"Option<{rust_type}>"

        # Find field
        for i, line in enumerate(lines):
            if re.search(rf"\b{field_spec.name}\s*:", line):
                # Replace the type
                pattern = rf"(\b{field_spec.name}\s*:\s*)[^,}}]+"
                new_line = re.sub(pattern, rf"\1{rust_type}", line)

                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Modify field '{field_spec.name}' type to {rust_type}",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Rust type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _is_diesel_model(self, lines: List[str], struct_start: int) -> bool:
        """Check if this is a Diesel model."""
        # Look for Diesel derive macros above the struct
        for i in range(max(0, struct_start - 10), struct_start + 1):
            if "Queryable" in lines[i] or "Insertable" in lines[i] or \
               "diesel(" in lines[i]:
                return True
        return False

    def _find_struct_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of a struct body."""
        struct_name = symbol.get("name", "")
        start = -1
        end = -1

        for i, line in enumerate(lines):
            if re.search(rf"struct\s+{struct_name}", line):
                if "{" in line:
                    start = i
                    # Find closing brace
                    brace_count = 1
                    for j in range(i + 1, len(lines)):
                        brace_count += lines[j].count("{") - lines[j].count("}")
                        if brace_count == 0:
                            end = j
                            break
                    break
                else:
                    # Multi-line struct definition
                    for j in range(i + 1, len(lines)):
                        if "{" in lines[j]:
                            start = j
                            brace_count = 1
                            for k in range(j + 1, len(lines)):
                                brace_count += lines[k].count("{") - lines[k].count("}")
                                if brace_count == 0:
                                    end = k
                                    break
                            break
                    break

        return start, end

    def _detect_indentation(
        self,
        lines: List[str],
        struct_start: int,
        struct_end: int
    ) -> str:
        """Detect the indentation used in the struct body."""
        for i in range(struct_start + 1, struct_end):
            line = lines[i]
            if line.strip() and not line.strip().startswith("//"):
                return self._get_indentation(line)
        return "    "  # Default to 4 spaces

    def _build_field_declaration(
        self,
        field_spec: FieldSpec,
        rust_type: str,
        indentation: str,
        is_diesel: bool
    ) -> str:
        """Build a Rust struct field declaration."""
        # Use snake_case for Rust field names
        field_name = self._to_snake_case(field_spec.name)

        lines = []

        # Add Diesel column attribute if needed
        if is_diesel and field_spec.column_name:
            column_name = field_spec.column_name.lower()
            if column_name != field_name:
                lines.append(f'{indentation}#[diesel(column_name = "{column_name}")]')

        # Add serde rename if column name differs
        if field_spec.column_name and field_spec.column_name.lower() != field_name:
            lines.append(f'{indentation}#[serde(rename = "{field_spec.column_name.lower()}")]')

        # Field declaration (pub by default for structs)
        lines.append(f"{indentation}pub {field_name}: {rust_type},")

        return "\n".join(lines)
