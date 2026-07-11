# Customer Feedback Aggregation Rubric (listen — pipeline 1/3)

Apply this inline. Aggregate customer feedback from discovered sources. Pipeline:
**listen -> analyze -> synthesize**. (Shared customer-voice rubric: `refs/analyze.md`
covers sentiment/theme/trend classification.)

## 1. Discover sources

```bash
PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
ls "${PRODUCT_ROOT}/voice/feedback/" 2>/dev/null
find . -name "*feedback*" -o -name "*survey*" -o -name "*tickets*" 2>/dev/null | head -10
gh issue list --label "customer-reported" 2>/dev/null | head -5
```

Typical sources: support tickets, feature requests/votes, survey responses, social
mentions, NPS comments, direct customer quotes.

## 2. For each source

1. Extract feedback items.
2. Normalize to a standard record: `ID, source, date, author, content, sentiment, tags, priority`.
3. Tag sentiment (positive / negative / neutral) and category.
4. Prioritize by impact (critical / high / medium / low).

Apply parameters: time window (`--days` / `--since`), filters (`--tags`,
`--capability`), `--limit`.

## Output

```markdown
## Listening Report: {timeframe}

### Sources Discovered
| Source | Items | Status |
|--------|-------|--------|
| {source} | {count} | Active |

### Quick Stats
- Total Items: {count}
- Sentiment: {%pos} positive, {%neg} negative, {%neu} neutral
- Top Tags: {tag} ({count}), …
- Critical Items: {count}

### Recent Highlights
#### 1. {Title} — {source} — {date}
**Sentiment**: {…} | **Priority**: {…}
> "{excerpt}"

### Next Steps
Run `/wicked-garden-product analyze` to extract themes and trends.
```

## Storage

Feedback stored at `{PRODUCT_ROOT}/voice/feedback/{source}/{YYYY-MM}/{id}.md`.
Log critical items via `TaskCreate` (`metadata.event_type="task"`); recall past
insights via `wicked-brain:memory`.
