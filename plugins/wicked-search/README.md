# wicked-search

AST-powered code intelligence for Claude Code. Provides structural symbol extraction, ORM relationship mapping, framework-specific adapters, blast-radius analysis, and data lineage tracing using tree-sitter grammars.

> For most users, wicked-brain provides sufficient code intelligence via keyword and semantic search. Install wicked-search if you need AST-level precision, ORM relationship mapping, or framework-specific linkers.

## What It Does

wicked-search builds a queryable symbol graph of your codebase. Rather than text matching, it parses source files into ASTs and extracts typed symbols — functions, classes, routes, models, migrations — then links them across language and framework boundaries.

At query time, commands like `blast-radius` and `lineage` walk the graph to answer structural questions: which files call this function, what database tables does this endpoint touch, where does this data flow.

## Why It Exists

wicked-search was originally the `search` domain inside wicked-garden. It was extracted as a standalone plugin so that wicked-garden can drop tree-sitter as a hard dependency. Users who need AST-level code intelligence install wicked-search separately; everyone else gets the lighter wicked-garden base.

The extraction is clean: wicked-search writes enriched symbol chunks to wicked-brain's memory store, so all other wicked-garden domains (crew, engineering, qe) transparently benefit when both plugins are installed.

## Installation

```bash
claude plugin install wicked-search
```

Requires Python 3.10+ and tree-sitter. The plugin installs tree-sitter grammar wheels automatically via `uv` on first index run.

If you are upgrading from wicked-garden < 4.0, see [MIGRATION.md](./MIGRATION.md).

## Features

- **73 language grammars** — coverage from Ada to Zig via tree-sitter query files
- **12 language adapters** — typed symbol extraction for C#, Go, HTML, Java, JavaScript, JSP, Python, Ruby, TypeScript, Vue, XML, and a generic base
- **9 ORM linker families** — Python (SQLAlchemy, Django ORM), TypeScript (TypeORM, Prisma), Java (Hibernate/JPA), Ruby (ActiveRecord), Go (GORM), C# (Entity Framework), SQL (raw DDL), JSP, and frontend component graphs
- **Blast-radius analysis** — given a symbol or file, find all callers, dependents, and transitively affected tests
- **Data lineage tracing** — follow data from source table through transformations to consumers
- **Impact analysis** — pre-change risk scoring based on call graph centrality and test coverage gaps
- **Service map** — detect service boundaries and cross-service call patterns
- **Incremental indexing** — file watcher updates the graph on save; full reindex on demand
- **External source indexing** — pull symbols from remote repos or package registries into the graph
- **Lifecycle scoring** — rank symbols by churn rate, complexity, and coupling for hotspot detection

## Commands

```
/wicked-search:index          # Build or rebuild the symbol graph
/wicked-search:code           # Search by symbol name, type, or pattern
/wicked-search:docs           # Search documentation and comments
/wicked-search:blast-radius   # Find everything affected by a change
/wicked-search:lineage        # Trace data flow from source to consumer
/wicked-search:impact         # Pre-change risk and coverage analysis
/wicked-search:service-map    # Visualize service boundaries
/wicked-search:hotspots       # Identify high-churn, high-coupling symbols
/wicked-search:coverage       # Symbol coverage report by language
/wicked-search:stats          # Index health and freshness metrics
/wicked-search:validate       # Verify index integrity
/wicked-search:scout          # Quick pattern scan without a full index
```

## Integration with wicked-brain

When wicked-brain is installed alongside wicked-search, indexed symbols are written to wicked-brain's memory store as enriched chunks. This means:

- `mem:recall` surfaces structurally-relevant symbols alongside semantic memories
- Crew agents (design, build, qe phases) get symbol context injected automatically via the smaht assembler
- `engineering:review` can reference call graphs without a separate search command

The integration is automatic once both plugins are installed. No configuration required.

## Requirements

- Python 3.10+
- tree-sitter (installed automatically on first index)
- uv (for dependency management — install via `pip install uv`)
- wicked-brain (optional — enables memory integration)
