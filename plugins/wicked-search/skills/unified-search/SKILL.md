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
/wicked-search:index /path/to/project

# 2. Search everything
/wicked-search:search "authentication"

# 3. Find where a symbol is documented
/wicked-search:refs AuthService

# 4. Find code that implements a doc section
/wicked-search:impl "Security Requirements"
```

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/wicked-search:index <path>` | Build index for code + docs |
| `/wicked-search:search <query>` | Search everything |
| `/wicked-search:code <query>` | Search code only |
| `/wicked-search:docs <query>` | Search docs only |
| `/wicked-search:refs <symbol>` | Find references + documentation |
| `/wicked-search:impl <section>` | Find implementing code |
| `/wicked-search:scout <pattern>` | Quick pattern recon (no index needed) |
| `/wicked-search:stats` | Show index statistics |

## When to Use Each Command

### User asks about code
Use `/wicked-search:code` for:
- "Find the UserService class"
- "Where is authenticate defined?"
- "Search for functions that handle login"

### User asks about documents
Use `/wicked-search:docs` for:
- "What does the requirements doc say about X?"
- "Find the API spec section on authentication"
- "Search the design docs for rate limiting"

### User asks about relationships
Use `/wicked-search:refs` for:
- "Where is this function documented?"
- "What calls this class?"
- "What does this module import?"

Use `/wicked-search:impl` for:
- "What code implements the auth spec?"
- "Find the code for this requirement"

### User asks general questions
Use `/wicked-search:search` for:
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

## Tips

1. **Index first**: Always run `/wicked-search:index` before searching
2. **Be specific**: More specific queries = better results
3. **Check cross-refs**: Use `/refs` to discover code-doc relationships
4. **Read cached docs**: For full context, read the extracted .txt files

## Supported File Types

**Code**: Python, JavaScript, TypeScript, Java, Go, Rust, C/C++, Ruby, and 20+ more

**Documents**: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Markdown, HTML, plain text
