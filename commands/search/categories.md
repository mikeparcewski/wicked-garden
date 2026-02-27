---
description: Show symbol categories — types, layers, directory groupings, and cross-category relationships
argument-hint: "[--project <name>]"
---

# /wicked-garden:search:categories

Show how indexed symbols break down by type, architectural layer, and directory — plus how categories relate to each other via references.

## Instructions

1. Run the categories query via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols categories
   ```

   If a project is specified:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols categories --project "<project>"
   ```

2. Present results in five sections:

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

   **Layer Relationships** — how architectural layers connect (from `data.relationships.by_layer`):
   | Source | Target | Ref Type | Count |
   |--------|--------|----------|-------|
   | backend | database | queries | 340 |
   | frontend | backend | calls | 210 |

   **Directory Relationships** — top cross-directory connections (from `data.relationships.by_directory`):
   | Source | Target | Ref Type | Count |
   |--------|--------|----------|-------|
   | controllers | services | calls | 120 |
   | services | models | imports | 95 |

3. Highlight:
   - The dominant layer and any imbalances
   - Strongest cross-layer relationships (which layers are tightly coupled)
   - Directory clusters that have high interconnection (potential modules)
   - Any unexpected relationship patterns (e.g., view layer directly querying database)

## Example

```
/wicked-garden:search:categories
/wicked-garden:search:categories --project my-app
```
