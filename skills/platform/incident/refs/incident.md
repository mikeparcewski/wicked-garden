# Incident Response Rubric

Rapid triage → investigate → mitigate → resolve → follow-up for production incidents.

> Scope: rapid active triage — root cause, blast radius, remediation steps.
> To log an incident against a crew project with traceability, use `/wicked-garden:crew:incident`.

## Phase 1: Triage (First 5 Minutes)

**GOAL**: Understand scope and severity.

- [ ] What is broken? (specific symptoms, error messages)
- [ ] When did it start? (timestamp)
- [ ] Who is affected? (users, services, regions)
- [ ] What is the impact? (revenue, user experience, data)
- [ ] Is it getting worse? (trend direction)

## Phase 2: Stabilize (Next 15 Minutes)

**GOAL**: Stop the bleeding.

- [ ] Can we roll back the last deploy?
- [ ] Can we fail over to a secondary?
- [ ] Can we disable the feature flag?
- [ ] Can we scale resources horizontally?
- [ ] Do we need to page more people?

## Phase 3: Investigate (Parallel to Stabilization)

**GOAL**: Find root cause.

Discover available observability sources via `ListMcpResourcesTool`:
- Priority 1: **error-tracking** (Sentry/Rollbar) — error rates, stack traces, affected users
- Priority 2: **logging** (Splunk/Elastic) — error messages, request IDs
- Priority 3: **tracing** (Jaeger/Zipkin) — request flow, latency breakdown
- Priority 4: **apm** (Datadog/New Relic) — service health metrics

Correlate with recent changes:
```bash
git log --oneline --since="2 hours ago"
git log --oneline -10 -- {affected_path}
```

## Phase 4: Resolve

- [ ] Implement fix or rollback
- [ ] Verify issue resolved (error rate back to baseline)
- [ ] Monitor for 15+ minutes for recurrence
- [ ] Communicate status to stakeholders

## Phase 5: Follow-Up

- [ ] Document incident timeline
- [ ] Identify contributing factors
- [ ] Create action items (missing circuit breaker, missing test, etc.)
- [ ] Update runbooks

## Severity Classification

| Severity | Impact | Response | Comms |
|----------|--------|----------|-------|
| SEV1/P0 | Complete outage or data loss | Immediate page | Every 30min |
| SEV2/P1 | Major feature degraded, significant impact | Within 15min | Every hour |
| SEV3/P2 | Minor feature broken, limited impact | Business hours | Daily |
| SEV4/P3 | Cosmetic, very limited | Next sprint | Weekly |

## Common Incident Patterns

### Deploy-Related
Signals: error spike immediately after deploy, new error messages.
Response: identify deploy time → compare pre/post error rates → rollback if >5x baseline.

### Traffic Spike
Signals: latency up across services, resource exhaustion.
Response: scale horizontally → enable rate limiting → identify traffic source.

### Cascading Failure
Signals: one service failure causing fan-out errors.
Response: trace to root failing service → isolate it → fix root → let dependents recover.

### Data-Related
Signals: errors related to data format, started after migration.
Response: identify bad data via errors → quarantine → fix validation at ingestion.

## Output Format

```markdown
## Incident Triage

**Severity**: [SEV1 | SEV2 | SEV3 | SEV4]
**Status**: [INVESTIGATING | IDENTIFIED | MITIGATING | RESOLVED]
**Started**: {timestamp}
**Duration**: {elapsed}

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

### Blast Radius
{list of affected components}

### Mitigation
**Immediate**:
1. {action — e.g., `kubectl rollout undo deployment/{name}`}

**After stabilization**:
1. {fix}
2. {preventive measure}

### Rollback Decision
{recommendation with criteria — RECOMMEND ROLLBACK / RECOMMEND FORWARD FIX}
```

## Communication Templates

**Initial (first 5 min)**:
`[INCIDENT] {Service} — {Brief}. Severity: P{N}. Started: {time}. Status: Investigating.`

**Update (every 30min P0, hourly P1)**:
`[UPDATE] {Service}. Status: {investigating/mitigating/resolved}. Progress: {done}. Next: {trying}. ETA: {unknown/time}.`

**Resolution**:
`[RESOLVED] {Service}. Duration: {total}. Root cause: {brief}. Prevention: {action items}. Postmortem: {link / "coming in 48h"}.`
