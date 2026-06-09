# Rollout Plan Rubric

Apply this inline. Plan safe, staged feature rollouts with risk assessment, canary
deployment stages, monitoring, and rollback criteria.

## Risk assessment

| Factor | LOW | MEDIUM | HIGH |
|--------|-----|--------|------|
| User impact | <1% users | <25% users | >50% users |
| Revenue impact | none | indirect | direct |
| System criticality | nice-to-have | important | mission-critical |
| Reversibility | instant flag-off | minutes | hours/manual |

## Rollout strategy by risk

| Risk | Strategy | Timeline |
|------|----------|----------|
| LOW | Big bang | 0% → 100% immediately |
| MEDIUM | Progressive | 0% → 10% → 50% → 100% over 2 weeks |
| HIGH | Canary | 0% → 1% → 5% → 10% → 25% → 50% → 100% over 4–6 weeks |

## Stage definition template

```
Stage N:
  Traffic: {percentage}%
  Duration: {time — minimum 24h}
  Success criteria: {metrics with thresholds}
  Rollback criteria: {automatic trigger conditions}
```

## Alert thresholds

- **WARNING**: 1.5x baseline on error rate or latency.
- **CRITICAL**: 2x baseline OR 5% error rate.

**Automatic rollback triggers**: error rate >2x baseline, latency >50% slower,
critical user-reported bugs.
**Manual rollback criteria**: revenue impact, security vulnerability, regulatory issue.

## Communication plan

| Audience | Content | Timing |
|----------|---------|--------|
| Engineering | Technical details, rollback plan | T-2 days |
| Product | Timeline, success criteria | T-2 days |
| Support | User-facing changes, FAQs | T-1 day |
| Leadership | Risk assessment, go/no-go | T-0 |

## Bus event (emit after go/no-go decision)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" \
  wicked.rollout.decided \
  '{"decision":"go","traffic_pct":10,"chain_id":"{chain_id}"}' 2>/dev/null || true
```

`decision`: one of `go`, `no-go`, `paused`. `traffic_pct`: integer 0–100.
Payload: Tier 1 + Tier 2 only — no customer-cohort details.

## Output format

```markdown
## Rollout Plan: {Feature Name}

**Risk Assessment**: {LOW|MEDIUM|HIGH}
**Strategy**: {Progressive|Canary|Big Bang}
**Total Duration**: {duration}

### Stages
| Stage | Traffic | Duration | Success Criteria | Rollback Criteria |
|-------|---------|----------|------------------|-------------------|
| 1     | {%}     | {time}   | {criteria}       | {triggers} |

### Monitoring
**Metrics to Watch**: primary {metric}, error rate {threshold}, latency {threshold}
**Alerts**: WARNING {condition} / CRITICAL {condition}

### Rollback Plan
**Automatic triggers**: {trigger 1}, {trigger 2}
**Rollback procedure**:
1. Set feature flag to 0%
2. Verify traffic shifted
3. Monitor error recovery
4. Notify stakeholders

### Communication
- [ ] Engineering notified  [ ] Product aligned  [ ] Support prepared  [ ] Leadership informed

### Next Steps
1. Configure feature flag: {flag_name}
2. Set up monitoring: {dashboard}
3. Stage 1 launch: {date/time}
```

## Best practices

- Start with internal users (0.1%), then canary (1–5%), then expand.
- Each stage: minimum 24h to collect data, maximum 1 week to maintain momentum.
- Always prefer feature flags over code deploys for rollback speed.
- For HIGH risk: consider shadow mode or dark launch before Stage 1.
