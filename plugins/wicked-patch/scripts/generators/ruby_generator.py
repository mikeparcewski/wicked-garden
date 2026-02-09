"""
Ruby code generator.

Generates patches for Ruby files including:
- ActiveRecord models (add/modify attributes, associations, validations)
- Classes (add attr_accessor, methods)
- Rails migrations (add columns)

ActiveRecord conventions:
- Attributes via attr_accessor or database columns
- Validations via validates :field, presence: true
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
class RubyGenerator(BaseGenerator):
    """Generate patches for Ruby files."""

    name = "ruby"
    extensions = {".rb"}
    symbol_types = {"class", "model", "module", "controller"}

    # Type mappings from generic types to Ruby/ActiveRecord types
    TYPE_MAP = {
        "string": "String",
        "str": "String",
        "text": "String",
        "int": "Integer",
        "integer": "Integer",
        "long": "Integer",
        "bigint": "Integer",
        "float": "Float",
        "double": "Float",
        "decimal": "BigDecimal",
        "boolean": "Boolean",
        "bool": "Boolean",
        "date": "Date",
        "datetime": "DateTime",
        "timestamp": "DateTime",
        "time": "Time",
        "uuid": "String",
        "binary": "String",
        "json": "Hash",
        "array": "Array",
    }

    # ActiveRecord column types for migrations
    COLUMN_TYPE_MAP = {
        "string": "string",
        "str": "string",
        "text": "text",
        "int": "integer",
        "integer": "integer",
        "long": "bigint",
        "bigint": "bigint",
        "float": "float",
        "double": "float",
        "decimal": "decimal",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "timestamp",
        "uuid": "uuid",
        "binary": "binary",
        "json": "jsonb",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Ruby file."""
        patches = []

        if change_spec.change_type == ChangeType.ADD_FIELD:
            patches.extend(self._add_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.ADD_VALIDATION:
            patches.extend(self._add_validation(change_spec, symbol, file_content))

        return patches

    def _add_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add a field to a Ruby class/model."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine if this is an ActiveRecord model
        is_activerecord = self._is_activerecord_model(lines)

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find insertion point
        insert_line = self._find_field_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build field declaration
        if is_activerecord:
            # For ActiveRecord, add attribute accessor if custom (not a column)
            # Also add validation if needed
            field_lines = self._build_activerecord_field(
                field_spec, indentation
            )
        else:
            # For plain Ruby class, add attr_accessor
            field_lines = self._build_attr_accessor(field_spec, indentation)

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
        """Remove a field from a Ruby class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find attr_accessor or attr_reader/attr_writer
        for i, line in enumerate(lines):
            if re.search(rf"attr_(accessor|reader|writer)\s+:{field_name}\b", line):
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content="",
                    description=f"Remove attr_accessor for '{field_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Find and remove validations for this field
        for i, line in enumerate(lines):
            if re.search(rf"validates\s+:{field_name}\b", line):
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content="",
                    description=f"Remove validation for '{field_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="medium",
                ))

        return patches

    def _rename_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename a field in a Ruby class."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Rename attr_accessor
        for i, line in enumerate(lines):
            if re.search(rf"attr_(accessor|reader|writer)\s+:{old_name}\b", line):
                new_line = re.sub(rf":{old_name}\b", f":{new_name}", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename attr_accessor '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Rename validations
        for i, line in enumerate(lines):
            if re.search(rf"validates\s+:{old_name}\b", line):
                new_line = re.sub(rf":{old_name}\b", f":{new_name}", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename validation for '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="medium",
                ))

        # Rename usages (@field, self.field)
        for i, line in enumerate(lines):
            if f"@{old_name}" in line or f"self.{old_name}" in line:
                new_line = line.replace(f"@{old_name}", f"@{new_name}")
                new_line = new_line.replace(f"self.{old_name}", f"self.{new_name}")
                if new_line != line:
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

    def _add_validation(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add validation to a field."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec or not field_spec.validation:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find validation insertion point (after existing validations or after class def)
        insert_line = self._find_validation_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build validation line
        validation_line = self._build_validation(
            field_spec.name, field_spec.validation, indentation
        )

        if validation_line:
            patches.append(Patch(
                file_path=file_path,
                line_start=insert_line + 1,
                line_end=insert_line,
                old_content="",
                new_content=validation_line,
                description=f"Add validation for '{field_spec.name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Ruby type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _is_activerecord_model(self, lines: List[str]) -> bool:
        """Check if this is an ActiveRecord model."""
        for line in lines:
            if "< ApplicationRecord" in line or "< ActiveRecord::Base" in line:
                return True
        return False

    def _find_class_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of a class body."""
        class_name = symbol.get("name", "")
        start = -1
        end = -1
        indent_level = 0
        in_class = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.search(rf"class\s+{class_name}", line):
                in_class = True
                start = i
                indent_level = len(line) - len(line.lstrip())
            elif in_class:
                current_indent = len(line) - len(line.lstrip()) if stripped else indent_level + 1
                if stripped == "end" and current_indent == indent_level:
                    end = i
                    break

        return start, end

    def _find_field_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert a new field."""
        # Insert after last attr_accessor or after class definition
        last_attr = class_start

        for i in range(class_start + 1, class_end):
            line = lines[i].strip()
            if line.startswith("attr_"):
                last_attr = i
            elif line.startswith("validates") or line.startswith("belongs_to") or \
                 line.startswith("has_") or line.startswith("def "):
                break

        return last_attr

    def _find_validation_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert a new validation."""
        last_validation = class_start

        for i in range(class_start + 1, class_end):
            line = lines[i].strip()
            if line.startswith("validates"):
                last_validation = i
            elif line.startswith("def "):
                break

        return last_validation

    def _detect_indentation(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> str:
        """Detect the indentation used in the class body."""
        for i in range(class_start + 1, class_end):
            line = lines[i]
            if line.strip() and not line.strip().startswith("#"):
                return self._get_indentation(line)
        return "  "  # Default to 2 spaces for Ruby

    def _build_attr_accessor(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build an attr_accessor declaration."""
        field_name = self._to_snake_case(field_spec.name)
        return [f"{indentation}attr_accessor :{field_name}"]

    def _build_activerecord_field(
        self,
        field_spec: FieldSpec,
        indentation: str
    ) -> List[str]:
        """Build ActiveRecord field declarations (attribute + validation)."""
        lines = []
        field_name = self._to_snake_case(field_spec.name)

        # For ActiveRecord, database columns are auto-mapped
        # Add validation if required
        if not field_spec.nullable:
            lines.append(f"{indentation}validates :{field_name}, presence: true")

        return lines if lines else [f"{indentation}# {field_name} (database column)"]

    def _build_validation(
        self,
        field_name: str,
        validation: Dict[str, Any],
        indentation: str
    ) -> str:
        """Build a validates statement from validation spec."""
        field_name = self._to_snake_case(field_name)
        options = []

        if validation.get("required"):
            options.append("presence: true")

        if "min" in validation or "max" in validation:
            if "min" in validation and "max" in validation:
                options.append(f"numericality: {{ greater_than_or_equal_to: {validation['min']}, less_than_or_equal_to: {validation['max']} }}")
            elif "min" in validation:
                options.append(f"numericality: {{ greater_than_or_equal_to: {validation['min']} }}")
            else:
                options.append(f"numericality: {{ less_than_or_equal_to: {validation['max']} }}")

        if "minLength" in validation or "maxLength" in validation:
            length_opts = []
            if "minLength" in validation:
                length_opts.append(f"minimum: {validation['minLength']}")
            if "maxLength" in validation:
                length_opts.append(f"maximum: {validation['maxLength']}")
            options.append(f"length: {{ {', '.join(length_opts)} }}")

        if "pattern" in validation:
            options.append(f"format: {{ with: /{validation['pattern']}/ }}")

        if validation.get("email"):
            options.append("format: { with: URI::MailTo::EMAIL_REGEXP }")

        if options:
            return f"{indentation}validates :{field_name}, {', '.join(options)}"

        return ""
