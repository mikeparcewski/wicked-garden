---
name: pipeline
description: |
  Data pipeline design and review: ETL patterns, orchestration, performance optimization.
  Use when designing new pipelines or reviewing existing data workflows.

  Use when:
  - "design a data pipeline"
  - "review this ETL"
  - "optimize data processing"
  - "how should I orchestrate this"
  - "pipeline architecture"
---

# Pipeline Engineering Skill

Design, review, and optimize data pipelines and ETL workflows.

## Quick Start

### Design a Pipeline

```bash
/wicked-data:pipeline design \
  --source "postgres://sales_db" \
  --target "s3://data-lake/sales" \
  --frequency daily
```

Generates: Architecture diagram, ETL logic, orchestration config, monitoring plan.

### Review Existing Pipeline

```bash
/wicked-data:pipeline review path/to/pipeline/
```

Analyzes: Code quality, error handling, performance, maintainability.

## Pipeline Patterns

### Batch ETL
**Use when**: Regular scheduled loads, historical processing
**Pattern**: Extract → Transform → Validate → Load
**Tools**: Airflow, Dagster, Prefect

### Streaming Pipeline
**Use when**: Real-time processing, event-driven
**Pattern**: Consume → Transform → Sink
**Tools**: Kafka, Flink, Spark Streaming

### Incremental Processing
**Use when**: Large datasets, only processing changes
**Pattern**: Watermark tracking + Merge/Upsert

## Pipeline Design Checklist

### Architecture
- [ ] Source systems identified and accessible
- [ ] Data volume estimated (GB/day)
- [ ] Latency requirements clear
- [ ] Target schema defined
- [ ] Orchestration tool selected

### Data Quality
- [ ] Schema validation at source
- [ ] Null handling strategy
- [ ] Duplicate detection
- [ ] Business rule validation

### Error Handling
- [ ] Transient errors: retry with backoff
- [ ] Fatal errors: alert and stop
- [ ] Invalid records: log separately
- [ ] Rollback/recovery strategy

### Performance
- [ ] Parallelization strategy
- [ ] Batch size optimized
- [ ] Bottlenecks identified
- [ ] Scaling plan documented

### Monitoring
- [ ] Row counts logged
- [ ] Processing duration tracked
- [ ] Error rates monitored
- [ ] Data freshness SLA defined

### Operations
- [ ] Backfill procedure documented
- [ ] Replay capability implemented
- [ ] Config externalized
- [ ] Secrets managed securely

## Common Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Fails halfway | Partial data, inconsistent state | Staging + commit pattern |
| Duplicates | Same data loaded multiple times | Watermarks + idempotency |
| Slow processing | Misses SLA | Profile and optimize bottlenecks |

## Integration

- **wicked-search**: Find pipeline code with `/wicked-search:code "dag|pipeline"`
- **wicked-kanban**: Track pipeline issues as tasks
- **wicked-mem**: Recall pipeline patterns

## Best Practices

- **Idempotency**: Same input → same output, pipelines safely rerunnable
- **Observability**: Log row counts, track duration, emit metrics, alert on anomalies
- **Testing**: Unit test transforms, integration test full pipeline, test error scenarios
- **Documentation**: Clear lineage, versioned schemas, operations runbook

## External Integration Discovery

Pipeline engineering can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Warehouses** | `snowflake`, `databricks`, `bigquery` | Query execution, schema access |
| **ETL** | `airbyte`, `fivetran`, `dbt` | Pipeline status, model metadata |
| **Observability** | `monte-carlo`, `datadog` | Data quality metrics |

Run `ListMcpResourcesTool` to discover available integrations. Fall back to wicked-data:numbers for local file analysis.

## Reference

For detailed patterns:
- [Output Templates](refs/templates.md) - Design doc, review report templates
