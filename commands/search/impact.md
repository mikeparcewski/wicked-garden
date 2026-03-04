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

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the impact analysis via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py impact "<symbol>" --path "${PWD}"
   ```

3. If the control plane is available, also query for enrichment:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph impact "<symbol>" --depth "${depth:-10}"
   ```
   This step is optional — the local index is fully functional without CP.

4. Parse the response which contains affected symbols and paths.

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
