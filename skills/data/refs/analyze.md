# Data Analysis Rubric

Apply this inline. Route by `--focus` to the right analysis mode. File has been
pre-profiled (columns / types / nulls / sample rows) by the caller.

## EDA output format (default / --focus stats)

```markdown
## Data Analysis Report

**Dataset**: {name}
**Analysis Date**: {date}

### Executive Summary
{2-3 key takeaways}

### Quick Stats
- **Rows**: {count}  **Columns**: {count}  **Date Range**: {start–end}

### Initial Findings
1. {Observable pattern or anomaly}
2. {Interesting correlation or trend}

### Visualization Recommendations
- {Chart type}: {What it shows}

### Next Steps / Questions Raised
- {Follow-up analyses or data needs}

**Confidence**: {HIGH|MEDIUM|LOW}
```

## Statistical analysis patterns

**Distributions**: MIN / Q1 / MEDIAN / Q3 / MAX; histogram or box-plot.
**Categorical**: frequency + percentage breakdown; bar chart.
**Time series**: DATE_TRUNC day/week aggregation; line chart.
**Correlations**: CORR(a, b) spot-check.
**Cohort/RFM**: group by signup month; recency/frequency/monetary.

## Insight pattern

- **Observation**: What the data shows (fact).
- **Insight**: Why it matters (interpretation).
- **Action**: What to do (recommendation).
- **Confidence**: HIGH | MEDIUM | LOW (state sample size + caveats).

**Bad** (just observations): "Average order value is $45", "60% of customers
are in the US".

**Good** (insight with action):
```
### Insight: Weekend Shopping Behavior
**Observation**: Sales peak on Friday (+40% vs weekday avg)
**Insight**: Customers shop for weekend needs on Friday.
**Action**: Launch "Friday Flash Sale" campaign (+15% expected)
**Confidence**: HIGH (consistent over 6 months)
```

## Segmentation methods

- **RFM**: Recency, Frequency, Monetary value.
- **Cohorts**: group by signup / first-purchase month.
- **Geographic**: by region, country, city.
- **Behavioral**: by usage patterns.

## Anomaly detection methods

- Statistical outliers (>3 standard deviations).
- Unusual patterns (volume spikes/drops).
- Temporal anomalies (day-of-week deviations).

## Visualization guidance

| Data Type | Comparison | Best Chart |
|-----------|------------|------------|
| Time series | Trend over time | Line chart |
| Categorical | Compare values | Bar chart |
| Distribution | Show spread | Histogram, Box plot |
| Relationship | Correlation | Scatter plot |
| Composition | Part of whole | Stacked bar, Pie |
| Geographic | Location data | Map (choropleth) |

## Best practices

- **Start simple**: begin with basic aggregations before complex models.
- **Validate assumptions**: check data quality, verify calculations.
- **Tell a story**: lead with the "so what?" and make it actionable.
- **Be honest about uncertainty**: note limitations, quantify confidence.

## Common pitfalls

- **Correlation ≠ Causation**: ice cream and drownings both increase in summer.
- **Simpson's Paradox**: aggregate trend may reverse when segmented.
- **Survivorship Bias**: include failed cases for balanced view.
- **Cherry-picking**: report all patterns, not just favorable ones.

## Detailed templates

See [analysis-templates.md](analysis-templates.md) for full report templates:
exploratory analysis report, insight report, segment analysis, A/B test
results, and anomaly report.

## --focus quality (data-quality mode)

| Dimension | Check |
|-----------|-------|
| Completeness | Null rates per column |
| Uniqueness | Duplicate detection |
| Validity | Type conformance + constraints |
| Consistency | Cross-field validation |
| Timeliness | Freshness metrics |

```markdown
## Data Quality Report

**Dataset**: {name}  **Rows**: {count}  **Columns**: {count}

### Quality Metrics
| Dimension | Score | Issues |
|-----------|-------|--------|
| Completeness | {%} | {null columns} |
| Uniqueness  | {%} | {duplicate rate} |
| Validity    | {%} | {constraint violations} |

### Critical Issues
- {Issue with severity and impact}

### Recommendations
1. {Prioritized action items}
```

## --focus warehouse (warehouse/lakehouse mode)

Evaluate dimensional model fit: Star vs Snowflake vs Data Vault vs Wide Table.
Cover partitioning / clustering / materialization strategy and cost plan.

```markdown
## Warehouse Analysis: {domain}

### Approach
Pattern: {Star|Snowflake|Data Vault|Wide Table}
Justification: {why}

### Schema
#### Fact: {fact_table}
| Column | Type | Description | Source |

#### Dimension: {dim_table}
| Column | Type | SCD Type | Description |

### Performance
- Partitioning: {strategy}   Clustering: {columns}   Materialization: {views vs tables}

### Cost Plan
{Storage tier, compute, optimization levers}
```

## --focus ml (ML-readiness mode)

Assess training data quality for ML: leakage, imbalance, feature distributions,
label quality. See refs/ml.md for full ML pipeline rubric.

## Scenarios block (--scenarios)

When `--scenarios` is set, append:
```yaml
scenarios:
  api:
    - name: "{dataset}_baseline"
      given: "data file at {path}"
      when: "analyze --focus {focus}"
      then: "key finding X observed"
  perf:
    - name: "{dataset}_large_file"
      given: "file with {N} rows"
      when: "profiling runs"
      then: "completes within threshold"
```
