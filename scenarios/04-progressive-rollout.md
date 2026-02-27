---
name: progressive-rollout
title: Progressive Feature Rollout
description: Plan a safe, staged rollout with risk assessment, canary deployment, and rollback criteria
type: workflow
difficulty: intermediate
estimated_minutes: 8
---

# Progressive Feature Rollout

This scenario validates that wicked-delivery can help engineering teams plan safe, progressive feature rollouts with proper risk assessment, staged traffic percentages, and clear rollback procedures.

## Setup

Create a context simulating a feature that needs careful rollout:

```bash
# Create test project directory
mkdir -p ~/test-wicked-delivery/payment-rollout
cd ~/test-wicked-delivery/payment-rollout

# Create feature description
cat > feature-description.md <<'EOF'
# Feature: New Payment Processing Pipeline

## What's Changing
Migrating from legacy payment processor (PaymentCo) to new provider (StripePay).

## Technical Details
- New payment SDK integration
- Database schema changes for transaction records
- Webhook handlers for payment events
- API endpoint changes (backwards compatible)

## Impact Assessment
- Affects ALL checkout transactions
- Revenue-critical path
- ~15,000 daily transactions
- Peak traffic: 11am-2pm EST, Black Friday weekend

## Dependencies
- New SDK deployed: YES
- Database migration: COMPLETED
- Feature flag: payment_pipeline_v2 (currently OFF)
- Monitoring dashboards: READY

## Rollback Plan
Feature flag toggle returns to legacy processor immediately.
No data migration rollback needed (dual-write enabled).
EOF

# Create current metrics baseline
cat > baseline-metrics.md <<'EOF'
# Current Payment Metrics (Baseline)

## Performance
- P50 latency: 245ms
- P95 latency: 890ms
- P99 latency: 1.2s

## Reliability
- Success rate: 99.2%
- Error rate: 0.8%
- Timeout rate: 0.1%

## Business
- Daily transaction volume: ~15,000
- Average transaction value: $67
- Daily revenue: ~$1M

## Error Breakdown
- Card declined: 65% of errors (expected)
- Network timeout: 20%
- Validation errors: 10%
- Unknown errors: 5%
EOF

echo "Setup complete. Rollout context created."
```

## Steps

### 1. Assess Rollout Risk

Ask the rollout manager to evaluate the risk:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="Assess the risk of rolling out our new payment processing pipeline. Context is in feature-description.md and baseline-metrics.md"
```

**Expected Output**:
- **Risk Assessment**:
  - User Impact: HIGH (affects all checkout users)
  - Revenue Impact: HIGH (direct payment path)
  - System Criticality: HIGH (mission-critical)
  - Reversibility: HIGH (feature flag toggle)
- **Overall Risk**: HIGH
- **Recommended Strategy**: Canary deployment (slowest, safest)
- Rationale for each risk factor

### 2. Define Rollout Stages

Plan the staged rollout:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="Define rollout stages for this payment migration. We need to be very careful - this is revenue-critical."
```

**Expected Output**:
```markdown
## Rollout Stages

| Stage | Traffic | Duration | Who | Success Criteria |
|-------|---------|----------|-----|------------------|
| 1 | 1% | 24 hours | Internal employees | Error rate < 1% |
| 2 | 5% | 3 days | Low-value transactions | Error rate < 1%, latency < 1s |
| 3 | 10% | 1 week | All users (sampled) | Error rate < 1%, P95 < 900ms |
| 4 | 25% | 1 week | All users (sampled) | All metrics stable |
| 5 | 50% | 1 week | All users (sampled) | Confidence in parity |
| 6 | 100% | - | Everyone | Full migration complete |
```

### 3. Define Success and Rollback Criteria

Establish clear thresholds:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="What are the success and rollback criteria for each stage? When should we automatically roll back?"
```

**Expected Output**:
- **Success Criteria** (all must pass to advance):
  - Error rate <= baseline (0.8%) + 0.2% tolerance
  - P95 latency <= baseline (890ms) + 10% tolerance
  - No increase in customer support tickets
  - No critical bugs reported
- **Automatic Rollback Triggers**:
  - Error rate > 2x baseline (>1.6%)
  - P95 latency > 2x baseline (>1.8s)
  - Revenue drop > 5% compared to control
  - Any payment data loss or corruption
- **Manual Rollback Triggers**:
  - Customer complaints about charges
  - Security incident
  - Regulatory concern

### 4. Create Monitoring Plan

Define what to watch:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="What monitoring should be in place during the rollout? What dashboards and alerts do we need?"
```

