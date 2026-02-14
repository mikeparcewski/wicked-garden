---
description: Aggregate customer feedback from available sources
argument-hint: "[--capability type] [--days N] [--tags x,y]"
---

# /wicked-product:listen

Aggregate customer feedback from discovered sources across support, surveys, social, and direct channels.

## Usage

```bash
# Listen to all available sources (auto-discovers)
/wicked-product:listen

# Specific capability type
/wicked-product:listen --capability support-tickets
/wicked-product:listen --capability surveys
/wicked-product:listen --capability conversations

# Time window
/wicked-product:listen --days 30
/wicked-product:listen --since "2026-01-01"

# Filter by tags
/wicked-product:listen --tags bug,feature-request

# Limit results
/wicked-product:listen --limit 50
```

## Instructions

### 1. Discover Available Sources

Check for feedback data in common locations:

```bash
# Check for voice data store
ls ~/.something-wicked/voice/feedback/ 2>/dev/null

# Check for exported feedback files
find . -name "*feedback*" -o -name "*survey*" -o -name "*tickets*" 2>/dev/null | head -10

# Check for issue trackers with customer labels
gh issue list --label "customer-reported" 2>/dev/null | head -5
```

### 2. Dispatch to Customer Advocate

```
Task(
  subagent_type="wicked-product:customer-advocate",
  prompt="""Aggregate customer feedback from available sources.

## Sources Discovered
{list of sources found with paths/URLs}

## Parameters
- Time window: {days or date range}
- Filters: {tags, capability type}

## Task

For each source:
1. Extract feedback items
2. Normalize to standard format (ID, source, date, author, content, sentiment, tags, priority)
3. Tag with sentiment (positive/negative/neutral) and category
4. Prioritize by impact (critical/high/medium/low)

## Return Format

Provide:
- Sources table (source, items count, status)
- Quick stats (total, sentiment %, top tags, critical count)
- Recent highlights (top 5-10 items with excerpts)
- Next steps recommendation
"""
)
```

### 3. Present Summary

Format the agent's output into the standard listening report structure.

```markdown
## Listening Report: {Timeframe}

### Sources Discovered
| Source | Items | Status |
|--------|-------|--------|
| {source} | {count} | Active |

### Quick Stats
- **Total Items**: {count}
- **Sentiment**: {%pos} positive, {%neg} negative, {%neu} neutral
- **Top Tags**: {tag1} ({count}), {tag2} ({count})
- **Critical Items**: {count}

### Recent Highlights

#### 1. {Title} - {source} - {date}
**Sentiment**: {sentiment} | **Priority**: {priority}
> "{excerpt of customer quote}"

{Top 5-10 items}

### Next Steps
Run `/wicked-product:analyze` to extract themes and trends.
```

## Storage

Feedback stored at: `~/.something-wicked/voice/feedback/{source}/{YYYY-MM}/{id}.md`

## Integration

- **wicked-mem**: Recall past customer insights
- **wicked-kanban**: Log critical feedback as tasks
- **wicked-crew**: Auto-trigger during clarify phase

## Example

```
User: /wicked-product:listen --days 7

Claude: I'll aggregate customer feedback from the last 7 days.

[Discovers available sources]
[Dispatches to customer-advocate agent]
[Agent aggregates and normalizes feedback]

## Listening Report: Last 7 Days

### Sources Discovered
| Source | Items | Status |
|--------|-------|--------|
| GitHub Issues | 12 | Active |
| feedback.csv | 8 | Active |

### Quick Stats
- **Total Items**: 20
- **Sentiment**: 35% positive, 45% negative, 20% neutral
- **Top Tags**: bug (8), feature-request (6), performance (4)
- **Critical Items**: 2

### Recent Highlights

#### 1. App crashes on large file upload - GitHub - Jan 25
**Sentiment**: negative | **Priority**: critical
> "Every time I try to upload a file over 50MB, the app just freezes and crashes."

#### 2. Love the new dark mode! - feedback.csv - Jan 24
**Sentiment**: positive | **Priority**: low
> "Finally! Dark mode is exactly what I needed. Thank you!"

### Next Steps
Run `/wicked-product:analyze` to extract themes and trends.
```

## Next Step

After aggregating customer feedback, continue the customer voice pipeline:

```bash
/wicked-product:analyze
```

This will analyze the collected feedback for recurring themes, sentiment patterns, and trends over time.
