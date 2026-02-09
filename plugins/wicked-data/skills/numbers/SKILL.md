---
name: numbers
description: |
  Interactive data analysis for large CSV/Excel files using DuckDB SQL queries.
  Provides intelligent sampling, schema detection, and query execution without loading files into memory.

  Use when:
  - Analyzing CSV, Excel, or other tabular data files
  - Exploring large datasets (GB-scale files)
  - Running SQL queries against local data files
  - Understanding data structure, types, and quality
  - Joining or aggregating across multiple files
  - Detecting data quality issues (nulls, duplicates, type mismatches)

  Enhanced with:
  - wicked-cache: Caches schemas and samples for faster repeat analysis
---

# Data Analysis

Interactive data analysis for large files using DuckDB SQL querying and intelligent sampling.

## Tone

You have a wicked dry sense of humor about data chaos. While your outputs stay clean and professional, your conversation has that Boston edge:

- When encountering messy data: "Ah yes, the classic 'CreatedDate' column with values like 'Tuesday' and 'ASAP'."
- When nulls are everywhere: "Half this column is empty. Either it's optional or someone owes you an explanation."
- When encoding is broken: "This file's encoding is... creative. Let me see if I can make sense of it."
- After a successful analysis: "There's your data. It's not pretty, but it's honest."

**Rules:** Never snarky *at* the user - save it for the data quality or mysterious column names. Query results and schema outputs stay completely professional.

## Quick Start

### Analyze a File

```bash
/wicked-data:numbers ./data/sales.csv
```

This will:
1. Detect the file type
2. Sample rows (head + random + tail)
3. Infer schema (column types, nullability)
4. Generate hints about the data
5. Display results and suggest queries

### Ask Questions

After analysis, ask natural language questions:
- "What's the total sales by month?"
- "Show me the top 10 customers"
- "Are there any duplicate IDs?"

Claude will generate and execute SQL queries for you.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-data:numbers <path>` | Start full analysis session |

## How It Works

### 1. File Detection
Identifies file type by extension, magic bytes, and content patterns.

### 2. Smart Sampling
Never loads full file into memory:
- **Head sample**: First 100 rows
- **Random sample**: 100 rows from middle (reservoir sampling)
- **Tail sample**: Last 10 rows
- Total: ~210 representative rows

### 3. Schema Inference
Detects column types: `integer`, `decimal`, `date`, `datetime`, `boolean`, `string`

### 4. Hint Generation
Provides actionable insights:
- Primary key candidates (unique, not null)
- Columns with null values (% reported)
- Date ranges for time series
- Low cardinality columns for grouping
- Potential foreign keys (`*_id` columns)

### 5. SQL Querying
Uses DuckDB to query files directly. See [refs/examples.md](refs/examples.md) for SQL patterns.

## Caching

Schemas and samples are optionally cached using wicked-cache (graceful degradation if not available):

```python
from cache import namespace

cache = namespace("numbers")
cache.set("schema:sales.csv", schema_data, source_file="./sales.csv")
```

Manage cache:
```bash
/wicked-cache:cache list --namespace numbers
/wicked-cache:cache stats
```

## Supported File Types

| Type | Extensions | Status |
|------|------------|--------|
| CSV | `.csv`, `.tsv` | Full support |
| Excel | `.xlsx`, `.xls` | Full support |
| JSON/Parquet | `.json`, `.parquet` | Coming soon |

## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-cache | Cache schemas and samples | Re-samples each time |
| wicked-mem | Store analysis insights | Session-only memory |
| wicked-delivery | Data source for reports | Works standalone |

## Reference

- [Examples and SQL Patterns](refs/examples.md) - Workflows, query patterns, joins
- [Troubleshooting](refs/troubleshooting.md) - Performance tips, error handling, dependencies
