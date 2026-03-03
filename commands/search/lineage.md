---
description: Trace data lineage from source to sink (UI → DB or reverse)
argument-hint: <symbol> [--direction upstream|downstream|both] [--depth N]
---

# /wicked-garden:search:lineage

Trace data lineage paths through the knowledge graph. Follow data flow from UI fields to database columns (downstream) or reverse (upstream).

## Arguments

- `symbol` (required): The symbol ID to trace from
- `--direction` (optional): Direction to trace (default: downstream)
  - `downstream`: Source → sink (e.g., UI field → DB column)
  - `upstream`: Sink → source (e.g., DB column → UI fields)
  - `both`: Trace in both directions
- `--depth` (optional): Maximum traversal depth (default: 10)

## Instructions

1. Determine which execution path to use:
   - **Local-only mode** (session mode is `local-only`, or CP is unavailable): use the vendored tracer directly (Step 2a).
   - **CP available**: proxy through the control plane (Step 2b).

2a. **Local-only — vendored tracer** (use when CP is unavailable or mode is `local-only`):
   ```bash
   DB_PATH=$(python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); from _paths import get_local_file; print(get_local_file('wicked-search', 'unified_search.db'))")
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lineage_tracer.py" \
     "${symbol_id}" \
     --db "${DB_PATH}" \
     --direction "${direction:-downstream}" \
     --depth "${depth:-10}"
   ```

   If `${DB_PATH}` does not exist yet, report that the search index has not been built and suggest running `/wicked-garden:search:index` first.

2b. **CP available — proxy**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge lineage search "<symbol_id>" --direction "${direction:-downstream}" --depth "${depth:-10}"
   ```

3. Parse the response:
   - For the vendored tracer (2a): output is plain text (table or mermaid). Present it directly.
   - For the CP proxy (2b): parse the `data` field of the JSON envelope.

4. Report the lineage paths found:
   - Show each path with steps from source to sink
   - Include confidence level and completeness status
   - Note any gaps in the lineage chain

## Examples

```bash
# Trace downstream from a UI field
/wicked-garden:search:lineage form_binding::person.firstName --direction downstream

# Find all UI fields that use a database column
/wicked-garden:search:lineage column::USERS.EMAIL --direction upstream

# Trace both directions
/wicked-garden:search:lineage entity_field::User.email --direction both
```

## Output

### Table Format
```
| # | Source | Sink | Steps | Confidence | Complete |
|---|--------|------|-------|------------|----------|
| 1 | firstName | FIRST_NAME | 3 | high | yes |
| 2 | lastName | LAST_NAME | 3 | medium | yes |
```

## Use Cases

- **Impact analysis**: Before changing a database column, find all UI fields that use it
- **Data flow documentation**: Understand how data flows through the system
- **Debugging**: Trace why a UI field isn't displaying expected data
- **Compliance**: Document which UI fields expose sensitive database columns

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Use `/wicked-garden:search:impact` for reverse lineage (upstream consumers)
