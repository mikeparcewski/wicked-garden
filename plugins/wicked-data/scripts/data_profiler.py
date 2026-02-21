#!/usr/bin/env python3
"""
Data profiler: Analyze datasets and generate profiling reports.

Profiles CSV/Excel files to understand:
- Row/column counts
- Data types
- Null rates
- Cardinality
- Statistical summaries
- Sample values
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import statistics


def detect_type(values: List[Any]) -> str:
    """Infer data type from sample values."""
    # Remove None/empty values for type detection
    non_null = [v for v in values if v not in (None, '', 'NULL', 'null')]

    if not non_null:
        return "string"

    # Try integer
    try:
        [int(v) for v in non_null[:100]]
        return "integer"
    except (ValueError, TypeError):
        pass

    # Try decimal
    try:
        [float(v) for v in non_null[:100]]
        return "decimal"
    except (ValueError, TypeError):
        pass

    # Try boolean
    bool_values = {'true', 'false', '1', '0', 'yes', 'no', 't', 'f'}
    if all(str(v).lower() in bool_values for v in non_null[:100]):
        return "boolean"

    # Try datetime — check a sample against common date formats
    import re
    datetime_re = re.compile(
        r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}'   # date part: YYYY-MM-DD
        r'([T ]\d{1,2}:\d{2}(:\d{2})?)?'   # optional time part
        r'([Zz]|[+-]\d{2}:?\d{2})?$'       # optional timezone
    )
    sample = non_null[:20]
    if all(datetime_re.match(str(v)) for v in sample):
        return "datetime"

    return "string"


def calculate_stats(values: List[Any], data_type: str) -> Dict[str, Any]:
    """Calculate statistical summary for numeric columns."""
    if data_type not in ("integer", "decimal"):
        return {}

    # Convert to floats
    numeric_values = []
    for v in values:
        if v not in (None, '', 'NULL', 'null'):
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass

    if not numeric_values:
        return {}

    stats = {
        "min": min(numeric_values),
        "max": max(numeric_values),
        "mean": statistics.mean(numeric_values),
        "median": statistics.median(numeric_values)
    }

    if len(numeric_values) > 1:
        stats["stddev"] = statistics.stdev(numeric_values)

    return stats


def profile_csv(file_path: Path, sample_size: int = 1000) -> Dict[str, Any]:
    """Profile a CSV file."""
    print(f"Profiling {file_path}...", file=sys.stderr)

    # First pass: collect samples
    column_samples = defaultdict(list)
    row_count = 0
    column_names = []

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        column_names = reader.fieldnames or []

        for row in reader:
            row_count += 1

            # Collect samples for profiling
            if row_count <= sample_size:
                for col in column_names:
                    value = row.get(col, '')
                    column_samples[col].append(value)

    # Second pass: analyze each column
    schema = []
    for col in column_names:
        samples = column_samples[col]

        # Count nulls
        null_count = sum(1 for v in samples if v in (None, '', 'NULL', 'null'))
        null_rate = null_count / len(samples) if samples else 0

        # Infer type
        data_type = detect_type(samples)

        # Calculate cardinality
        unique_values = set(samples)
        cardinality = len(unique_values)

        # Get sample values (non-null)
        non_null_samples = [v for v in samples if v not in (None, '', 'NULL', 'null')]
        sample_values = list(set(non_null_samples[:10]))

        # Calculate stats for numeric columns
        stats = calculate_stats(samples, data_type)

        column_info = {
            "name": col,
            "type": data_type,
            "null_rate": round(null_rate, 4),
            "cardinality": cardinality,
            "sample": sample_values[:5]
        }

        if stats:
            column_info["stats"] = {
                k: round(v, 2) if isinstance(v, float) else v
                for k, v in stats.items()
            }

        schema.append(column_info)

    # Calculate quality score
    quality_score = calculate_quality_score(schema, row_count)

    # Identify issues
    issues = []
    for col in schema:
        if col["null_rate"] > 0.05:
            issues.append(f"Column '{col['name']}' has {col['null_rate']*100:.1f}% null values")

        if col["cardinality"] == 1:
            issues.append(f"Column '{col['name']}' has only one distinct value")

    return {
        "file": str(file_path),
        "rows": row_count,
        "columns": len(column_names),
        "schema": schema,
        "quality_score": quality_score,
        "issues": issues
    }


def calculate_quality_score(schema: List[Dict], row_count: int) -> int:
    """Calculate overall quality score (0-100)."""
    if not schema or row_count == 0:
        return 0

    # Factors:
    # - Low null rates (60% weight)
    # - Type diversity (20% weight)
    # - Reasonable cardinality (20% weight)

    # Null rate score
    avg_null_rate = sum(col["null_rate"] for col in schema) / len(schema)
    null_score = max(0, 100 - (avg_null_rate * 100))

    # Type diversity score
    types = set(col["type"] for col in schema)
    type_score = min(100, len(types) * 25)

    # Cardinality score (avoid all unique or all same)
    cardinality_scores = []
    for col in schema:
        ratio = col["cardinality"] / row_count if row_count > 0 else 0
        # Good: 0.1 to 0.9 (neither all same nor all unique)
        if 0.1 <= ratio <= 0.9:
            cardinality_scores.append(100)
        elif ratio == 1.0 and col["type"] in ("integer", "string"):
            # IDs are OK
            cardinality_scores.append(100)
        else:
            cardinality_scores.append(50)

    card_score = statistics.mean(cardinality_scores) if cardinality_scores else 50

    # Weighted average
    quality_score = (null_score * 0.6) + (type_score * 0.2) + (card_score * 0.2)

    return int(quality_score)


def profile_excel(file_path: Path) -> Dict[str, Any]:
    """Profile an Excel file."""
    try:
        import openpyxl
    except ImportError:
        return {
            "error": "openpyxl not installed. Install with: pip install openpyxl"
        }

    # For now, return placeholder
    # Full implementation would be similar to CSV
    return {
        "error": "Excel profiling not yet implemented. Convert to CSV first."
    }


def main():
    parser = argparse.ArgumentParser(description="Profile datasets")
    parser.add_argument("--input", required=True, help="Input file path")
    parser.add_argument("--output", help="Output JSON file (default: stdout)")
    parser.add_argument("--sample-size", type=int, default=1000,
                        help="Number of rows to sample (default: 1000)")

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Detect file type and profile
    if input_path.suffix.lower() == '.csv':
        profile = profile_csv(input_path, args.sample_size)
    elif input_path.suffix.lower() in ('.xlsx', '.xls'):
        profile = profile_excel(input_path)
    else:
        print(f"Error: Unsupported file type: {input_path.suffix}", file=sys.stderr)
        sys.exit(1)

    # Output
    output_json = json.dumps(profile, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Profile written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
