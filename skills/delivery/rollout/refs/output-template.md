# Rollout Plan Output Template

Markdown template for the rollout plan returned by `/wicked-garden:delivery:rollout`. Substitute the placeholders with values from the risk assessment, strategy, and capability-discovery results.

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
