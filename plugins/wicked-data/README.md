# wicked-data

Data engineering specialists with DuckDB-powered analysis -- run SQL queries on 10GB+ CSV and Excel files with zero database setup. Ask questions in plain English, get SQL plus results with memory-efficient streaming that never chokes on large files.

Beyond ad-hoc queries, wicked-data brings ML pipeline guidance, analytics architecture review, and ETL design into one plugin. Your entire data workflow gets expert-level support from exploration to production.

## Quick Start

```bash
# Install
claude plugin install wicked-data@wicked-garden

# Analyze a CSV file
/wicked-data:analyze sales.csv

# Then ask questions in plain English:
# "What's the total revenue by month?"
# "Show me the top 10 customers"
# "Are there any duplicate order IDs?"
```

That's it. Claude generates SQL, DuckDB executes it, you get answers.

## Commands & Skills

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-data:analyze` | Interactive analysis session for CSV/Excel | `/wicked-data:analyze sales.csv` |
| `/wicked-data:numbers` | DuckDB SQL queries on large files | `/wicked-data:numbers transactions.csv` |
| `/wicked-data:data` | Schema validation and data profiling | `/wicked-data:data profile users.csv` |
| `/wicked-data:pipeline` | ETL pipeline design and review | `/wicked-data:pipeline review pipelines/etl/` |
| `/wicked-data:analysis` | Statistical insights and pattern finding | `/wicked-data:analysis explore sales.csv` |
| `/wicked-data:ml` | ML model guidance and architecture review | `/wicked-data:ml review models/churn/` |

## When to Use What

| Need | Use This |
|------|----------|
| Quick CSV/Excel exploration | `/wicked-data:analyze` |
| SQL queries on large files | `/wicked-data:numbers` |
| Validate data against a schema | `/wicked-data:data` |
| Review or design ETL pipelines | `/wicked-data:pipeline` |
| Find patterns and insights | `/wicked-data:analysis` |
| Review ML model architecture | `/wicked-data:ml` |

## Key Features

- **No database setup**: Query CSV/Excel files directly with SQL via DuckDB
- **Memory efficient**: Streams results without loading full files (10GB+ supported)
- **Natural language**: Ask questions, get SQL queries and results
- **Auto schema detection**: Infers types, nullability, patterns
- **Multi-file joins**: Reference multiple files in one query

## Workflows

### Quick CSV Analysis

```bash
# 1. Start analysis
/wicked-data:analyze sales_2024.csv

# 2. Ask questions
"What's the total revenue by month?"
"Show me the top 5 products by sales"
"Are there any null email addresses?"
```

### Data Pipeline Review

```bash
# Review existing pipeline code
/wicked-data:pipeline review pipelines/sales_etl/
```

### ML Model Review

```bash
# Review model architecture and deployment readiness
/wicked-data:ml review models/churn_predictor/
```

## Agents

| Agent | Focus |
|-------|-------|
| `data-engineer` | ETL pipelines, data quality, schema design |
| `data-analyst` | Exploration, statistical analysis, insights |
| `ml-engineer` | Model development, training pipelines, deployment |
| `analytics-architect` | Data warehouse design, modeling, governance |

## Prerequisites

```bash
pip install duckdb openpyxl chardet
```

Data profiling scripts use Python stdlib only - no external packages needed.

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-cache | Faster repeated queries via cached schemas | Re-analyzes each time |
| wicked-crew | Auto-engaged during design/build phases | Use commands directly |
| wicked-search | Find existing pipeline code and schemas | Manual discovery |
| wicked-mem | Store data patterns and architecture decisions | Session-only context |

## License

MIT
