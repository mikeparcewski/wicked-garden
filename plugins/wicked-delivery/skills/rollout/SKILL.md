---
name: rollout
description: |
  Plan and coordinate progressive feature rollouts.
  Risk assessment, canary deployments, feature flag management,
  rollback procedures. Discovers deployment tools via capabilities.

  Use when: "roll out feature", "progressive rollout", "canary deployment",
  "feature flag", "rollback plan", "launch feature", "deploy gradually"
---

# Rollout Skill

Plan and execute safe, progressive feature rollouts.

## Quick Start

```bash
# Plan rollout for feature
/wicked-delivery:rollout feature-new-dashboard

# Plan with specific strategy
/wicked-delivery:rollout feature-checkout --strategy canary

# Discover deployment tools
/wicked-delivery:rollout --discover
```

## What This Skill Does

1. Assesses rollout risk
2. Selects appropriate rollout strategy
3. Defines progressive stages
4. Establishes success and rollback criteria
5. Creates monitoring and communication plan

## Risk Assessment

### Risk Factors

**User impact**: <1% (LOW) | 1-25% (MEDIUM) | >25% (HIGH)
**Revenue impact**: Non-revenue (LOW) | Funnel (MEDIUM) | Direct payment (HIGH)
**System criticality**: Nice-to-have (LOW) | Important (MEDIUM) | Mission-critical (HIGH)
**Reversibility**: Flag toggle (HIGH) | Schema change (MEDIUM) | Data migration (LOW)

### Overall Risk

```
Risk = MAX(user, revenue, criticality) + reversibility_penalty
```

## Rollout Strategies

| Risk | Strategy | Timeline | Stages |
|------|----------|----------|--------|
| LOW | Big Bang | Immediate | 0% → 100% |
| MEDIUM | Progressive | 1-2 weeks | 0% → 10% → 25% → 50% → 100% |
| HIGH | Canary | 4-6 weeks | 0% → 1% → 5% → 10% → 25% → 50% → 100% |

See [strategies.md](refs/strategies.md) for detailed guidance.

## Stage Definition

For each stage:
- **Traffic percentage**: 1%, 10%, 25%, 50%, 100%
- **Duration**: 24h to 1 week
- **Success criteria**: Error rate, conversion, performance
- **Rollback criteria**: Automatic and manual triggers

## Success & Rollback Criteria

**Success** (all must pass):
- Primary metric stable or improved
- Error rate within bounds
- Performance acceptable
- No critical bugs

**Automatic rollback**:
- Error rate >2x baseline
- Performance >2x latency
- Availability <99.5%

**Manual rollback**:
- Revenue impact detected
- Security vulnerability
- Regulatory issue

## Monitoring Plan

**Business**: Primary metric, revenue, retention
**Technical**: Error rate, latency (p50/p95/p99), throughput
**User**: Support tickets, feedback, crashes

**Alerts**:
- WARNING: 1.5x baseline
- CRITICAL: 2x baseline or 5% error rate

## Communication Plan

**Stakeholders**: Engineering (technical), Product (timeline), Support (FAQs), Leadership (risk)

**Timeline**:
- T-2 days: Pre-rollout notification
- T-0: Rollout begins
- T+checkpoints: Progress updates
- T+complete: Completion summary

## Output Format

```markdown
## Rollout Plan: {Feature Name}

### Risk Assessment
- **Overall Risk**: {LOW | MEDIUM | HIGH}
- **User Impact**: {%} of users
- **Revenue Impact**: {LOW | MEDIUM | HIGH}
- **Reversibility**: {HIGH | MEDIUM | LOW}

### Strategy: {Progressive | Canary | Big Bang}
**Duration**: {weeks}
**Feature Flag**: {flag_name}

### Rollout Stages

| Stage | Traffic | Duration | Success Criteria | Auto Rollback |
|-------|---------|----------|------------------|---------------|
| 1 | 1% | 24h | Error < 0.1% | Error > 0.5% |
| 2 | 10% | 3d | Conversion >= baseline | Conv < 95% |

### Monitoring
**Dashboard**: {url}
**Key Metrics**: {list}
**Alerts**: WARNING ({conditions}), CRITICAL ({conditions})

### Rollback Plan
**Automatic**: {triggers}
**Manual**: {criteria}
**Procedure**: 1. Set flag to 0%, 2. Verify, 3. Monitor, 4. Notify

### Communication
**Pre-Launch**: {stakeholder checklist}
**During**: {update frequency}
**Post-Launch**: {summary and learnings}

### Stage Gate Checklist
- [ ] Feature flag configured
- [ ] Monitoring live
- [ ] Alerts tested
- [ ] On-call rotation set
- [ ] Rollback tested

### Next Steps
1. {Action 1}
2. {Action 2}
```

## Capability Discovery

Discovers deployment tools automatically via capability detection:

**Capabilities needed**:
- `feature-flags`: Feature toggle and flag management
- `deployment`: Progressive rollout and canary deployment tools
- `monitoring`: Metrics, dashboards, and alerting

**Discovery methods**:
- CLI tools (container orchestration, feature flag CLIs, IaC tools)
- Configuration files (deployment manifests, infrastructure configs)
- Environment variables (API keys, endpoints)
- SDK detection (package dependencies)

Asks "Do I have deployment capability?" not "Do I have Kubernetes?"
Gracefully degrades to manual procedures when capabilities unavailable.

## Integration

**With wicked-kanban**: Tracks rollout progress per stage
**With wicked-qe**: Uses test scenarios for validation
**With wicked-mem**: Recalls past rollout learnings
**With wicked-delivery:analyze**: Uses experiment results for confidence

## See Also

- [strategies.md](refs/strategies.md) - Detailed rollout strategies
- `/wicked-delivery:design` - Design experiments
- `/wicked-delivery:analyze` - Analyze results before rollout
