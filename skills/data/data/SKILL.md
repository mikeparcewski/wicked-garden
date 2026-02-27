---
name: data
description: |
  Core data engineering capabilities: dataset profiling, schema validation, and data quality assessment.
  Use when analyzing datasets, validating schemas, or assessing data quality.

  Use when:
  - "profile this dataset"
  - "validate schema"
  - "check data quality"
  - "what's in this CSV/Excel file"
  - "analyze this data"
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
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/data_profiler.py" \
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
| wicked-garden:data:numbers | Use for SQL-based profiling of large files |
| wicked-cache | Cache profiling results for repeat analysis |
| wicked-kanban | Document quality issues as tasks |
| wicked-mem | Store quality patterns across sessions |

## Large Files

For files >1GB, use wicked-garden:data:numbers for efficient SQL-based profiling:

```bash
/wicked-garden:data:numbers large_file.csv
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
