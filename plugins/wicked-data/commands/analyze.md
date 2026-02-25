---
description: Start interactive data analysis session for CSV/Excel files
argument-hint: <file-path> [--focus <type>] [--context <file>] [--refresh] [--scenarios]
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

### 5. Optional: Generate Wicked-Scenarios Format

When `--scenarios` is passed, generate wicked-scenarios format test scenarios for data validation based on the analysis findings.

**Analysis type → scenario mapping:**

| Analysis Focus | Scenario Category | Tools | What to Test |
|---------------|-------------------|-------|-------------|
| Quality issues (nulls, duplicates, format violations) | api | curl, hurl | API input validation, constraint enforcement |
| Schema validation (type mismatches, constraint violations) | api | curl | Schema contract verification |
| Pipeline readiness (ETL failures, transformation edge cases) | api | curl | Pipeline endpoint error handling |
| Performance (slow queries, large payload handling) | perf | k6, hey | Load testing, response time thresholds |

For each significant quality finding, produce a wicked-scenarios block:

````markdown
---
name: {dataset-kebab}-data-validation
description: "Data validation scenarios from analysis of {file-path}"
category: api
tools:
  required: [curl]
  optional: [hurl]
difficulty: intermediate
timeout: 60
---

## Steps

### Step 1: {Quality finding} - null handling ({tool})

```bash
# Test API handles missing/null values correctly
curl -sf -X POST http://localhost:${PORT}/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"field": null}'
```

**Expect**: Appropriate error response (400) or graceful handling

### Step 2: {Schema finding} - type validation ({tool})

```bash
# Test API rejects invalid types
curl -sf -X POST http://localhost:${PORT}/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"numeric_field": "not-a-number"}'
```

**Expect**: 400 with validation error message
````

**Quality issue → CLI test patterns:**
- **Null/missing values** → `curl` POST with null fields, verify rejection or default handling
- **Duplicate detection** → `curl` POST with duplicate records, verify dedup or conflict response
- **Format violations** → `curl` with malformed dates, emails, etc., verify validation
- **Boundary values** → `curl` with min/max values, verify range enforcement
- **Large payloads** → generate a separate `perf` category scenario using `k6` for load testing
- **ETL failure modes** → `curl` with partial/malformed data, verify pipeline resilience
