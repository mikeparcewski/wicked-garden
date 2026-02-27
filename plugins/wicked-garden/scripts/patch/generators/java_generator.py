"""
Java code generator.

Generates patches for Java files including:
- JPA entities (add/modify fields, columns)
- Controllers (add endpoints, mappings)
- Services (add methods)
- DTOs (add fields)
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
class JavaGenerator(BaseGenerator):
    """Generate patches for Java files."""

    name = "java"
    extensions = {".java"}
    symbol_types = {"entity", "entity_field", "class", "service", "controller", "dao"}

    # Type mappings from generic types to Java types
    TYPE_MAP = {
        "string": "String",
        "str": "String",
        "text": "String",
        "int": "int",
        "integer": "Integer",
        "long": "Long",
        "bigint": "Long",
        "float": "float",
        "double": "double",
        "decimal": "BigDecimal",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "LocalDate",
        "datetime": "LocalDateTime",
        "timestamp": "LocalDateTime",
        "time": "LocalTime",
        "uuid": "UUID",
        "binary": "byte[]",
        "blob": "byte[]",
    }

    # Import mappings for types that need imports
    IMPORT_MAP = {
        "BigDecimal": "java.math.BigDecimal",
        "LocalDate": "java.time.LocalDate",
        "LocalDateTime": "java.time.LocalDateTime",
        "LocalTime": "java.time.LocalTime",
        "UUID": "java.util.UUID",
        "List": "java.util.List",
        "Set": "java.util.Set",
        "Map": "java.util.Map",
        "Date": "java.util.Date",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """
        Generate patches for a Java file.

        Args:
            change_spec: The change specification
            symbol: The symbol being modified
            file_content: Current file content

        Returns:
            List of patches
        """
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

    def _detect_class_role(self, symbol: Dict[str, Any], file_content: str) -> str:
        """Detect the role of a Java class: entity, service, controller, or dto."""
        sym_type = symbol.get("type", "").lower()
        if sym_type in ("service", "controller", "dao"):
            return sym_type

        name = symbol.get("name", "")
        content_lower = file_content.lower()

        if "service" in name.lower() or "@service" in content_lower:
            return "service"
        if "controller" in name.lower() or "@controller" in content_lower or "@restcontroller" in content_lower:
            return "controller"
        if "repository" in name.lower() or "@repository" in content_lower:
            return "dao"
        if "@entity" in content_lower or sym_type in ("entity", "entity_field"):
            return "entity"
        return "entity"  # default

    def _add_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """
        Add a field to a Java class/entity.

        For entity/DTO classes: generates field declaration + getter + setter.
        For service/controller classes: generates validation logic instead.
        """
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Determine Java type
        java_type = self._map_type(field_spec.type)

        # For service/controller classes, generate validation instead of field
        class_role = self._detect_class_role(symbol, file_content)
        if class_role in ("service", "controller"):
            return self._add_validation_for_field(change_spec, symbol, file_content, java_type)


        # Find class body insertion point (after last field declaration)
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        # Find where to insert the field (after last field, before first method)
        insert_line = self._find_field_insertion_point(lines, class_start, class_end)
        indentation = self._detect_indentation(lines, class_start, class_end)

        # Build field declaration
        field_lines = self._build_field_declaration(
            field_spec, java_type, indentation, symbol
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,  # Insert after this line
            line_end=insert_line,        # No lines replaced (insertion)
            old_content="",
            new_content="\n".join(field_lines),
            description=f"Add field '{field_spec.name}' ({java_type})",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Find where to insert getter/setter (after existing methods or before class end)
        method_insert_line = self._find_method_insertion_point(lines, class_start, class_end)

        # Build getter
        getter_lines = self._build_getter(field_spec, java_type, indentation)
        patches.append(Patch(
            file_path=file_path,
            line_start=method_insert_line + 1,
            line_end=method_insert_line,
            old_content="",
            new_content="\n".join(getter_lines),
            description=f"Add getter for '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Build setter (same insertion point as getter — descending sort
        # in patches_by_file() will place setter after getter, both inside class)
        setter_lines = self._build_setter(field_spec, java_type, indentation)
        patches.append(Patch(
            file_path=file_path,
            line_start=method_insert_line + 1,
            line_end=method_insert_line,
            old_content="",
            new_content="\n".join(setter_lines),
            description=f"Add setter for '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        # Add imports if needed
        import_patch = self._add_imports(java_type, lines, file_path)
        if import_patch:
            patches.insert(0, import_patch)  # Imports first

        return patches

    def _remove_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Remove a field and its getter/setter, or remove usages in non-owner files."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        class_role = self._detect_class_role(symbol, file_content)

        # Find field declaration (present in owner files: entity, DTO)
        field_start, field_end = self._find_field_declaration(lines, field_name)

        if field_start >= 0:
            # Owner file: remove field declaration + getter + setter
            patches.append(Patch(
                file_path=file_path,
                line_start=field_start + 1,
                line_end=field_end + 1,
                old_content="\n".join(lines[field_start:field_end + 1]),
                new_content="",
                description=f"Remove field '{field_name}'",
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
        else:
            # Non-owner file (service, repository, test): remove methods that
            # exclusively use this field's getter/setter, or remove usage lines
            getter_name = f"get{self._capitalize(field_name)}"
            setter_name = f"set{self._capitalize(field_name)}"
            accessor_names = [getter_name, setter_name]

            patches.extend(
                self._remove_accessor_usages(lines, accessor_names, file_path, symbol)
            )

        return patches

    def _remove_accessor_usages(
        self,
        lines: List[str],
        accessor_names: List[str],
        file_path: str,
        symbol: Dict[str, Any],
    ) -> List[Patch]:
        """Remove methods that use deprecated field accessors in non-owner files.

        Two-pass approach:
        1. Find methods containing accessor calls
        2. If method body is simple (accessor is the primary logic), remove entire method
           Otherwise, remove just the accessor lines
        """
        patches = []
        removed_methods = set()  # Track method-start lines scheduled for full removal
        removed_lines = set()   # Track individual lines scheduled for removal

        for accessor_name in accessor_names:
            # Find all methods that contain calls to this accessor
            i = 0
            while i < len(lines):
                if accessor_name + "(" in lines[i]:
                    # Check if this line is inside a method
                    method_start = self._find_enclosing_method_start(lines, i)
                    if method_start >= 0 and method_start not in removed_methods:
                        method_end = self._find_method_end_from(lines, method_start)
                        if method_end >= 0:
                            # Count how many non-trivial lines are in the method body
                            body_lines = [
                                l.strip() for l in lines[method_start + 1:method_end]
                                if l.strip() and not l.strip().startswith("//") and l.strip() != "{"
                            ]
                            # Count lines that DON'T reference any of the accessors
                            non_accessor_lines = [
                                l for l in body_lines
                                if not any(a + "(" in l for a in accessor_names)
                                and l != "}" and l != "{"
                            ]

                            if len(non_accessor_lines) == 0:
                                # Method exclusively uses this accessor — remove entire method
                                removed_methods.add(method_start)
                                patches.append(Patch(
                                    file_path=file_path,
                                    line_start=method_start + 1,
                                    line_end=method_end + 1,
                                    old_content="\n".join(lines[method_start:method_end + 1]),
                                    new_content="",
                                    description=f"Remove method using deprecated accessor '{accessor_name}'",
                                    symbol_id=symbol.get("id"),
                                    confidence="medium",
                                ))
                            else:
                                # Mixed method — remove just the lines with accessor calls
                                for j in range(method_start, method_end + 1):
                                    if any(a + "(" in lines[j] for a in accessor_names):
                                        if j not in removed_lines:
                                            removed_lines.add(j)
                                            patches.append(Patch(
                                                file_path=file_path,
                                                line_start=j + 1,
                                                line_end=j + 1,
                                                old_content=lines[j],
                                                new_content="",
                                                description=f"Remove usage of deprecated accessor '{accessor_name}'",
                                                symbol_id=symbol.get("id"),
                                                confidence="low",
                                            ))
                i += 1

        return patches

    def _find_enclosing_method_start(self, lines: List[str], line_idx: int) -> int:
        """Walk backward from a line to find the enclosing method signature."""
        brace_count = 0
        for i in range(line_idx, -1, -1):
            brace_count += lines[i].count("}") - lines[i].count("{")
            stripped = lines[i].strip()
            if re.match(r'((public|private|protected)\s+)?\w+\s+\w+\s*\(', stripped):
                # Found a method signature — verify we're inside it
                if brace_count <= 0:
                    return i
        return -1

    def _find_method_end_from(self, lines: List[str], method_start: int) -> int:
        """Find the end of a method starting from the method signature line."""
        brace_count = 0
        for i in range(method_start, len(lines)):
            brace_count += lines[i].count("{") - lines[i].count("}")
            if i > method_start and brace_count <= 0:
                return i
        return -1

    def _rename_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename a field and update getter/setter."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find and rename field declaration
        for i, line in enumerate(lines):
            # Match field declaration: private Type fieldName;
            pattern = rf"(\s*(?:private|protected|public)\s+\w+\s+){old_name}(\s*[;=])"
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
                break

        # Rename getter
        old_getter = f"get{self._capitalize(old_name)}"
        new_getter = f"get{self._capitalize(new_name)}"
        for i, line in enumerate(lines):
            if old_getter in line and "(" in line:
                new_line = line.replace(old_getter, new_getter)
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
            if old_setter in line and "(" in line:
                new_line = line.replace(old_setter, new_setter)
                # Also rename the parameter: (Type oldName) -> (Type newName)
                new_line = re.sub(
                    rf'\(\s*([^)]+?)\s+{re.escape(old_name)}\s*\)',
                    rf'(\1 {new_name})',
                    new_line
                )
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename setter '{old_setter}' to '{new_setter}' and parameter",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        # Update all usages of field within the file (this.field, bare field refs)
        class_start, class_end = self._find_class_body(lines, symbol)
        for i, line in enumerate(lines):
            # Skip lines already patched
            if any(p.line_start == i + 1 for p in patches):
                continue

            new_line = line
            modified = False

            # Match this.fieldName
            if f"this.{old_name}" in line:
                new_line = new_line.replace(f"this.{old_name}", f"this.{new_name}")
                modified = True

            # Match bare field references inside class body (word boundary)
            if class_start >= 0 and class_start < i <= class_end:
                if re.search(rf'\b{re.escape(old_name)}\b', new_line):
                    # Only replace if it's clearly a field ref (not in string literals,
                    # not a type name, not a local variable declaration)
                    stripped = new_line.strip()
                    # Skip lines that declare the field or import statements
                    if not re.match(r'(private|protected|public)\s+\w+\s+' + re.escape(old_name), stripped) \
                       and not stripped.startswith("import "):
                        new_line = re.sub(rf'\b{re.escape(old_name)}\b', new_name, new_line)
                        modified = True

            if modified:
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
        """Modify a field's type or annotations."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field declaration
        field_start, field_end = self._find_field_declaration(lines, field_spec.name)
        if field_start < 0:
            return patches

        # Build new field declaration
        indentation = self._get_indentation(lines[field_start])
        java_type = self._map_type(field_spec.type)
        new_field_lines = self._build_field_declaration(
            field_spec, java_type, indentation, symbol
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=field_start + 1,
            line_end=field_end + 1,
            old_content="\n".join(lines[field_start:field_end + 1]),
            new_content="\n".join(new_field_lines),
            description=f"Modify field '{field_spec.name}'",
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
        """Add validation annotations to a field."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec or not field_spec.validation:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find field declaration
        field_start, _ = self._find_field_declaration(lines, field_spec.name)
        if field_start < 0:
            return patches

        # Build validation annotations
        indentation = self._get_indentation(lines[field_start])
        validation_lines = self._build_validation_annotations(
            field_spec.validation, indentation
        )

        if validation_lines:
            patches.append(Patch(
                file_path=file_path,
                line_start=field_start + 1,
                line_end=field_start,  # Insert before field
                old_content="",
                new_content="\n".join(validation_lines),
                description=f"Add validation to '{field_spec.name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    def _add_validation_for_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        java_type: str,
    ) -> List[Patch]:
        """Add validation logic to a service/controller for a new field."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        class_start, class_end = self._find_class_body(lines, symbol)
        if class_start < 0:
            return patches

        indentation = self._detect_indentation(lines, class_start, class_end)
        getter_name = f"get{self._capitalize(field_spec.name)}"

        # Find a validate method and extract its parameter name
        validate_method_end = -1
        param_name = None
        for i in range(class_start + 1, class_end):
            if "validate" in lines[i].lower() and "(" in lines[i]:
                # Extract parameter name from method signature
                param_match = re.search(r'\(\s*\w+\s+(\w+)\s*\)', lines[i])
                if param_match:
                    param_name = param_match.group(1)
                # Find end of this method (j > i ensures we're past the opening brace)
                brace_count = 0
                for j in range(i, class_end + 1):
                    brace_count += lines[j].count("{") - lines[j].count("}")
                    if j > i and brace_count <= 0:
                        validate_method_end = j
                        break
                break

        if validate_method_end > 0:
            # Insert validation check before the closing brace of the validate method
            insert_at = validate_method_end - 1
        else:
            # Insert as a new method before class closing brace
            insert_at = class_end - 1

        # Derive the object variable name: from method parameter, class name, or generic
        if not param_name:
            class_name = symbol.get("name", "")
            if class_name.endswith("Service"):
                entity = class_name[:-len("Service")]
            elif class_name.endswith("Controller"):
                entity = class_name[:-len("Controller")]
            else:
                entity = class_name
            param_name = entity[0].lower() + entity[1:] if entity else "request"

        # Build validation code
        if not field_spec.nullable:
            validation_lines = [
                "",
                f"{indentation}// Validate {field_spec.name}",
                f"{indentation}if ({param_name}.{getter_name}() == null || {param_name}.{getter_name}().isEmpty()) {{",
                f'{indentation}    throw new IllegalArgumentException("{self._capitalize(field_spec.name)} is required");',
                f"{indentation}}}",
            ]
        else:
            validation_lines = [
                "",
                f"{indentation}// Validate {field_spec.name} if provided",
                f"{indentation}if ({param_name}.{getter_name}() != null && {param_name}.{getter_name}().isEmpty()) {{",
                f'{indentation}    throw new IllegalArgumentException("{self._capitalize(field_spec.name)} cannot be empty");',
                f"{indentation}}}",
            ]

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_at + 1,
            line_end=insert_at,
            old_content="",
            new_content="\n".join(validation_lines),
            description=f"Add validation for '{field_spec.name}' in service",
            symbol_id=symbol.get("id"),
            confidence="medium",
        ))

        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Java type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _capitalize(self, name: str) -> str:
        """Capitalize first letter for getter/setter names."""
        return name[0].upper() + name[1:] if name else name

    def _find_class_body(self, lines: List[str], symbol: Dict[str, Any]) -> tuple:
        """Find the start and end of the class body."""
        class_name = symbol.get("name", "")
        start = -1
        end = -1
        brace_count = 0
        in_class = False

        for i, line in enumerate(lines):
            if f"class {class_name}" in line:
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

    def _find_field_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert a new field."""
        last_field_line = class_start + 1  # Default: after class opening

        for i in range(class_start + 1, class_end):
            line = lines[i].strip()
            # Skip comments and blank lines
            if not line or line.startswith("//") or line.startswith("/*"):
                continue
            # Check if this is a field declaration
            if re.match(r"(private|protected|public)\s+\w+\s+\w+\s*[;=]", line):
                last_field_line = i
            # Stop at first method
            elif re.match(r"(private|protected|public)\s+\w+\s+\w+\s*\(", line):
                break

        return last_field_line

    def _find_method_insertion_point(
        self,
        lines: List[str],
        class_start: int,
        class_end: int
    ) -> int:
        """Find the line after which to insert new methods."""
        return class_end - 1  # Before closing brace

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

    def _build_field_declaration(
        self,
        field_spec: FieldSpec,
        java_type: str,
        indentation: str,
        symbol: Dict[str, Any]
    ) -> List[str]:
        """Build field declaration with annotations."""
        lines = []
        metadata = symbol.get("metadata", {})
        is_entity = "Entity" in metadata.get("annotations", [])

        # Add JPA column annotation for entities
        if is_entity:
            column_name = field_spec.column_name or self._to_snake_case(field_spec.name).upper()
            lines.append(f'{indentation}@Column(name = "{column_name}")')

            # Add nullable constraint
            if not field_spec.nullable:
                lines.append(f'{indentation}@NotNull')

        # Add custom annotations
        for annotation in field_spec.annotations:
            lines.append(f"{indentation}@{annotation}")

        # Field declaration
        default_value = ""
        if field_spec.default:
            default_value = f" = {field_spec.default}"

        lines.append(f"{indentation}private {java_type} {field_spec.name}{default_value};")
        lines.append("")  # Blank line after field

        return lines

    def _build_getter(
        self,
        field_spec: FieldSpec,
        java_type: str,
        indentation: str
    ) -> List[str]:
        """Build getter method."""
        method_name = f"get{self._capitalize(field_spec.name)}"
        return [
            "",
            f"{indentation}public {java_type} {method_name}() {{",
            f"{indentation}    return this.{field_spec.name};",
            f"{indentation}}}",
        ]

    def _build_setter(
        self,
        field_spec: FieldSpec,
        java_type: str,
        indentation: str
    ) -> List[str]:
        """Build setter method."""
        method_name = f"set{self._capitalize(field_spec.name)}"
        return [
            "",
            f"{indentation}public void {method_name}({java_type} {field_spec.name}) {{",
            f"{indentation}    this.{field_spec.name} = {field_spec.name};",
            f"{indentation}}}",
        ]

    def _build_validation_annotations(
        self,
        validation: Dict[str, Any],
        indentation: str
    ) -> List[str]:
        """Build validation annotations from spec."""
        lines = []

        if validation.get("required"):
            lines.append(f"{indentation}@NotNull")

        if "min" in validation:
            lines.append(f'{indentation}@Min({validation["min"]})')

        if "max" in validation:
            lines.append(f'{indentation}@Max({validation["max"]})')

        if "minLength" in validation:
            lines.append(f'{indentation}@Size(min = {validation["minLength"]})')

        if "maxLength" in validation:
            if "minLength" in validation:
                lines[-1] = f'{indentation}@Size(min = {validation["minLength"]}, max = {validation["maxLength"]})'
            else:
                lines.append(f'{indentation}@Size(max = {validation["maxLength"]})')

        if "pattern" in validation:
            lines.append(f'{indentation}@Pattern(regexp = "{validation["pattern"]}")')

        if validation.get("email"):
            lines.append(f"{indentation}@Email")

        return lines

    def _find_field_declaration(
        self,
        lines: List[str],
        field_name: str
    ) -> tuple:
        """Find the start and end lines of a field declaration."""
        for i, line in enumerate(lines):
            # Match field declaration
            if re.search(rf"\s+{field_name}\s*[;=]", line):
                # Check for annotations above
                start = i
                while start > 0 and lines[start - 1].strip().startswith("@"):
                    start -= 1
                # Field is typically one line
                return start, i
        return -1, -1

    def _find_method(self, lines: List[str], method_name: str) -> tuple:
        """Find the start and end lines of a method."""
        start = -1
        brace_count = 0

        for i, line in enumerate(lines):
            if start < 0 and f"{method_name}(" in line:
                start = i
                brace_count = line.count("{") - line.count("}")
            elif start >= 0:
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    return start, i

        return -1, -1

    def _add_imports(
        self,
        java_type: str,
        lines: List[str],
        file_path: str
    ) -> Optional[Patch]:
        """Add import statement if needed."""
        import_class = self.IMPORT_MAP.get(java_type)
        if not import_class:
            return None

        import_line = f"import {import_class};"

        # Check if already imported
        for line in lines:
            if import_line in line:
                return None

        # Find import section
        for i, line in enumerate(lines):
            if line.startswith("import "):
                # Insert alphabetically
                existing_import = line.strip()
                if import_line < existing_import:
                    return Patch(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i,
                        old_content="",
                        new_content=import_line,
                        description=f"Add import for {java_type}",
                        confidence="high",
                    )
            elif line.startswith("public class") or line.startswith("@"):
                # Insert before class definition
                return Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i,
                    old_content="",
                    new_content=import_line + "\n",
                    description=f"Add import for {java_type}",
                    confidence="high",
                )

        return None

    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to SNAKE_CASE."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").upper()
