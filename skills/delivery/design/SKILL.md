---
name: design
description: |
  Design statistically rigorous A/B tests and experiments.
  Formulate hypotheses, select metrics, calculate sample sizes.
  Discovers analytics and feature flag tools via capability detection.

  Use when: "design experiment", "A/B test", "hypothesis", "sample size",
  "what metrics", "test my feature", "should we experiment"
---

# Design Skill

Design experiments with statistical rigor.

## Quick Start

```bash
# Design experiment from hypothesis
/wicked-garden:delivery:design "Blue CTA increases clicks by 10%"

# Design with context file
/wicked-garden:delivery:design feature-spec.md

# Discover available tools
/wicked-garden:delivery:design --discover
```

## What This Skill Does

1. Formulates clear, testable hypotheses
2. Selects appropriate success metrics
3. Calculates required sample sizes
4. Plans instrumentation strategy
5. Defines success criteria

## Hypothesis Formulation

**Template**:
```
[Action] will [increase/decrease] [Metric] by [Amount] because [Reason]
```

**Good**: "Adding social proof to checkout will increase conversion by 8% because it reduces purchase anxiety"

**Bad**: "New design will be better" (not specific or measurable)

## Metric Selection

**Hierarchy**:
- **Primary**: The ONE metric determining success
- **Secondary**: Supporting metrics for context
- **Guardrail**: Metrics that must not degrade

**Example for checkout optimization**:
- Primary: Purchase completion rate
- Secondary: Time to purchase, cart value
- Guardrail: Page load time, error rate

## Sample Size Calculation

**Quick estimates** (95% confidence, 80% power):
- 5% effect: ~3,200 per variant
- 10% effect: ~800 per variant
- 20% effect: ~200 per variant

See [statistics.md](refs/statistics.md) for detailed formulas.

## Variant Design

**Best practices**:
- Start with 2 variants (control + treatment)
- Make ONE clear change per variant
- Ensure variants are mutually exclusive
- Document variant details clearly

## Instrumentation Planning

**Required tracking**:
```javascript
// Variant assignment
trackEvent('experiment_viewed', {
  experiment: 'checkout_social_proof',
  variant: 'control' | 'treatment',
  user_id: '...'
})

// Primary metric
trackEvent('purchase_completed', {
  experiment: 'checkout_social_proof',
  variant: '...',
  value: 49.99
})
```

## Success Criteria

**Statistical**:
- Significance: p < 0.05
- Confidence: 95%
- Power: 80%

**Business**:
- Minimum effect worth shipping
- Resource constraints
- Timeline limitations

## Output Format

```markdown
## Experiment Design: {Name}

### Hypothesis
{Clear, testable hypothesis}

### Metrics
- **Primary**: {metric} - {how measured}
- **Secondary**: {list}
- **Guardrail**: {list}

### Variants
- **Control**: {current experience}
- **Treatment**: {new experience}

### Sample Size
- Per variant: {n} users
- Total: {total} users
- Duration: {days} at {%} traffic

### Statistical Parameters
- Significance: 0.05
- Confidence: 95%
- Power: 80%
- MDE: {minimum detectable effect}%

### Instrumentation
**Feature Flag**: {name}
**Analytics Events**:
- experiment_viewed
- {primary_metric_event}
- {secondary_metric_events}

### Success Criteria
{What constitutes success}

### Risks & Mitigations
{Potential issues and how to handle}
```

## Capability Discovery

Discovers available tools automatically via capability detection:

**Capabilities needed**:
- `feature-flags`: Feature toggle and flag management
- `analytics`: Event tracking and metrics collection
- `experiment-platform`: Dedicated A/B testing platforms

**Discovery methods**:
- CLI tools presence (check for commands)
- API configuration (config files, environment variables)
- SDK detection (package.json, requirements.txt, go.mod)

Asks "Do I have analytics capability?" not "Do I have Amplitude?"

## Integration

**With wicked-kanban**: Stores design as task comment
**With wicked-qe**: QE provides test scenarios for instrumentation
**With wicked-mem**: Recalls past experiment patterns
**With wicked-product**: Uses product context for hypothesis

## See Also

- [statistics.md](refs/statistics.md) - Statistical concepts and formulas
- `/wicked-garden:delivery:analyze` - Analyze experiment results
- `/wicked-garden:delivery:rollout` - Plan feature rollout
