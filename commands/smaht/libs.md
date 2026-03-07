---
description: List locally cached library cheatsheets
argument-hint: "[--search <query>]"
---

# /wicked-garden:smaht:libs

Show all library cheatsheets stored in the local knowledge base. Each cheatsheet was created by `/wicked-garden:smaht:learn` and is used automatically by the smaht context assembler to answer library questions without a live MCP call.

## Usage

```
/wicked-garden:smaht:libs
/wicked-garden:smaht:libs --search react
```

## Instructions

### 1. Parse Arguments

- `--search` (optional): Filter results to libraries whose name contains this substring

### 2. Query the Cheatsheet Store

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/smaht/cheatsheet_store.py list {--search "{query}"}
```

### 3. Format and Display

If records are returned, present a summary table:

```
Library Knowledge Base
======================

| Library    | Version  | Key APIs | Patterns | Age       |
|------------|----------|----------|----------|-----------|
| react      | 18.x     | 8        | 4        | 2 days    |
| fastapi    | 0.115    | 6        | 3        | 1 week    |
| next.js    | —        | 9        | 5        | 3 hours   |

{total} cheatsheet(s) stored.

To inspect a specific cheatsheet, run:
  /wicked-garden:smaht:learn {library}   — refresh with latest docs
```

Column definitions:
- **Library**: `library` field from the cheatsheet record
- **Version**: `version_hint` if present, else `—`
- **Key APIs**: `len(key_apis)` array
- **Patterns**: `len(common_patterns)` array
- **Age**: human-readable age derived from `timestamp` field

Sort by `timestamp` descending (newest first).

### 4. Empty State

If no cheatsheets are stored (or the search matched nothing), show:

```
No library cheatsheets found{for "{query}"}.

Get started by learning a library:
  /wicked-garden:smaht:learn react
  /wicked-garden:smaht:learn fastapi
  /wicked-garden:smaht:learn "next.js"

Cheatsheets are fetched from Context7 and cached locally.
Future prompts mentioning that library skip the live MCP call.
```

## Notes

- Cheatsheets are stored per-library; the most recent entry wins on lookup.
- Re-running `/wicked-garden:smaht:learn {library}` refreshes the cheatsheet with current docs.
- The smaht context assembler uses these cheatsheets automatically — no manual lookup needed during normal work.
