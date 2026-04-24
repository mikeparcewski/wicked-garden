---
name: data
description: |
  Use when profiling a dataset's structure, validating it against a schema, or generating a data quality
  report (completeness, uniqueness, validity constraints). Runs the data_profiler.py and schema_validator.py scripts.
  NOT for exploratory pattern analysis (use data/analysis) or SQL queries (use data:analyze).
---

# Data Engineering Skill

Core data engineering operations for profiling, validation, and quality assessment.

## Quick Start

### Profile a Dataset

```bash
/wicked-garden:data:data profile path/to/data.csv
```

This will:
1. Detect file format
2. Sample rows (head/random/tail)
3. Infer schema and types
4. Calculate quality metrics
5. Generate recommendations

### Validate Schema

```bash
/wicked-garden:data:data validate --schema schema.json --data data.csv
```

Checks: Column presence, type conformance, constraint validation, nullability rules.

### Assess Quality

```bash
/wicked-garden:data:data quality data.csv
```

Reports on: Completeness (null rates), Uniqueness (duplicates), Validity (constraints), Consistency (cross-field checks).

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:data:data profile <path>` | Profile dataset structure and quality |
| `/wicked-garden:data:data validate` | Validate data against schema |
| `/wicked-garden:data:data quality <path>` | Generate quality report |

## Dataset Profiling

Uses `data_profiler.py` script:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/data/data_profiler.py" \
  --input data.csv --output profile.json
```

**Output includes**:
- Row count and column count
- Column types (inferred)
- Null rates per column
- Cardinality (distinct values)
- Sample values
- Statistical summaries for numeric columns

## Schema Validation

Uses `schema_validator.py` script. Define expected columns with:
- **name**: Column name
- **type**: integer, string, decimal, datetime, date
- **nullable**: true/false
- **constraints**: unique, min, max, pattern, enum

See [examples](refs/examples.md) for schema format.

## Quality Dimensions

| Dimension | Metric | Threshold |
|-----------|--------|-----------|
| Completeness | Null rate | <5% |
| Uniqueness | Duplicate rate | <1% |
| Validity | Type conformance | 100% |
| Consistency | Cross-field rules | 100% |

## Integration

| Plugin | Enhancement |
|--------|-------------|
| wicked-garden:data:analyze | Use for SQL-based profiling of large files via DuckDB |
| Native tasks | Document quality issues via TaskCreate with `metadata.event_type="task"` |
| wicked-garden:mem | Store quality patterns across sessions |

## Large Files

For files >1GB, use wicked-garden:data:analyze for efficient SQL-based profiling:

```bash
/wicked-garden:data:analyze large_file.csv
```

## Output Standards

All reports include:
- **Summary**: High-level findings
- **Metrics**: Quantitative measurements
- **Issues**: Prioritized problems
- **Recommendations**: Actionable next steps
- **Confidence**: Assessment reliability

## Reference

For detailed examples and patterns:
- [Examples](refs/examples.md) - Profile output, schema format, quality report
