# Experiment Design Output Template

Markdown template for the experiment design output emitted by the `delivery:design` skill. Substitute the placeholders with values from the hypothesis, metrics, sample-size, and instrumentation steps.

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
