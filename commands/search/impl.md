---
description: Find code that implements a documented feature/section
argument-hint: <doc-section>
---

# /wicked-garden:search:impl

Find code that implements a documented feature or section by searching for implementation edges in the knowledge graph.

## Arguments

- `doc-section` (required): Name of the doc section to find implementations for

## Instructions

1. Run the search via the CP proxy with edge type filter:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<doc-section>" --edge_type implements
   ```

2. Parse the response `data` array. Each result represents a code symbol linked to the documentation.

3. Report the code symbols that implement this section, with file locations.

## Example

```
/wicked-garden:search:impl "Repository Layer"
/wicked-garden:search:impl "Security Requirements"
```

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Cross-references are auto-detected during indexing (CamelCase, snake_case, backtick-quoted names)
