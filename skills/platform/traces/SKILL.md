---
name: traces
description: |
  Distributed tracing analysis for performance investigation and service dependency
  mapping. Analyze latency breakdowns, identify bottlenecks, map service calls,
  and correlate slow requests with code changes.
triggers:
  - trace analysis
  - distributed tracing
  - latency investigation
  - performance tracing
  - slow requests
  - service dependencies
---

# Distributed Tracing Analysis Skill

Analyze distributed traces for performance investigation and service dependency mapping.

## When to Use

- Latency investigation
- Performance bottleneck detection
- Service dependency mapping
- Slow request analysis
- Cross-service debugging
- User asks "traces", "latency", "slow", "performance"

## Tracing Analysis Approach

### 1. Discover Tracing Sources

Use capability-based discovery:

```bash
# List available MCP servers
ListMcpResourcesTool

# Scan for tracing capabilities by analyzing server descriptions:
# - tracing capability: Dedicated distributed tracing systems
# - apm capability: APM tools that include distributed tracing
# - telemetry capability: Unified observability with tracing support
```

### 2. Query Trace Data

For each discovered source:
- Slow traces (>SLO threshold)
- Error traces
- Service operation latencies
- Request volume by endpoint
- Service-to-service call patterns

### 3. Analyze Latency Breakdown

For slow traces:
- Total request duration
- Time spent in each service
- Database query time
- External API call time
- Queue/async processing time
- Network/serialization overhead

### 4. Map Service Dependencies

Build dependency graph:
- Service call chains
- Synchronous vs asynchronous calls
- Fan-out patterns
- Critical path services

### 5. Identify Bottlenecks

See refs/bottlenecks.md for detailed patterns.

Common bottleneck types:
- **N+1 query patterns**: Many sequential DB calls
- **Slow external calls**: Third-party API latency
- **Database bottlenecks**: Long query times
- **Sequential processing**: Parallelizable operations
- **Resource contention**: Lock waits, queue depth

### 6. Correlate with Code

Use wicked-search to find:
- Database queries in slow services
- External API calls
- Synchronous operations that could be async
- Missing caching opportunities

## Integration Discovery

| Capability | What to Look For | Provides |
|------------|------------------|----------|
| **tracing** | Distributed tracing, span collection, trace analysis | Distributed traces, span details |
| **apm** | Performance monitoring with distributed tracing | Traces with performance context |
| **telemetry** | Unified observability with traces and metrics | Unified traces and metrics |

**Fallback**: Analyze code for call patterns via wicked-search (database calls, HTTP clients, async operations).

## Output Format

Provide trace analysis with:
- Performance summary (slow traces, latency percentiles)
- Service dependency map (tree view with timing)
- Bottleneck analysis (latency, type, root cause)
- Optimization opportunities (quick wins vs long-term)

See refs/bottlenecks.md for detailed output templates.

## Common Performance Patterns

See refs/bottlenecks.md for detailed analysis of:

### N+1 Query Pattern
Sequential database queries in a loop. Fix with batch queries or JOIN.

### Synchronous External Calls
Waiting for external APIs sequentially. Fix with Promise.all or async processing.

### Missing Caching
Repeated identical queries. Fix with caching layer (Redis, in-memory).

### Database Query Inefficiency
Slow database operations. Fix with indexes, query optimization, pagination.

### Resource Contention
Lock waits or queue delays. Fix with reduced lock scope, optimistic locking.

## Service Dependency Analysis

### Critical Path Detection
Identify services on critical path (required for request completion). Focus optimization here.

### Fan-Out Pattern Detection
Single request triggers many downstream calls. Risk of amplified load and cascading failures.

### Circular Dependency Detection
Service A calls B calls A (cycle). Risk of infinite loops and complex debugging.

See refs/dependencies.md for detailed dependency analysis patterns.

## Integration with wicked-engineering

When bottlenecks identified, engage wicked-garden:engineering:backend with trace context, code locations, and optimization recommendations.

## Integration with wicked-crew

During build phase:
1. Capture baseline latency metrics
2. Monitor post-deployment latency
3. Alert on p95 increases >20%
4. Recommend rollback if critical path slows

Emit events:
- `observe:trace:slow:warning`
- `observe:correlation:found:success`

## Notes

- Focus on p95/p99, not averages (outliers matter)
- Identify critical path first (highest impact)
- Consider parallelization opportunities
- External calls often biggest bottleneck
- Add instrumentation if spans missing
- Correlate slow traces with error traces
