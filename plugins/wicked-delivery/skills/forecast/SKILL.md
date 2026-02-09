---
name: forecast
description: |
  Cloud cost forecasting and budget planning. Project future costs based on trends,
  model growth scenarios, and provide budget recommendations with confidence ranges.

  Use when: "forecast costs", "budget planning", "project spending",
  "future costs", "capacity planning costs", "cost projections"
---

# Forecast Skill

Project future cloud costs with trend analysis and scenario modeling.

## Purpose

Enable proactive cost planning through:
- Historical trend analysis
- Multi-scenario forecasting
- Capacity planning cost models
- Budget recommendations
- Forecast accuracy tracking

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-delivery:forecast` | Full forecast |
| `/wicked-delivery:forecast --monthly` | Monthly projections |
| `/wicked-delivery:forecast --quarterly` | Quarterly planning |
| `/wicked-delivery:forecast --capacity [plan]` | Model growth |

## Process

### 1. Gather Historical Data

**Required** (6+ months): Monthly costs, service breakdown, usage metrics, business metrics

**Sources**: wicked-mem, cloud cost APIs, past invoices

```bash
wicked-mem recall "finops/monthly-costs/*" --limit 12
```

### 2. Analyze Trends

Methods: Growth rate, linear regression, seasonal adjustment

See [Forecasting Methods](refs/methods.md).

### 3. Model Scenarios

**Best Case**: Lower growth, optimizations succeed
**Likely Case**: Expected growth, stable pricing
**Worst Case**: Higher growth, delays

### 4. Incorporate Business Context

```bash
wicked-product recall "growth-projections"
```

Factors: User growth, launches, expansion, campaigns
Translation: +20% users → +15% compute

### 5. Model Capacity Planning

```
Current: 100 servers @ $50/mo = $5,000
Growth: +20% per quarter
With optimizations: Net growth 35% (vs 108%)
```

See [Capacity Models](refs/capacity.md).

### 6. Generate Forecast

Monthly breakdown with base, variable, projects
Confidence ranges: Best (-20%), Likely, Worst (+30%)

### 7. Set Budget Recommendations

```
Budget = Likely Forecast × 1.10 (10% buffer)
```

Alert thresholds: 50%, 80%, 100%

### 8. Track Accuracy

```
Error = |Forecasted - Actual| / Actual × 100%
Targets: 1-mo <5%, 3-mo <10%, 12-mo <20%
```

## Integration

**wicked-mem**: Store/retrieve forecasts
**wicked-product**: Align with business plans
**FinOps Analyst**: Historical data
**Cost Optimizer**: Planned optimizations

## Output Format

```markdown
## Cloud Cost Forecast: {Period}

### Executive Summary
**Current**: ${current}
**Forecasted**: ${forecast}
**Budget**: ${budget}
**Growth**: {%}%/month
**Confidence**: {HIGH|MEDIUM|LOW}

### Historical Trend
{6 months data}

### Scenarios
**Best**: ${best} - {assumptions}
**Likely**: ${likely} - {assumptions} ⭐
**Worst**: ${worst} - {assumptions}

### Monthly Breakdown
| Month | Base | Variable | Projects | Total | Budget |
{rows}

### Cost Drivers
1. Business growth: {%}%
2. Infrastructure changes
3. Optimizations: -{%}%

### Budget Recommendation
**Budget**: ${budget}
**Alerts**: 50%, 80%, 100%

### Risks
| Risk | Probability | Impact | Mitigation |
{rows}

### Assumptions
{list}

### Validation
**Next Review**: {date}
```

## Forecasting Techniques

**Linear Regression**: Clear trend
**Exponential Smoothing**: Recent data emphasis
**Seasonal Decomposition**: Repeating patterns
**Scenario Modeling**: Uncertainty

See [Methods](refs/methods.md) for details.

## Events

Published:
- `[finops:forecast:started:success]`
- `[finops:forecast:completed:success]`
- `[finops:forecast:validated:success]`

## Configuration

```yaml
forecasting:
  default_period: quarterly
  scenarios:
    best_case_factor: 0.80
    worst_case_factor: 1.30
  buffer_percent: 10
```

## Tips

1. **Use Real Data**: Trends beat assumptions
2. **Provide Ranges**: Not single points
3. **Document Assumptions**: Be explicit
4. **Track Accuracy**: Learn from misses
5. **Update Frequently**: Quarterly minimum
6. **Separate Components**: Base vs variable
7. **Business Context**: Align with growth

## Common Pitfalls

- Straight-line extrapolation (ignores changes)
- Overconfidence (forecasting is uncertain)
- No seasonality (Q4 ≠ Q2)
- Forgetting one-time costs
- No validation

## Reference Materials

- [Forecasting Methods](refs/methods.md)
- [Capacity Planning Models](refs/capacity.md)
- [Scenario Analysis Guide](refs/scenarios.md)
