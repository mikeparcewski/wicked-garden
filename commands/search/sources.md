---
description: Manage external content sources for the search index
argument-hint: "list | add | remove <name> | refresh [--force]"
---

# /wicked-garden:search:sources

Manage external content sources that feed into the brain knowledge layer. Supports any MCP-compatible tool (Confluence, Jira, Notion, etc.).

## Arguments

- `list` — List all configured external sources
- `add` — Interactively add a new external source
- `remove <name>` — Remove a source by name
- `refresh [--force]` — Refresh stale sources (fetch + ingest their content)

## Instructions

### list

Query brain for indexed external sources:
```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"source:external","limit":50}}'
```

Format the output as a table with columns: Name, Plugin, Content Type, Last Fetched, Status.

---

### add

Interactively gather source details, then register:

1. Ask the user for:
   - **Source name** (unique identifier, e.g. `confluence-engineering`)
   - **Plugin** (MCP plugin name, e.g. `mcp-confluence`)
   - **Fetch command** (tool command, e.g. `get_space_pages`)
   - **Fetch args** (JSON object, e.g. `{"space_key": "ENG"}`) — default `{}`
   - **Content type** (`document`, `code`, or `ticket`) — default `document`

2. Confirm registration and suggest running `/wicked-garden:search:sources refresh` to fetch initial content.

---

### remove `<name>`

Remove the named source. Note: existing indexed content from this source is NOT automatically purged from the brain.

---

### refresh `[--force]`

For each configured external source:

1. Invoke its MCP plugin to fetch content:
   ```
   Use the <plugin> MCP tool: call <fetch_command> with args <fetch_args>
   ```

2. Ingest the fetched content into the brain via `wicked-brain:ingest`.

3. Report results: how many sources were refreshed, how many chunks ingested, any failures.

## Examples

```
# See all configured sources
/wicked-garden:search:sources list

# Add a Confluence space
/wicked-garden:search:sources add

# Remove a source
/wicked-garden:search:sources remove confluence-engineering

# Refresh all stale sources
/wicked-garden:search:sources refresh

# Force refresh all sources regardless of freshness
/wicked-garden:search:sources refresh --force
```

## Notes

- External content appears in brain search results alongside local code/docs
- The `refresh` command requires the relevant MCP plugins to be active in the session
- Use `wicked-brain:ingest` to manually ingest content into the brain
