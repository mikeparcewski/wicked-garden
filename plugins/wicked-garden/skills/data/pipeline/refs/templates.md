# Pipeline Output Templates

Standard templates for pipeline design and review documentation.

## Pipeline Design Document

```markdown
## Pipeline Design: {name}

**Author**: {name}
**Date**: {date}
**Status**: {draft/review/approved}

### Requirements
- **Source**: {system/database/API}
- **Target**: {destination system}
- **Frequency**: {hourly/daily/streaming}
- **Latency SLA**: {max delay from source}
- **Volume**: {GB/day or events/sec}
- **Retention**: {how long to keep data}

### Architecture

```
┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐
│  Source  │───►│  Extract  │───►│ Transform │───►│  Target  │
└──────────┘    └───────────┘    └───────────┘    └──────────┘
                     │                 │
                     ▼                 ▼
              ┌───────────┐    ┌───────────┐
              │  Staging  │    │  Errors   │
              └───────────┘    └───────────┘
```

### Data Flow

#### 1. Extract
- **Method**: {full/incremental/CDC}
- **Source format**: {JSON/CSV/SQL}
- **Volume**: {rows/day}
- **Watermark**: {how to track progress}

#### 2. Transform
| Step | Operation | Input | Output |
|------|-----------|-------|--------|
| 1 | Parse | raw JSON | typed records |
| 2 | Validate | typed records | valid records + errors |
| 3 | Enrich | valid records | enriched records |
| 4 | Aggregate | enriched records | summary tables |

#### 3. Validate
- [ ] Schema validation
- [ ] Business rule validation
- [ ] Referential integrity
- [ ] Data quality checks

#### 4. Load
- **Pattern**: {append/merge/replace}
- **Partitioning**: {by date/region/etc}
- **Indexing**: {primary key, indexes}

### Error Handling

| Error Type | Detection | Response | Recovery |
|------------|-----------|----------|----------|
| Network | Connection timeout | Retry 3x | Alert if persists |
| Data format | Schema validation | Log + skip | Manual review |
| Business rule | Validation check | Dead letter queue | Reprocess |
| System | Exception | Alert + stop | Manual restart |

### Monitoring

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Row count | ±5% of avg | >10% deviation |
| Duration | <2 hours | >3 hours |
| Error rate | <0.1% | >1% |
| Freshness | <4 hours | >6 hours |

### Operations

#### Backfill Procedure
1. Set date range parameters
2. Run in staging mode first
3. Validate results
4. Run production load

#### Recovery Procedure
1. Check error logs
2. Fix root cause
3. Replay from last checkpoint
4. Verify data consistency

### Dependencies
| Dependency | Type | Owner | SLA |
|------------|------|-------|-----|
| {system} | upstream | {team} | {SLA} |

### Deployment
- **Orchestration**: {Airflow/Dagster/Prefect}
- **Schedule**: {cron expression}
- **Resources**: {CPU/memory/storage}
- **Environments**: {dev/staging/prod}
```

## Pipeline Review Report

```markdown
## Pipeline Review: {name}

**Reviewed**: {date}
**Reviewer**: {name}

### Summary
{2-3 sentence assessment of pipeline quality and readiness}

### Findings

#### Critical (Must Fix)
| # | Finding | Risk | Recommendation |
|---|---------|------|----------------|
| 1 | {issue} | Data loss | {action} |

#### High (Should Fix)
| # | Finding | Risk | Recommendation |
|---|---------|------|----------------|
| 1 | {issue} | Performance | {action} |

#### Medium (Consider)
| # | Finding | Risk | Recommendation |
|---|---------|------|----------------|
| 1 | {issue} | Maintenance | {action} |

### Code Quality Assessment

| Category | Score | Notes |
|----------|-------|-------|
| Structure | {1-10} | {comments} |
| Error Handling | {1-10} | {comments} |
| Testing | {1-10} | {comments} |
| Documentation | {1-10} | {comments} |
| Maintainability | {1-10} | {comments} |

**Overall**: {score}/50

### Performance Assessment

- **Current load**: {X rows in Y time}
- **Bottleneck**: {identified}
- **10x projection**: {will it scale?}
- **Recommendations**: {optimizations}

### Operational Readiness

- [ ] Monitoring configured
- [ ] Alerting configured
- [ ] Runbook documented
- [ ] Backfill tested
- [ ] Recovery tested
- [ ] On-call rotation assigned

### Verdict

**Status**: [PRODUCTION READY | NEEDS WORK | MAJOR REFACTOR]

**Blocking Issues**: {count}
**Required Actions Before Deploy**:
1. {action}

**Sign-off**: {name, date}
```
