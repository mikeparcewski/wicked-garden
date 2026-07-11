# Data Engineering Rubric — profile / validate / quality

Apply this inline for schema-level checks. Caller has pre-read the data file
head/tail and captured columns / types / nulls.

## profile

Emit a structured profile with shape, per-column stats, and prioritized findings.

```markdown
## Data Profile: {name}

**Rows**: {count}  **Columns**: {count}  **File**: {path}

### Column Summary
| Column | Type | Null% | Unique | Min | Max | Sample |
|--------|------|-------|--------|-----|-----|--------|

### Key Observations
1. {High null-rate columns}
2. {Type anomalies or mixed types}
3. {Skew / outlier signals}

### Recommendations
1. {Prioritized action — e.g. handle nulls in col X}

**Confidence**: {HIGH|MEDIUM|LOW}
```

## validate

Compare actual data against the provided schema. Report breaking vs non-breaking drift.

```markdown
## Schema Validation: {name}

**Schema**: {schema-path}  **Data**: {data-path}

### Result: {PASS|FAIL}

### Breaking Issues (must fix)
| Column | Expected | Actual | Impact |
|--------|----------|--------|--------|

### Warnings (non-breaking)
| Column | Note |
|--------|------|

### Recommendations
1. {Fix breaking issues first}

**Confidence**: {HIGH|MEDIUM|LOW}
```

Schema design principles to apply:
- Explicit types (avoid variant unless necessary).
- Clear nullability contracts.
- Consistent naming conventions.
- Version schemas explicitly.
- Document breaking vs non-breaking changes.

## quality

Five-dimension quality assessment: Completeness, Uniqueness, Validity, Consistency, Timeliness.

```markdown
## Data Quality Report

**Dataset**: {name}  **Rows**: {count}  **Columns**: {count}

### Quality Metrics
| Dimension    | Score | Issues |
|--------------|-------|--------|
| Completeness | {%}   | {null columns} |
| Uniqueness   | {%}   | {duplicate rate} |
| Validity     | {%}   | {constraint violations} |
| Consistency  | {%}   | {cross-field failures} |
| Timeliness   | {age} | {freshness status} |

### Critical Issues
- {Issue with severity and impact}

### Recommendations
1. {Prioritized action items}

**Confidence**: {HIGH|MEDIUM|LOW}
```

## Quality thresholds

| Dimension | Metric | Threshold |
|-----------|--------|-----------|
| Completeness | Null rate | <5% |
| Uniqueness | Duplicate rate | <1% |
| Validity | Type conformance | 100% |
| Consistency | Cross-field rules | 100% |

## Scripted paths (optional)

Profile a dataset with `data_profiler.py`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/data/data_profiler.py" \
  --input data.csv --output profile.json
```

Output includes: row and column counts, inferred column types, null rates per
column, cardinality (distinct values), sample values, and statistical
summaries for numeric columns.

Validate against a schema with `schema_validator.py`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/data/schema_validator.py" \
  --schema schemas/expected.json \
  --data data/actual.csv
```

Schema columns define: **name**, **type** (integer, string, decimal, datetime,
date), **nullable** (true/false), **constraints** (unique, min, max, pattern,
enum). See [data-examples.md](data-examples.md) for the schema format, profile
output, quality-report example, common workflows, and SQL quality queries.

## Large files (>1GB)

Route to the `analyze` sub-action of the wicked-garden-data skill for
efficient SQL-based profiling via DuckDB.

## Integration

- Native tasks: document quality issues via TaskCreate with `metadata.event_type="task"`.
- wicked-brain:memory: store quality patterns across sessions.

## General engineering checklist

- [ ] Schema-first: define schemas before processing.
- [ ] Fail fast: validate early, fail loudly.
- [ ] Idempotent: pipelines rerunnable without side effects.
- [ ] Observable: emit metrics + logs at every stage.
- [ ] Tested: data quality tests are non-negotiable.
