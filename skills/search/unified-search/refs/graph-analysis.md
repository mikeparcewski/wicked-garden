# Graph Analysis — Brain API Reference

Advanced graph queries via the brain server at `localhost:4242` (requires `wicked-brain`).

## Traverse

BFS traversal from a symbol, returning full node/edge objects:

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"<symbol-id>","limit":10}}'
```

Options:
- `--depth`: 1-3 (default 1, max 3)
- `--direction`: `both`, `in`, `out`

Returns root node, connected nodes, and typed edges.

## Hotspots

Rank symbols by total connectivity (in-degree + out-degree):

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"hotspots","limit":10}}'
```

Supports `--layer` and `--type` filters. Default limit: 20, sorted by `total_count` descending.

High-connectivity symbols are change-risk candidates — touching them has wide blast radius.

## Multi-Project

All queries support project-scoped isolation:

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"hotspots","project":"my-app","limit":10}}'
```

Use the `project` param to isolate results to a single indexed project.

## Knowledge Domain Sources

| Source | Verbs | Purpose |
|--------|-------|---------|
| `graph` | search, traverse, hotspots, impact, stats, list, get | Symbol graph queries |
| `symbols` | list, categories, ingest | Symbol catalog |
| `lineage` | search | Data flow tracing |
| `code` | content | Source code retrieval |
| `projects` | list | Multi-project isolation |
| `refs` | ingest | Cross-reference ingestion |
