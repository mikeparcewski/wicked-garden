---
name: listen
description: |
  Aggregate customer feedback from discovered sources across support, surveys,
  social, and direct channels. Use when you need to gather customer voice data
  to inform product decisions or understand customer sentiment.
---

# Listen Skill

Aggregate customer feedback from multiple channels with automatic source discovery.

## When to Use

- Starting product requirements (gather customer needs)
- Investigating customer pain points
- Reviewing recent feedback
- User asks to "listen to customers" or "what are customers saying"

## Capability Discovery

The skill automatically discovers available feedback capabilities:

### support-tickets capability
```bash
# Discovers CLI tools, APIs, and exports that provide ticket data
# Examples: ticket system CLIs, support platform exports, help desk APIs
```

### customer-feedback capability
```bash
# Discovers feedback platforms, voting systems, feature request tools
# Examples: feedback exports, product board files, customer labels in issue trackers
```

### surveys capability
```bash
# Discovers survey response exports (CSV, JSON)
# Examples: survey platform exports, NPS data files, form responses
```

### conversations capability
```bash
# Discovers chat and messaging data sources
# Examples: chat exports, messaging platform data
```

### issue-tracking capability
```bash
# Discovers bug/issue tracking systems with customer-reported items
# Examples: issue tracker CLIs with customer labels or tags
```

## Usage

```bash
# Listen to all available capabilities (auto-discovers sources)
/wicked-garden:product:listen

# Specific capability type
/wicked-garden:product:listen --capability support-tickets

# Time window
/wicked-garden:product:listen --days 30
/wicked-garden:product:listen --since "2026-01-01"

# Filter by tags
/wicked-garden:product:listen --tags bug,feature-request

# Limit results
/wicked-garden:product:listen --limit 50
```

## Aggregation Strategy

1. **Discover Available Capabilities**
   - Check for support-tickets capability (CLI tools, APIs)
   - Check for customer-feedback capability (exports, voting systems)
   - Check for surveys capability (CSV/JSON exports)
   - Check for conversations capability (chat/messaging data)
   - Check for issue-tracking capability (customer-labeled issues)
   - Look for saved feedback in voice store

2. **Fetch Recent Feedback**
   - Default: Last 30 days
   - Configurable timeframe
   - Filter by source, tag, or keyword

3. **Normalize Format**
   - Extract: ID, source, date, author, content, sentiment
   - Tag with categories (bug, feature, praise, complaint)
   - Store in unified format

4. **Store for Analysis**
   ```
   ~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/{source}/{date}/{id}.md
   ```

## Unified Feedback Format

```yaml
---
id: fb_abc123
capability: support-tickets
source_tool: detected-cli-tool
source_id: ticket_456
date: 2026-01-20T10:30:00Z
author: customer@example.com
segment: enterprise
tags: [bug, mobile, performance]
sentiment: negative
priority: high
---

# {Title/Subject}

## Original Feedback
{Raw customer quote}

## Context
- Platform: iOS 16
- Plan: Enterprise
- User since: 2025-06-01
```

## Output

Concise summary of aggregated feedback:

```markdown
## Listening Report: {Timeframe}

### Capabilities Discovered
- support-tickets: {X} items from {N} source(s)
- customer-feedback: {Y} items from {N} source(s)
- surveys: {Z} responses from {N} source(s)
- Total: {N} feedback items across {M} capabilities

### Quick Stats
- Sentiment: {%pos} positive, {%neg} negative, {%neu} neutral
- Top tags: {tag1} ({count}), {tag2} ({count})
- Critical items: {count}

### Recent Highlights
1. **{Title}** - {source} - {date}
   - Sentiment: {sentiment}
   - Quote: "{excerpt}"

{Top 5-10 items}

### Next Steps
Run /wicked-garden:product:analyze to extract themes and trends.
```

See [channels.md](refs/channels.md) for detailed capability integration patterns.

## Integration

### With wicked-mem
```python
# Recall past customer insights
if has_plugin("wicked-mem"):
    memories = recall(f"customer feedback about {topic}")
    # Provide historical context
```

### With wicked-crew
```python
# Auto-trigger during product:requirements phase
if event == "product:requirements:started":
    feedback = listen(days=30, tags=["feature-request"])
    inject_context(feedback)
```

## Storage

Feedback stored at: `~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/{source}/{YYYY-MM}/{id}.md`

## Error Handling

- Source unavailable: Skip gracefully, report in summary
- No recent feedback: Report "No feedback found in timeframe"
- API rate limits: Cache and resume
- Invalid format: Log warning, continue with valid items

## Rules

- Never expose customer PII beyond what's already in feedback
- Respect source rate limits
- Cache API responses when possible
- Report source availability in output
- Keep summaries concise (top 10 items max)
