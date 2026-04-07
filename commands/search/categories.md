---
description: Show symbol categories — types, layers, directory groupings, and cross-category relationships
argument-hint: "[--project <name>]"
---

# /wicked-garden:search:categories

Show how indexed symbols break down by type, architectural layer, and directory — plus how categories relate to each other via references.

## Instructions

1. **Query brain for symbol inventory**:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"class function method entity table component","limit":100}}'
   ```
   If brain is unavailable, fall back to Grep/Glob:
   - Use Glob to discover source file structure by directory
   - Use Grep to extract symbol definitions (class, function, method, etc.)
   Suggest `wicked-brain:ingest` to index the codebase for richer categorization.

2. **Categorize symbols** by analyzing brain results and file paths:
   - **By Layer**: backend, frontend, database, view (inferred from directory structure)
   - **By Type**: class, function, method, table, component (from symbol definitions)
   - **By Directory**: group by top-level directory categories

3. **Detect relationships** using Grep to find cross-category references (imports, calls).

4. Present results in five sections:

   **By Layer** — architectural layers:
   | Layer | Symbols |
   |-------|---------|
   | backend | 1,234 |
   | database | 456 |

   **By Type** — symbol types:
   | Type | Count |
   |------|-------|
   | class | 500 |
   | function | 400 |

   **By Directory** — top directory categories:
   | Directory | Symbols |
   |-----------|---------|
   | controllers | 200 |
   | models | 150 |

   **Layer Relationships** — how architectural layers connect:
   | Source | Target | Ref Type | Count |
   |--------|--------|----------|-------|
   | backend | database | queries | 340 |
   | frontend | backend | calls | 210 |

   **Directory Relationships** — top cross-directory connections:
   | Source | Target | Ref Type | Count |
   |--------|--------|----------|-------|
   | controllers | services | calls | 120 |
   | services | models | imports | 95 |

5. Highlight:
   - The dominant layer and any imbalances
   - Strongest cross-layer relationships (which layers are tightly coupled)
   - Directory clusters that have high interconnection (potential modules)
   - Any unexpected relationship patterns (e.g., view layer directly querying database)

## Example

```
/wicked-garden:search:categories
```
