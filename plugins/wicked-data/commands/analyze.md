---
description: Start interactive data analysis session for CSV/Excel files
argument-hint: <file-path> [--focus <type>] [--context <file>] [--refresh]
---

# /wicked-data:analyze

Start an interactive data analysis session on the specified file.

## Instructions

### 1. Parse Arguments

Extract from arguments:
- `file-path` (required): Path to CSV, Excel, or data file
- `--focus` (optional): Analysis type — `stats`, `quality`, `warehouse`, `ml`. If omitted, infer from data context.
- `--context` (optional): Additional context file for domain understanding
- `--refresh` (optional): Force re-read of cached data profile

### 2. Profile the Data

Read the target file to understand its structure:
- Column names and types
- Row count and sample rows
- Null/missing value patterns
- Basic statistics for numeric columns

### 3. Route to Specialist

Based on `--focus` or inferred analysis type, dispatch to the appropriate agent:

**stats/exploration** (default):
```
Task(
  subagent_type="wicked-data:data-analyst",
  prompt="""
  Perform exploratory data analysis on the provided dataset.

  File: {file-path}
  Context: {context file contents or "none"}
  Data profile: {column names, types, row count, sample}

  Analysis steps:
  1. Statistical summary (distributions, correlations, outliers)
  2. Pattern identification (trends, clusters, anomalies)
  3. Visualization recommendations (chart types for key insights)
  4. Key findings and next-step suggestions

  Return structured markdown with tables and visualization guidance.
  """
)
```

**quality/pipelines**:
```
Task(
  subagent_type="wicked-data:data-engineer",
  prompt="""
  Assess data quality and pipeline readiness for the provided dataset.

  File: {file-path}
  Data profile: {column names, types, row count, sample}

  Check for:
  1. Schema validation (types, constraints, nullability)
  2. Data quality issues (duplicates, inconsistencies, format violations)
  3. Pipeline readiness (partitioning candidates, indexing suggestions)
  4. ETL recommendations (transformations needed, staging strategy)

  Return findings organized by severity with specific remediation steps.
  """
)
```

**warehouse**:
```
Task(
  subagent_type="wicked-data:analytics-architect",
  prompt="""
  Design warehouse integration for the provided dataset.

  File: {file-path}
  Data profile: {column names, types, row count, sample}

  Evaluate:
  1. Data modeling (star schema, snowflake, or wide table)
  2. Dimension and fact table identification
  3. Governance recommendations (ownership, access, retention)
  4. Query optimization patterns for analytics workloads

  Return a data model design with DDL sketches and governance notes.
  """
)
```

**ml**:
```
Task(
  subagent_type="wicked-data:ml-engineer",
  prompt="""
  Assess ML readiness and recommend modeling approaches for the provided dataset.

  File: {file-path}
  Data profile: {column names, types, row count, sample}

  Evaluate:
  1. Feature engineering opportunities
  2. Target variable identification and task type (classification, regression, clustering)
  3. Model architecture recommendations
  4. Training pipeline design (splits, validation, monitoring)

  Return structured recommendations with feature importance estimates.
  """
)
```

### 4. Present Results

```markdown
## Data Analysis: {file-path}

### Analysis Type: {stats|quality|warehouse|ml}

### Summary
{agent findings summary}

### Details
{structured findings from agent}

### Recommendations
1. {action item}

### Next Steps
- Run with `--focus {other-type}` for additional perspectives
```
