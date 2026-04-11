# Script Runner Reference

Standard procedure for executing wicked-garden:search queries via the search scripts.

## Search Script Pattern

All search commands use the brain API:

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"{verb}","params":{...}}'
```

### Examples

```bash
# Search symbols
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"authenticate","limit":10}}'

# Get stats
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"stats","params":{}}'

# Health check
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"health","params":{}}'
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

- Connection refused: Brain server may not be running — start with `/wicked-brain:server`
- Empty results: Verify indexing was done (`/wicked-garden:search:stats`)

## Troubleshooting

- **Connection error**: Ensure the brain server is running at `http://localhost:4242`
- **Empty results**: Verify indexing was done (`/wicked-garden:search:stats`)
- **Wrong project**: Use `project` param in the API request to target the correct codebase
