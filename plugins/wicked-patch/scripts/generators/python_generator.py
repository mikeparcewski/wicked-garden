"""
Python code generator.

Generates patches for Python files including:
- SQLAlchemy/Django models (add/modify fields)
- Pydantic models
- Dataclasses
- FastAPI/Flask endpoints
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
class PythonGenerator(BaseGenerator):
    """Generate patches for Python files."""

    name = "python"
    extensions = {".py"}
    symbol_types = {"entity", "entity_field", "class", "model", "dataclass"}

    # Type mappings from generic types to Python types
    TYPE_MAP = {
        "string": "str",
        "text": "str",
        "int": "int",
        "integer": "int",
        "long": "int",
        "bigint": "int",
        "float": "float",
        "double": "float",
        "decimal": "Decimal",
        "boolean": "bool",
        "bool": "bool",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "datetime",
        "time": "time",
        "uuid": "UUID",
        "binary": "bytes",
        "blob": "bytes",
        "list": "List",
        "dict": "Dict",
    }

    # SQLAlchemy type mappings
    SQLALCHEMY_TYPE_MAP = {
        "str": "String",
        "string": "String",
        "text": "Text",
        "int": "Integer",
        "integer": "Integer",
        "long": "BigInteger",
        "float": "Float",
        "double": "Float",
        "decimal": "Numeric",
        "bool": "Boolean",
        "boolean": "Boolean",
        "date": "Date",
        "datetime": "DateTime",
        "time": "Time",
        "uuid": "UUID",
        "binary": "LargeBinary",
        "bytes": "LargeBinary",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Python file."""
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
        """Add a field to a Python class/model."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {})

        # Detect the class type (SQLAlchemy, Pydantic, dataclass, plain)
        class_type = self._detect_class_type(lines, symbol)

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find field insertion point
        insert_line = self._find_field_insertion_point(lines, class_start, class_end, class_type)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build field declaration based on class type
        if class_type == "sqlalchemy":
            field_lines = self._build_sqlalchemy_field(field_spec, indentation)
        elif class_type == "pydantic":
            field_lines = self._build_pydantic_field(field_spec, indentation)
        elif class_type == "dataclass":
            field_lines = self._build_dataclass_field(field_spec, indentation)
        else:
            field_lines = self._build_plain_field(field_spec, indentation)

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
        """Remove a field from a Python class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field line
        for i, line in enumerate(lines):
            # Match: field_name = ... or field_name: ...
            if re.match(rf"^\s+{field_name}\s*[:=]", line):
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

    def _camel_to_snake(self, name: str) -> str:
        """Convert camelCase to snake_case for Python naming conventions."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _rename_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename a field across the file, converting to snake_case."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        # Convert both names to snake_case for Python
        old_name_py = self._camel_to_snake(old_name)
        new_name_py = self._camel_to_snake(new_name)

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Try both the original name and the snake_case version for matching
        # (source might already be snake_case or camelCase)
        old_names = list(dict.fromkeys([old_name_py, old_name]))  # dedupe, prefer snake
        target_name = new_name_py

        for i, line in enumerate(lines):
            modified = False
            new_line = line

            for oname in old_names:
                # Field declaration: old_name = ... or old_name: ...
                if re.match(rf"^\s+{re.escape(oname)}\s*[:=]", new_line):
                    new_line = re.sub(
                        rf"^(\s+){re.escape(oname)}(\s*[:=])",
                        rf"\1{target_name}\2",
                        new_line,
                    )
                    modified = True
                    break

                # Attribute access: self.old_name
                if f"self.{oname}" in new_line:
                    new_line = new_line.replace(f"self.{oname}", f"self.{target_name}")
                    modified = True
                    break

                # Bare word-boundary match (dot access like order.status)
                if re.search(rf"\.{re.escape(oname)}\b", new_line):
                    new_line = re.sub(rf"\.{re.escape(oname)}\b", f".{target_name}", new_line)
                    modified = True
                    break

                # Method parameters and dict keys
                if f'["{oname}"]' in new_line or f"['{oname}']" in new_line:
                    new_line = new_line.replace(f'["{oname}"]', f'["{target_name}"]')
                    new_line = new_line.replace(f"['{oname}']", f"['{target_name}']")
                    modified = True
                    break

            if modified:
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename '{old_name}' to '{target_name}' (snake_case)",
                    symbol_id=symbol.get("id"),
                    confidence="high" if "self." in line else "medium",
                ))

        return patches

    def _modify_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Modify a field's type or default value."""
        # Combination of remove and add
        remove_patches = self._remove_field(change_spec, symbol, file_content)
        add_patches = self._add_field(change_spec, symbol, file_content)
        return remove_patches + add_patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Python type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _detect_class_type(self, lines: List[str], symbol: Dict[str, Any]) -> str:
        """Detect if class is SQLAlchemy, Pydantic, dataclass, or plain."""
        class_name = symbol.get("name", "")

        for i, line in enumerate(lines):
            # Check for decorators and base classes
            if "@dataclass" in line:
                return "dataclass"
            if f"class {class_name}" in line:
                if "(Base)" in line or "(db.Model)" in line or "DeclarativeBase" in line:
                    return "sqlalchemy"
                if "(BaseModel)" in line or "(pydantic" in line.lower():
                    return "pydantic"
                # Check previous line for decorators
                if i > 0 and "@dataclass" in lines[i - 1]:
                    return "dataclass"

        # Check for Column() usage (SQLAlchemy)
        content = "\n".join(lines)
        if "Column(" in content or "mapped_column(" in content:
            return "sqlalchemy"
        if "Field(" in content and "pydantic" in content.lower():
            return "pydantic"

        return "plain"

    def _find_class_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of the class body."""
        class_name = symbol.get("name", "")
        start = -1
        end = len(lines) - 1
        indent_level = -1

        for i, line in enumerate(lines):
            if f"class {class_name}" in line:
                start = i
                # Find the indentation level of class members
                for j in range(i + 1, len(lines)):
                    stripped = lines[j].strip()
                    if stripped and not stripped.startswith("#"):
                        indent_level = len(lines[j]) - len(lines[j].lstrip())
                        break
                continue

            if start >= 0 and indent_level >= 0:
                # Check if we've left the class (less indentation or new class)
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent < indent_level and stripped:
                        end = i - 1
                        break
                    if line.startswith("class ") and i > start:
                        end = i - 1
                        break

        return start, end

    def _find_field_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int,
        class_type: str
    ) -> int:
        """Find where to insert a new field."""
        last_field_line = class_start + 1

        for i in range(class_start + 1, class_end + 1):
            line = lines[i].strip()

            # Skip empty lines, comments, docstrings
            if not line or line.startswith("#") or line.startswith('"""') or line.startswith("'''"):
                continue

            # Check for field patterns based on class type
            if class_type == "sqlalchemy":
                if "=" in line and ("Column(" in line or "mapped_column(" in line or "relationship(" in line):
                    last_field_line = i
            elif class_type == "pydantic" or class_type == "dataclass":
                if ":" in line and not line.startswith("def "):
                    last_field_line = i
            else:
                # Plain class - look for assignments
                if "=" in line and not line.startswith("def "):
                    last_field_line = i

            # Stop at methods
            if line.startswith("def "):
                break

        return last_field_line

    def _detect_indentation(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> str:
        """Detect the indentation used in the class body."""
        for i in range(class_start + 1, min(class_end + 1, len(lines))):
            line = lines[i]
            if line.strip() and not line.strip().startswith("#"):
                return self._get_indentation(line)
        return "    "  # Default to 4 spaces

    def _build_sqlalchemy_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build SQLAlchemy column definition."""
        python_type = self._map_type(field_spec.type)
        sa_type = self.SQLALCHEMY_TYPE_MAP.get(field_spec.type.lower(), "String")

        # Build Column arguments
        args = [sa_type]

        if field_spec.column_name:
            args.insert(0, f'"{field_spec.column_name}"')

        kwargs = []
        if not field_spec.nullable:
            kwargs.append("nullable=False")
        if field_spec.default:
            kwargs.append(f"default={field_spec.default}")

        args_str = ", ".join(args + kwargs)

        return [f"{indentation}{field_spec.name} = Column({args_str})"]

    def _build_pydantic_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build Pydantic field definition."""
        python_type = self._map_type(field_spec.type)

        if field_spec.nullable:
            type_hint = f"Optional[{python_type}]"
        else:
            type_hint = python_type

        # Build Field arguments
        kwargs = []
        if field_spec.default is not None:
            kwargs.append(f"default={field_spec.default}")
        elif field_spec.nullable:
            kwargs.append("default=None")
        if field_spec.description:
            kwargs.append(f'description="{field_spec.description}"')

        if kwargs:
            return [f"{indentation}{field_spec.name}: {type_hint} = Field({', '.join(kwargs)})"]
        elif field_spec.default is not None:
            return [f"{indentation}{field_spec.name}: {type_hint} = {field_spec.default}"]
        elif field_spec.nullable:
            return [f"{indentation}{field_spec.name}: {type_hint} = None"]
        else:
            return [f"{indentation}{field_spec.name}: {type_hint}"]

    def _build_dataclass_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build dataclass field definition."""
        python_type = self._map_type(field_spec.type)

        if field_spec.nullable:
            type_hint = f"Optional[{python_type}]"
        else:
            type_hint = python_type

        # Build field arguments
        kwargs = []
        if field_spec.default is not None:
            kwargs.append(f"default={field_spec.default}")
        elif field_spec.nullable:
            kwargs.append("default=None")

        if kwargs:
            return [f"{indentation}{field_spec.name}: {type_hint} = field({', '.join(kwargs)})"]
        elif field_spec.default is not None:
            return [f"{indentation}{field_spec.name}: {type_hint} = {field_spec.default}"]
        elif field_spec.nullable:
            return [f"{indentation}{field_spec.name}: {type_hint} = None"]
        else:
            return [f"{indentation}{field_spec.name}: {type_hint}"]

    def _build_plain_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build plain Python class field."""
        if field_spec.default is not None:
            return [f"{indentation}{field_spec.name} = {field_spec.default}"]
        else:
            return [f"{indentation}{field_spec.name} = None"]
