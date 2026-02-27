---
description: Quick pattern reconnaissance for common code patterns (no index required)
argument-hint: <pattern-type> [--path PATH]
---

# /wicked-garden:search:scout

Quick pattern reconnaissance without needing to build an index first.

## Arguments

- `pattern-type` (required): Type of pattern to scout for
- `--path` (optional): Directory to scout (default: current)

## Instructions

1. Run the scout (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py scout "<pattern>" --path "<path>"
   ```

## Pattern Types

- `api` - Find API endpoints and routes
- `test` - Find test files and functions
- `config` - Find configuration files
- `auth` - Find authentication code
- `db` - Find database queries and models

## Example

```
/wicked-garden:search:scout api --path /path/to/project
```

## Notes

- No index required - uses direct pattern matching
- Faster than indexing for quick recon
