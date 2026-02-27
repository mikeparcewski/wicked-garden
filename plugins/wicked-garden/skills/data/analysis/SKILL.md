---
name: analysis
description: |
  Data analysis and insights generation: exploratory analysis, statistical methods, visualization guidance.
  Use when exploring datasets, finding patterns, or generating business insights.

  Use when:
  - "analyze this data"
  - "what patterns are in the data"
  - "generate insights from"
  - "exploratory data analysis"
  - "what does this data tell us"
---

# Data Analysis Skill

Explore datasets, identify patterns, and generate actionable insights.

## Quick Start

```bash
/wicked-garden:data-analysis explore data/sales.csv
```

This will:
1. Profile the data
2. Generate descriptive statistics
3. Identify patterns and trends
4. Suggest visualizations
5. Provide initial insights

After exploration, ask specific questions:
- "What's the trend in sales over time?"
- "Which customer segments are most valuable?"
- "Are there any anomalies in the data?"

## Analysis Workflow

### 1. Profile & Understand

```bash
/wicked-garden:data-numbers sales.csv
```

**Key questions**:
- What's the grain? (one row per what?)
- What's the date range?
- What are the key metrics?
- Any obvious data quality issues?

### 2. Explore Patterns

**Basic explorations**:
- Distributions (histograms, percentiles)
- Categorical breakdowns (frequency tables)
- Time trends (daily/monthly aggregations)
- Correlations (relationship between metrics)

### 3. Segment Analysis

**Common segmentations**:
- **RFM**: Recency, Frequency, Monetary value
- **Cohorts**: Group by signup/first purchase month
- **Geographic**: By region, country, city
- **Behavioral**: By usage patterns

### 4. Anomaly Detection

**Detection methods**:
- Statistical outliers (>3 standard deviations)
- Unusual patterns (volume spikes/drops)
- Temporal anomalies (day-of-week deviations)

## Insight Generation

### Pattern: Observation → Insight → Action

**Bad** (just observations):
- Average order value is $45
- 60% of customers are in the US

**Good** (insights with actions):
```
### Insight: Weekend Shopping Behavior
**Observation**: Sales peak on Friday (+40% vs weekday avg)
**Insight**: Customers shop for weekend needs on Friday.
**Action**: Launch "Friday Flash Sale" campaign (+15% expected)
**Confidence**: HIGH (consistent over 6 months)
```

## Visualization Guidance

| Data Type | Comparison | Best Chart |
|-----------|------------|------------|
| Time series | Trend over time | Line chart |
| Categorical | Compare values | Bar chart |
| Distribution | Show spread | Histogram, Box plot |
| Relationship | Correlation | Scatter plot |
| Composition | Part of whole | Stacked bar, Pie |
| Geographic | Location data | Map (choropleth) |

## Integration

**wicked-garden:data-numbers** - Primary tool for data queries:
```bash
/wicked-garden:data-numbers data.csv
```

**wicked-kanban** - Document insights as tasks
**wicked-mem** - Store analysis patterns for reuse

## Best Practices

- **Start simple**: Begin with basic aggregations before complex models
- **Validate assumptions**: Check data quality, verify calculations
- **Tell a story**: Lead with the "so what?" and make it actionable
- **Be honest about uncertainty**: Note limitations, quantify confidence

## Common Pitfalls

- **Correlation ≠ Causation**: Ice cream and drownings both increase in summer
- **Simpson's Paradox**: Aggregate trend may reverse when segmented
- **Survivorship Bias**: Include failed cases for balanced view
- **Cherry-picking**: Report all patterns, not just favorable ones

## Reference

For detailed content:
- [Output Templates](refs/templates.md) - Report and insight templates
