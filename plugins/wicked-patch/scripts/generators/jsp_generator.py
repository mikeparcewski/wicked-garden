"""
JSP code generator.

Generates patches for JSP files including:
- Form fields with Spring form tags
- EL expression bindings
- Display elements
- Input validation
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
class JspGenerator(BaseGenerator):
    """Generate patches for JSP files."""

    name = "jsp"
    extensions = {".jsp", ".jspx", ".tag"}
    symbol_types = {"ui_binding", "el_expression", "form_field", "form_binding"}

    # Input type mappings from Java types
    INPUT_TYPE_MAP = {
        "String": "text",
        "string": "text",
        "Integer": "number",
        "int": "number",
        "Long": "number",
        "long": "number",
        "Float": "number",
        "float": "number",
        "Double": "number",
        "double": "number",
        "BigDecimal": "number",
        "decimal": "number",
        "Boolean": "checkbox",
        "boolean": "checkbox",
        "Date": "date",
        "LocalDate": "date",
        "LocalDateTime": "datetime-local",
        "datetime": "datetime-local",
        "LocalTime": "time",
        "time": "time",
    }

    # Spring form tag mappings
    FORM_TAG_MAP = {
        "text": "form:input",
        "number": "form:input",
        "date": "form:input",
        "datetime-local": "form:input",
        "time": "form:input",
        "checkbox": "form:checkbox",
        "select": "form:select",
        "textarea": "form:textarea",
        "hidden": "form:hidden",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """
        Generate patches for a JSP file.

        Args:
            change_spec: The change specification
            symbol: The symbol being modified
            file_content: Current file content

        Returns:
            List of patches
        """
        patches = []

        if change_spec.change_type == ChangeType.ADD_UI_BINDING:
            patches.extend(self._add_ui_binding(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.UPDATE_UI_BINDING:
            patches.extend(self._update_ui_binding(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.ADD_FIELD:
            # Adding a field might require adding a form input
            patches.extend(self._add_form_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_binding(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_binding(change_spec, symbol, file_content))

        return patches

    def _add_ui_binding(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add a new UI binding to the JSP."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {}) or change_spec.metadata

        # Determine the binding path (entity.fieldName)
        entity_name = metadata.get("entity", "entity")
        binding_path = f"{self._to_camel_case(entity_name)}.{field_spec.name}"

        # Determine input type
        input_type = self._get_input_type(field_spec.type)

        # Find insertion point (after last form field or in form body)
        insert_line = self._find_form_field_insertion_point(lines, symbol)
        if insert_line < 0:
            return patches

        # Detect indentation
        indentation = self._detect_indentation(lines, insert_line)

        # Build the form field HTML
        field_html = self._build_form_field(
            field_spec, binding_path, input_type, indentation, metadata
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content="\n".join(field_html),
            description=f"Add form field for '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _update_ui_binding(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Update an existing UI binding."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find the existing binding
        binding_start, binding_end = self._find_binding(lines, field_spec.name)
        if binding_start < 0:
            return patches

        # Detect indentation from existing line
        indentation = self._get_indentation(lines[binding_start])

        # Get context
        metadata = symbol.get("metadata", {}) or change_spec.metadata
        entity_name = metadata.get("entity", "entity")
        binding_path = f"{self._to_camel_case(entity_name)}.{field_spec.name}"
        input_type = self._get_input_type(field_spec.type)

        # Build new field HTML
        field_html = self._build_form_field(
            field_spec, binding_path, input_type, indentation, metadata
        )

        patches.append(Patch(
            file_path=file_path,
            line_start=binding_start + 1,
            line_end=binding_end + 1,
            old_content="\n".join(lines[binding_start:binding_end + 1]),
            new_content="\n".join(field_html),
            description=f"Update form field for '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _add_form_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Add a form field for a new entity field."""
        # Delegate to add_ui_binding with form context
        return self._add_ui_binding(change_spec, symbol, file_content)

    def _rename_binding(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Rename EL expression bindings."""
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

            # Update EL expressions: ${entity.oldName} -> ${entity.newName}
            # Use raw string concatenation to avoid f-string brace issues
            el_pattern = r"\$\{([^}]*\.)" + old_name + r"([^}]*)\}"
            if re.search(el_pattern, line):
                new_line = re.sub(el_pattern, r"${\1" + new_name + r"\2}", new_line)
                modified = True

            # Update path attributes: path="oldName" -> path="newName"
            path_pattern = rf'path\s*=\s*"([^"]*\.)?{old_name}"'
            if re.search(path_pattern, line):
                new_line = re.sub(path_pattern, rf'path="\1{new_name}"', new_line)
                modified = True

            # Update for/id attributes
            for attr in ["for", "id", "name"]:
                attr_pattern = rf'{attr}\s*=\s*"([^"]*){old_name}([^"]*)"'
                if re.search(attr_pattern, line, re.IGNORECASE):
                    new_line = re.sub(attr_pattern, rf'{attr}="\1{new_name}\2"', new_line, flags=re.IGNORECASE)
                    modified = True

            if modified:
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename binding '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

        return patches

    def _remove_binding(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Remove a form field/binding."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find the binding/field group (label + input + error message)
        binding_start, binding_end = self._find_binding_group(lines, field_name)
        if binding_start >= 0:
            patches.append(Patch(
                file_path=file_path,
                line_start=binding_start + 1,
                line_end=binding_end + 1,
                old_content="\n".join(lines[binding_start:binding_end + 1]),
                new_content="",
                description=f"Remove form field for '{field_name}'",
                symbol_id=symbol.get("id"),
                confidence="high",
            ))

        return patches

    # Helper methods

    def _get_input_type(self, field_type: str) -> str:
        """Map field type to HTML input type."""
        return self.INPUT_TYPE_MAP.get(field_type, "text")

    def _to_camel_case(self, name: str) -> str:
        """Convert PascalCase to camelCase."""
        return name[0].lower() + name[1:] if name else name

    def _find_form_field_insertion_point(
        self,
        lines: List[str],
        symbol: Dict[str, Any]
    ) -> int:
        """Find where to insert a new form field."""
        # Look for existing form:input, form:select, etc.
        last_form_field = -1

        for i, line in enumerate(lines):
            # Check for form tags
            if re.search(r"<form:", line):
                last_form_field = i
            # Check for closing form:form tag
            if "</form:form>" in line and last_form_field > 0:
                return last_form_field

        # Try to find form body
        for i, line in enumerate(lines):
            if "<form:form" in line:
                # Look for next non-empty line
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip():
                        return j - 1
                return i

        # Fall back to symbol location
        line_start = symbol.get("line_start", 0)
        if line_start > 0:
            return line_start - 1

        return len(lines) - 1

    def _detect_indentation(self, lines: List[str], around_line: int) -> str:
        """Detect indentation near the given line."""
        for i in range(around_line, -1, -1):
            line = lines[i]
            if line.strip() and not line.strip().startswith("<%"):
                return self._get_indentation(line)
        return "        "  # Default to 8 spaces

    def _build_form_field(
        self,
        field_spec: FieldSpec,
        binding_path: str,
        input_type: str,
        indentation: str,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """Build form field HTML with Spring form tags."""
        lines = []
        field_id = self._to_field_id(field_spec.name)
        label = field_spec.label or self._to_label(field_spec.name)

        # Container div
        lines.append(f'{indentation}<div class="form-group">')
        inner_indent = indentation + "    "

        # Label
        lines.append(f'{inner_indent}<label for="{field_id}">{label}</label>')

        # Input field based on type
        form_tag = self.FORM_TAG_MAP.get(input_type, "form:input")

        if input_type == "checkbox":
            lines.append(
                f'{inner_indent}<{form_tag} path="{binding_path}" '
                f'id="{field_id}" cssClass="form-check-input" />'
            )
        elif input_type == "select":
            # Select needs items attribute
            items_path = metadata.get("items_path", f"{field_spec.name}Options")
            lines.append(
                f'{inner_indent}<{form_tag} path="{binding_path}" '
                f'id="{field_id}" cssClass="form-control" items="${{{items_path}}}" />'
            )
        elif input_type == "textarea":
            lines.append(
                f'{inner_indent}<{form_tag} path="{binding_path}" '
                f'id="{field_id}" cssClass="form-control" rows="3" />'
            )
        else:
            # Standard input
            type_attr = f'type="{input_type}" ' if input_type != "text" else ""
            required = 'required="required" ' if not field_spec.nullable else ""
            lines.append(
                f'{inner_indent}<{form_tag} path="{binding_path}" '
                f'{type_attr}id="{field_id}" cssClass="form-control" {required}/>'
            )

        # Error message
        lines.append(f'{inner_indent}<form:errors path="{binding_path}" cssClass="text-danger" />')

        # Close container
        lines.append(f'{indentation}</div>')

        return lines

    def _find_binding(self, lines: List[str], field_name: str) -> tuple:
        """Find lines containing a binding for the field."""
        for i, line in enumerate(lines):
            # Look for path attribute or EL expression with field name
            if (f'path="{field_name}"' in line or
                f'path="' in line and f'.{field_name}"' in line or
                f".{field_name}" in line and "${" in line):
                return i, i
        return -1, -1

    def _find_binding_group(self, lines: List[str], field_name: str) -> tuple:
        """Find the entire form group containing a field binding."""
        # First find the binding line
        binding_line = -1
        for i, line in enumerate(lines):
            if (f'path="{field_name}"' in line or
                f'path="' in line and f'.{field_name}"' in line):
                binding_line = i
                break

        if binding_line < 0:
            return -1, -1

        # Find the containing div (form-group)
        start = binding_line
        for i in range(binding_line, -1, -1):
            if '<div class="form-group"' in lines[i] or '<div class="form-row"' in lines[i]:
                start = i
                break

        # Find the closing div
        end = binding_line
        div_depth = 0
        for i in range(start, len(lines)):
            div_depth += lines[i].count("<div") - lines[i].count("</div>")
            if div_depth <= 0:
                end = i
                break

        return start, end

    def _to_field_id(self, name: str) -> str:
        """Convert field name to HTML id."""
        return name

    def _to_label(self, name: str) -> str:
        """Convert camelCase field name to human-readable label."""
        # Split on capital letters
        words = re.sub(r"([A-Z])", r" \1", name).split()
        return " ".join(w.capitalize() for w in words)
