# Error Severity Classification

Guidelines for classifying error severity and determining appropriate response.

## Severity Levels

### CRITICAL

**Criteria**:
- Error rate >10x baseline
- New error in critical path (auth, payment, checkout, etc.)
- Complete service failure or outage
- Data corruption or data loss errors
- Security breach indicators

**Response Time**: Immediate (page on-call if after hours)

**Actions**:
- Declare incident
- Engage incident responder
- Consider immediate rollback
- Notify stakeholders every 30 minutes
- All hands on deck if needed

**Examples**:
```
- Authentication service returning 500 for all requests
- Payment processing failing for 100% of transactions
- Database writes failing (data loss risk)
- SQL injection attack detected in logs
- Memory leak causing OOM crashes every 5 minutes
```

### HIGH

**Criteria**:
- Error rate >3x baseline
- New error affecting >10% of users
- Payment or transaction-related errors
- Security-related errors (non-critical)
- Major feature completely broken

**Response Time**: Within 15 minutes during business hours

**Actions**:
- Investigate immediately
- Prepare rollback plan
- Notify stakeholders hourly
- Consider feature disable if possible
- Hotfix or rollback within 2 hours

**Examples**:
```
- Checkout flow failing for 15% of users
- User registration errors spiking
- Password reset emails not sending
- Critical API endpoints returning errors
- Data export feature completely broken
```

### MEDIUM

**Criteria**:
- Error rate >1.5x baseline
- New error affecting <10% of users
- Non-critical feature broken
- Recoverable errors (retries succeeding)
- Performance degradation errors

**Response Time**: Within business hours (same day)

**Actions**:
- Investigate and root cause
- Schedule fix in current sprint
- Update status page if user-facing
- Daily stakeholder updates
- Implement monitoring/alerting

**Examples**:
```
- Search returning errors for 5% of queries
- Image upload failing occasionally
- Non-critical API rate limiting errors
- Cache misses causing slow responses
- Background job failures with retry
```

### LOW

**Criteria**:
- Error rate <1.5x baseline
- Cosmetic or UI issues
- Logging or instrumentation errors
- Low-traffic feature errors
- Development/staging environment errors

**Response Time**: Next sprint or backlog

**Actions**:
- Create bug ticket
- Include in weekly update
- Fix when capacity available
- Consider if fix is worth effort
- May close as "won't fix"

**Examples**:
```
- Typo in error message
- Analytics event tracking error
- Debug logging errors
- Admin panel minor issues
- Deprecated API warnings
```

## Decision Matrix

Use this matrix to classify errors:

| Factor | CRITICAL | HIGH | MEDIUM | LOW |
|--------|----------|------|--------|-----|
| **Error Rate** | >10x baseline | >3x baseline | >1.5x baseline | <1.5x baseline |
| **User Impact** | All/most users | >10% users | <10% users | Minimal |
| **Function** | Critical path | Major feature | Minor feature | Cosmetic |
| **Data Risk** | Loss/corruption | Inconsistency | None | None |
| **Revenue Impact** | Direct loss | Potential loss | Minimal | None |
| **Security** | Active breach | Vulnerability | Weakness | Info disclosure |

## Special Considerations

### Escalate Severity If:

1. **Error rate is increasing rapidly**
   - MEDIUM → HIGH if doubling every 15 minutes
   - HIGH → CRITICAL if affecting critical path

2. **Multiple services affected**
   - Indicates cascading failure
   - Potential systemic issue

3. **During high-traffic period**
   - Black Friday, holiday season
   - Product launch day
   - Marketing campaign

4. **Media/PR sensitivity**
   - Public-facing issue
   - Social media mentions
   - Competitor awareness

### Downgrade Severity If:

1. **Isolated to test/staging environment**
   - Production not affected
   - No user impact

2. **Auto-recovery happening**
   - Retries succeeding
   - Circuit breaker protecting
   - Self-healing in progress

3. **Feature flag isolation**
   - Can disable feature
   - Limited rollout (1% users)
   - Canary deployment

4. **Workaround available**
   - Users can accomplish task differently
   - Support can manually process
   - Alternative feature exists

## Response Actions by Severity

### CRITICAL Response

```markdown
1. [ ] Declare incident (PagerDuty, Slack, etc.)
2. [ ] Page on-call engineer immediately
3. [ ] Engage incident responder
4. [ ] Start incident timeline
5. [ ] Assess rollback vs hotfix
6. [ ] Notify stakeholders (30min cadence)
7. [ ] Execute rollback if safe
8. [ ] Monitor for resolution
9. [ ] Verify user impact reduced
10. [ ] Schedule postmortem
```

### HIGH Response

```markdown
1. [ ] Create incident ticket
2. [ ] Notify team in Slack
3. [ ] Investigate root cause (15min)
4. [ ] Assess rollback vs hotfix
5. [ ] Prepare rollback plan
6. [ ] Notify stakeholders (hourly)
7. [ ] Implement fix within 2 hours
8. [ ] Deploy and verify
9. [ ] Monitor for 1 hour
10. [ ] Document in incident log
```

### MEDIUM Response

```markdown
1. [ ] Create bug ticket
2. [ ] Assign to team member
3. [ ] Root cause analysis
4. [ ] Schedule fix this sprint
5. [ ] Update status page
6. [ ] Implement fix
7. [ ] Deploy in normal release
8. [ ] Verify resolution
9. [ ] Close ticket
```

### LOW Response

```markdown
1. [ ] Create backlog item
2. [ ] Prioritize in grooming
3. [ ] Fix when capacity available
4. [ ] Or close as won't fix
```

## Communication Templates

### CRITICAL
```
[CRITICAL] {Service} - {Brief Description}
Impact: {percentage}% of users / ${revenue} at risk
Started: {timestamp}
Status: Investigating / Mitigating / Resolved
Team: {responders}
Next Update: 30 minutes
```

### HIGH
```
[HIGH] {Service} - {Brief Description}
Impact: {user count} users affected
Started: {timestamp}
ETA: {best estimate}
Next Update: 1 hour
```

### MEDIUM
```
[MEDIUM] {Service} - {Brief Description}
Impact: Limited to {feature}
Fix Scheduled: {sprint/date}
Status Page: {link}
```

### LOW
```
[LOW] {Service} - {Brief Description}
Tracked: {ticket link}
Minimal impact, will fix when capacity available
```
