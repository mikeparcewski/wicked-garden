# wicked-data

Query 10GB+ CSV and Excel files with plain-English questions — no database setup, no loading files into memory, just DuckDB-powered SQL with schema detection and specialist data engineers on demand.

## Quick Start

```bash
# Install
claude plugin install wicked-data@wicked-garden

# Start an interactive analysis session
/wicked-data:analyze sales_2024.csv

# Ask in plain English — SQL is generated and executed automatically
# "What's total revenue by month?"
# "Show me the top 10 customers by order count"
# "Are there duplicate order IDs?"
```

## Workflows

### Explore a Large CSV Without Loading It

You have a 4GB transaction file. Instead of loading it into a dataframe or spinning up a database, start an analysis session:

```bash
/wicked-data:analyze transactions_q4.csv
```

The data engineer agent profiles the schema, detects column types, samples rows, and opens an interactive session. Ask questions in natural language:

```
"How many transactions per day over the last 30 days?"
"Which payment methods have the highest failure rate?"
"Find rows where amount is null or negative"
```

DuckDB executes streaming SQL against the file — the full file is never loaded into memory. Results come back in seconds even at scale.

### ETL Pipeline Review

You have an existing pipeline and want an expert review before it goes to production:

```bash
/wicked-data:pipeline review pipelines/sales_etl/
```

The data engineer agent examines your transforms, checks for common anti-patterns (full table scans, missing null handling, unbounded windows), and recommends optimizations with specific code changes.

### Find the Right Ontology for Your Dataset

You're building a data catalog and need to map your schema to a standard:

```bash
/wicked-data:ontology customers.csv
# Output:
# Schema.org: Person, PostalAddress match 8/12 columns
# Industry match: Retail — suggested: GS1, ARTS data model
# Custom recommendation: 4 columns don't map to public ontologies
#   → suggested custom namespace: org.yourco.customer.v1
```

### ML Model Review

Before deploying a churn model to production, run a review:

```bash
/wicked-data:ml review models/churn_predictor/
```

The ML engineer agent checks training pipeline integrity, feature leakage, class imbalance handling, and deployment readiness. Output includes a checklist of blockers and recommendations.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-data:analyze` | Interactive DuckDB analysis session for CSV/Excel | `/wicked-data:analyze sales.csv` |
| `/wicked-data:ontology` | Recommend ontologies based on dataset structure | `/wicked-data:ontology customers.csv` |

## When to Use What

| Need | Use This |
|------|----------|
| Explore or query a CSV/Excel file | `/wicked-data:analyze` |
| Map a dataset to a public ontology | `/wicked-data:ontology` |
| Run SQL against large files directly | `/wicked-data:numbers` skill |
| Validate data quality or schema | `/wicked-data:data` skill |
| Design or review an ETL pipeline | `/wicked-data:pipeline` skill |
| Exploratory analysis and pattern finding | `/wicked-data:analysis` skill |
| ML architecture or pipeline review | `/wicked-data:ml` skill |

## How It Works

The `analyze` command dispatches to a specialist agent based on your `--focus` flag or inferred intent from the data. The agent uses DuckDB to profile the file, generate SQL for your questions, and stream results — the file is never fully loaded. For GB-scale files, this is the difference between waiting 30 seconds and waiting 3 minutes.

## Agents

| Agent | Focus |
|-------|-------|
| `data-engineer` | ETL pipelines, data quality, schema design |
| `data-analyst` | Exploratory analysis, statistical patterns, business insights |
| `ml-engineer` | Model development, training pipelines, deployment readiness |
| `analytics-architect` | Data warehouse design, modeling, governance |

## Skills

| Skill | What It Does |
|-------|-------------|
| `numbers` | DuckDB SQL queries on large files with schema detection |
| `data` | Schema validation and data profiling |
| `pipeline` | ETL pipeline design and review |
| `analysis` | Statistical insights and pattern finding |
| `ml` | ML model guidance and architecture review |

## Prerequisites

```bash
pip install duckdb openpyxl chardet
```

Data profiling scripts use Python stdlib only — no external packages needed.

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged during data-focused phases | Use commands directly |
| wicked-search | Find existing pipeline code and schemas in your codebase | Manual file discovery |
| wicked-mem | Store data architecture decisions across sessions | Decisions lost between sessions |

## License

MIT
