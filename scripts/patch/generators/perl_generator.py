"""
Perl code generator.

Generates patches for Perl files including:
- DBIx::Class result classes (add/modify columns)
- Moose/Moo classes (add attributes with has)
- Classic Perl OO (add accessor methods)

DBIx::Class format:
    __PACKAGE__->add_columns(
        email => { data_type => 'varchar', size => 255, is_nullable => 0 },
    );

Moose/Moo format:
    has 'email' => (
        is       => 'rw',
        isa      => 'Str',
        required => 1,
    );
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
class PerlGenerator(BaseGenerator):
    """Generate patches for Perl files."""

    name = "perl"
    extensions = {".pm", ".pl"}
    symbol_types = {"package", "class", "result_class", "module"}

    # Type mappings from generic types to Perl/Moose types
    TYPE_MAP = {
        "string": "Str",
        "str": "Str",
        "text": "Str",
        "int": "Int",
        "integer": "Int",
        "long": "Int",
        "bigint": "Int",
        "float": "Num",
        "double": "Num",
        "decimal": "Num",
        "boolean": "Bool",
        "bool": "Bool",
        "date": "Str",  # Often stored as string in Perl
        "datetime": "Str",
        "timestamp": "Str",
        "uuid": "Str",
        "binary": "Str",
        "json": "HashRef",
        "array": "ArrayRef",
        "hash": "HashRef",
    }

    # DBIx::Class data types
    DBIC_TYPE_MAP = {
        "string": "varchar",
        "str": "varchar",
        "text": "text",
        "int": "integer",
        "integer": "integer",
        "long": "bigint",
        "bigint": "bigint",
        "float": "float",
        "double": "double precision",
        "decimal": "decimal",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "timestamp",
        "uuid": "uuid",
        "binary": "blob",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a Perl file."""
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
        """Add a field/attribute to a Perl class."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Detect class type
        class_type = self._detect_class_type(lines)

        if class_type == "dbic":
            patches.extend(self._add_dbic_column(field_spec, lines, file_path, symbol))
        elif class_type in ("moose", "moo"):
            patches.extend(self._add_moose_attribute(field_spec, lines, file_path, symbol, class_type))
        else:
            # Classic Perl OO - add accessor
            patches.extend(self._add_classic_accessor(field_spec, lines, file_path, symbol))

        return patches

    def _add_dbic_column(
        self,
        field_spec: FieldSpec,
        lines: List[str],
        file_path: str,
        symbol: Dict[str, Any]
    ) -> List[Patch]:
        """Add a column to a DBIx::Class result class."""
        patches = []

        # Find add_columns block or last column definition
        insert_line = -1
        indentation = "    "

        for i, line in enumerate(lines):
            if "__PACKAGE__->add_columns(" in line:
                # Find the end of add_columns
                paren_count = line.count("(") - line.count(")")
                for j in range(i + 1, len(lines)):
                    paren_count += lines[j].count("(") - lines[j].count(")")
                    if paren_count <= 0:
                        insert_line = j
                        break
                # Detect indentation from existing columns
                if i + 1 < len(lines):
                    indentation = self._get_indentation(lines[i + 1])
                break
            elif "->add_column(" in line:
                insert_line = i + 1

        if insert_line < 0:
            # No existing columns, find package declaration
            for i, line in enumerate(lines):
                if line.startswith("package "):
                    insert_line = i + 2
                    break

        if insert_line < 0:
            return patches

        # Build column definition
        column_def = self._build_dbic_column(field_spec, indentation)

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line,
            line_end=insert_line - 1,
            old_content="",
            new_content=column_def,
            description=f"Add DBIx::Class column '{field_spec.name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _add_moose_attribute(
        self,
        field_spec: FieldSpec,
        lines: List[str],
        file_path: str,
        symbol: Dict[str, Any],
        class_type: str
    ) -> List[Patch]:
        """Add a Moose/Moo attribute."""
        patches = []

        # Find last 'has' declaration or after 'use Moose/Moo'
        insert_line = -1
        indentation = ""

        for i, line in enumerate(lines):
            if line.strip().startswith("has "):
                insert_line = i + 1
                # Find end of this has block
                if ";" not in line:
                    paren_count = line.count("(") - line.count(")")
                    for j in range(i + 1, len(lines)):
                        paren_count += lines[j].count("(") - lines[j].count(")")
                        if ";" in lines[j] or paren_count <= 0:
                            insert_line = j + 1
                            break
                indentation = self._get_indentation(line)
            elif f"use {class_type.capitalize()}" in line or f"use {class_type}" in line:
                if insert_line < 0:
                    insert_line = i + 2

        if insert_line < 0:
            # Find package declaration
            for i, line in enumerate(lines):
                if line.startswith("package "):
                    insert_line = i + 2
                    break

        if insert_line < 0:
            return patches

        # Build has declaration
        attr_def = self._build_moose_attribute(field_spec, indentation)

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content=attr_def,
            symbol_id=symbol.get("id"),
            description=f"Add {class_type.capitalize()} attribute '{field_spec.name}'",
            confidence="high",
        ))

        return patches

    def _add_classic_accessor(
        self,
        field_spec: FieldSpec,
        lines: List[str],
        file_path: str,
        symbol: Dict[str, Any]
    ) -> List[Patch]:
        """Add a classic Perl accessor method."""
        patches = []

        # Find end of package (before 1; or __END__)
        insert_line = len(lines) - 1
        for i, line in enumerate(lines):
            if line.strip() in ("1;", "__END__", "__DATA__"):
                insert_line = i - 1
                break

        # Build accessor sub
        accessor = self._build_classic_accessor(field_spec)

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 1,
            line_end=insert_line,
            old_content="",
            new_content=accessor,
            symbol_id=symbol.get("id"),
            description=f"Add accessor for '{field_spec.name}'",
            confidence="high",
        ))

        return patches

    def _remove_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Remove a field from a Perl class."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        # Find has declaration or column definition
        for i, line in enumerate(lines):
            # Moose/Moo has
            if re.search(rf"has\s+['\"]?{field_name}['\"]?\s*=>", line):
                # Find end of declaration
                end = i
                if ";" not in line:
                    paren_count = line.count("(") - line.count(")")
                    for j in range(i + 1, len(lines)):
                        paren_count += lines[j].count("(") - lines[j].count(")")
                        if ";" in lines[j] or paren_count <= 0:
                            end = j
                            break

                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=end + 1,
                    old_content="\n".join(lines[i:end + 1]),
                    new_content="",
                    description=f"Remove attribute '{field_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))
                break

            # DBIx::Class column
            if re.search(rf"^\s*{field_name}\s*=>", line):
                end = i
                if "}," not in line and "}" not in line:
                    for j in range(i + 1, len(lines)):
                        if "}," in lines[j] or re.match(r"^\s*\},?\s*$", lines[j]):
                            end = j
                            break

                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=end + 1,
                    old_content="\n".join(lines[i:end + 1]),
                    new_content="",
                    description=f"Remove column '{field_name}'",
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
        """Rename a field in a Perl class."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")

        for i, line in enumerate(lines):
            # Moose/Moo has
            if re.search(rf"has\s+['\"]?{old_name}['\"]?\s*=>", line):
                new_line = re.sub(
                    rf"(has\s+)['\"]?{old_name}['\"]?(\s*=>)",
                    rf"\1'{new_name}'\2",
                    line
                )
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename attribute '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

            # DBIx::Class column
            elif re.search(rf"^\s*{old_name}\s*=>", line):
                new_line = re.sub(rf"(\s*){old_name}(\s*=>)", rf"\1{new_name}\2", line)
                patches.append(Patch(
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                    old_content=line,
                    new_content=new_line,
                    description=f"Rename column '{old_name}' to '{new_name}'",
                    symbol_id=symbol.get("id"),
                    confidence="high",
                ))

            # $self->{field} or $self->field
            elif f"$self->{{{old_name}}}" in line or f"$self->{old_name}" in line:
                new_line = line.replace(f"$self->{{{old_name}}}", f"$self->{{{new_name}}}")
                new_line = new_line.replace(f"$self->{old_name}", f"$self->{new_name}")
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

    def _modify_field(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Modify a field's type."""
        # For Perl, modification typically means removing and re-adding
        # with the new specification
        patches = []
        patches.extend(self._remove_field(change_spec, symbol, file_content))
        patches.extend(self._add_field(change_spec, symbol, file_content))
        return patches

    # Helper methods

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to Perl/Moose type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)

    def _detect_class_type(self, lines: List[str]) -> str:
        """Detect the type of Perl class."""
        for line in lines:
            if "use Moose" in line or "extends " in line:
                return "moose"
            elif "use Moo" in line:
                return "moo"
            elif "DBIx::Class" in line or "__PACKAGE__->load_components" in line:
                return "dbic"
            elif "use base" in line and "DBIx::Class" in line:
                return "dbic"
        return "classic"

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()

    def _build_dbic_column(self, field_spec: FieldSpec, indentation: str) -> str:
        """Build a DBIx::Class column definition."""
        field_name = self._to_snake_case(field_spec.name)
        data_type = self.DBIC_TYPE_MAP.get(field_spec.type.lower(), "varchar")

        parts = [f"data_type => '{data_type}'"]

        if data_type == "varchar":
            parts.append("size => 255")

        if not field_spec.nullable:
            parts.append("is_nullable => 0")
        else:
            parts.append("is_nullable => 1")

        if field_spec.default:
            parts.append(f"default_value => '{field_spec.default}'")

        column_def = f"{indentation}{field_name} => {{ {', '.join(parts)} }},"
        return column_def

    def _build_moose_attribute(self, field_spec: FieldSpec, indentation: str) -> str:
        """Build a Moose/Moo has declaration."""
        field_name = self._to_snake_case(field_spec.name)
        moose_type = self._map_type(field_spec.type)

        lines = [f"{indentation}has '{field_name}' => ("]
        lines.append(f"{indentation}    is       => 'rw',")
        lines.append(f"{indentation}    isa      => '{moose_type}',")

        if not field_spec.nullable:
            lines.append(f"{indentation}    required => 1,")

        if field_spec.default:
            if moose_type in ("Str",):
                lines.append(f"{indentation}    default  => '{field_spec.default}',")
            else:
                lines.append(f"{indentation}    default  => {field_spec.default},")

        lines.append(f"{indentation});")
        lines.append("")

        return "\n".join(lines)

    def _build_classic_accessor(self, field_spec: FieldSpec) -> str:
        """Build a classic Perl accessor sub."""
        field_name = self._to_snake_case(field_spec.name)

        return f"""
sub {field_name} {{
    my $self = shift;
    if (@_) {{
        $self->{{{field_name}}} = shift;
    }}
    return $self->{{{field_name}}};
}}
"""
