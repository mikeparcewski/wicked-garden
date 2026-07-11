# Data Pipeline Rubric — design / review

Apply this inline for ETL/streaming pipeline architecture.
Caller has pre-captured source / target / frequency (for design) or read pipeline
files at `<path>` (for review).

## design

Cover architecture pattern, orchestrator, stage flow, quality gates, monitoring, costs, risks.

```markdown
## Pipeline Design: {name}

### Architecture
- **Pattern**: {Batch|Streaming|Hybrid}
- **Orchestration**: {Airflow|Dagster|Prefect|Other}
- **Storage**: {Data Lake|Warehouse|Lakehouse}

### Data Flow
1. **Source**: {description — type, API/DB/file, credentials approach}
2. **Extract**: {method and frequency}
3. **Transform**: {key transformations}
4. **Load**: {destination and format}

### Quality Gates
- **Source validation**: {checks before processing}
- **Transform validation**: {checks mid-pipeline}
- **Load validation**: {row counts, key checks post-load}

### Performance
- **Expected volume**: {records/day}
- **Processing time estimate**: {duration}
- **Cost estimate**: {$/month}

### Risk Assessment
| Level | Risk | Mitigation |
|-------|------|------------|
| HIGH  | {critical risk} | {mitigation} |
| MED   | {moderate risk} | {mitigation} |

### Design Checklist
- [ ] Data sources identified and accessible
- [ ] Schema evolution strategy defined
- [ ] Error handling and retry logic designed
- [ ] Idempotency and reprocessing supported
- [ ] Monitoring and alerting plan
- [ ] Data quality checks embedded
- [ ] Cost estimation completed

**Confidence**: {HIGH|MEDIUM|LOW}
```

## review

Cover code quality, idempotency, monitoring, validation, silent-loss risk.
Emit P1/P2/P3 findings with code fixes.

```markdown
## Pipeline Review: {path}

**Architecture**: {summary — pattern, orchestrator, storage}
**Quality Score**: {score}/100

### Findings
| Priority | Finding | Impact | Effort | Fix |
|----------|---------|--------|--------|-----|
| P1 | {critical} | HIGH | {S/M/L} | {code snippet} |
| P2 | {moderate} | MED  | {S/M/L} | {code snippet} |
| P3 | {minor}    | LOW  | {S/M/L} | {note} |

### Review Checklist
- [ ] Error handling: failures managed and surfaced
- [ ] Schema versioned and enforced
- [ ] Monitoring: what metrics are tracked
- [ ] Testing: data quality tests present
- [ ] Idempotent: safe to reprocess without duplication
- [ ] Silent-loss risk: no data drops without alert
- [ ] Documentation: pipeline well-documented

### Recommendations
1. {Action with rationale and expected outcome}

**Confidence**: {HIGH|MEDIUM|LOW}
```

## Pattern selection

### Batch ETL
**Use when**: regular scheduled loads, historical processing.
**Pattern**: Extract → Transform → Validate → Load.
**Tools**: Airflow, Dagster, Prefect.

### Streaming pipeline
**Use when**: real-time processing, event-driven.
**Pattern**: Consume → Transform → Sink.
**Tools**: Kafka, Flink, Spark Streaming.

### Incremental processing
**Use when**: large datasets, only processing changes.
**Pattern**: watermark tracking + merge/upsert.

## Common issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Fails halfway | Partial data, inconsistent state | Staging + commit pattern |
| Duplicates | Same data loaded multiple times | Watermarks + idempotency |
| Slow processing | Misses SLA | Profile and optimize bottlenecks |

## External integration discovery

Pipeline engineering can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Warehouses** | `snowflake`, `databricks`, `bigquery` | Query execution, schema access |
| **ETL** | `airbyte`, `fivetran`, `dbt` | Pipeline status, model metadata |
| **Observability** | `monte-carlo`, `datadog` | Data quality metrics |

Discover available integrations via capability detection. Fall back to the
`analyze` sub-action of the wicked-garden-data skill for local file analysis
via DuckDB.

## Integration

- **wicked-brain:search**: find pipeline code with `wicked-brain:search "dag|pipeline"` (FTS5 over indexed code).
- **Native tasks**: track pipeline issues via TaskCreate with `metadata.event_type="task"`.
- **wicked-brain:memory**: recall pipeline patterns.

## Engineering standards (apply to both)

- **Schema-first**: always define schemas before processing.
- **Fail fast**: validate early, fail loudly.
- **Idempotent**: pipelines rerunnable.
- **Observable**: emit metrics + logs at every stage.
- **Tested**: data quality tests are non-negotiable — unit test transforms,
  integration test the full pipeline, test error scenarios.
- **Documented**: clear lineage, versioned schemas, operations runbook.

## Detailed templates

See [pipeline-templates.md](pipeline-templates.md) for the full design
document (ASCII architecture diagram, error-handling matrix, monitoring
thresholds, backfill/recovery procedures, dependencies, deployment) and the
scored pipeline review report.
