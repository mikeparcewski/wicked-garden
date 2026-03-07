---
description: Manage external content sources for the search index
argument-hint: "list | add | remove <name> | refresh [--force]"
---

# /wicked-garden:search:sources

Manage external plugin sources that feed content into the wicked-search index.
Supports any MCP-compatible tool (Confluence, Jira, Notion, etc.).

## Arguments

- `list` — List all configured external sources
- `add` — Interactively add a new external source
- `remove <name>` — Remove a source by name
- `refresh [--force]` — Refresh stale sources (fetch + index their content)

## Instructions

### list

Show all configured external sources:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py list --json
```

Format the output as a table with columns: Name, Plugin, Command, Content Type, Refresh Interval, Last Fetched, Status.

---

### add

Interactively gather source details, then register:

1. Ask the user for:
   - **Source name** (unique identifier, e.g. `confluence-engineering`)
   - **Plugin** (MCP plugin name, e.g. `mcp-confluence`)
   - **Fetch command** (tool command, e.g. `get_space_pages`)
   - **Fetch args** (JSON object, e.g. `{"space_key": "ENG"}`) — default `{}`
   - **Content type** (`document`, `code`, or `ticket`) — default `document`
   - **Refresh interval** (minutes) — default `60`

2. Register the source:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py add \
     --name "<name>" \
     --plugin "<plugin>" \
     --command "<fetch_command>" \
     --args '<fetch_args_json>' \
     --content-type "<content_type>" \
     --refresh-interval <minutes> \
     --json
   ```

3. Confirm registration and suggest running `/wicked-garden:search:sources refresh` to fetch initial content.

---

### remove `<name>`

Remove the named source from the registry:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py remove \
  --name "<name>" \
  --json
```

Confirm removal. Note: existing indexed content from this source is NOT automatically purged.

---

### refresh `[--force]`

Check which sources are stale and fetch+index their content:

1. Identify stale sources:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py refresh \
     --dry-run \
     ${force:+--force} \
     --json
   ```

2. For each stale source, invoke its MCP plugin to fetch content. Example for a Confluence source:
   ```
   Use the <plugin> MCP tool: call <fetch_command> with args <fetch_args>
   ```
   Collect the returned content as a string.

3. Index the fetched content with source attribution. For short content use `--content`; for large documents use `--content-file` or `--content-stdin` to avoid shell argument length limits:
   ```bash
   # Short content (inline)
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py index-content \
     --name "<source_name>" \
     --content "<fetched_content>" \
     --doc-id "<unique_doc_id>" \
     --json

   # Large content (from file)
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py index-content \
     --name "<source_name>" \
     --content-file "/path/to/content.txt" \
     --doc-id "<unique_doc_id>" \
     --json

   # Large content (piped via stdin)
   cat /path/to/content.txt | cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/external_indexer.py index-content \
     --name "<source_name>" \
     --content-stdin \
     --doc-id "<unique_doc_id>" \
     --json
   ```

4. Report results: how many sources were refreshed, how many nodes indexed, any failures.

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

- Source configs and indexed content are managed by DomainStore — paths are resolved dynamically via `resolve_path.py search`
- External content appears in `/wicked-garden:search:search` results alongside local code/docs
- Results from external sources are tagged with `source_name` and `source_plugin` in metadata
- The `refresh` command requires the relevant MCP plugins to be active in the session
