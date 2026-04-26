---
description: "Query the unified event log for cross-domain activity"
argument-hint: "[--domain D] [--project P] [--since 7d] [--fts 'search terms'] [--action A] [--limit N]"
---

# /wicked-garden:crew:activity

Query the unified event log to see cross-domain project activity.

## Instructions

### Parse Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `--domain` | Filter by domain (crew, mem, jam, etc.) | all |
| `--project` | Filter by project ID | all |
| `--since` | Time window (7d, 24h, 2026-03-01) | 7d |
| `--action` | Filter by action (supports prefix: "phases.*") | all |
| `--fts` | Full-text search across payloads | none |
| `--limit` | Max results | 50 |
| `--json` | Output as JSON | false |

### Run Query

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/_event_store.py query \
  ${domain:+--domain "$domain"} \
  ${project:+--project "$project"} \
  ${since:+--since "$since"} \
  ${fts:+--fts "$fts"} \
  ${action:+--action "$action"} \
  --limit ${limit:-50} \
  --json
```

### Present Results

Format results as a timeline:

```markdown
## Event Log

| Time | Domain | Action | Details |
|------|--------|--------|---------|
| 2026-03-22 14:30 | crew | phases.transitioned | clarify → build |
| 2026-03-22 14:28 | mem | memories.created | "Chose JWT over sessions" |
| 2026-03-22 14:15 | jam | sessions.created | "Auth migration approaches" |
```

If `--json` flag, output raw JSON.

## Examples

```bash
# What happened in the last 7 days?
/wicked-garden:crew:activity --since 7d

# What happened on project X?
/wicked-garden:crew:activity --project my-project

# Search for auth-related events
/wicked-garden:crew:activity --fts "auth migration"

# All crew phase transitions
/wicked-garden:crew:activity --domain crew --action "phases.*"
```
