---
name: external-source-index-happy-path
title: Index Content from External Plugin Sources
description: Register an external source, fetch its content, and make it searchable
type: feature
difficulty: intermediate
estimated_minutes: 10
---

# Index Content from External Plugin Sources

## Setup

Prepare a config location for external sources:

```bash
mkdir -p /tmp/wicked-external-test
export EXTERNAL_CONFIG=/tmp/wicked-external-test/sources.json
```

## Steps

1. List configured sources — empty initially:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py list \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

2. Add an external source for a Confluence wiki space:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py add \
     --name "confluence-engineering" \
     --plugin "mcp-confluence" \
     --command "get_space_pages" \
     --args '{"space_key": "ENG", "limit": 100}' \
     --content-type "document" \
     --refresh-interval 60 \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

3. Add a second source for a Jira project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py add \
     --name "jira-backend" \
     --plugin "mcp-jira" \
     --command "search_issues" \
     --args '{"project": "BACK", "status": "Done"}' \
     --content-type "document" \
     --refresh-interval 120 \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

4. List sources again — should show both:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py list \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

5. Remove a source:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py remove \
     --name "jira-backend" \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

6. Verify removal — only confluence-engineering remains:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py list \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

7. Index content manually into the search index with source attribution:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py index-content \
     --name "confluence-engineering" \
     --content "# Engineering Wiki\n\nThe AuthService class handles all authentication." \
     --doc-id "ENG-001" \
     --config "${EXTERNAL_CONFIG}" \
     --json
   ```

8. Check refresh status — shows when each source was last fetched:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/external_indexer.py refresh \
     --config "${EXTERNAL_CONFIG}" \
     --dry-run \
     --json
   ```

## Expected Outcomes

- Initial list returns empty sources array
- After adding sources, list shows each with name, plugin, command, refresh interval
- Remove operation confirms deletion and source is absent from subsequent list
- index-content stores a document with source attribution metadata attached
- refresh --dry-run shows which sources are stale without actually fetching
- All JSON output is well-formed with consistent structure
- Config file is valid JSON after each operation

## Success Criteria

- [ ] `list` returns `{"sources": []}` on empty config
- [ ] `add` stores source and returns `{"ok": true, "name": "confluence-engineering"}`
- [ ] `list` after add returns both sources with all fields populated
- [ ] `remove` returns `{"ok": true, "removed": "jira-backend"}`
- [ ] `list` after remove shows only the remaining source
- [ ] `index-content` returns `{"ok": true, "nodes_indexed": 1}`
- [ ] Indexed document has `source`, `source_name`, `source_plugin` in metadata
- [ ] `refresh --dry-run` lists stale sources without side effects
- [ ] Config file is valid JSON persisted to disk

## Value Demonstrated

**Problem solved**: Search only covers local files. Developers miss relevant context in Confluence, Jira, Notion, or other team knowledge bases when searching.

**Why this matters**:
- **Unified knowledge search**: Find implementation docs alongside the code that implements them
- **Cross-tool context**: A search for "authentication" surfaces both AuthService code and the Confluence spec that describes it
- **Plugin ecosystem**: Any MCP-compatible tool can become a search source without modifying wicked-search core
- **Freshness control**: Per-source refresh intervals keep external content up to date without hammering APIs
