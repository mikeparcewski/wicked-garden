---
name: unified-search
description: |
  This skill should be used when searching code, finding documentation,
  understanding code-doc relationships, or performing impact analysis.
  Triggered by queries like "search code", "find function", "find class",
  "where is defined", "search docs", "PDF content", "cross reference",
  "impact analysis", "blast radius", "what calls this", "find all references".

  Prefer this over raw Grep/Glob for symbol search, impact analysis,
  code-doc cross-references, and understanding codebase structure.
---

# Unified Search Skill

Search across code AND documents, with automatic cross-reference detection.

## Quick Start

```bash
# 1. Index a project (code + docs)
/wicked-garden:search:index /path/to/project

# 2. Search everything
/wicked-garden:search:search "authentication"

# 3. Find where a symbol is documented
/wicked-garden:search:refs AuthService

# 4. Find code that implements a doc section
/wicked-garden:search:impl "Security Requirements"
```

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/wicked-garden:search:index <path>` | Build index for code + docs |
| `/wicked-garden:search:search <query>` | Search everything |
| `/wicked-garden:search:code <query>` | Search code only |
| `/wicked-garden:search:docs <query>` | Search docs only |
| `/wicked-garden:search:refs <symbol>` | Find references + documentation |
| `/wicked-garden:search:impl <section>` | Find implementing code |
| `/wicked-garden:search:scout <pattern>` | Quick pattern recon (no index needed) |
| `/wicked-garden:search:stats` | Show index statistics |

## When to Use Each Command

### User asks about code
Use `/wicked-garden:search:code` for:
- "Find the UserService class"
- "Where is authenticate defined?"
- "Search for functions that handle login"

### User asks about documents
Use `/wicked-garden:search:docs` for:
- "What does the requirements doc say about X?"
- "Find the API spec section on authentication"
- "Search the design docs for rate limiting"

### User asks about relationships
Use `/wicked-garden:search:refs` for:
- "Where is this function documented?"
- "What calls this class?"
- "What does this module import?"

Use `/wicked-garden:search:impl` for:
- "What code implements the auth spec?"
- "Find the code for this requirement"

### User asks general questions
Use `/wicked-garden:search:search` for:
- Broad searches across everything
- When unsure if it's code or docs
- "Find anything related to authentication"

## Cross-Reference Detection

The indexer automatically detects when documents mention code symbols:

1. **CamelCase**: `AuthService`, `UserRepository`
2. **snake_case**: `authenticate_user`, `get_user_by_id`
3. **Backtick quoted**: `` `my_function` ``
4. **Function calls**: `process_data()`

These create "documents" edges in the graph, linking doc sections to code.

## Reading Extracted Documents

After indexing, extracted document text is cached at:
```
~/.something-wicked/search/extracted/<filename>.txt
```

Read these files to get full document content for context.

## Graph Analysis

### Traverse
BFS traversal from a symbol, returning full node/edge objects:
```bash
python3 scripts/cp.py knowledge graph traverse <symbol-id> --depth 2 --direction both
```
- `--depth`: 1-3 (default 1, max 3)
- `--direction`: `both`, `in`, `out`
- Returns root node, connected nodes, and typed edges

### Hotspots
Rank symbols by total connectivity (in-degree + out-degree):
```bash
python3 scripts/cp.py knowledge graph hotspots --limit 10 --layer backend --type entity
```
- Supports `--layer` and `--type` filters
- Default limit: 20, sorted by total_count descending

### Multi-Project
All verbs support `--project` for multi-codebase isolation:
```bash
python3 scripts/cp.py knowledge projects list                     # List indexed projects
python3 scripts/cp.py knowledge graph hotspots --project my-app   # Query specific project
```

### Symbol Enrichment
Symbols indexed after v1.6.0 include: `inferred_type` (test, configuration, data-model, controller, service, utility, general), `description` (first docstring/comment), and `domains` (path-derived tags).

## Tips

1. **Index first**: Always run `/wicked-garden:search:index` before searching
2. **Be specific**: More specific queries = better results
3. **Check cross-refs**: Use `/refs` to discover code-doc relationships
4. **Read cached docs**: For full context, read the extracted .txt files
5. **Use hotspots**: Find high-coupling symbols that are change-risk candidates
6. **Use traverse**: Understand a symbol's neighborhood before refactoring

## Supported File Types

**Code**: Python, JavaScript, TypeScript, Java, Go, Rust, C/C++, Ruby, and 20+ more

**Documents**: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Markdown, HTML, plain text
