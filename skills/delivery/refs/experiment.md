# Experiment Design Rubric

Apply this inline. Design statistically rigorous A/B test experiments with proper
hypothesis formulation, metric selection, sample size calculation, and instrumentation.

## Hypothesis formulation

**Good format**: `"[Action] will [increase/decrease] [Metric] by [Amount] because [Reason]"`

Examples:
- "Blue CTA will increase clicks by 10% because it provides better contrast"
- "Auto-save will reduce abandonment by 15% because users fear losing progress"

Bad: "Users will like the new design" (not measurable), "Feature X is better" (no direction).

## Metrics hierarchy

1. **Primary** — the ONE metric that determines success (e.g. conversion rate).
2. **Secondary** — supporting metrics to understand impact (time-to-convert, cart value).
3. **Guardrail** — metrics that must NOT degrade (page load time, error rate).

## Sample size rules of thumb

| Minimum Detectable Effect | Samples per variant |
|--------------------------|---------------------|
| 5% | ~3,200 |
| 10% | ~800 |
| 20% | ~200 |

Standard parameters: significance α = 0.05, power 1−β = 0.80, confidence 95%.
Adjust for multiple variants (Bonferroni correction) and sequential testing.

## Variant design

- **Control**: current experience.
- **Treatment(s)**: new experience(s) — limit to 2–3 variants total.
- One clear change per variant; variants mutually exclusive.

## Instrumentation plan

```
experiment_viewed    {variant, user_id, timestamp}
primary_metric_achieved  {variant, user_id, value}
secondary_metric_achieved {variant, user_id, value}
```

Implementation: feature flag for assignment, analytics events for metrics, logging for debug.

## Success criteria

- Statistical: p < 0.05, 95% confidence, 80% power.
- Business: minimum effect worth shipping + maximum acceptable risk.

## Bus event (emit after experiment concludes)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" \
  wicked.experiment.concluded \
  '{"winner":"variant_a","significance":0.95,"chain_id":"{chain_id}"}' 2>/dev/null || true
```

`winner`: one of `variant_a`, `variant_b`, `inconclusive`. `significance`: float in [0.0, 1.0].
Payload: Tier 1 + Tier 2 only — no customer-cohort details, no per-user data.

## Output format

```markdown
## Experiment Design

**Hypothesis**: {clear hypothesis}

### Metrics
- **Primary**: {metric} — {definition}
- **Secondary**: {metrics}
- **Guardrail**: {metrics}

### Variants
- **Control**: {description}
- **Treatment**: {description}

### Sample Size
- Per variant: {n}  Total: {total}  Duration: {duration} at {traffic_rate}%

### Statistical Parameters
- Significance: 0.05  Confidence: 95%  Power: 80%  MDE: {mde}%

### Instrumentation Plan
{Feature flags, analytics events, logging}

### Success Criteria
{What makes this experiment a success}

### Risks
{Potential issues and mitigations}

### Next Steps
1. Set up feature flag
2. Implement instrumentation
3. Run in staging
4. Launch to {x}% traffic
```

## Common pitfalls

- Multiple testing without correction.
- Peeking at results early (inflates Type I error).
- Changing metrics mid-experiment.
- Confounding variables (seasonality, concurrent launches).
