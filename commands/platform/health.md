---
description: System health check and reliability assessment
argument-hint: "[service name or 'all' for full assessment]"
---

# /wicked-garden:platform:health

Assess system health, aggregate observability data, and provide reliability recommendations.

## Instructions

### 1. Discover Observability Sources

Use capability-based discovery to find available integrations:

```
ListMcpResourcesTool

Look for:
- error-tracking: Sentry, Rollbar, Datadog errors
- apm: New Relic, Dynatrace, application metrics
- logging: Splunk, Elastic, CloudWatch logs
- tracing: Jaeger, Zipkin, distributed traces
```

### 2. Dispatch to SRE

```python
Task(
    subagent_type="wicked-garden:platform/sre",
    prompt="""Perform comprehensive system health assessment.

Target: {service name or 'all'}
Available Sources: {discovered observability integrations}

Assessment Checklist:
1. Error rates and trends - Current vs baseline, spikes
2. Latency metrics - p50, p95, p99 distributions
3. SLO compliance status - Are we meeting service level objectives?
4. Recent deployment correlation - Changes in last N hours
5. Capacity utilization - Resource usage, headroom

Return Format:
- Overall status (HEALTHY/DEGRADED/CRITICAL)
- Metrics summary table (service, status, error rate, latency, SLO)
- Issues detected with severity
- Correlation with deployments
- Recommendations:
  - Immediate actions (urgent)
  - Short-term improvements
  - Capacity planning
"""
)
```

### 3. Fallback to Code Analysis

If no observability sources available:
- Use wicked-search to find error patterns in code
- Check recent commits for deployment correlation
- Analyze logging statements for potential issues

### 4. Deliver Health Report

```markdown
## System Health Report

**Overall Status**: [HEALTHY | DEGRADED | CRITICAL]
**Assessment Time**: {timestamp}

### Metrics Summary
| Service | Status | Error Rate | p95 Latency | SLO |
|---------|--------|------------|-------------|-----|
| {name}  | {status} | {rate}   | {latency}   | {status} |

### Issues Detected
{list of issues with severity}

### Recommendations
**Immediate**: {urgent actions}
**Short-term**: {improvements}
**Capacity**: {planning}
```

## Example

```
User: /wicked-garden:platform:health api-gateway

Claude: I'll assess the health of the api-gateway service.

[Discovers Datadog integration]
[Queries metrics and error rates]

## System Health Report

**Overall Status**: DEGRADED
**Assessment Time**: 2024-01-15 14:30 UTC

### api-gateway Health
| Metric | Current | Baseline | Status |
|--------|---------|----------|--------|
| Error Rate | 0.8% | 0.1% | Elevated |
| p95 Latency | 450ms | 200ms | Degraded |
| Throughput | 2.5k/s | 2.5k/s | Normal |

### Issues
1. **Elevated error rate** - 8x baseline since 13:45 UTC
2. **Latency degradation** - p95 doubled in last hour

### Correlation
- Deployment api-gateway-v2.1.0 at 13:42 UTC
- Changed: rate limiting middleware

### Recommendations
Consider rollback if error rate continues trending up.
```
