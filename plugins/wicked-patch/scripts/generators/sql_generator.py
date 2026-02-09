"""
SQL code generator.

Generates patches for SQL files including:
- ALTER TABLE statements for adding/removing columns
- CREATE TABLE modifications
- Migration scripts
- Supports PostgreSQL, MySQL, Oracle, SQL Server dialects
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
class SqlGenerator(BaseGenerator):
    """Generate patches for SQL files and migration scripts."""

    name = "sql"
    extensions = {".sql"}
    symbol_types = {"table", "column", "migration"}

    # Type mappings from generic types to SQL types (default PostgreSQL)
    TYPE_MAP = {
        "string": "VARCHAR(255)",
        "str": "VARCHAR(255)",
        "text": "TEXT",
        "int": "INTEGER",
        "integer": "INTEGER",
        "long": "BIGINT",
        "bigint": "BIGINT",
        "float": "REAL",
        "double": "DOUBLE PRECISION",
        "decimal": "DECIMAL(18,2)",
        "boolean": "BOOLEAN",
        "bool": "BOOLEAN",
        "date": "DATE",
        "datetime": "TIMESTAMP",
        "timestamp": "TIMESTAMP",
        "time": "TIME",
        "uuid": "UUID",
        "binary": "BYTEA",
        "blob": "BYTEA",
        "json": "JSONB",
    }

    # Oracle-specific type mappings
    ORACLE_TYPE_MAP = {
        "string": "VARCHAR2(255)",
        "str": "VARCHAR2(255)",
        "text": "CLOB",
        "int": "NUMBER(10)",
        "integer": "NUMBER(10)",
        "long": "NUMBER(19)",
        "bigint": "NUMBER(19)",
        "float": "FLOAT",
        "double": "FLOAT",
        "decimal": "NUMBER(18,2)",
        "boolean": "NUMBER(1)",
        "bool": "NUMBER(1)",
        "date": "DATE",
        "datetime": "TIMESTAMP",
        "timestamp": "TIMESTAMP",
        "time": "TIMESTAMP",
        "uuid": "RAW(16)",
        "binary": "BLOB",
        "blob": "BLOB",
        "json": "CLOB",
    }

    # MySQL-specific type mappings
    MYSQL_TYPE_MAP = {
        "string": "VARCHAR(255)",
        "str": "VARCHAR(255)",
        "text": "TEXT",
        "int": "INT",
        "integer": "INT",
        "long": "BIGINT",
        "bigint": "BIGINT",
        "float": "FLOAT",
        "double": "DOUBLE",
        "decimal": "DECIMAL(18,2)",
        "boolean": "TINYINT(1)",
        "bool": "TINYINT(1)",
        "date": "DATE",
        "datetime": "DATETIME",
        "timestamp": "TIMESTAMP",
        "time": "TIME",
        "uuid": "CHAR(36)",
        "binary": "BLOB",
        "blob": "BLOB",
        "json": "JSON",
    }

    # SQL Server-specific type mappings
    SQLSERVER_TYPE_MAP = {
        "string": "NVARCHAR(255)",
        "str": "NVARCHAR(255)",
        "text": "NVARCHAR(MAX)",
        "int": "INT",
        "integer": "INT",
        "long": "BIGINT",
        "bigint": "BIGINT",
        "float": "REAL",
        "double": "FLOAT",
        "decimal": "DECIMAL(18,2)",
        "boolean": "BIT",
        "bool": "BIT",
        "date": "DATE",
        "datetime": "DATETIME2",
        "timestamp": "DATETIME2",
        "time": "TIME",
        "uuid": "UNIQUEIDENTIFIER",
        "binary": "VARBINARY(MAX)",
        "blob": "VARBINARY(MAX)",
        "json": "NVARCHAR(MAX)",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for SQL files."""
        patches = []

        # Detect SQL dialect
        dialect = self._detect_dialect(file_content, symbol)

        if change_spec.change_type == ChangeType.ADD_FIELD:
            patches.extend(self._add_column(change_spec, symbol, file_content, dialect))
        elif change_spec.change_type == ChangeType.ADD_COLUMN:
            patches.extend(self._add_column(change_spec, symbol, file_content, dialect))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_column(change_spec, symbol, file_content, dialect))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_column(change_spec, symbol, file_content, dialect))
        elif change_spec.change_type == ChangeType.MODIFY_FIELD:
            patches.extend(self._modify_column(change_spec, symbol, file_content, dialect))

        return patches

    def _detect_dialect(self, content: str, symbol: Dict[str, Any]) -> str:
        """Detect SQL dialect from content or metadata."""
        metadata = symbol.get("metadata", {})

        # Check metadata first
        if metadata.get("dialect"):
            return metadata["dialect"].lower()

        content_lower = content.lower()

        # Detect by syntax patterns
        if "varchar2" in content_lower or "number(" in content_lower:
            return "oracle"
        if "nvarchar" in content_lower or "uniqueidentifier" in content_lower:
            return "sqlserver"
        if "auto_increment" in content_lower or "tinyint(1)" in content_lower:
            return "mysql"
        if "serial" in content_lower or "bytea" in content_lower or "jsonb" in content_lower:
            return "postgresql"

        return "postgresql"  # Default

    def _get_type_map(self, dialect: str) -> Dict[str, str]:
        """Get type mapping for dialect."""
        if dialect == "oracle":
            return self.ORACLE_TYPE_MAP
        if dialect == "mysql":
            return self.MYSQL_TYPE_MAP
        if dialect == "sqlserver":
            return self.SQLSERVER_TYPE_MAP
        return self.TYPE_MAP

    def _map_type(self, generic_type: str, dialect: str = "postgresql") -> str:
        """Map generic type to SQL type for dialect."""
        type_map = self._get_type_map(dialect)
        return type_map.get(generic_type.lower(), "VARCHAR(255)")

    def _add_column(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        dialect: str,
    ) -> List[Patch]:
        """Generate ALTER TABLE ADD COLUMN statement."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {})

        # Get table name
        table_name = metadata.get("table_name") or metadata.get("table") or symbol.get("name", "UNKNOWN_TABLE")
        column_name = field_spec.column_name or self._to_snake_case(field_spec.name).upper()
        sql_type = self._map_type(field_spec.type, dialect)

        # Build ALTER TABLE statement
        nullable = "" if field_spec.nullable else " NOT NULL"
        default = ""
        if field_spec.default:
            default = f" DEFAULT {field_spec.default}"

        if dialect == "oracle":
            alter_stmt = f"ALTER TABLE {table_name} ADD ({column_name} {sql_type}{nullable}{default});"
        elif dialect == "sqlserver":
            alter_stmt = f"ALTER TABLE {table_name} ADD {column_name} {sql_type}{nullable}{default};"
        else:
            alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}{nullable}{default};"

        # Find insertion point (end of file or after last statement)
        insert_line = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                insert_line = i
                break

        # Add comment for context
        comment = f"\n-- Add column {column_name} to {table_name}"
        new_content = f"{comment}\n{alter_stmt}"

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 2,
            line_end=insert_line + 1,
            old_content="",
            new_content=new_content,
            description=f"Add column '{column_name}' to '{table_name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _remove_column(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        dialect: str,
    ) -> List[Patch]:
        """Generate ALTER TABLE DROP COLUMN statement."""
        patches = []
        field_name = change_spec.old_name or (change_spec.field_spec.name if change_spec.field_spec else None)
        if not field_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {})

        table_name = metadata.get("table_name") or metadata.get("table") or symbol.get("name", "UNKNOWN_TABLE")
        column_name = self._to_snake_case(field_name).upper()

        if dialect == "oracle":
            alter_stmt = f"ALTER TABLE {table_name} DROP ({column_name});"
        elif dialect == "sqlserver":
            alter_stmt = f"ALTER TABLE {table_name} DROP COLUMN {column_name};"
        else:
            alter_stmt = f"ALTER TABLE {table_name} DROP COLUMN {column_name};"

        # Find insertion point
        insert_line = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                insert_line = i
                break

        comment = f"\n-- Drop column {column_name} from {table_name}"
        new_content = f"{comment}\n{alter_stmt}"

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 2,
            line_end=insert_line + 1,
            old_content="",
            new_content=new_content,
            description=f"Drop column '{column_name}' from '{table_name}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _rename_column(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        dialect: str,
    ) -> List[Patch]:
        """Generate ALTER TABLE RENAME COLUMN statement."""
        patches = []
        old_name = change_spec.old_name
        new_name = change_spec.new_name
        if not old_name or not new_name:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {})

        table_name = metadata.get("table_name") or metadata.get("table") or symbol.get("name", "UNKNOWN_TABLE")
        old_column = self._to_snake_case(old_name).upper()
        new_column = self._to_snake_case(new_name).upper()

        if dialect == "oracle":
            alter_stmt = f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column};"
        elif dialect == "sqlserver":
            alter_stmt = f"EXEC sp_rename '{table_name}.{old_column}', '{new_column}', 'COLUMN';"
        elif dialect == "mysql":
            # MySQL requires type in CHANGE COLUMN - use VARCHAR as placeholder
            alter_stmt = f"-- MySQL requires column type; adjust as needed\nALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column};"
        else:
            alter_stmt = f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column};"

        # Find insertion point
        insert_line = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                insert_line = i
                break

        comment = f"\n-- Rename column {old_column} to {new_column} in {table_name}"
        new_content = f"{comment}\n{alter_stmt}"

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 2,
            line_end=insert_line + 1,
            old_content="",
            new_content=new_content,
            description=f"Rename column '{old_column}' to '{new_column}'",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _modify_column(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
        dialect: str,
    ) -> List[Patch]:
        """Generate ALTER TABLE MODIFY/ALTER COLUMN statement."""
        patches = []
        field_spec = change_spec.field_spec
        if not field_spec:
            return patches

        lines = file_content.split("\n")
        file_path = symbol.get("file_path", "")
        metadata = symbol.get("metadata", {})

        table_name = metadata.get("table_name") or metadata.get("table") or symbol.get("name", "UNKNOWN_TABLE")
        column_name = field_spec.column_name or self._to_snake_case(field_spec.name).upper()
        sql_type = self._map_type(field_spec.type, dialect)
        nullable = "" if field_spec.nullable else " NOT NULL"

        if dialect == "oracle":
            alter_stmt = f"ALTER TABLE {table_name} MODIFY ({column_name} {sql_type}{nullable});"
        elif dialect == "sqlserver":
            alter_stmt = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} {sql_type}{nullable};"
        elif dialect == "mysql":
            alter_stmt = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {sql_type}{nullable};"
        else:
            alter_stmt = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {sql_type};"
            if not field_spec.nullable:
                alter_stmt += f"\nALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL;"

        # Find insertion point
        insert_line = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                insert_line = i
                break

        comment = f"\n-- Modify column {column_name} in {table_name}"
        new_content = f"{comment}\n{alter_stmt}"

        patches.append(Patch(
            file_path=file_path,
            line_start=insert_line + 2,
            line_end=insert_line + 1,
            old_content="",
            new_content=new_content,
            description=f"Modify column '{column_name}' type to {sql_type}",
            symbol_id=symbol.get("id"),
            confidence="high",
        ))

        return patches

    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name)
        return result.lstrip("_").lower()


def generate_migration_script(
    table_name: str,
    changes: List[ChangeSpec],
    dialect: str = "postgresql",
) -> str:
    """
    Generate a complete migration script for multiple changes.

    This is a utility function for generating standalone migration files.
    """
    generator = SqlGenerator()
    lines = [
        f"-- Migration script for {table_name}",
        f"-- Generated by wicked-search",
        f"-- Dialect: {dialect}",
        "",
    ]

    symbol = {
        "name": table_name,
        "file_path": "migration.sql",
        "metadata": {"table_name": table_name, "dialect": dialect},
    }

    for change in changes:
        patches = generator.generate(change, symbol, "\n".join(lines))
        for patch in patches:
            lines.append(patch.new_content)

    return "\n".join(lines)
