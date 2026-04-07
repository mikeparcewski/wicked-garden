---
description: Recall memories matching a query
argument-hint: "[query] [--tags tag1,tag2] [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic]"
---

# /wicked-garden:mem:recall

Recall memories matching search criteria via the brain API. Results are ranked by relevance with tier weighting: semantic (1.3x), episodic (1.0x), working (0.8x).

## Arguments

Parse the arguments from: $ARGUMENTS

- `query` (optional): Free-text search query
- `--type`: Filter by memory type (episodic, decision, procedural, preference)
- `--tier`: Filter by consolidation tier (working, episodic, semantic)
- `--tags`: Comma-separated tags to filter by
- `--limit`: Maximum results (default: 10)

## Execution

### Step 1: Search brain API

Build a search query that combines the user's query text with any tag/type filters.

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"{query text, include tags if specified}","limit":{limit}}}'
```

### Step 2: Filter results to memories

From the search results, keep only entries whose `path` or `id` contains `/mem-`. Discard non-memory chunks (wiki articles, code chunks, etc.).

### Step 3: Read matching chunk files

For each matching result, use the Read tool to read the chunk file at `$HOME/.wicked-brain/{path}` (where path is from the search result, e.g. `memories/episodic/mem-abc123.md`).

Parse the YAML frontmatter to extract: memory_type, memory_tier, title, tags, importance, indexed_at.

### Step 4: Apply client-side filters

If `--type` was specified, keep only memories where `memory_type` matches.
If `--tier` was specified, keep only memories where `memory_tier` matches.
If `--tags` was specified, keep only memories that have at least one matching tag.

### Step 5: Handle brain unavailability

If the curl command fails (connection refused, timeout), display:
> Brain API is not reachable. Start it with `wicked-brain:ingest` or check `wicked-brain:server`.

## Low-Result Handling

If recall returns 0-2 results, try expanding the search:
1. Generate 2-3 synonym/related terms for the query
2. Re-run the brain search with expanded terms
3. Display both the original and expanded results, noting which came from expansion

Example: Query "auth" returns 0 results -> expand to "authentication session tokens security" -> retry

## Output

For each memory, display:
- ID (from filename), type, tier
- Title
- Tags
- Content summary (first 100 chars)
- Age (from indexed_at)
