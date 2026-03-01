---
description: Analyze what would be affected by changing a symbol (reverse lineage)
argument-hint: <symbol> [--depth N] [--format table|json]
---

# /wicked-garden:search:impact

Analyze what would be affected if you changed a symbol. This is reverse lineage analysis - find all upstream consumers of a database column, entity field, or other sink.

## Arguments

- `symbol` (required): The symbol to analyze impact for
- `--depth` (optional): How deep to traverse dependencies (default: 10)
- `--format` (optional): Output format - table, json, mermaid (default: table)

## Instructions

1. Run the impact analysis (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python lineage_tracer.py "<symbol_id>" --db /path/to/graph.db --direction upstream --depth 10 --format table
   ```

3. Report the impact assessment:
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

# Impact analysis with JSON output
/wicked-garden:search:impact USERS.FIRST_NAME --format json
```

## Output

```markdown
## Impact Analysis: USERS.EMAIL

### Summary
- **Affected UI Fields**: 5
- **Affected Entity Fields**: 2
- **Affected Pages**: 3
- **Risk Level**: HIGH (PII field)

### Affected Symbols

| Layer | Symbol | Type | File | Line |
|-------|--------|------|------|------|
| entity | User.email | entity_field | User.java | 45 |
| entity | Customer.contactEmail | entity_field | Customer.java | 78 |
| ui | profile-form.email | form_binding | profile.jsp | 67 |
| ui | settings-email | el_expression | settings.jsp | 89 |
| ui | user-list.email | data_binding | UserList.vue | 34 |

### Lineage Paths

1. **column::USERS.EMAIL** ← entity_field::User.email ← form_binding::profile-form.email
2. **column::USERS.EMAIL** ← entity_field::User.email ← el_expression::${user.email}
```

## Use Cases

- **Pre-refactoring**: Know what will break before changing code
- **Database migration**: Find all code touching a column before altering it
- **Safe changes**: Identify low-risk symbols to modify first
- **Tech debt prioritization**: Focus on high-impact components

## Comparison with blast-radius

`/impact` is the enhanced replacement for `/blast-radius`:

| Feature | blast-radius | impact |
|---------|--------------|--------|
| Direction | Both | Upstream (consumers) |
| Output | Simple list | Rich table with locations |
| Confidence | No | Yes |
| Lineage paths | No | Yes |
| Save to DB | No | Yes (with --save) |

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- For database columns, specify as `column::TABLE.COLUMN` or just `TABLE.COLUMN`
- Deeper depth = more complete but slower analysis
- Use `/wicked-garden:search:lineage --direction downstream` for the reverse (what does this symbol affect)
