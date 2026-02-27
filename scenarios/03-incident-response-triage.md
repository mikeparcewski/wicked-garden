---
name: incident-response-triage
title: Production Incident Response and Triage
description: Rapid incident triage with root cause correlation, blast radius assessment, and rollback decision support
type: infrastructure
difficulty: advanced
estimated_minutes: 15
---

# Production Incident Response and Triage

This scenario demonstrates wicked-platform's incident response capabilities, including rapid triage, root cause correlation with deployments, blast radius assessment, and data-driven rollback decisions.

## Setup

Create a simulated microservices environment with recent deployments:

```bash
# Create test environment
mkdir -p ~/test-wicked-platform/incident-response
cd ~/test-wicked-platform/incident-response

# Initialize git repo with deployment history
git init

# Create service structure
mkdir -p services/checkout-api services/payment-service services/user-service

# Create checkout-api with recent changes
cat > services/checkout-api/config.ts << 'EOF'
export const config = {
  paymentTimeout: 500,  // Changed from 5000ms - potential issue!
  retryAttempts: 3,
  circuitBreakerThreshold: 5
};
EOF

cat > services/checkout-api/checkout.ts << 'EOF'
import { config } from './config';
import { PaymentService } from '../payment-service/client';

export async function processCheckout(orderId: string) {
  const payment = new PaymentService({ timeout: config.paymentTimeout });

  try {
    const result = await payment.charge(orderId);
    return { success: true, transactionId: result.id };
  } catch (error) {
    if (error.code === 'TIMEOUT') {
      // Timeout errors spiking after recent change
      throw new Error(`Payment timeout for order ${orderId}`);
    }
    throw error;
  }
}
EOF

# Create deployment history
git add -A
git commit -m "Initial setup"

git add -A
git commit -m "feat(user-service): Add session caching"

git add -A
git commit -m "fix(payment-service): Update retry logic"

# The problematic deployment
cat > services/checkout-api/config.ts << 'EOF'
export const config = {
  paymentTimeout: 500,  // BUG: Should be 5000
  retryAttempts: 3,
  circuitBreakerThreshold: 5
};
EOF
git add -A
git commit -m "perf(checkout-api): Optimize timeout settings"

# Create simulated error log
cat > error.log << 'EOF'
2024-01-15T14:20:00Z INFO checkout-api Deployment checkout-api-v2.4.1 started
2024-01-15T14:20:30Z INFO checkout-api Deployment checkout-api-v2.4.1 completed
2024-01-15T14:23:15Z ERROR checkout-api Payment timeout for order ORD-1001
2024-01-15T14:23:16Z ERROR checkout-api Payment timeout for order ORD-1002
2024-01-15T14:23:17Z ERROR checkout-api Payment timeout for order ORD-1003
2024-01-15T14:23:18Z ERROR checkout-api Payment timeout for order ORD-1004
2024-01-15T14:23:19Z ERROR checkout-api Payment timeout for order ORD-1005
2024-01-15T14:23:20Z ERROR checkout-api Payment timeout for order ORD-1006
2024-01-15T14:24:00Z WARN payment-service High timeout rate from checkout-api
2024-01-15T14:24:30Z ERROR checkout-api Circuit breaker OPEN for payment-service
2024-01-15T14:25:00Z CRITICAL checkout-api Checkout failures exceeding threshold
EOF
```

## Steps

### 1. Initiate Incident Triage

```bash
/wicked-platform:incident "500 errors spiking on checkout API, customers unable to complete purchases"
```

**Expected**:
- Spawns incident-responder agent
- Begins structured incident triage
- Asks for additional context if needed

### 2. Review Incident Assessment

The incident responder should:

**Gather context**:
- [ ] When did the issue start? (Around 14:23 UTC)
- [ ] What are the symptoms? (500 errors, timeouts)
- [ ] Which services are affected? (checkout-api, payment-service)
- [ ] User impact scope? (Customers cannot checkout)

**Correlate with changes**:
- [ ] Check recent deployments (checkout-api-v2.4.1 at 14:20)
- [ ] Review code changes in deployment
- [ ] Identify suspicious changes (timeout: 5000 -> 500)

### 3. Analyze Blast Radius

The triage should assess impact:

```markdown
### Blast Radius Assessment

**Direct Impact**:
- checkout-api: 500 errors on /api/checkout
- Checkout failure rate: ~85% (baseline: 1%)

**Cascade Effects**:
- payment-service: Receiving burst of requests then timeouts
- Circuit breaker: OPEN (all checkout requests failing)
- Order confirmation: Not sending emails

**User Impact**:
- Estimated affected users: ~2,400 (based on checkout attempt rate)
- Revenue impact: ~$180,000/hour (estimated)
- Customer support: Spike in tickets expected
```

### 4. Review Root Cause Analysis

The incident responder should identify:

