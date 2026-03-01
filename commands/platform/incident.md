---
description: Incident response and triage
argument-hint: "<error message, alert, or symptom description>"
---

# /wicked-garden:platform:incident

Rapid incident triage with root cause correlation, blast radius assessment, and remediation guidance.

## Instructions

### 1. Gather Incident Context

Collect information about the incident:
- Error messages or symptoms
- When it started
- Affected services or users
- Any recent changes

### 2. Dispatch to Incident Responder

```python
Task(
    subagent_type="wicked-garden:platform:incident-responder",
    prompt="""Triage production incident and provide remediation guidance.

Symptom: {error/alert description}
Started: {time if known}
Impact: {affected scope}

Investigation Checklist:
1. Error spike investigation - Rate, timing, affected endpoints
2. Service dependency mapping - Trace impact through service graph
3. Recent deployment correlation - Changes in last N hours
4. Blast radius assessment - Users, services, business impact
5. Cascading failure detection - Downstream effects

Return Format:
- Severity (SEV1/SEV2/SEV3)
- Status (INVESTIGATING/IDENTIFIED/MITIGATING/RESOLVED)
- Impact metrics (users affected, services down)
- Timeline of events
- Root cause (identified or suspected)
- Correlation with deployments or changes
- Blast radius diagram
- Immediate mitigation actions
- Rollback recommendation with criteria
"""
)
```

### 3. Discover Observability Data

Check for available sources:
- Error tracking (Sentry, Rollbar)
- APM data (latency, throughput)
- Logs (error patterns)
- Traces (request flow)

### 4. Correlate with Changes

Use wicked-search and git:
```bash
# Recent deployments
git log --oneline --since="2 hours ago"

# Changes to affected area
git log --oneline -10 -- {affected path}
```

### 5. Deliver Incident Report

```markdown
## Incident Triage

**Severity**: [SEV1 | SEV2 | SEV3]
**Status**: [INVESTIGATING | IDENTIFIED | MITIGATING | RESOLVED]
**Started**: {timestamp}
**Duration**: {time elapsed}

### Summary
{brief description of incident}

### Impact
- **Users affected**: {count/percentage}
- **Services affected**: {list}
- **Business impact**: {description}

### Timeline
| Time | Event |
|------|-------|
| {time} | {event} |

### Root Cause
{identified or suspected cause}

### Correlation
- **Deployment**: {recent deploy if relevant}
- **Changes**: {relevant code changes}
- **External**: {dependency issues}

### Blast Radius
{diagram or list of affected components}

### Mitigation
**Immediate**:
1. {action}

**Remediation**:
1. {fix}

### Rollback Decision
{recommendation with criteria}
```

## Example

```
User: /wicked-garden:platform:incident "500 errors spiking on checkout API"

Claude: I'll triage this incident immediately.

[Spawns incident-responder]
[Checks error tracking for spike details]
[Correlates with recent deployments]

## Incident Triage: Checkout API 500 Errors

**Severity**: SEV2
**Status**: IDENTIFIED
**Started**: 14:23 UTC (18 minutes ago)

### Summary
500 errors on /api/checkout endpoint increased 50x from baseline.

### Impact
- **Users affected**: ~2,400 (15% of checkout attempts)
- **Services**: checkout-api, payment-service
- **Business**: Checkout failures, potential revenue loss

### Timeline
| Time | Event |
|------|-------|
| 14:20 | Deployment checkout-api v2.4.1 |
| 14:23 | Error rate spike begins |
| 14:25 | Alerts triggered |

### Root Cause
Payment service integration failing due to timeout configuration change in v2.4.1.

Changed `paymentTimeout: 5000` → `paymentTimeout: 500` (likely typo)

### Mitigation
**Immediate**:
1. Rollback checkout-api to v2.4.0
   ```bash
   kubectl rollout undo deployment/checkout-api
   ```

**After stabilization**:
1. Fix timeout value in code
2. Add integration test for payment timeouts
3. Deploy with proper value

### Rollback Decision
**RECOMMEND ROLLBACK** - Error rate exceeds threshold, clear regression
```
