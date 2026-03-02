---
name: analyze
description: |
  Sentiment analysis, theme extraction, and trend detection from customer feedback.

  Use when: "what are customers saying about X", "feedback trends",
  "analyze customer feedback", "sentiment analysis", "customer themes",
  "what's the top complaint"
---

# Analyze Skill

Extract themes, sentiment, and trends from aggregated customer feedback.

## When to Use

- After running `/wicked-garden:product:listen`
- User asks "what are customers saying about X"
- Need to understand sentiment trends
- Preparing customer insights for product decisions

## Usage

```bash
# Analyze all recent feedback
/wicked-garden:product:analyze

# Analyze specific theme
/wicked-garden:product:analyze --theme "mobile experience"

# Analyze sentiment only
/wicked-garden:product:analyze --sentiment negative

# Trend analysis
/wicked-garden:product:analyze --trend "last-quarter"

# Segment analysis
/wicked-garden:product:analyze --segment enterprise
```

## Analysis Types

### 1. Sentiment Analysis
- Classify: positive/negative/neutral/mixed
- Score intensity: strong/moderate/mild
- Indicators: See [refs/sentiment-patterns.md](refs/sentiment-patterns.md)

### 2. Theme Extraction
- Cluster by keywords and co-occurrence
- Categories: Product, Experience, Business
- See [refs/algorithms.md](refs/algorithms.md) for clustering logic

### 3. Trend Detection
- Compare time periods (week, month, quarter)
- Categories: Emerging, Growing, Stable, Declining, Resolved
- Threshold: >50% = Growing, >30% decline = Declining

### 4. Priority Scoring
```
Priority = (Frequency × Severity × Urgency) / Total_Feedback
```
See [refs/algorithms.md](refs/algorithms.md) for detailed scoring.

## Analysis Process

1. **Load Feedback Data**:
   ```bash
   # Count total items
   find {SM_LOCAL_ROOT}/wicked-product/voice/feedback/ -name "*.md" | wc -l

   # Load recent feedback
   find {SM_LOCAL_ROOT}/wicked-product/voice/feedback/ -name "*.md" -mtime -30
   ```

2. **Extract Themes**:
   - Keyword frequency analysis
   - Tag co-occurrence
   - Natural language clustering

3. **Score Sentiment**:
   - Classify each item (positive/negative/neutral/mixed)
   - Score intensity (strong/moderate/mild)
   - Calculate net sentiment

4. **Detect Trends**:
   - Group by time period (week, month, quarter)
   - Compare frequencies
   - Identify direction (up, down, stable)

5. **Segment Analysis**:
   - Group by customer segment (if available)
   - Compare sentiment across segments
   - Identify segment-specific themes

## Output Format

```markdown
## Analysis: {Topic or Timeframe}

### Sentiment Overview
- Net Sentiment: {+/-N} ({X}% positive, {Y}% negative)
- Strong Emotions: {count} highly positive, {count} highly negative
- Trend: {IMPROVING/DECLINING/STABLE} compared to previous period

### Top Themes (by priority)
1. **{Theme}** - Priority: {score}
   - Frequency: {count} mentions ({%} of total)
   - Sentiment: {positive/negative/mixed} ({intensity})
   - Trend: {GROWING/STABLE/DECLINING} ({+/-X}% vs. baseline)
   - Severity: {CRITICAL/HIGH/MEDIUM/LOW}
   - Key quote: "{representative example}"

{Top 5 themes}

### Emerging Patterns
- **{New Theme}**: Recently appeared, {count} mentions
- **{Growing Theme}**: {X}% increase from last period

### Segment Insights
- **{Segment}**: {sentiment + top theme}

### Recommendations
{1-3 actionable recommendations based on analysis}
```

## Technical Implementation

See [refs/algorithms.md](refs/algorithms.md) for detailed analysis algorithms.

## Integration

### With wicked-crew (Auto Context)

```python
# Triggered by product:requirements:started event
if event.type == "product:requirements:started":
    # Analyze recent feedback for feature context
    analysis = analyze(days=30, tags=["feature-request"])
    emit_signal("voice:analysis:ready", analysis)
```

### With wicked-kanban (Link to Tasks)

```python
# Tag themes with related task IDs
if has_plugin("wicked-kanban"):
    tasks = search_tasks(theme.keywords)
    theme.related_tasks = tasks
```

## Storage

Analysis results stored at: `{SM_LOCAL_ROOT}/wicked-product/voice/analysis/{theme}/{date}.md`

## Rules

- Limit to top 5 themes (context efficiency)
- Always include sample size (N=X)
- Provide confidence levels for trends
- Include representative quotes
- Keep output under 800 words
- Distinguish frequency from severity
