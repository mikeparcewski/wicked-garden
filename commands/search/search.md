---
description: Search across all code and documents
argument-hint: <query>
---

# /wicked-garden:search:search

Search across both code symbols and documents via the knowledge graph.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the search via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>"
   ```

2. Parse the response `data` array. Each result contains: `name`, `type`, `file`, `line`, `layer`, `description`.

3. Report results grouped by type (code symbols vs documents), with relevance context:
   - Symbol name and type
   - File location
   - Architectural layer (if present)
   - Description snippet

## Example

```
/wicked-garden:search:search "authentication"
/wicked-garden:search:search "error handling"
```