```markdown
### Root Cause Analysis

**Identified Cause**: Configuration change in checkout-api-v2.4.1

**Evidence**:
1. Error spike began 3 minutes after deployment (14:20 -> 14:23)
2. All errors are timeout-related
3. Payment service healthy (no internal errors)
4. Config change: `paymentTimeout: 5000` -> `paymentTimeout: 500`

**Root Cause**: Timeout value changed from 5000ms to 500ms (likely typo)
- Payment service p99 latency: ~800ms
- New timeout: 500ms
- Result: Most payment calls timeout

**Correlation Confidence**: HIGH
```

### 5. Get Rollback Recommendation

```bash
/wicked-platform:incident --rollback-decision
```

**Expected**:
Decision framework with clear criteria:

```markdown
### Rollback Decision

**Recommendation**: ROLLBACK

**Criteria Met**:
- [x] Error rate > 10x baseline (85% vs 1%)
- [x] Affecting critical user path (checkout)
- [x] Clear correlation with deployment
- [x] Quick mitigation not available
- [x] Revenue impact exceeds threshold

**Rollback Command**:
```bash
kubectl rollout undo deployment/checkout-api
```

**Alternative** (if rollback not possible):
```bash
# Hotfix: Update timeout to correct value
kubectl set env deployment/checkout-api PAYMENT_TIMEOUT=5000
```

**Post-Rollback Verification**:
1. Monitor error rate for 5 minutes
2. Verify checkout success rate returns to baseline
3. Confirm circuit breaker closes
```

### 6. Document Timeline

The incident triage should produce a timeline:

```markdown
### Incident Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:20:00 | Deployment checkout-api-v2.4.1 started |
| 14:20:30 | Deployment completed |
| 14:23:15 | First timeout errors appear |
| 14:24:00 | Payment service reports high timeout rate |
| 14:24:30 | Circuit breaker opens |
| 14:25:00 | CRITICAL alert triggered |
| 14:30:00 | Incident response initiated |
| 14:35:00 | Root cause identified |
| 14:36:00 | Rollback decision made |
```

## Expected Outcome

A complete incident triage report:

```markdown
## Incident Triage: Checkout API 500 Errors

**Severity**: SEV1
**Status**: IDENTIFIED
**Duration**: 18 minutes (ongoing)
**Started**: 14:23 UTC

### Summary
Checkout API returning 500 errors due to payment timeout misconfiguration deployed in v2.4.1. All checkout attempts failing, affecting estimated $180K/hour in revenue.

### Impact
- **Users affected**: ~2,400 (15% of active users)
- **Services**: checkout-api, payment-service (cascade)
- **Business**: Checkout completely blocked, revenue loss

### Root Cause
Configuration typo in checkout-api-v2.4.1:
- Changed: `paymentTimeout: 5000` -> `paymentTimeout: 500`
- Payment service p99: 800ms
- Result: All payments timeout

### Mitigation
**Recommended**: Immediate rollback

```bash
kubectl rollout undo deployment/checkout-api
```

### Follow-up Actions
1. [ ] Add config validation to prevent timeout < 1000ms
2. [ ] Add integration test for payment timeout
3. [ ] Review deployment checklist
4. [ ] Schedule blameless postmortem

### Lessons Learned
- Configuration changes need same scrutiny as code changes
- Consider config validation in CI/CD
- Payment timeout should be environment variable, not hardcoded
```

## Success Criteria

- [ ] Incident severity correctly assessed (SEV1)
- [ ] Timeline accurately reconstructed
- [ ] Root cause correctly identified (timeout config change)
- [ ] Deployment correlation established
- [ ] Blast radius properly assessed
- [ ] Clear rollback recommendation provided
- [ ] Rollback command ready to execute
- [ ] Follow-up actions documented

## Value Demonstrated

**Problem solved**: During production incidents, engineers waste precious minutes context-switching between logs, deployment history, metrics, and code changes. Mean Time To Resolution (MTTR) suffers while the team scrambles to correlate information.

**Why this matters**:

1. **Structured triage**: The incident-responder agent follows a consistent process: symptoms -> timeline -> correlation -> blast radius -> mitigation. No steps skipped in the chaos.

2. **Rapid correlation**: Automatically connects error spikes with recent deployments and code changes. What took 15 minutes of git log archaeology now happens in seconds.

3. **Data-driven decisions**: Rollback recommendations based on objective criteria (error rate, user impact, correlation confidence), not gut feelings.

4. **Documentation by default**: The incident report is generated as triage happens, not reconstructed days later for the postmortem.

5. **MTTR reduction**: By automating the investigation grunt work, engineers can focus on the actual fix. A 30-minute diagnosis becomes 5 minutes.

This replaces the ad-hoc incident response where:
- Engineers check logs manually
- Someone searches git history while another checks metrics
- Rollback decisions are made under pressure without clear criteria
- Postmortem documentation is incomplete or forgotten

The `/incident` command brings SRE expertise to any team facing a production issue.
