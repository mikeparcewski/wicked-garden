---
description: |
  Use when profiling a dataset's structure, validating it against a schema, or generating a data quality
  report (completeness, uniqueness, validity). NOT for interactive SQL queries (use data:analyze)
  or ML pipeline work (use data:ml).
argument-hint: "<subcommand> [args...] — profile <path> | validate --schema <schema> --data <path> | quality <path>"
---

# /wicked-garden:data:data

Core data engineering operations: profiling, schema validation, and quality assessment.

## Instructions

### 1. Parse Arguments

Extract the subcommand and its arguments:
- `profile <path>` — Profile a dataset (types, nulls, cardinality, statistics)
- `validate --schema <schema-path> --data <data-path>` — Validate data against a schema
- `quality <path>` — Generate a quality report (completeness, uniqueness, validity, consistency)

If no subcommand is given, show usage and exit.

### 2. Read the Data

Read the target file to understand its structure:
- Column names and types
- Row count and sample rows (head + tail)
- Null/missing value patterns

### 3. Dispatch to Data Engineer

```
Task(
  subagent_type="wicked-garden:data:data-engineer",
  prompt="""
  Perform data {subcommand} on the provided dataset.

  Subcommand: {subcommand}
  File: {path}
  {Schema: {schema-path} (if validate)}
  Data profile: {column names, types, row count, sample}

  For 'profile':
  1. Infer column types and nullability
  2. Calculate cardinality (distinct values per column)
  3. Generate statistics for numeric columns (min, max, mean, std, percentiles)
  4. Identify primary key candidates
  5. Detect data quality signals (null rates, duplicates)

  For 'validate':
  1. Load the schema definition
  2. Check each column against schema constraints
  3. Report violations by row with severity
  4. Summarize pass/fail per constraint type

  For 'quality':
  1. Assess completeness (null rates per column)
  2. Assess uniqueness (duplicate detection)
  3. Assess validity (type conformance, constraint checks)
  4. Assess consistency (cross-field rules, case consistency)
  5. Calculate an overall quality score
  6. Prioritize issues (P1/P2/P3)
  7. Provide remediation recommendations

  Return structured markdown with tables and actionable findings.
  """
)
```

### 4. Present Results

Display the agent's findings with a summary header:

```markdown
## Data {Subcommand}: {path}

{agent findings}
```
