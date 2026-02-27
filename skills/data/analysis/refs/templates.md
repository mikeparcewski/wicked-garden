# Analysis Output Templates

Standard templates for data analysis reports.

## Exploratory Analysis Report

```markdown
## Exploratory Analysis: {dataset}

**Date**: {date}
**Analyst**: {name}
**Rows**: {count}

### Quick Stats
- **Date Range**: {start} to {end}
- **Key Metrics**: {summary}
- **Data Quality**: {score}/100

### Data Profile
| Column | Type | Nulls | Unique | Min | Max |
|--------|------|-------|--------|-----|-----|
| {col}  | {type} | {pct}% | {n} | {min} | {max} |

### Distributions
{Summary of key metric distributions}

### Key Findings
1. {Finding with supporting data}
2. {Finding with supporting data}
3. {Finding with supporting data}

### Data Quality Issues
- {Issue and impact}

### Questions Raised
- {Question needing further investigation}

### Next Steps
- {Recommended follow-up analysis}
```

## Insight Report

```markdown
## Data Insights: {topic}

**Context**: {why this analysis}
**Data**: {source and timeframe}
**Confidence**: {HIGH|MEDIUM|LOW}

### Executive Summary
{Top 3 takeaways in bullet points}

---

### Insight 1: {Title}

**Observation**: {What the data shows - facts only}

**Insight**: {What it means - interpretation}

**Action**:
- Specific action 1
- Expected impact: {quantified if possible}

**Confidence**: {HIGH|MEDIUM|LOW}

---

### Insight 2: {Title}
{Same structure as above}

---

### Supporting Analysis
{Methodology and data quality notes}

### Assumptions & Limitations
- {Key assumption}
- {Data limitation}

### Next Steps
1. {Immediate action}
2. {Follow-up analysis}
```

## Segment Analysis Report

```markdown
## Segment Analysis: {dimension}

**Segments**: {n segments}
**Method**: {RFM, cohort, behavioral, etc.}

### Segment Overview
| Segment | Size | % Total | Avg Value | Key Trait |
|---------|------|---------|-----------|-----------|
| {name}  | {n}  | {pct}%  | ${avg}    | {trait}   |

### Segment Profiles

#### Segment 1: {Name}
- **Size**: {n} ({pct}%)
- **Characteristics**: {description}
- **Value**: ${total} ({pct}% of revenue)
- **Recommended Action**: {action}

### Cross-Segment Insights
- {Pattern across segments}

### Recommended Actions
1. **{Segment}**: {Action}
```

## A/B Test Results

```markdown
## A/B Test Results: {experiment name}

**Test Period**: {start} to {end}
**Sample Size**: Control: {n}, Treatment: {n}

### Summary
| Metric | Control | Treatment | Lift | Confidence |
|--------|---------|-----------|------|------------|
| {KPI}  | {val}   | {val}     | +{x}%| {pct}%     |

### Statistical Details
- **Test Type**: {t-test, chi-square, etc.}
- **p-value**: {p}
- **Confidence Interval**: [{low}, {high}]

### Recommendation
{SHIP / DO NOT SHIP / NEEDS MORE DATA}

### Caveats
- {Limitation or consideration}
```

## Anomaly Report

```markdown
## Anomaly Detection: {metric}

**Period**: {date range}
**Method**: {statistical, isolation forest, etc.}

### Anomalies Detected
| Date | Value | Expected | Deviation | Severity |
|------|-------|----------|-----------|----------|
| {date} | {val} | {expected} | {+/-x}% | {HIGH/MED/LOW} |

### Investigation

#### Anomaly 1: {Date}
- **Observed**: {value}
- **Expected**: {value} (based on {method})
- **Possible Causes**:
  1. {Hypothesis}
  2. {Hypothesis}
- **Impact**: {business impact}
- **Action**: {recommendation}

### Systemic Issues
- {Pattern in anomalies}
```
