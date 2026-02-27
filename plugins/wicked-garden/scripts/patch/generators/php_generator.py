"""
PHP code generator.

Generates patches for PHP files including:
- Doctrine entities (add/modify properties with annotations/attributes)
- Classes (add properties)
- Laravel Eloquent models
- Symfony entities

Doctrine format: #[ORM\\Column(type: 'string', length: 255)]
                private ?string $name = null;
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
class PHPGenerator(BaseGenerator):
    """Generate patches for PHP files."""

    name = "php"
    extensions = {".php"}
    symbol_types = {"class", "entity", "model", "trait", "interface"}

    # Type mappings from generic types to PHP types
    TYPE_MAP = {
        "string": "string",
        "str": "string",
        "text": "string",
        "int": "int",
        "integer": "int",
        "long": "int",
        "bigint": "int",
        "float": "float",
        "double": "float",
        "decimal": "float",
        "boolean": "bool",
        "bool": "bool",
        "date": "\\DateTimeInterface",
        "datetime": "\\DateTimeInterface",
        "timestamp": "\\DateTimeInterface",
        "time": "\\DateTimeInterface",
        "uuid": "string",
        "binary": "string",
        "blob": "string",
        "json": "array",
        "array": "array",
    }

    # Doctrine column types
    DOCTRINE_TYPE_MAP = {
        "string": "string",
        "text": "text",
        "int": "integer",
        "integer": "integer",
        "long": "bigint",
        "bigint": "bigint",
        "float": "float",
        "double": "float",
        "decimal": "decimal",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "datetime",
        "uuid": "guid",
        "binary": "blob",
        "json": "json",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a PHP file."""
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
        """Add a property to a PHP class."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine PHP type
        php_type = self._map_type(field_spec.type)

        # Make nullable if needed
        if field_spec.nullable:
            php_type = f"?{php_type}"

        # Find class body
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Check if this is a Doctrine entity
        is_doctrine = self._is_doctrine_entity(lines, class_start)

        # Find insertion point
        insert_line = self._find_property_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build property declaration
        property_lines = self._build_property_declaration(
            field_spec, php_type, indentation, is_doctrine
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content="\n".join(property_lines),
            description=f"Add property '${field_spec.name}' ({php_type})",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Add getter
        getter_lines = self._build_getter(field_spec, php_type, indentation)
        method_insert = self._find_method_insertion_point(lines, class_start, class_end)
        patches.append(Patch(
            file_path=file_path,
            line_start=method_insert + 1,
            line_end=method_insert,
            old_content="",
            new_content="\n".join(getter_lines),
            description=f"Add getter for '${field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Add setter
        setter_lines = self._build_setter(field_spec, php_type, indentation)
        patches.append(Patch(
            file_path=file_path,
            line_start=method_insert + 2,
            line_end=method_insert + 1,
            old_content="",
            new_content="\n".join(setter_lines),
            description=f"Add setter for '${field_spec.name}'",
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
        """Remove a property from a PHP class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find property declaration
        prop_start, prop_end = self._find_property_declaration(lines, field_name)
        if prop_start >= 0:
            patches.append(Patch(
                file_path=file_path,
                line_start=prop_start + 1,
                line_end=prop_end + 1,
                old_content="\n".join(lines[prop_start:prop_end + 1]),
                new_content="",
                description=f"Remove property '${field_name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        # Find and remove getter
        getter_name = f"get{self._capitalize(field_name)}"
        getter_start, getter_end = self._find_method(lines, getter_name)
        if getter_start >= 0:
            patches.append(Patch(
                file_path=file_path,
                line_start=getter_start + 1,
                line_end=getter_end + 1,
                old_content="\n".join(lines[getter_start:getter_end + 1]),
                new_content="",
                description=f"Remove getter '{getter_name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        # Find and remove setter
        setter_name = f"set{self._capitalize(field_name)}"
        setter_start, setter_end = self._find_method(lines, setter_name)
        if setter_start >= 0:
            patches.append(Patch(
                file_path=file_path,
                line_start=setter_start + 1,
                line_end=setter_end + 1,
                old_content="\n".join(lines[setter_start:setter_end + 1]),
                new_content="",
                description=f"Remove setter '{setter_name}'",
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
        """Rename a property in a PHP class."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Rename property declaration
        for i, line in enumerate(lines):
            pattern = rf"(\$){old_name}(\s*[;=])"
            match = re.search(pattern, line)
            if match:
                new_line = re.sub(pattern, rf"\1{new_name}\2", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename property '${old_name}' to '${new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

        # Rename getter
        old_getter = f"get{self._capitalize(old_name)}"
        new_getter = f"get{self._capitalize(new_name)}"
        for i, line in enumerate(lines):
            if f"function {old_getter}" in line:
                new_line = line.replace(f"function {old_getter}", f"function {new_getter}")
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename getter '{old_getter}' to '{new_getter}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Rename setter
        old_setter = f"set{self._capitalize(old_name)}"
        new_setter = f"set{self._capitalize(new_name)}"
        for i, line in enumerate(lines):
            if f"function {old_setter}" in line:
                new_line = line.replace(f"function {old_setter}", f"function {new_setter}")
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename setter '{old_setter}' to '{new_setter}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Update $this->property references
        for i, line in enumerate(lines):
            if f"$this->{old_name}" in line:
                new_line = line.replace(f"$this->{old_name}", f"$this->{new_name}")
                if new_line != line and not any(p.line_start == i + 1 for p in patches):
                    patches.append(Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        old_content=line,
                        new_content=new_line,
                        description=f"Update property reference '${old_name}' to '${new_name}'",
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

        php_type = self._map_type(field_spec.type)
        if field_spec.nullable:
            php_type = f"?{php_type}"

        # Find property declaration
        prop_start, prop_end = self._find_property_declaration(lines, field_spec.name)
        if prop_start < 0:
            return patches

        # Check if this is a Doctrine entity
        is_doctrine = self._is_doctrine_entity(lines, prop_start)

        # Build new property
        indentation = self._get_indentation(lines[prop_end])
        new_property_lines = self._build_property_declaration(
            field_spec, php_type, indentation, is_doctrine
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=prop_start + 1,
            line_end=prop_end + 1,
            old_content="\n".join(lines[prop_start:prop_end + 1]),
            new_content="\n".join(new_property_lines),
            description=f"Modify property '${field_spec.name}'",
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
                description=f"Add validation to '${field_spec.name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to PHP type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _capitalize(self, name: str) -> str:
        """Capitalize first letter for getter/setter names."""
        return name[0].upper() + name[1:] if name else name

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _is_doctrine_entity(self, lines: List[str], class_start: int) -> bool:
        """Check if this is a Doctrine entity."""
        for i in range(max(0, class_start - 10), class_start + 1):
            if "#[ORM\\" in lines[i] or "@ORM\\" in lines[i] or \
               "@Entity" in lines[i] or "#[Entity" in lines[i]:
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
            if re.search(rf"class\s+{class_name}", line):
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
            if re.match(r"(private|protected|public)\s+\??[a-zA-Z\\]+\s+\$\w+", line):
                last_property = i
            elif line.startswith("public function") or line.startswith("private function") or \
                 line.startswith("protected function"):
                break

        return last_property

    def _find_method_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert new methods."""
        return class_end - 1

    def _detect_indentation(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> str:
        """Detect the indentation used in the class body."""
        for i in range(class_start + 1, class_end):
            line = lines[i]
            if line.strip() and not line.strip().startswith("//") and not line.strip().startswith("#"):
                return self._get_indentation(line)
        return "    "  # Default to 4 spaces

    def _build_property_declaration(
        self,
        field_spec: FieldSpec,
        php_type: str,
        indentation: str,
        is_doctrine: bool
    ) -> List[str]:
        """Build a PHP property declaration with attributes."""
        lines = []

        # Add Doctrine ORM Column attribute
        if is_doctrine:
            doctrine_type = self.DOCTRINE_TYPE_MAP.get(field_spec.type.lower(), "string")
            column_opts = [f"type: '{doctrine_type}'"]

            if field_spec.column_name:
                column_opts.append(f"name: '{field_spec.column_name}'")

            if not field_spec.nullable:
                column_opts.append("nullable: false")
            else:
                column_opts.append("nullable: true")

            # Add length for strings
            if doctrine_type == "string":
                column_opts.append("length: 255")

            lines.append(f"{indentation}#[ORM\\Column({', '.join(column_opts)})]")

        # Property declaration
        default_value = ""
        if field_spec.default:
            default_value = f" = {field_spec.default}"
        elif field_spec.nullable:
            default_value = " = null"

        lines.append(f"{indentation}private {php_type} ${field_spec.name}{default_value};")
        lines.append("")

        return lines

    def _build_getter(
        self,
        field_spec: FieldSpec,
        php_type: str,
        indentation: str
    ) -> List[str]:
        """Build getter method."""
        method_name = f"get{self._capitalize(field_spec.name)}"
        return_type = php_type

        return [
            "",
            f"{indentation}public function {method_name}(): {return_type}",
            f"{indentation}{{",
            f"{indentation}    return $this->{field_spec.name};",
            f"{indentation}}}",
        ]

    def _build_setter(
        self,
        field_spec: FieldSpec,
        php_type: str,
        indentation: str
    ) -> List[str]:
        """Build setter method."""
        method_name = f"set{self._capitalize(field_spec.name)}"

        return [
            "",
            f"{indentation}public function {method_name}({php_type} ${field_spec.name}): self",
            f"{indentation}{{",
            f"{indentation}    $this->{field_spec.name} = ${field_spec.name};",
            "",
            f"{indentation}    return $this;",
            f"{indentation}}}",
        ]

    def _build_validation_attributes(
        self,
        validation: Dict[str, Any],
        indentation: str
    ) -> List[str]:
        """Build Symfony validation attributes."""
        lines = []

        if validation.get("required"):
            lines.append(f"{indentation}#[Assert\\NotBlank]")

        if "min" in validation and "max" in validation:
            lines.append(f"{indentation}#[Assert\\Range(min: {validation['min']}, max: {validation['max']})]")
        elif "min" in validation:
            lines.append(f"{indentation}#[Assert\\GreaterThanOrEqual({validation['min']})]")
        elif "max" in validation:
            lines.append(f"{indentation}#[Assert\\LessThanOrEqual({validation['max']})]")

        if "maxLength" in validation:
            lines.append(f"{indentation}#[Assert\\Length(max: {validation['maxLength']})]")

        if "pattern" in validation:
            lines.append(f"{indentation}#[Assert\\Regex(pattern: '/{validation['pattern']}/')]")

        if validation.get("email"):
            lines.append(f"{indentation}#[Assert\\Email]")

        return lines

    def _find_property_declaration(
        self,
        lines: List[str],
        property_name: str
    ) -> tuple:
        """Find the start and end lines of a property declaration."""
        for i, line in enumerate(lines):
            if re.search(rf"\$\s*{property_name}\s*[;=]", line):
                # Check for attributes above
                start = i
                while start > 0 and (lines[start - 1].strip().startswith("#[") or
                                     lines[start - 1].strip().startswith("*") or
                                     lines[start - 1].strip().startswith("/*")):
                    start -= 1
                return start, i
        return -1, -1

    def _find_method(self, lines: List[str], method_name: str) -> tuple:
        """Find the start and end lines of a method."""
        start = -1
        brace_count = 0

        for i, line in enumerate(lines):
            if start < 0 and f"function {method_name}" in line:
                start = i
                brace_count = line.count("{") - line.count("}")
            elif start >= 0:
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    return start, i

        return -1, -1
