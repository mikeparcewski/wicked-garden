---
name: health
description: |
  System health overview from discovered observability sources. Aggregates errors,
  performance metrics, and SLO status across services. Correlates with deployments
  and code changes. Use for proactive health monitoring and post-deployment validation.
  Use when: system health, health check, deployment health, production status
---

# Health Aggregation Skill

Aggregate system health from discovered observability sources with deployment correlation.

## When to Use

- Overall system health check
- Pre/post deployment validation
- SLO/SLA compliance monitoring
- Capacity assessment
- Proactive issue detection
- User asks "health", "status", "how is production"

## Health Assessment Approach

### 1. Discover Observability Sources

Use capability-based discovery to find available integrations:

```bash
# List all MCP servers
ListMcpResourcesTool

# Scan for capabilities by analyzing server descriptions and resources:
# - error-tracking capability: Exception/error tracking and reporting
# - apm capability: Application performance monitoring and metrics
# - logging capability: Log aggregation, search, and analysis
# - tracing capability: Distributed tracing and service mapping
# - telemetry capability: Metrics collection and custom instrumentation
```

### 2. Aggregate Health Metrics

For each discovered source, collect:
- **Error rates**: Current vs baseline
- **Performance**: Latency (p50, p95, p99)
- **Throughput**: Requests per second
- **SLO status**: Availability, latency, error budgets
- **Alerts**: Active alerts and severity

### 3. Calculate Health Score

**HEALTHY**: All metrics within SLO, no active alerts, stable trends
**DEGRADED**: Some metrics elevated, minor alerts, or negative trends
**CRITICAL**: SLO violations, critical alerts, or severe degradation

### 4. Correlate with Changes

Check for recent changes that might impact health:
- Deployments (via CI/CD integrations or git history)
- Code changes (via wicked-search)
- Infrastructure changes
- Traffic patterns

### 5. Provide Actionable Recommendations

Based on health status:
- Immediate actions for critical issues
- Investigation paths for degradations
- Optimization opportunities
- Capacity planning insights

## Integration Discovery

This skill discovers integrations at runtime based on capability:

| Capability | What to Look For | Provides |
|------------|------------------|----------|
| **error-tracking** | Exception tracking, error reporting, crash analytics | Error rates, stack traces, user impact |
| **apm** | Performance monitoring, service metrics, observability | Latency, throughput, service health |
| **logging** | Log aggregation, log search, log analysis | Log aggregation, search, patterns |
| **tracing** | Distributed tracing, request tracing, trace analysis | Distributed traces, dependencies |
| **telemetry** | Metrics collection, custom instrumentation, time-series data | Custom metrics, instrumentation |

**Fallback**: If no integrations found, perform local analysis via wicked-search for error patterns in code.

See refs/sources.md for detailed capability discovery patterns.

## Output Format

```markdown
## System Health Report

**Overall Status**: [HEALTHY | DEGRADED | CRITICAL]
**Assessment Time**: {timestamp}
**Data Sources**: {list of integrations used}

### Health Summary

| Service | Status | Error Rate | Latency (p95) | SLO Status |
|---------|--------|------------|---------------|------------|
| {service} | {status} | {rate} | {latency} | {✓ or ✗} |

### Issues Detected

[For each issue]
**{Service}: {Issue Description}**
- Severity: [CRITICAL | HIGH | MEDIUM | LOW]
- Started: {timestamp}
- Metric: {specific metric and values}
- Pattern: {error pattern or behavior}
- Correlation: {deployment or change if found}
- Blast Radius: {impact scope}

### Trends (24h)

- Error Rates: {trend with percentage}
- Latency: {trend with percentage}
- Traffic: {trend with percentage}

### Recommendations

**Immediate**:
{critical actions needed now}

**Short-term**:
{optimizations and improvements}

**Capacity**:
{capacity planning insights}
```

## Common Health Patterns

### Post-Deployment Degradation
Error rates or latency increase after deployment. Correlate metrics with deployment time and consider rollback.

### Gradual Performance Decline
Metrics slowly degrading over hours/days. Investigate memory leaks, growing data, cache efficiency.

### Traffic-Related Issues
Performance degrades with traffic spikes. Check capacity utilization and scaling policies.

### Cascading Failures
Single service failure causes downstream issues. Use traces to identify root cause and implement circuit breakers.

## Integration with wicked-crew

When crew enters build phase:
1. Capture baseline health metrics
2. Monitor during deployment
3. Validate post-deployment health
4. Alert if degradation detected

Emit events:
- `observe:health:checked:success`
- `observe:health:degraded:warning`
- `observe:health:critical:failure`

## Integration with wicked-engineering

When debugging issues, provide observability context:
- Recent errors from discovered sources
- Performance metrics around the issue
- Correlation with code changes
- Trace data for request flow

## Notes

- Prioritize data from real observability tools over static analysis
- Always correlate health changes with deployments or code changes
- Consider traffic patterns when assessing metrics
- Document baseline metrics for comparison
- Alert on SLO burn rate, not just absolute values
