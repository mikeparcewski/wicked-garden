# Rollout Strategies: Core Approaches

Core rollout strategy guidance: Big Bang, Progressive, and Canary rollouts.

## Big Bang Rollout

**When to use**: LOW risk features
**Timeline**: Immediate (0% → 100%)
**Monitoring**: Basic

### Characteristics

- Deploy to all users at once
- Minimal overhead and complexity
- Fast to market
- Higher risk if issues occur

### Good Candidates

- Non-critical cosmetic changes
- Internal tools
- Bug fixes (already broken)
- Features already validated via experiment
- <1% user impact

### Example

```
Feature: Update button color from green to blue
Risk: LOW (cosmetic, easily reversible)
Strategy: Big Bang

Timeline:
- T+0: Deploy to 100%
- T+1h: Monitor for errors
- T+24h: Close rollout

Monitoring:
- Error rate baseline
- No specific metrics
```

### Rollback

Simple flag toggle or code revert. Should be tested in staging first.

## Progressive Rollout

**When to use**: MEDIUM risk features
**Timeline**: 1-2 weeks
**Monitoring**: Standard

### Stages

```
Stage 1: 10% traffic, 1-2 days
Stage 2: 25% traffic, 2-3 days
Stage 3: 50% traffic, 3-5 days
Stage 4: 100% traffic, full launch
```

### Characteristics

- Gradual increase in exposure
- Balance speed and safety
- Clear decision points
- Moderate monitoring overhead

### Good Candidates

- Important features
- Moderate user impact (1-25%)
- Revenue-affecting but not direct payments
- Reversible via feature flag
- Performance-sensitive code

### Example

```
Feature: New search algorithm
Risk: MEDIUM (affects all searches, reversible)
Strategy: Progressive

Timeline:
Week 1:
- Day 1-2: 10% traffic
  Success: Search latency < 200ms, relevance score >= baseline
  Rollback: Latency > 300ms
- Day 3-5: 25% traffic
  Success: User engagement >= baseline
  Rollback: Engagement < 95% baseline

Week 2:
- Day 1-3: 50% traffic
  Success: All metrics stable
  Rollback: Any critical issue
- Day 4: 100% launch

Monitoring:
- Search latency (p50, p95, p99)
- Relevance clicks
- Zero-result rate
- User engagement
```

### Stage Gates

Each stage requires:
1. Previous stage success criteria met
2. No active incidents
3. Stakeholder approval
4. 24h minimum observation period

## Canary Rollout

**When to use**: HIGH risk features
**Timeline**: 4-6 weeks
**Monitoring**: Intensive

### Stages

```
Stage 0: Internal (0.1%, 1-2 days)
Stage 1: Canary (1%, 3-5 days)
Stage 2: Early (5%, 5-7 days)
Stage 3: Expand (10%, 7 days)
Stage 4: Majority (25%, 7 days)
Stage 5: Large (50%, 7 days)
Stage 6: Full (100%)
```

### Characteristics

- Very gradual exposure
- Extensive monitoring
- Multiple decision points
- High confidence before scaling
- Longer time to full rollout

### Good Candidates

- Mission-critical systems (auth, payments)
- High user impact (>25%)
- Direct revenue impact
- New infrastructure/dependencies
- Hard to reverse changes

### Example

```
Feature: New checkout flow
Risk: HIGH (mission-critical, 100% of purchasers)
Strategy: Canary

Timeline:
Week 1:
- Internal (0.1%): 2 days
  Success: Manual testing passes, no crashes
  Rollback: Any error

- Canary (1%): 3 days
  Success: Error rate < 0.1%, conversion >= baseline
  Rollback: Error > 0.5% OR conversion < 90%

Week 2:
- Early (5%): 5 days
  Success: Conversion >= 95% baseline, latency acceptable
  Rollback: Conversion < 90% OR latency > 1s

Week 3:
- Expand (10%): 7 days
  Success: All metrics stable, revenue >= baseline
  Rollback: Revenue < 95% baseline

Week 4:
- Majority (25%): 7 days
  Success: Support tickets normal, no escalations
  Rollback: Ticket spike > 2x

Week 5-6:
- Large (50%): 7 days
  Success: Full week with no issues
  Rollback: Any critical issue

- Full (100%): Launch
  Success: Complete
  Rollback: Available for 1 week post-launch

Monitoring:
- Purchase completion rate (primary)
- Revenue per user
- Error rate (application + HTTP)
- p95 latency
- Payment processor errors
- Support ticket volume
- User sentiment (NPS)
```

### Canary Analysis

At each stage, compare canary vs. control:

```
Metric: Conversion rate
Control (remaining traffic): 10.2%
Canary (staged traffic): 10.1%
Difference: -0.1pp (-1% relative)
Significance: p=0.34 (not significant)
Decision: PROCEED (no degradation detected)
```

### Extended Canary

For extremely high-risk features:
- Stage 0: Shadow mode (backend only, no user impact)
- Stage 0.5: Dark launch (enabled backend, UI hidden)
- Then proceed with standard canary
