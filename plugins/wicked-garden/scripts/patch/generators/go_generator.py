"""
Go code generator.

Generates patches for Go files including:
- GORM models (add/modify fields, tags)
- Structs (add fields)
- Interfaces (add methods)

GORM tag format: `gorm:"column:name;type:varchar(100);not null"`
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
class GoGenerator(BaseGenerator):
    """Generate patches for Go files."""

    name = "go"
    extensions = {".go"}
    symbol_types = {"struct", "model", "interface", "type"}

    # Type mappings from generic types to Go types
    TYPE_MAP = {
        "string": "string",
        "str": "string",
        "text": "string",
        "int": "int",
        "integer": "int",
        "long": "int64",
        "bigint": "int64",
        "float": "float32",
        "double": "float64",
        "decimal": "float64",
        "boolean": "bool",
        "bool": "bool",
        "date": "time.Time",
        "datetime": "time.Time",
        "timestamp": "time.Time",
        "time": "time.Time",
        "uuid": "uuid.UUID",
        "binary": "[]byte",
        "blob": "[]byte",
        "json": "datatypes.JSON",
    }

    # SQL types for GORM tags
    SQL_TYPE_MAP = {
        "string": "varchar(255)",
        "str": "varchar(255)",
        "text": "text",
        "int": "int",
        "integer": "int",
        "long": "bigint",
        "bigint": "bigint",
        "float": "float",
        "double": "double precision",
        "decimal": "decimal(10,2)",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "date",
        "datetime": "timestamp",
        "timestamp": "timestamp",
        "uuid": "uuid",
    }

    # Import mappings
    IMPORT_MAP = {
        "time.Time": "time",
        "uuid.UUID": "github.com/google/uuid",
        "datatypes.JSON": "gorm.io/datatypes",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Go file."""
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
        """Add a field to a Go struct."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine Go type
        go_type = self._map_type(field_spec.type)

        # Check if pointer type for nullable
        if field_spec.nullable and go_type not in ("string", "[]byte"):
            go_type = f"*{go_type}"

        # Find struct body
        struct_start, struct_end = self._find_struct_body(lines, symbol)
        if struct_start < 0:
            return patches

        # Find insertion point (before closing brace)
        insert_line = struct_end - 1
        indentation = self._detect_indentation(lines, struct_start, struct_end)

        # Build field declaration with tags
        field_line = self._build_field_declaration(
            field_spec, go_type, indentation, symbol
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content=field_line,
            description=f"Add field '{field_spec.name}' ({go_type})",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Add imports if needed
        import_patch = self._add_imports(go_type, lines, file_path)
        if import_patch:
            patches.insert(0, import_patch)

        return patches

    def _remove_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Remove a field from a Go struct."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field declaration (Go fields: FieldName Type `tags`)
        for i, line in enumerate(lines):
            # Match: FieldName Type or FieldName *Type
            if re.match(rf"\s+{field_name}\s+\*?\w+", line):
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
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
        """Rename a field in a Go struct."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find and rename field declaration
        for i, line in enumerate(lines):
            # Match field declaration
            pattern = rf"(\s+){old_name}(\s+\*?\w+)"
            match = re.match(pattern, line)
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
                break

        # Update json/gorm tags if present
        for i, line in enumerate(lines):
            if f'json:"{old_name.lower()}"' in line or f"json:\"{self._to_snake_case(old_name)}\"" in line:
                new_line = line.replace(
                    f'json:"{old_name.lower()}"',
                    f'json:"{new_name.lower()}"'
                ).replace(
                    f'json:"{self._to_snake_case(old_name)}"',
                    f'json:"{self._to_snake_case(new_name)}"'
                )
                if new_line != line:
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Update json tag for '{new_name}'",
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
        """Modify a field's type or tags."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field
        for i, line in enumerate(lines):
            if re.match(rf"\s+{field_spec.name}\s+", line):
                indentation = self._get_indentation(line)
                go_type = self._map_type(field_spec.type)
                if field_spec.nullable and go_type not in ("string", "[]byte"):
                    go_type = f"*{go_type}"

                new_line = self._build_field_declaration(
                    field_spec, go_type, indentation, symbol
                )

                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Modify field '{field_spec.name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Go type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _capitalize(self, name: str) -> str:
        """Capitalize first letter for exported Go fields."""
        return name[0].upper() + name[1:] if name else name

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _find_struct_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of a struct body."""
        struct_name = symbol.get("name", "")
        start = -1
        end = -1

        for i, line in enumerate(lines):
            if f"type {struct_name} struct" in line:
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
        return "\t"  # Default to tab for Go

    def _build_field_declaration(
        self,
        field_spec: FieldSpec,
        go_type: str,
        indentation: str,
        symbol: Dict[str, Any]
    ) -> str:
        """Build a Go struct field declaration with tags."""
        # Use exported (capitalized) field name
        field_name = self._capitalize(field_spec.name)

        # Build tags
        tags = []

        # GORM tag
        gorm_parts = []
        if field_spec.column_name:
            gorm_parts.append(f"column:{field_spec.column_name.lower()}")
        else:
            gorm_parts.append(f"column:{self._to_snake_case(field_spec.name)}")

        # Add SQL type
        sql_type = self.SQL_TYPE_MAP.get(field_spec.type.lower())
        if sql_type:
            gorm_parts.append(f"type:{sql_type}")

        if not field_spec.nullable:
            gorm_parts.append("not null")

        if gorm_parts:
            tags.append(f'gorm:"{";".join(gorm_parts)}"')

        # JSON tag (snake_case)
        json_name = self._to_snake_case(field_spec.name)
        if field_spec.nullable:
            tags.append(f'json:"{json_name},omitempty"')
        else:
            tags.append(f'json:"{json_name}"')

        # Build the field line
        tag_str = " ".join(tags)
        return f"{indentation}{field_name} {go_type} `{tag_str}`"

    def _add_imports(
        self,
        go_type: str,
        lines: List[str],
        file_path: str
    ) -> Optional[Patch]:
        """Add import statement if needed."""
        # Extract base type (remove pointer *)
        base_type = go_type.lstrip("*")
        import_pkg = self.IMPORT_MAP.get(base_type)
        if not import_pkg:
            return None

        # Check if already imported
        for line in lines:
            if f'"{import_pkg}"' in line:
                return None

        # Find import block
        import_start = -1
        import_end = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("import ("):
                import_start = i
            elif import_start >= 0 and line.strip() == ")":
                import_end = i
                break
            elif line.strip().startswith("import ") and "(" not in line:
                # Single import - need to convert to block
                pass

        if import_start >= 0 and import_end >= 0:
            # Insert into existing import block
            return Patch(
                file_path=file_path,
                line_start=import_end,
                line_end=import_end - 1,
                old_content="",
                new_content=f'\t"{import_pkg}"',
                description=f"Add import for {import_pkg}",
                confidence="high",
            )

        return None
