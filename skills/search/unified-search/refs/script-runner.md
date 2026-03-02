# CP Proxy Reference

Standard procedure for executing wicked-search queries via the control plane.

## CP Proxy Pattern

All search commands use the CP proxy script to query the knowledge domain:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge {source} {verb} [id] [--param value ...]
```

### Examples

```bash
# Search symbols
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "authenticate"

# Search code only
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "UserService" --type code

# Traverse from a symbol
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph traverse "MyClass" --direction both --depth 2

# Get hotspots
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph hotspots --limit 20

# Get categories
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols categories

# Get stats
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph stats

# Impact analysis
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph impact "USERS.EMAIL" --depth 10

# Lineage search
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge lineage search "User.email" --direction downstream

# Ingest symbols
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols ingest < symbols.json

# Ingest refs
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge refs ingest < refs.json
```

## Knowledge Domain Endpoints

| Source | Verb | Method | Purpose |
|--------|------|--------|---------|
| `graph` | `stats` | GET | Index statistics |
| `graph` | `search` | GET | Text search across symbols |
| `graph` | `list` | GET | List symbols with filters |
| `graph` | `get` | GET | Get single symbol by ID |
| `graph` | `traverse` | GET | BFS traversal from a symbol |
| `graph` | `hotspots` | GET | Ranked symbols by connectivity |
| `graph` | `impact` | GET | Upstream impact analysis |
| `symbols` | `list` | GET | List symbol catalog |
| `symbols` | `categories` | GET | Type/layer/directory breakdown |
| `symbols` | `ingest` | POST | Ingest new symbols |
| `lineage` | `search` | GET | Data flow path search |
| `code` | `content` | GET | Retrieve source code |
| `projects` | `list` | GET | List indexed projects |
| `refs` | `ingest` | POST | Ingest cross-references |

## Response Format

All CP responses use the envelope: `{"data": ..., "meta": {...}}`

- List operations return `data` as an array
- Single-item operations return `data` as an object
- `meta` contains pagination info, timestamps, etc.

## Common Parameters

| Parameter | Description | Used By |
|-----------|-------------|---------|
| `--q` | Search query text | graph search |
| `--type` | Symbol type filter (code, document, CLASS, FUNCTION) | graph search, symbols list |
| `--direction` | Traversal direction (both, in, out) | graph traverse, lineage search |
| `--depth` | Traversal depth (1-10) | graph traverse, graph impact, lineage search |
| `--limit` | Max results | graph hotspots, graph list |
| `--layer` | Architectural layer filter | graph hotspots |
| `--project` | Project name for isolation | all verbs |
| `--edge_type` | Edge type filter (implements, calls, imports) | graph search |

## Error Handling

- CP unavailable: `{"error": "Control plane unreachable", "code": "CP_UNAVAILABLE"}` on stderr
- Request failed: `{"error": "...", "code": "CP_ERROR"}` on stderr
- Exit code 1 on any error

## Troubleshooting

- **CP unavailable**: Check that the control plane is running (`curl http://localhost:18889/health`)
- **Empty results**: Verify indexing was done (`/wicked-garden:search:stats`)
- **Wrong project**: Use `--project` to target the correct codebase
