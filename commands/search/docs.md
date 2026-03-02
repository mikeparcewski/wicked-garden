---
description: Search documents only (PDF, Office docs, markdown)
argument-hint: <query>
---

# /wicked-garden:search:docs

Search documents only (PDF, Office docs, markdown) via the knowledge graph.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the doc search via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>" --type document
   ```

2. Parse the response `data` array. Each result contains: `name`, `type`, `file`, `line`, `description`.

3. Report matching document sections with source file locations.

## Example

```
/wicked-garden:search:docs "security requirements"
/wicked-garden:search:docs "API design"
```
