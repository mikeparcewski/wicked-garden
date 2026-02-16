---
description: Show symbol categories — types, layers, and directory groupings
argument-hint: "[--project <name>]"
---

# /wicked-search:categories

Show how indexed symbols break down by type, architectural layer, and directory.

## Instructions

1. Run the categories query via the data API:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/api.py categories symbols
   ```

   If a project is specified:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/api.py categories symbols --project "<project>"
   ```

2. Present results in three sections:

   **By Layer** — architectural layers (backend, frontend, database, view):
   | Layer | Symbols |
   |-------|---------|
   | backend | 1,234 |
   | database | 456 |

   **By Type** — symbol types (class, function, method, table, etc.):
   | Type | Count |
   |------|-------|
   | class | 500 |
   | function | 400 |

   **By Directory** — top directory categories:
   | Directory | Symbols |
   |-----------|---------|
   | controllers | 200 |
   | models | 150 |

3. Highlight the dominant layer and any imbalances (e.g., many backend symbols but zero database symbols may indicate missing schema indexing).

## Example

```
/wicked-search:categories
/wicked-search:categories --project my-app
```
