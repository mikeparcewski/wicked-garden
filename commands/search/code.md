---
description: Search code symbols only (functions, classes, methods)
argument-hint: <query>
---

# /wicked-garden:search:code

Search code symbols only (functions, classes, methods) via the knowledge graph.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the code search via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>" --type code
   ```

2. Parse the response `data` array. Each result contains: `name`, `type`, `file`, `line`, `layer`, `description`.

3. Report matching symbols with file locations and types.

## Example

```
/wicked-garden:search:code "UserService"
/wicked-garden:search:code "authenticate"
```
