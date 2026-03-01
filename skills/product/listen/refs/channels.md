# Capability Integration Patterns

Detailed integration patterns for customer voice capabilities.

## support-tickets Capability

Discovers tools that provide customer support ticket data.

### Discovery Pattern

```bash
# Check for CLI tools with ticket management capabilities
for cmd in zd zendesk intercom freshdesk desk; do
  which "$cmd" 2>/dev/null && echo "support-tickets: $cmd available"
done

# Check for ticket export files
find ~/Downloads -name "*tickets*.csv" -o -name "*support*.json" -mtime -90
```

### Data Extraction Pattern

```bash
# Generic CLI pattern (tool-agnostic)
{discovered_cli} tickets list --status {states} --created_since {timeframe}
{discovered_cli} ticket show {id}

# Generic export pattern
# Parse CSV/JSON for: id, created_date, customer, subject, description, status, tags
```

**Normalization**:
- `id`: unique ticket identifier
- `capability`: support-tickets
- `source_tool`: discovered CLI/tool name
- `author`: customer identifier
- `date`: creation timestamp
- `content`: subject + description + comments
- `tags`: extracted from ticket metadata
- `sentiment`: analyze from text

## customer-feedback Capability

Discovers tools that provide customer feedback, feature requests, and voting data.

### Discovery Pattern

```bash
# Check for issue trackers with customer labels
which gh 2>/dev/null && gh issue list --label customer --limit 1 2>/dev/null

# Check for feedback platform exports
find ~/Downloads -name "*feedback*.csv" -o \
                 -name "*productboard*.csv" -o \
                 -name "*canny*.json" -o \
                 -name "*uservoice*.json" -mtime -90
```

### Data Extraction Pattern

```bash
# Issue tracker pattern (with customer labels)
gh issue list --label customer --state all --limit 100
gh issue view {number} --json body,comments,createdAt,author

# Export file pattern
# Parse for: title, description, votes, author, created_date, status
```

**Normalization**:
- `id`: unique feedback identifier
- `capability`: customer-feedback
- `source_tool`: discovered source name
- `votes`: if available (indicates priority)
- `tags`: extracted from labels/categories
- `sentiment`: analyze from content

## surveys Capability

Discovers survey and NPS response data from export files.

### Discovery Pattern

```bash
# Check for survey exports (platform-agnostic)
find ~/Downloads -name "*survey*.csv" -o \
                 -name "*typeform*.csv" -o \
                 -name "*nps*.csv" -o \
                 -name "*responses*.csv" -mtime -90
```

### Data Extraction Pattern

```bash
# Generic CSV pattern
# Look for columns: timestamp/submitted_at, email/respondent, question columns

# Common structures:
# - First column: timestamp
# - Second column: respondent identifier
# - Remaining columns: question responses
```

**Normalization**:
- `id`: generated from timestamp + respondent
- `capability`: surveys
- `source_tool`: inferred from filename
- `date`: submission timestamp
- `content`: concatenated responses
- `sentiment`: analyze from open-ended responses

## conversations Capability

Discovers chat and messaging platform data.

### Discovery Pattern

```bash
# Check for conversation exports or cached data
find ~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/conversations/ -name "*.md" -o -name "*.json"

# Check for messaging platform exports
find ~/Downloads -name "*slack*.json" -o \
                 -name "*discord*.json" -o \
                 -name "*chat*.csv" -mtime -90
```

### Data Extraction Pattern

```bash
# Look for: timestamp, author, channel, message content, thread context
```

**Normalization**:
- `id`: message or thread identifier
- `capability`: conversations
- `source_tool`: platform name
- `date`: message timestamp
- `content`: message text + thread context
- `sentiment`: analyze from conversation tone

## Direct Feedback

Manually saved customer feedback from various channels.

### Discovery Pattern

```bash
# Check voice store for direct feedback
ls ~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/direct/
ls ~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/social/
```

**Note**: Direct feedback and social mentions are typically manually collected and saved to the voice store.

## Discovery Process

1. **Check for support-tickets Capability**:
   ```bash
   # Discover ANY CLI tool that provides ticket data
   for cmd in zd zendesk intercom freshdesk desk support; do
     which "$cmd" 2>/dev/null && echo "support-tickets: $cmd"
   done

   # Check for ticket exports
   find ~/Downloads -name "*ticket*.csv" -o -name "*support*.json" -mtime -90
   ```

2. **Check for customer-feedback Capability**:
   ```bash
   # Discover feedback platforms
   which gh 2>/dev/null && gh issue list --label customer --limit 1

   # Check for feedback exports
   find ~/Downloads -name "*feedback*.csv" -o \
                    -name "*productboard*.csv" -o \
                    -name "*canny*.json" -mtime -90
   ```

3. **Check for surveys Capability**:
   ```bash
   # Discover survey exports
   find ~/Downloads -name "*survey*.csv" -o \
                    -name "*typeform*.csv" -o \
                    -name "*nps*.csv" -mtime -90
   ```

4. **Check Voice Store**:
   ```bash
   ls -la ~/.something-wicked/wicked-garden/local/wicked-product/voice/feedback/
   ```

5. **Report Availability**:
   ```markdown
   ### Available Capabilities
   - support-tickets: 2 source(s) discovered
   - customer-feedback: 1 source(s) discovered
   - surveys: 3 export file(s) found
   - Cached feedback: 150 items
   ```

## Rate Limiting

Respect API limits for discovered tools:
- Most support platforms: 100-500 req/min
- Most issue trackers: 5000 req/hour
- Always check tool-specific documentation

Cache responses for 1 hour to avoid re-fetching.

## Data Privacy

- Never log full PII (hash emails if needed)
- Redact sensitive content (credentials, payment info)
- Store only feedback content, not personal data
- Follow GDPR/privacy guidelines
