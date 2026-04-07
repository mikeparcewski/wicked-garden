---
description: Analyze what would be affected by changing a symbol (reverse lineage)
argument-hint: "<symbol> [--depth N]"
---

# /wicked-garden:search:impact

Analyze what would be affected if you changed a symbol. Uses the knowledge graph's impact analysis to find all upstream consumers of a database column, entity field, or other symbol.

## Arguments

- `symbol` (required): The symbol to analyze impact for
- `--depth` (optional): How deep to traverse dependencies (default: 10)

## Instructions

1. **Search via brain** for reference discovery:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<symbol>","limit":30}}'
   ```
   Use matching chunks as the starting set for impact analysis.

2. **Trace upstream consumers**: Use Grep to find all code that imports, calls, or references the affected symbol. Follow the data flow from database → entity → API → UI.

3. **If brain is unavailable**: Use Grep and Glob exclusively to trace the impact chain.
   Suggest: `wicked-brain:ingest` for richer lineage-aware analysis.

3. Parse the response which contains affected symbols and paths.

5. Report the impact assessment:
   - **Affected UI Fields**: What UI elements display/collect this data
   - **Affected Entities**: What entity fields map to this column
   - **Affected Pages**: What pages contain the affected UI fields
   - Show file:line locations for each affected symbol

## Examples

```bash
# What breaks if I change this column?
/wicked-garden:search:impact column::USERS.EMAIL

# What uses this entity field?
/wicked-garden:search:impact entity_field::User.email

# Shallow impact (direct dependents only)
/wicked-garden:search:impact USERS.FIRST_NAME --depth 2
```

## Output

```markdown
## Impact Analysis: USERS.EMAIL

### Summary
- **Affected UI Fields**: 5
- **Affected Entity Fields**: 2
- **Affected Pages**: 3

### Affected Symbols

| Layer | Symbol | Type | File | Line |
|-------|--------|------|------|------|
| entity | User.email | entity_field | User.java | 45 |
| ui | profile-form.email | form_binding | profile.jsp | 67 |
```

## Comparison with blast-radius

| Feature | blast-radius | impact |
|---------|--------------|--------|
| Analysis | Graph traversal (all edges) | Lineage-aware (data flow) |
| Direction | Both | Upstream (consumers) |
| Best for | Refactoring risk | Database/schema changes |

## Use Cases

- **Pre-refactoring**: Know what will break before changing code
- **Database migration**: Find all code touching a column before altering it
- **Safe changes**: Identify low-risk symbols to modify first

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- For database columns, specify as `column::TABLE.COLUMN` or just `TABLE.COLUMN`
- For general dependency analysis, use `/wicked-garden:search:blast-radius` instead
