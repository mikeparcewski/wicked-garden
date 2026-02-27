---
description: Analyze customer feedback for themes, sentiment, and trends
argument-hint: "[--theme X] [--sentiment pos|neg] [--trend period]"
---

# /wicked-garden:product-analyze

Analyze aggregated customer feedback to extract themes, sentiment patterns, and trends over time.

## Usage

```bash
# Analyze all available feedback
/wicked-garden:product-analyze

# Focus on specific theme
/wicked-garden:product-analyze --theme "mobile experience"
/wicked-garden:product-analyze --theme "performance"

# Filter by sentiment
/wicked-garden:product-analyze --sentiment negative
/wicked-garden:product-analyze --sentiment positive

# Trend analysis
/wicked-garden:product-analyze --trend "last-quarter"
/wicked-garden:product-analyze --trend "week-over-week"

# Segment analysis
/wicked-garden:product-analyze --segment enterprise
/wicked-garden:product-analyze --segment "new-users"
```

## Instructions

### 1. Load Feedback Data

Read from voice data store or recent listen results:

```bash
# Check for aggregated feedback
ls ~/.something-wicked/voice/feedback/
```

If no data found, prompt user to run `/wicked-garden:product-listen` first.

### 2. Dispatch to Feedback Analyst

```
Task(
  subagent_type="wicked-garden:product/feedback-analyst",
  prompt="""Analyze customer feedback for patterns and insights.

## Feedback Data
{aggregated feedback items - include full content}

## Analysis Parameters
- Focus: {theme, sentiment, or trend filter if specified}
- Time period: {timeframe}

## Analysis Required

1. **Theme Extraction**: What topics appear repeatedly?
   - Identify recurring themes via keyword clustering, topic modeling, category frequency
   - For each theme: name, frequency, sentiment, trend, sample quotes

2. **Sentiment Patterns**: What drives positive/negative sentiment?
   - Overall sentiment breakdown
   - Sentiment by theme
   - Sentiment by segment
   - Sentiment drivers (root causes)

3. **Trend Detection**: What's changing over time?
   - Volume trends (more/less feedback)
   - Sentiment trends (improving/declining)
   - Emerging themes (new topics)
   - Resolved themes (topics decreasing)

4. **Segment Differences**: How do user groups differ?

5. **Priority Signals**: What indicates urgency?

## Return Format

Provide:
- Summary (period, items analyzed, overall sentiment + trend)
- Top Themes table (theme, frequency, sentiment, trend)
- Theme deep dives (frequency, sentiment, quotes, drivers, recommendations)
- Sentiment drivers (positive and negative)
- Trends table (volume, positive %, top theme changes)
- Segment insights
- Actionable recommendations
"""
)
```

### 3. Present Analysis

Format the agent's output into the standard analysis report structure.

```markdown
## Feedback Analysis Report

### Summary
**Period**: {timeframe}
**Items Analyzed**: {count}
**Overall Sentiment**: {score} ({trend})

### Top Themes

| Theme | Frequency | Sentiment | Trend |
|-------|-----------|-----------|-------|
| {theme} | {count} ({%}) | {sentiment} | {arrow} |

### Theme Deep Dive

#### 1. {Theme Name}
**Frequency**: {count} mentions ({%} of total)
**Sentiment**: {score} - {positive/negative/mixed}
**Trend**: {increasing/stable/decreasing}

**What customers say**:
> "{representative quote 1}"
> "{representative quote 2}"

**Key drivers**:
- {driver 1}
- {driver 2}

**Recommendation**: {actionable insight}

### Sentiment Drivers

**Positive Sentiment Drivers**:
1. {feature/experience that delights}
2. {another positive driver}

**Negative Sentiment Drivers**:
1. {pain point causing frustration}
2. {another negative driver}

### Trends

| Metric | This Period | Last Period | Change |
|--------|-------------|-------------|--------|
| Volume | {n} | {n} | {%} |
| Positive % | {%} | {%} | {change} |
| Top Theme | {theme} | {theme} | {change} |

### Segment Insights

| Segment | Sentiment | Top Theme | Notable |
|---------|-----------|-----------|---------|
| {segment} | {score} | {theme} | {insight} |

### Recommendations

1. **{Priority}**: {Actionable recommendation}
   - Evidence: {supporting data}
   - Impact: {expected outcome}

### Next Steps
Run `/wicked-garden:product-synthesize` to generate actionable recommendations.
```

## Integration

- **wicked-garden:product-listen**: Run first to aggregate feedback
- **wicked-garden:product-synthesize**: Run after to generate recommendations
- **wicked-kanban**: Track insights as tasks
- **wicked-mem**: Store analysis for future reference

## Example

```
User: /wicked-garden:product-analyze --theme "performance"

Claude: I'll analyze feedback related to performance.

[Loads aggregated feedback]
[Dispatches to feedback-analyst agent]
[Agent extracts themes and patterns]

## Feedback Analysis Report

### Summary
**Period**: Last 30 days
**Items Analyzed**: 45 (filtered to performance theme)
**Overall Sentiment**: -0.3 (declining)

### Performance Theme Deep Dive

**Frequency**: 45 mentions (28% of total)
**Sentiment**: Negative (-0.3)
**Trend**: Increasing (up 40% from last month)

**What customers say**:
> "The dashboard takes forever to load now. It used to be instant."
> "Search is painfully slow with large datasets."
> "Mobile app has become unusable - constant lag."

**Key drivers**:
- Dashboard load time (18 mentions)
- Search performance (12 mentions)
- Mobile responsiveness (9 mentions)

### Sentiment Drivers

**Negative Sentiment Drivers**:
1. Dashboard load time >5s (was <1s before)
2. Search timing out on large result sets
3. Mobile app memory issues causing lag

### Recommendations

1. **Critical**: Investigate dashboard performance regression
   - Evidence: 18 complaints in 30 days, 40% increase
   - Impact: Likely affecting retention, multiple churn signals
```

## Next Step

After analyzing customer feedback, continue the customer voice pipeline:

```bash
/wicked-garden:product-synthesize
```

This will convert the insights into prioritized, actionable recommendations with effort estimates and expected outcomes.
