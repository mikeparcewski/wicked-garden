---
description: Show available search and code intelligence commands and usage
---

# /wicked-garden:search:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-garden:search Help

Structural code search, document search, lineage tracing, and codebase intelligence powered by the brain knowledge layer.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:search:search <query>` | Search across all code and documents |
| `/wicked-garden:search:code <query>` | Search code symbols (functions, classes, methods) |
| `/wicked-garden:search:docs <query>` | Search documents (PDF, Office, markdown) |
| `/wicked-garden:search:index <path>` | Build index via `wicked-brain:ingest` |
| `/wicked-garden:search:lineage <symbol>` | Trace data lineage from source to sink |
| `/wicked-garden:search:blast-radius <symbol>` | Analyze dependencies and dependents of a symbol |
| `/wicked-garden:search:impact <symbol>` | Analyze what would be affected by changing a symbol |
| `/wicked-garden:search:refs <symbol>` | Find where a symbol is referenced and documented |
| `/wicked-garden:search:impl <doc-section>` | Find code that implements a documented feature |
| `/wicked-garden:search:hotspots` | Find most-referenced symbols in the codebase |
| `/wicked-garden:search:categories` | Show symbol categories, layers, and relationships |
| `/wicked-garden:search:coverage` | Report lineage coverage and identify orphan symbols |
| `/wicked-garden:search:service-map` | Detect and visualize service architecture |
| `/wicked-garden:search:scout <pattern>` | Quick pattern reconnaissance (no index required) |
| `/wicked-garden:search:stats` | Show brain index statistics |
| `/wicked-garden:search:quality` | Validate and improve brain index accuracy |
| `/wicked-garden:search:validate` | Validate brain index accuracy with consistency checks |
| `/wicked-garden:search:help` | This help message |

## Quick Start

```
wicked-brain:ingest .
/wicked-garden:search:code "handlePayment"
/wicked-garden:search:blast-radius UserService --depth 3
```

## Architecture

Search commands use a **brain-first** architecture:

1. **Primary**: Query the brain knowledge layer at `http://localhost:4242/api`
2. **Fallback**: Use native Grep/Glob/Read tools for direct file search
3. **Indexing**: `wicked-brain:ingest` replaces the old indexer

```bash
# Brain search pattern used by all commands:
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"<query>","limit":N}}'
```

## Examples

### Code Search
```
/wicked-garden:search:code "authenticate"
/wicked-garden:search:search "error handling"
/wicked-garden:search:docs "API design"
```

### Impact Analysis
```
/wicked-garden:search:blast-radius PaymentService --depth 2
/wicked-garden:search:impact UserModel
/wicked-garden:search:refs createOrder
```

### Lineage and Architecture
```
/wicked-garden:search:lineage order_total --direction both
/wicked-garden:search:service-map --format mermaid
/wicked-garden:search:hotspots --limit 20 --layer service
```

### Index Management
```
wicked-brain:ingest .
/wicked-garden:search:stats
/wicked-garden:search:validate
/wicked-garden:search:quality --max-iterations 3
```

## Integration

- **wicked-brain**: Knowledge layer providing search, stats, and ingestion
- **wicked-smaht**: Search adapter feeds context assembly via brain
- **wicked-patch**: Symbol lookup for structural refactoring
- **engineering**: Architecture and code analysis
- **wicked-crew**: Context for all workflow phases
```
