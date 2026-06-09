# Distributed Trace Analysis Rubric

Analyze distributed traces for latency, bottleneck detection, and service dependencies.

## Step 1: Discover Tracing Sources

Use `ListMcpResourcesTool` and scan for tracing capability:
- Jaeger, Zipkin, Tempo
- Datadog APM, New Relic
- AWS X-Ray, GCP Cloud Trace
- OpenTelemetry Collector

## Step 2: Determine Analysis Type

Based on argument:
- **Service name**: Analyze traces for a specific service
- **Trace ID**: Deep dive into a single trace
- **"slow"**: Find and analyze the slowest p99 requests

## Step 3: Investigation Checklist

For each target trace or service:
- [ ] Latency breakdown by span — where is time spent?
- [ ] Service dependency chain — request flow through all services
- [ ] Bottleneck identification — slowest spans as % of total
- [ ] Error propagation — failure chain analysis
- [ ] N+1 query patterns — repeated DB queries per loop iteration
- [ ] Sequential vs parallel opportunities — spans that could run concurrently

## Step 4: Fallback (No Tracing Available)

Infer architecture from code patterns:
```bash
# Find service calls
grep -r "fetch\|axios\|http\|grpc\|requests\." --include="*.{js,ts,py,go}" -l

# Find database queries
grep -r "query\|select\|insert\|db\." --include="*.{js,ts,py,go}" -l
```

Report inferred dependency graph and flag where tracing instrumentation is missing.

## Output Format

```markdown
## Trace Analysis

**Target**: {service name | trace ID | "slow requests"}
**Time Range**: {period}
**Source**: {tracing backend | "code inference (no tracing found)"}

### Latency Breakdown
| Span | Duration | % of Total |
|------|----------|------------|
| {service} | {ms} | {%} |
| └─ {child-span} | {ms} | {%} |

### Service Dependencies
```
{ascii dependency diagram}
service-a → service-b → db
          → cache
```

### Bottlenecks Identified
1. **{span name}** — {duration} ({%} of total)
   - Evidence: {trace ID or pattern}
   - Fix: {recommendation}

### Patterns Detected
- **N+1 queries**: {location — e.g., `src/inventory.ts:45`, 12 sequential queries}
- **Slow external calls**: {service name, avg latency}
- **Sequential when parallel possible**: {location}
- **Missing instrumentation**: {service boundaries not traced}

### Optimization Recommendations
| Issue | Expected Improvement | Effort |
|-------|---------------------|--------|
| {issue} | {reduction} | Low/Med/High |

1. {highest-impact fix with before/after code if applicable}
```

## Common Patterns

### N+1 Query
**Symptom**: Many short repeated spans (same query, N iterations).
**Fix**: Batch the query — `WHERE id IN (?)` instead of loop.
**Expected**: Often 80-90% latency reduction on the affected span.

### Synchronous Fan-out
**Symptom**: Several external calls sequential that could be parallel.
**Fix**: `Promise.all()` / `asyncio.gather()` / goroutines.

### Missing Circuit Breaker
**Symptom**: One downstream timeout causes caller to also timeout.
**Fix**: Add circuit breaker (Resilience4j, Hystrix, custom) with fallback.

### Cold-Start Penalty
**Symptom**: First request to a service much slower than subsequent.
**Fix**: Warm-up endpoints, connection pool pre-warming, lazy init moved to startup.
