# wicked-search

Structural codebase understanding that traces a JSP form field to the exact database column it writes to, finds every file affected by a column rename, and generates architecture diagrams from infrastructure manifests merged with code-inferred connections -- none of which grep can do.

Unlike text search, wicked-search understands relationships. It indexes 73 languages via tree-sitter, extracts text from PDFs and Office documents, and links everything into a unified symbol graph with typed, confidence-tagged relationships. Cross-layer data flow tracing works across 8 ORM frameworks (JPA, SQLAlchemy, Django, TypeORM, Prisma, ActiveRecord, Entity Framework, GORM).

## Quick Start

```bash
# Install
claude plugin install wicked-search@wicked-garden

# Index your project
/wicked-search:index .

# Trace data flow from UI to database
/wicked-search:lineage user.email
```

## Workflows

### Impact analysis before a risky change

Know what breaks before you change it:

```bash
/wicked-search:blast-radius AuthenticationService   # What depends on this?
/wicked-search:impact users.email                   # What uses this column?
/wicked-search:lineage user.email                   # Full data flow path

# Lineage output example:
# UI: login.jsp → Controller → Service → Repository → Entity → Database
```

### Understanding a legacy codebase

Navigate unknown code without reading every file:

```bash
/wicked-search:index .
/wicked-search:code "@SpringBootApplication"    # Find entry points
/wicked-search:blast-radius LoginController     # Trace all dependencies
/wicked-search:docs "architecture"              # Surface design docs
/wicked-search:service-map                      # Detect service boundaries
```

### Improving index accuracy

A self-improving quality crew discovers symbol relationships until 95%+ of your codebase is mapped:

```bash
/wicked-search:coverage     # Find gaps in lineage coverage
/wicked-search:validate --deep   # Check index accuracy
/wicked-search:quality      # Run agent-based quality crew to 95%+ accuracy
/wicked-search:stats        # Show index statistics and coverage
```

## Commands

### Search

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-search:index` | Build structural index for code and documents | `/wicked-search:index .` |
| `/wicked-search:search` | Search across code and documents simultaneously | `/wicked-search:search "payment"` |
| `/wicked-search:code` | Search code symbols only | `/wicked-search:code "AuthService"` |
| `/wicked-search:docs` | Search documents only | `/wicked-search:docs "security requirements"` |
| `/wicked-search:refs` | Find references and related documentation | `/wicked-search:refs validate_token` |
| `/wicked-search:impl` | Find code that implements a specification | `/wicked-search:impl "Authentication API"` |
| `/wicked-search:scout` | Quick pattern search with no index required | `/wicked-search:scout "@Deprecated"` |
| `/wicked-search:stats` | Show index statistics and coverage | `/wicked-search:stats` |

### Analysis

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-search:blast-radius` | What depends on this symbol? | `/wicked-search:blast-radius UserService` |
| `/wicked-search:lineage` | Trace data flow from UI to database | `/wicked-search:lineage user.email` |
| `/wicked-search:impact` | What breaks if I change this? | `/wicked-search:impact EmailValidator` |
| `/wicked-search:coverage` | Find gaps in lineage coverage | `/wicked-search:coverage` |
| `/wicked-search:service-map` | Detect microservice architecture from code | `/wicked-search:service-map` |
| `/wicked-search:hotspots` | Rank symbols by connectivity (most-depended-on) | `/wicked-search:hotspots` |
| `/wicked-search:validate` | Validate index accuracy | `/wicked-search:validate --deep` |
| `/wicked-search:quality` | Agent-based quality crew to 95%+ accuracy | `/wicked-search:quality` |

## What Makes It Different

| Capability | wicked-search | grep/ripgrep | IDE Search |
|-----------|--------------|-------------|------------|
| Text search | Yes | Yes | Yes |
| Symbol-aware | Yes | No | Yes |
| Cross-layer data flow | Yes | No | No |
| ORM entity mapping | Yes | No | No |
| Impact analysis | Yes | No | Partial |
| Data lineage tracing | Yes | No | No |
| Document cross-references | Yes | No | No |

### Supported Technologies

**Code**: 73 languages via tree-sitter (Python, Java, TypeScript, Go, Rust, C#, and more)

**ORMs**: JPA, SQLAlchemy, Django ORM, TypeORM, Prisma, ActiveRecord, Entity Framework, GORM

**Frontend**: JSP/EL expressions, Vue SFC, React props

**Documents**: PDF, Word, Excel, PowerPoint, Markdown, HTML (via Kreuzberg)

### Multi-Project Isolation

Index multiple codebases separately with `--project`:

```bash
/wicked-search:index /path/to/project --project my-project

# Query a specific project
python3 scripts/api.py list graph --project my-project
python3 scripts/api.py hotspots graph --project my-project

# List all indexed projects
python3 scripts/api.py list projects
```

Project names: alphanumeric + hyphens, max 64 chars. Without `--project`, uses the legacy flat index (backward compatible).

## Skills

| Skill | What It Covers |
|-------|---------------|
| `unified-search` | Search strategy, index management, and cross-source queries |
| `graph-export` | Symbol graph traversal, BFS, connectivity analysis, and cross-plugin export |

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| symbols | list, get, search, stats | Code symbols (functions, classes, methods) from indexed projects |
| documents | list, search | Indexed documents (Markdown, PDF, Office) with frontmatter |
| references | list, search | Cross-references between symbols and documents |
| graph | list, get, search, stats, traverse, hotspots | Symbol dependency graph with BFS traversal and connectivity ranking |
| lineage | list, search | Precomputed data lineage paths (source to sink) with confidence scores |
| services | list, stats | Detected service nodes and connections from infrastructure analysis |
| projects | list | Indexed projects with symbol counts and last-indexed timestamps |

All sources support `--project` for multi-project isolation. Symbols include enrichment fields: `inferred_type` (test, configuration, data-model, controller, service, utility), `description` (first docstring or comment), and `domains` (path-inferred tags like auth, api, db).

Query via the workbench gateway:
```
GET /api/v1/data/wicked-search/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

Graph traversal and hotspot commands:
```bash
python3 scripts/api.py traverse graph <symbol-id> --depth 2 --direction both
python3 scripts/api.py hotspots graph --limit 10 --type entity
```

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-smaht | Code context and symbol definitions auto-loaded before each response | Manual search required every turn |
| wicked-patch | Change propagation using the symbol graph for multi-file edits | Manual multi-file edits without structural awareness |
| wicked-startah | Cached index results for faster repeated searches | Re-indexes each session |
| wicked-crew | Auto-engaged during build and review phases for impact analysis | Use commands directly |

## License

MIT
