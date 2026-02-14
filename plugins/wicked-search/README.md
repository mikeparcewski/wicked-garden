# wicked-search

wicked-search builds a structural understanding of your codebase that text search cannot. Trace a JSP form field to the exact database column it writes to, find every file affected by a column rename, and generate architecture diagrams from infrastructure manifests merged with code-inferred connections.

Unlike grep or IDE search, wicked-search understands relationships. It indexes 73 languages via tree-sitter, extracts text from PDFs and Office documents, and links everything into a unified symbol graph with typed, confidence-tagged relationships. Cross-layer data flow tracing works across 8 ORM frameworks (JPA, SQLAlchemy, Django, TypeORM, Prisma, ActiveRecord, Entity Framework, GORM).

A self-improving quality crew discovers symbol relationships until 95%+ of your codebase is mapped. One command to understand how data flows, what breaks when you change something, and where your architecture actually connects.

## Quick Start

```bash
# Install
claude plugin install wicked-search@wicked-garden

# Index your project
/wicked-search:index .

# Search everything
/wicked-search:search "authentication"

# Find what depends on a symbol
/wicked-search:blast-radius UserService

# Trace data flow from UI to database
/wicked-search:lineage user.email

# Quick pattern search (no index needed)
/wicked-search:scout "TODO|FIXME|HACK"
```

## Commands

### Search

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-search:index` | Build index for code + documents | `/wicked-search:index .` |
| `/wicked-search:search` | Search across everything | `/wicked-search:search "payment"` |
| `/wicked-search:code` | Search code symbols only | `/wicked-search:code "AuthService"` |
| `/wicked-search:docs` | Search documents only | `/wicked-search:docs "security requirements"` |
| `/wicked-search:refs` | Find references and documentation | `/wicked-search:refs validate_token` |
| `/wicked-search:impl` | Find code implementing a spec | `/wicked-search:impl "Authentication API"` |
| `/wicked-search:scout` | Quick pattern search (no index) | `/wicked-search:scout "@Deprecated"` |
| `/wicked-search:stats` | Show index statistics | `/wicked-search:stats` |

### Analysis

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-search:blast-radius` | What depends on this symbol? | `/wicked-search:blast-radius UserService` |
| `/wicked-search:lineage` | Trace data flow from UI to database | `/wicked-search:lineage user.email` |
| `/wicked-search:impact` | What's affected if I change this? | `/wicked-search:impact EmailValidator` |
| `/wicked-search:coverage` | Find gaps in lineage coverage | `/wicked-search:coverage` |
| `/wicked-search:service-map` | Detect microservice architecture | `/wicked-search:service-map` |
| `/wicked-search:validate` | Validate index accuracy | `/wicked-search:validate --deep` |
| `/wicked-search:quality` | Agent-based quality crew to 95%+ accuracy | `/wicked-search:quality` |

## What Makes It Different

Unlike grep or IDE search, wicked-search understands your application's architecture:

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

## Workflows

### Understanding a Legacy Codebase

```bash
/wicked-search:index .
/wicked-search:code "@SpringBootApplication"    # Find entry points
/wicked-search:blast-radius LoginController     # Trace dependencies
/wicked-search:docs "architecture"              # Find design docs
```

### Impact Analysis Before Changes

```bash
/wicked-search:blast-radius AuthenticationService  # What depends on this?
/wicked-search:impact users.email                  # What uses this column?
/wicked-search:lineage user.email                  # Trace full data flow
```

### Data Flow Analysis

```bash
# Trace from UI binding to database
/wicked-search:lineage user.email
# UI: login.jsp → Controller → Service → Repository → Entity → Database
```

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| symbols | list, get, search, stats | Code symbols (functions, classes, methods) from indexed projects |
| documents | list, search | Indexed documents (markdown, PDF, Office) with frontmatter |
| references | list, search | Cross-references between symbols and documents |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-search/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-smaht | Auto-loads code context before responses | Manual search only |
| wicked-patch | Change propagation using symbol graph | Manual multi-file edits |
| wicked-startah | Faster repeated searches | Re-indexes each time |
| wicked-crew | Auto-engaged during build/review phases | Use commands directly |

## License

MIT
