# Script Runner Reference

Standard procedure for executing wicked-search queries via the search scripts.

## Search Script Pattern

All search commands use the search scripts directly:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py {verb} [--param value ...]
```

### Examples

```bash
# Search symbols
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py search --q "authenticate"

# Traverse from a symbol
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py traverse "MyClass" --direction both --depth 2

# Get hotspots
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py hotspots --limit 20

# Get stats
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py stats

# Impact analysis
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/query_builder.py impact "USERS.EMAIL" --depth 10
```

## Available Verbs

| Verb | Purpose |
|------|---------|
| `stats` | Index statistics |
| `search` | Text search across symbols (FTS5 + BM25) |
| `list` | List symbols with filters |
| `get` | Get single symbol by ID |
| `traverse` | BFS traversal from a symbol |
| `hotspots` | Ranked symbols by connectivity |
| `impact` | Upstream impact analysis |
| `categories` | Type/layer/directory breakdown |

## Common Parameters

| Parameter | Description | Used By |
|-----------|-------------|---------|
| `--q` | Search query text | search |
| `--type` | Symbol type filter (code, document, CLASS, FUNCTION) | search, list |
| `--direction` | Traversal direction (both, in, out) | traverse, impact |
| `--depth` | Traversal depth (1-10) | traverse, impact |
| `--limit` | Max results | hotspots, list |
| `--layer` | Architectural layer filter | hotspots |
| `--project` | Project name for isolation | all verbs |
| `--edge_type` | Edge type filter (implements, calls, imports) | search |

## Response Format

Results are returned as JSON:

- List operations return a JSON array
- Single-item operations return a JSON object
- Errors print to stderr and exit with code 1

## Error Handling

- Script not found: Check `CLAUDE_PLUGIN_ROOT` is set correctly
- Empty results: Verify indexing was done (`/wicked-garden:search:stats`)
- Import errors: Run `cd "${CLAUDE_PLUGIN_ROOT}" && uv sync` to install dependencies

## Troubleshooting

- **Script error**: Check that the search scripts are accessible and the index is built
- **Empty results**: Verify indexing was done (`/wicked-garden:search:stats`)
- **Wrong project**: Use `--project` to target the correct codebase
