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

## General engineering checklist

- [ ] Schema-first: define schemas before processing.
- [ ] Fail fast: validate early, fail loudly.
- [ ] Idempotent: pipelines rerunnable without side effects.
- [ ] Observable: emit metrics + logs at every stage.
- [ ] Tested: data quality tests are non-negotiable.
