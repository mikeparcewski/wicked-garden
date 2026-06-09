# System Health Assessment Rubric

Assess system health by aggregating observability data from all available sources.

## Step 1: Discover Observability Sources

Use `ListMcpResourcesTool` to find available integrations. Look for:
- **error-tracking**: Sentry, Rollbar, Datadog errors
- **apm**: New Relic, Dynatrace, application metrics
- **logging**: Splunk, Elastic, CloudWatch logs
- **tracing**: Jaeger, Zipkin, distributed traces

## Step 2: Assessment Checklist (per source found)

- [ ] Error rates and trends — current vs baseline, any spikes
- [ ] Latency metrics — p50, p95, p99 distributions
- [ ] SLO compliance status — meeting service level objectives?
- [ ] Recent deployment correlation — changes in last N hours
- [ ] Capacity utilization — resource usage and headroom

## Step 3: Fallback (No Observability Sources)

If no integrations are available:
1. Use wicked-garden:search to find error patterns in code
2. Check recent git commits for deployment correlation (`git log --oneline --since="2 hours ago"`)
3. Analyze logging statements for potential issues

## Output Format

```markdown
## System Health Report

**Overall Status**: [HEALTHY | DEGRADED | CRITICAL]
**Assessment Time**: {timestamp}
**Data Sources**: {list of sources used, or "code analysis (no integrations found)"}

### Metrics Summary
| Service | Status | Error Rate | p95 Latency | SLO |
|---------|--------|------------|-------------|-----|
| {name}  | {status} | {rate}   | {latency}   | ✓/✗ |

### Issues Detected
{list with severity: CRITICAL | HIGH | MEDIUM | LOW}

### Deployment Correlation
{recent deployments and their impact}

### Recommendations
**Immediate**: {urgent actions}
**Short-term**: {improvements}
**Capacity**: {planning horizon}
```

## Severity Classification

- **CRITICAL**: SLO violation, error rate >10x baseline, service down
- **DEGRADED**: Elevated errors (2-10x), latency doubled, trend worsening
- **HEALTHY**: Metrics within SLO, no alerts, stable or improving

## Common Patterns

### Error Spike After Deployment
Check if spike aligns with a deploy timestamp. Recommend rollback if:
- Error rate >5x baseline
- Critical paths affected
- No quick config fix available

### Gradual Performance Degradation
Check for memory leaks, growing data volume, cache hit rate drop, DB query growth.

### Cascading Failures
Identify the root failing service via traces. Fix root service first; dependents recover automatically.
