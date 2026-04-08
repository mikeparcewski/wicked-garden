# Rollout Strategies: Operations & Communication

Dark launch, feature flags, monitoring, rollback procedures, communication templates, and post-rollout learning.

## Dark Launch

**When to use**: Infrastructure validation
**Timeline**: Varies
**Monitoring**: Technical focus

### Characteristics

- Backend enabled, frontend disabled
- Validate infrastructure and performance
- No user-facing changes yet
- Dual-write or shadowing patterns

### Process

```
Phase 1: Dual Write (1 week)
- Write to new system (no reads)
- Compare data consistency
- Monitor performance impact

Phase 2: Shadow Read (1 week)
- Read from new system (results discarded)
- Compare with old system
- Validate correctness

Phase 3: Canary Read (2-4 weeks)
- Use new system for small % of real traffic
- Standard canary rollout from here
```

### Example

```
Feature: Migrate from SQL to NoSQL
Risk: VERY HIGH (data migration, hard to reverse)
Strategy: Dark Launch → Canary

Timeline:
Week 1-2: Dual write to both DBs
- Success: Data consistency > 99.99%
- Rollback: Stop dual-write

Week 3-4: Shadow reads from NoSQL
- Success: Response match > 99.9%, latency acceptable
- Rollback: Stop shadow reads

Week 5+: Canary rollout
- 1% → 5% → 10% → 25% → 50% → 100%
- Standard canary criteria
```

## Feature Flag Patterns

### Boolean Flag

Simple on/off toggle.

```
if (featureFlags.newCheckout) {
  return <NewCheckout />
} else {
  return <OldCheckout />
}
```

### Percentage Rollout

Gradual percentage-based rollout.

```
// Feature flag system automatically handles percentage
if (featureFlags.newCheckout) {
  // User in rollout percentage
}
```

### Targeted Rollout

Specific user segments.

```
// Internal employees first
rollout: {
  internal: 100%,
  beta_users: 50%,
  everyone_else: 0%
}
```

### Multivariate

Multiple variants (A/B/C testing).

```
const variant = featureFlags.checkoutExperiment
// Returns: 'control' | 'variant_a' | 'variant_b'
```

## Monitoring Best Practices

### Real-time Dashboards

**What to show**:
- Current rollout stage and percentage
- Key metrics: current vs. baseline vs. target
- Error rates and alerts
- Traffic distribution (sanity check)

**Update frequency**: 1-5 minutes

### Automated Alerts

**Levels**:
- INFO: Stage advancement
- WARNING: Metric at 1.5x baseline
- CRITICAL: Metric at 2x baseline or rollback trigger

**Channels** (based on monitoring capability):
- Team chat: All levels
- Incident management: CRITICAL only
- Email: Daily summaries

### Anomaly Detection

Beyond static thresholds:
- Compare to same day last week
- Detect sudden changes (not just absolute values)
- Account for seasonality and trends

## Rollback Procedures

### Immediate Rollback (Feature Flag)

```
1. Set flag to 0% (or previous stage)
   # Using feature flag CLI/API
   feature-flag update feature_name --enabled=false
   # OR via dashboard/API depending on capability

2. Verify traffic shifted (1-2 minutes)
   Check dashboard: traffic to new = 0%

3. Monitor for recovery (5 minutes)
   Error rate returns to baseline

4. Notify stakeholders
   Team chat: #engineering-critical
   Incident: Create post-mortem ticket

5. Investigate and fix
   Root cause analysis
   Fix in staging
   Re-test before re-rollout
```

**Speed**: <5 minutes from decision to full rollback

### Code Rollback (Deployment)

If feature flag not available:

```
1. Revert commit
   git revert <commit-sha>

2. Deploy previous version
   ./deploy.sh --version previous

3. Verify deployment
   Check version in production

4. Monitor recovery
   Errors should resolve within deploy time
```

**Speed**: 10-30 minutes depending on deploy pipeline

### Partial Rollback

Roll back to previous stable stage (not necessarily 0%):

```
Current: 50% with issues
Action: Roll back to 25% (last stable stage)
Monitor: If issues persist, go to 10% or 0%
```

## Communication Templates

### Pre-Launch Announcement

```
Subject: [Rollout] New Checkout Experience - Starting Friday 2pm PT

Team,

We're beginning a canary rollout of the new checkout flow on Friday.

**What**: New checkout UX with social proof and progress indicators
**Risk**: HIGH (mission-critical, 100% of purchasers eventually)
**Strategy**: Canary (6 weeks, 1% → 100%)
**Feature Flag**: checkout_v2_enabled

**Timeline**:
- Week 1: Internal (0.1%), then 1%
- Week 2-3: 5%, 10%
- Week 4-5: 25%, 50%
- Week 6: 100%

**Monitoring**: [Link to monitoring dashboard]

**On-call**: Alice (primary), Bob (secondary)

**Stage gates**: Each stage requires sign-off from Eng + Product

Questions? #checkout-rollout team chat channel
```

### Stage Advancement Update

```
Subject: [Rollout Update] Checkout v2 → 10%

Team,

Stage 2 (5%) completed successfully. Advancing to Stage 3 (10%).

**Stage 2 Results** (5%, 7 days):
✓ Conversion: 10.3% vs 10.2% baseline (+1%)
✓ Error rate: 0.08% (well below 0.1% threshold)
✓ p95 latency: 420ms (below 500ms target)
✓ Support tickets: No increase

**Stage 3 Plan** (10%, 7 days):
- Start: Today 2pm PT
- Duration: Until next Friday
- Success criteria: Same as Stage 2
- Rollback: Auto if error > 0.5%

**Next Check-in**: Tuesday (3 days in)

Dashboard: [Link to monitoring dashboard]
```

### Rollback Notification

```
Subject: [ROLLBACK] Checkout v2 rolled back from 10% → 5%

Team,

We rolled back the checkout rollout due to conversion rate drop.

**What happened**:
- At 10%, conversion dropped to 9.1% (vs 10.2% baseline)
- Drop detected at 4pm PT, rollback executed at 4:15pm
- Currently at 5% (last stable stage), conversion recovered

**Root cause**: Under investigation
**Impact**: ~200 lost conversions during 10% period
**Next steps**:
1. RCA by EOD today
2. Fix and test in staging
3. Retry 10% stage next week

**Post-mortem**: Friday 2pm, #checkout-rollout

Status: Incident resolved, monitoring 5% stage
```

## Learning from Rollouts

### Post-Rollout Review

After 100% launch, document: planned vs. actual timeline, issues encountered and their resolutions, wins (what the gradual rollout caught), learnings (what to do differently), and final business impact (conversion/revenue lift).

### Rollout Playbook Updates

After each major rollout, update playbooks:
- Add new monitoring dashboards
- Document new rollback procedures
- Update risk assessment criteria
- Share learnings with team