**Expected Output**:
- **Real-time Metrics**:
  - Transaction success rate (by variant)
  - Latency percentiles (P50, P95, P99)
  - Error breakdown by type
  - Revenue comparison (treatment vs control)
- **Dashboards**:
  - Rollout progress dashboard (% traffic on new pipeline)
  - Side-by-side comparison (legacy vs new)
  - Error rate alerting panel
- **Alerts**:
  - WARNING: Error rate > 1.0%
  - CRITICAL: Error rate > 1.6%
  - WARNING: P95 latency > 1.0s
  - CRITICAL: Revenue -5% vs control
- **On-call requirements**:
  - Engineer on-call during Stage 1-3
  - Escalation path documented

### 5. Plan Communication

Define stakeholder communication:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="Create a communication plan for this rollout. Who needs to know what, and when?"
```

**Expected Output**:
- **Stakeholder Matrix**:
  | Stakeholder | What They Need | When | Channel |
  |-------------|---------------|------|---------|
  | Engineering | Technical details, rollback steps | T-2 days | Slack #platform |
  | Support | Customer impact, FAQs | T-1 day | Email + runbook |
  | Product | Timeline, success metrics | Weekly updates | Status meeting |
  | Leadership | Risk assessment, go/no-go | Stage gates | Summary email |
- **Communication Templates**:
  - Pre-rollout announcement
  - Stage advancement notice
  - Rollback notification (if needed)
  - Completion announcement

### 6. Generate Full Rollout Plan

Request the complete plan document:

```
Task tool: subagent_type="wicked-delivery:rollout-manager"
prompt="Generate a complete rollout plan document I can share with the team and get sign-off."
```

**Expected Output**:
Comprehensive rollout plan including:
- Executive summary
- Risk assessment
- Rollout stages table
- Success and rollback criteria
- Monitoring plan
- Communication plan
- Stage gate checklist
- Rollback procedure (step-by-step)
- Next steps

## Expected Outcome

- Risk properly assessed based on impact and reversibility
- Rollout stages progress gradually (1% -> 5% -> 10% -> etc.)
- Clear success criteria for advancing stages
- Automatic rollback triggers defined
- Monitoring plan covers technical and business metrics
- Communication plan identifies all stakeholders
- Document is actionable and ready for sign-off

## Success Criteria

- [ ] Risk assessment covers user impact, revenue impact, criticality, and reversibility
- [ ] Overall risk rating provided (LOW/MEDIUM/HIGH)
- [ ] Rollout strategy matches risk level (canary for HIGH risk)
- [ ] At least 5 rollout stages defined for high-risk feature
- [ ] First stage is internal/employee-only or very low percentage
- [ ] Success criteria are measurable (specific thresholds)
- [ ] Automatic rollback triggers defined with specific thresholds
- [ ] Monitoring includes both technical and business metrics
- [ ] Alerts have WARNING and CRITICAL levels
- [ ] Communication plan identifies stakeholders by role
- [ ] Rollback procedure is documented step-by-step
- [ ] Stage gate checklist provided for each advancement

## Value Demonstrated

**Real-world value**: Feature launches are high-stakes moments. Teams often face pressure to "just ship it" or "we'll monitor it manually." The results are predictable:
- Outages that affect all users simultaneously
- Revenue loss during incidents
- Customer trust damage from repeated issues
- Engineer burnout from firefighting

wicked-delivery's rollout capabilities enforce the discipline that separates mature engineering orgs from chaotic ones:

1. **Risk-proportionate response**: High-risk features get canary deployments, not big-bang launches
2. **Staged exposure**: Problems affect 1% before they affect 100%
3. **Clear rollback triggers**: No debate about "is this bad enough to roll back?"
4. **Automated safety**: When thresholds breach, rollback happens without waiting for humans
5. **Stakeholder alignment**: Everyone knows the plan before the rollout starts

For teams shipping to production multiple times per week, this discipline is the difference between confident deployment and fearful releases. The rollout-manager agent encodes the patterns used by companies like Netflix, Google, and Facebook for safe deployment at scale.

## Integration Notes

**With wicked-kanban**: Tracks rollout stages as tasks with progress
**With wicked-mem**: Recalls past rollout learnings and patterns
**With wicked-delivery:analyze**: Uses experiment results to inform rollout confidence
**Standalone**: Works with provided context documents

## Cleanup

```bash
rm -rf ~/test-wicked-delivery/payment-rollout
```
