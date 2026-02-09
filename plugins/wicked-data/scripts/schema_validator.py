#!/usr/bin/env python3
"""
Schema validator: Validate data against expected schemas.

Validates CSV files against JSON schema definitions to ensure:
- All required columns present
- Data types match
- Nullability constraints satisfied
- Custom constraints met
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ValidationError:
    def __init__(self, severity: str, column: str, message: str, row: Optional[int] = None):
        self.severity = severity  # ERROR, WARNING
        self.column = column
        self.message = message
        self.row = row

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "severity": self.severity,
            "column": self.column,
            "message": self.message
        }
        if self.row is not None:
            result["row"] = self.row
        return result


def validate_type(value: str, expected_type: str) -> bool:
    """Check if value conforms to expected type."""
    if value in ('', 'NULL', 'null', None):
        return True  # Null check is separate

    try:
        if expected_type == "integer":
            int(value)
            return True
        elif expected_type == "decimal":
            float(value)
            return True
        elif expected_type == "boolean":
            return str(value).lower() in ('true', 'false', '1', '0', 'yes', 'no', 't', 'f')
        elif expected_type == "datetime":
            # Basic datetime check (contains date/time separators)
            return any(sep in str(value) for sep in ['-', '/', ':', 'T'])
        elif expected_type == "string":
            return True
        else:
            return True  # Unknown type, pass
    except (ValueError, TypeError):
        return False


def validate_constraints(value: str, constraints: Dict[str, Any], data_type: str) -> Optional[str]:
    """Validate value against constraints. Returns error message if invalid."""
    if not constraints:
        return None

    # Check unique constraint (requires full dataset - handled separately)
    # Check pattern constraint (regex)
    if "pattern" in constraints:
        pattern = constraints["pattern"]
        if value and not re.match(pattern, value):
            return f"Value '{value}' does not match pattern '{pattern}'"

    # Check min/max for numeric types
    if data_type in ("integer", "decimal") and value:
        try:
            numeric_value = float(value)

            if "min" in constraints and numeric_value < constraints["min"]:
                return f"Value {numeric_value} is below minimum {constraints['min']}"

            if "max" in constraints and numeric_value > constraints["max"]:
                return f"Value {numeric_value} exceeds maximum {constraints['max']}"

        except ValueError:
            pass  # Type validation will catch this

    # Check length for strings
    if data_type == "string" and value:
        if "min_length" in constraints and len(value) < constraints["min_length"]:
            return f"Length {len(value)} is below minimum {constraints['min_length']}"

        if "max_length" in constraints and len(value) > constraints["max_length"]:
            return f"Length {len(value)} exceeds maximum {constraints['max_length']}"

    return None


def validate_csv(csv_path: Path, schema: Dict[str, Any], sample_size: int = 1000) -> Dict[str, Any]:
    """Validate CSV file against schema."""
    print(f"Validating {csv_path} against schema...", file=sys.stderr)

    errors: List[ValidationError] = []
    schema_columns = {col["name"]: col for col in schema["columns"]}

    # Read CSV
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        actual_columns = set(reader.fieldnames or [])

        # Check for missing required columns
        required_columns = set(schema_columns.keys())
        missing_columns = required_columns - actual_columns

        for col in missing_columns:
            errors.append(ValidationError(
                "ERROR",
                col,
                f"Required column '{col}' is missing from data"
            ))

        # Check for extra columns (warning)
        extra_columns = actual_columns - required_columns
        for col in extra_columns:
            errors.append(ValidationError(
                "WARNING",
                col,
                f"Column '{col}' exists in data but not in schema"
            ))

        # Validate row data
        row_num = 0
        unique_values = {col: set() for col in schema_columns}

        for row in reader:
            row_num += 1

            # Only validate a sample for performance
            if row_num > sample_size:
                break

            for col_name, col_def in schema_columns.items():
                if col_name not in row:
                    continue  # Already flagged as missing

                value = row[col_name]

                # Check nullable constraint
                is_null = value in ('', 'NULL', 'null', None)
                if is_null and not col_def.get("nullable", True):
                    errors.append(ValidationError(
                        "ERROR",
                        col_name,
                        f"Null value found in non-nullable column",
                        row_num
                    ))
                    continue

                if not is_null:
                    # Check type
                    expected_type = col_def.get("type", "string")
                    if not validate_type(value, expected_type):
                        errors.append(ValidationError(
                            "ERROR",
                            col_name,
                            f"Value '{value}' does not match type '{expected_type}'",
                            row_num
                        ))

                    # Check constraints
                    constraints = col_def.get("constraints", {})
                    constraint_error = validate_constraints(value, constraints, expected_type)
                    if constraint_error:
                        errors.append(ValidationError(
                            "ERROR",
                            col_name,
                            constraint_error,
                            row_num
                        ))

                    # Collect for uniqueness check
                    if constraints.get("unique"):
                        if value in unique_values[col_name]:
                            errors.append(ValidationError(
                                "ERROR",
                                col_name,
                                f"Duplicate value '{value}' found in unique column",
                                row_num
                            ))
                        unique_values[col_name].add(value)

    # Summarize results
    error_count = sum(1 for e in errors if e.severity == "ERROR")
    warning_count = sum(1 for e in errors if e.severity == "WARNING")

    is_valid = error_count == 0

    return {
        "valid": is_valid,
        "rows_checked": min(row_num, sample_size),
        "error_count": error_count,
        "warning_count": warning_count,
        "errors": [e.to_dict() for e in errors[:100]]  # Limit output
    }


def main():
    parser = argparse.ArgumentParser(description="Validate data against schema")
    parser.add_argument("--schema", required=True, help="Schema JSON file")
    parser.add_argument("--data", required=True, help="Data CSV file")
    parser.add_argument("--output", help="Output JSON file (default: stdout)")
    parser.add_argument("--sample-size", type=int, default=1000,
                        help="Number of rows to validate (default: 1000)")

    args = parser.parse_args()

    schema_path = Path(args.schema)
    data_path = Path(args.data)

    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)

    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    # Load schema
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    # Validate
    result = validate_csv(data_path, schema, args.sample_size)

    # Output
    output_json = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Validation result written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    # Exit with error code if validation failed
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
