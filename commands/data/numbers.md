---
description: "Interactive data analysis using DuckDB SQL queries"
argument-hint: "<file-path> — start interactive SQL analysis session"
---

# /wicked-garden:data:numbers

Interactive data analysis for CSV/Excel files using DuckDB SQL queries. Handles large files efficiently without loading into memory.

## Instructions

### 1. Parse Arguments

Extract the file path (required). If no path is given, show usage and exit.

### 2. Detect and Sample the File

Read the target file to understand its structure:
- Detect file type (CSV, TSV, Excel, Parquet, JSON)
- Sample rows: head (first 100), random (middle 100), tail (last 10)
- Infer column types (integer, decimal, date, datetime, boolean, string)
- Calculate null rates per column

### 3. Generate Hints

Provide actionable observations about the data:
- Primary key candidates (unique, not null columns)
- Columns with significant null rates (report %)
- Date ranges for time series columns
- Low cardinality columns (good for GROUP BY)
- Potential foreign keys (*_id columns)
- Numeric column statistics (min, max, mean)

### 4. Dispatch to Data Analyst

```
Task(
  subagent_type="wicked-garden:data:data-analyst",
  prompt="""
  Start an interactive DuckDB SQL analysis session on this file.

  File: {path}
  File type: {detected type}
  Schema: {column names and inferred types}
  Row count: {count}
  Sample data: {head + random + tail samples}
  Hints: {generated hints}

  Present the data profile and hints to the user, then suggest initial queries:
  1. Overview query (row count, date range, key aggregations)
  2. Quality query (null counts, duplicate checks)
  3. Top-N query (most common values in key dimensions)

  Use DuckDB SQL syntax for all queries. Reference the file directly:
    SELECT * FROM '{path}' LIMIT 10

  After presenting initial findings, offer to:
  - Answer specific questions about the data
  - Run custom SQL queries
  - Generate visualisation recommendations
  - Profile specific columns in depth

  Maintain the wicked-garden data analysis tone: dry humor about data chaos,
  professional results. Never snarky at the user — save it for messy data.
  """
)
```

### 5. Interactive Loop

After the initial profile, the user can ask follow-up questions. Each question gets translated to DuckDB SQL and executed. Continue until the user moves on.
