---
description: "Exploratory data analysis and insight generation"
argument-hint: "explore <path> — perform exploratory analysis on a dataset"
---

# /wicked-garden:data:analysis

Explore datasets, identify patterns, and generate actionable business insights.

## Instructions

### 1. Parse Arguments

Extract the subcommand and path:
- `explore <path>` — Run exploratory data analysis on the file

If no subcommand or path is given, show usage and exit.

### 2. Profile the Data

Read the target file to understand its structure:
- Column names and types
- Row count and sample rows
- Key dimensions and metrics
- Date ranges for time series columns

### 3. Dispatch to Data Analyst

```
Task(
  subagent_type="wicked-garden:data:data-analyst",
  prompt="""
  Perform exploratory data analysis on the provided dataset.

  File: {path}
  Data profile: {column names, types, row count, sample rows}

  Analysis workflow:
  1. Identify the grain (one row per what?) and key dimensions
  2. Generate descriptive statistics (distributions, aggregations)
  3. Analyze segments (group by key dimensions, compare metrics)
  4. Discover time patterns (day-of-week, seasonality, trends)
  5. Identify anomalies and concerning patterns
  6. Profile high-value entities (top customers, products, etc.)
  7. Generate business recommendations using the insight framework:
     - Observation: What does the data show?
     - Insight: What does it mean?
     - Action: What should we do?
     - Expected Impact: Quantified estimate
     - Confidence: HIGH / MEDIUM / LOW

  Include SQL queries (DuckDB-compatible) for reproducibility.
  Return structured markdown with tables, insights, and recommendations.
  """
)
```

### 4. Present Results

Display the agent's findings:

```markdown
## Exploratory Analysis: {path}

{agent findings}

### Next Steps
- Ask follow-up questions about specific patterns
- Use `/wicked-garden:data:numbers {path}` for interactive SQL queries
- Use `/wicked-garden:data:analyze {path} --focus quality` for quality assessment
```
