---
description: Distributed tracing analysis for latency and dependencies
argument-hint: "[service name, trace ID, or 'slow' for latency investigation]"
---

# /wicked-platform:traces

Analyze distributed traces for latency investigation, service dependencies, and bottleneck detection.

## Instructions

### 1. Discover Tracing Sources

Use capability-based discovery:
```
ListMcpResourcesTool

Look for tracing capability:
- Jaeger, Zipkin, Tempo
- Datadog APM, New Relic
- AWS X-Ray, GCP Cloud Trace
```

### 2. Determine Analysis Type

Based on argument:
- **Service name**: Analyze traces for specific service
- **Trace ID**: Deep dive into specific trace
- **"slow"**: Find and analyze slowest requests

### 3. Dispatch to SRE for Trace Analysis

If tracing source available:
```python
Task(
    subagent_type="wicked-platform:sre",
    prompt="""Analyze distributed traces for latency and bottleneck investigation.

Target: {service name, trace ID, or 'slow requests'}
Tracing Source: {discovered tracing integration}

Investigation Checklist:
1. Latency breakdown by span - Where is time spent?
2. Service dependency chain - Request flow through services
3. Bottleneck identification - Slowest operations
4. Error propagation - Failure chain analysis
5. N+1 query patterns - Database query inefficiencies
6. Sequential vs parallel opportunities

Return Format:
- Latency breakdown table (span, duration, % of total)
- Service dependency diagram
- Bottlenecks identified with evidence
- Patterns detected (N+1, slow external calls, etc.)
- Optimization recommendations with expected impact
"""
)
```

### 4. Fallback Analysis

If no tracing available, analyze code:
```bash
# Find service calls
grep -r "fetch\|axios\|http\|grpc" --include="*.{js,ts,py,go}"

# Find database queries
grep -r "query\|select\|insert" --include="*.{js,ts,py}"
```

Infer architecture from code patterns.

### 5. Deliver Trace Report

```markdown
## Trace Analysis

**Target**: {service or trace ID}
**Time Range**: {period analyzed}

### Latency Breakdown
| Span | Duration | % of Total |
|------|----------|------------|
| {span} | {ms} | {%} |

### Service Dependencies
```
user-api → auth-service → database
         → user-cache
         → notification-service
```

### Bottlenecks Identified
1. {bottleneck with evidence}

### Patterns Detected
- N+1 queries: {location}
- Slow external calls: {service}
- Sequential when parallel possible: {location}

### Recommendations
1. {optimization}
```

## Example

```
User: /wicked-platform:traces slow

Claude: I'll analyze slow traces to identify latency issues.

[Discovers Jaeger integration]
[Queries for p99 latency traces]

## Trace Analysis: Slow Requests

**Target**: p99 latency requests (>2s)
**Time Range**: Last 1 hour

### Slowest Trace: abc123
**Total Duration**: 3.2s
**Endpoint**: POST /api/orders

### Latency Breakdown
| Span | Duration | % of Total |
|------|----------|------------|
| order-service | 3200ms | 100% |
| └─ validate-cart | 45ms | 1.4% |
| └─ check-inventory | 2800ms | 87.5% |
| │  └─ db-query (x12) | 230ms each | - |
| └─ create-order | 320ms | 10% |

### Bottleneck Identified

**N+1 Query Pattern** in inventory check:
- 12 sequential DB queries (1 per cart item)
- Each query: ~230ms
- Total: 2.8s (87% of request time)

**Location**: `src/services/inventory.ts:45`
```typescript
// Current: N+1 queries
for (const item of cart.items) {
  const stock = await db.query('SELECT * FROM inventory WHERE sku = ?', [item.sku]);
}
```

### Recommendation

Batch the inventory query:
```typescript
// Fixed: Single query
const skus = cart.items.map(i => i.sku);
const stocks = await db.query('SELECT * FROM inventory WHERE sku IN (?)', [skus]);
```

**Expected improvement**: 3.2s → 450ms (85% reduction)
```
