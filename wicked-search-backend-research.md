# wicked-search Single Unified Backend - Research Report

**Project**: single-unified-search-backend
**Date**: 2026-02-16
**Researcher**: Research Agent

## Executive Summary

This report documents the current architecture of wicked-search to guide migration from dual backends (JSONL + Graph DBs) to a single unified SQLite backend. The migration infrastructure (`migration.py` and `query_builder.py`) is built but not yet wired into the command flow.

---

## 1. Current api.py Command Structure

**File**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/api.py` (1358 lines)

### Verb/Source Matrix

| Verb | Sources | Backend Used | Key Functions |
|------|---------|--------------|---------------|
| `list` | symbols, documents, references, graph, lineage, services, projects | JSONL (`_load_jsonl_index`) for symbols/docs/refs; SQLite (`_query_graph_dbs`) for graph/lineage/services | `cmd_list` (lines 332-436) |
| `search` | symbols, documents, references, graph, lineage | JSONL (`_search_nodes`) for symbols/docs/refs; SQLite for graph/lineage | `cmd_search` (lines 499-583) |
| `get` | symbols, documents, graph | JSONL for symbols/docs; SQLite for graph | `cmd_get` (lines 439-496) |
| `stats` | symbols, graph, services | Hybrid: JSONL + `_get_db_stats()` | `cmd_stats` (lines 1121-1282) |
| `traverse` | graph | SQLite (`_query_graph_dbs` + BFS) | `cmd_traverse` (lines 586-691) |
| `hotspots` | graph | SQLite (aggregates in/out refs) | `cmd_hotspots` (lines 694-755) |
| `categories` | symbols | SQLite (`_query_graph_dbs` + Python aggregation) | `cmd_categories` (lines 902-971) |
| `impact` | graph | SQLite (reverse lineage: column → entity_field → UI) | `cmd_impact` (lines 974-1045) |
| `content` | code | File system (reads source files) | `cmd_content` (lines 1048-1089) |
| `ide-url` | code | File system (generates deep links) | `cmd_ide_url` (lines 1092-1118) |

### Critical Backend Patterns

1. **`_query_graph_dbs(query, params, project)`** (lines 215-239)
   - Finds all `*_graph.db` files under index directory
   - Executes SQL across ALL graph DBs, merges results
   - Used for: graph list/search/get, lineage, services, traverse, hotspots, categories, impact
   - **27 callsites total** across api.py

2. **`_load_jsonl_index(project)`** (lines 87-108)
   - Loads ALL `*.jsonl` files into memory as list of dicts
   - Used for: symbols/docs/refs list/search/get
   - No caching — reads every time

3. **Hybrid Stats** (lines 250-275)
   - `_get_db_stats()` queries SQLite for symbol/ref counts
   - Returns `{db_files, total_symbols, total_refs}`
   - Combined with JSONL counts in `cmd_stats`

### Filter Application

- **Layer/Type/Category filters** applied in Python AFTER SQL query (lines 162-186, 342-390, 507-550)
- SQL queries never reference `layer` column (may not exist in older DBs)
- Over-fetching strategy: `sql_limit = (offset + limit) * 10` when Python filtering needed

---

## 2. Current unified_search.py Command Structure

**File**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/unified_search.py` (2979 lines)

### Commands and Backends

| Command | Current Backend | Handler Lines | What It Queries |
|---------|----------------|---------------|-----------------|
| `index` | JSONL builder + optional SymbolGraph SQLite | 2577-2650 | Builds JSONL via `ParallelIndexer`, optionally exports SymbolGraph to `*_graph.db` |
| `search` | JsonlSearcher (`search_all`) | 2708-2719 | JSONL with fuzzy matching (rapidfuzz) + filters |
| `code` | JsonlSearcher (`search_code`) | 2721-2732 | JSONL domain='code' + filters |
| `docs` | JsonlSearcher (`search_docs`) | 2734-2736 | JSONL domain='doc' |
| `refs` | JsonlSearcher (`find_references`) | 2738-2804 | JSONL relationships (calls, bases, dependents) |
| `impl` | JsonlSearcher (legacy, incomplete) | 2806-2827 | Finds doc → code cross-refs (not fully implemented) |
| `blast-radius` | JsonlSearcher OR SymbolGraph SQLite | 2829-2934 | JSONL by default; `--use-graph` flag switches to SQLite BFS |
| `stats` | JsonlSearcher (`get_stats`) | 2936-2975 | JSONL node/edge counts + group-by |
| `graph` | SymbolGraph SQLite | 2652-2696 | Exports SymbolGraph to JSON/SQLite |

### JsonlSearcher Class (lines 67-432)

**Instantiation**: Line 2402 in `load_jsonl()`
**Key Methods**:
- `search_all(query, limit)` — fuzzy search all nodes
- `search_code(query, limit)` — domain='code' only
- `search_docs(query, limit)` — domain='doc' only
- `find_references(symbol)` — bidirectional refs (calls, bases, dependents)
- `blast_radius(symbol, depth, edge_types, direction)` — BFS on calls/dependents
- `get_stats()` — aggregate counts by type/domain

**Storage**: Loads entire JSONL into memory dicts:
- `self._nodes: Dict[str, JsonlGraphNode]` — all nodes
- `self._name_index: Dict[str, List[str]]` — name → node IDs for fast lookup

**Fuzzy Search**: Uses `rapidfuzz.process.extract()` with WRatio scorer (score cutoff 50.0)

### SymbolGraph SQLite Usage

**When used**:
1. `index` command with `--export-db` flag → exports to `*_graph.db`
2. `blast-radius --use-graph` → reads from `*_graph.db` for cross-layer lineage
3. `graph` command → builds and exports SymbolGraph

**Schema**: Defined in `symbol_graph.py` (not in migration.py)
- Tables: `symbols`, `refs` (not `symbol_refs`), optional `lineage_paths`, `service_nodes`
- No unified schema — each language adapter writes its own structure

---

## 3. UnifiedQueryEngine Methods (query_builder.py)

**File**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/query_builder.py` (558 lines)

### Available Methods

| Method | Purpose | Lines | What api.py/unified_search.py Need |
|--------|---------|-------|-------------------------------------|
| `search_all(query, limit, offset)` | Multi-tier search: exact → prefix → FTS → qualified_name LIKE | 96-179 | Replaces JsonlSearcher.search_all() |
| `search_code(query, limit)` | Search code domain only | 181-242 | Replaces JsonlSearcher.search_code() |
| `search_docs(query, limit)` | Search doc domain only | 244-305 | Replaces JsonlSearcher.search_docs() |
| `find_references(symbol_id)` | Bidirectional refs (outgoing/incoming) | 307-341 | Replaces JsonlSearcher.find_references() |
| `blast_radius(symbol_id, max_depth)` | BFS on symbol_refs for downstream dependents | 343-383 | Replaces JsonlSearcher.blast_radius() |
| `list_symbols(limit, offset, type_filter, layer_filter, category_filter, domain_filter)` | List with filters | 385-429 | Replaces api.py cmd_list for symbols |
| `get_symbol(symbol_id)` | Get single symbol by ID | 431-436 | Replaces api.py cmd_get for symbols |
| `get_categories()` | Category stats + cross-category relationships | 438-508 | Replaces api.py cmd_categories |

### Missing Functionality

Methods needed but NOT in UnifiedQueryEngine:

1. **Traverse** (api.py lines 586-691)
   - BFS with depth + direction (in/out/both)
   - Returns `{root, nodes, edges}` structure
   - **Gap**: No equivalent in query_builder.py

2. **Hotspots** (api.py lines 694-755)
   - Aggregates in/out ref counts per symbol
   - Sorted by `total_count DESC`
   - **Gap**: No equivalent in query_builder.py

3. **Impact** (api.py lines 974-1045)
   - Reverse lineage: column → entity_field → UI field
   - Specific to ref_type='maps_to' and 'binds_to'
   - **Gap**: No equivalent in query_builder.py

4. **List/Search lineage** (api.py lines 24, 393-394, 557-566)
   - Queries `lineage_paths` table
   - **Gap**: No lineage methods in query_builder.py

5. **List/Search services** (api.py lines 26, 397-405, 1191-1250)
   - Queries `service_nodes` and `service_connections` tables
   - **Gap**: No service methods in query_builder.py

6. **Stats** (api.py cmd_stats, unified_search.py stats command)
   - Aggregates by type, ref_type, layer, domain
   - **Gap**: `get_categories()` only covers category stats, not full stats

7. **Get with dependencies/dependents** (api.py lines 444-482)
   - `cmd_get` for graph source enriches symbol with deps/dependents lists
   - **Gap**: `get_symbol()` returns plain symbol, no relationships

### Schema Assumptions

UnifiedQueryEngine assumes:
- `symbols` table with: id, name, type, qualified_name, file_path, line_start, line_end, domain, layer, category, content, metadata
- `symbol_refs` table with: source_id, target_id, ref_type
- `symbols_fts` FTS5 virtual table

These match migration.py schema, NOT the current `*_graph.db` schema.

---

## 4. Integration Point for Auto-Migration

### Current Index Flow (unified_search.py lines 2577-2650)

```
1. index command → build_index_jsonl() → writes JSONL files
2. Optional: --export-db flag → build_symbol_graph() → exports to *_graph.db
3. No unified DB built automatically
```

### Proposed Auto-Migration Hook

**Location**: `build_index_jsonl()` method in UnifiedSearchIndex class

**After** JSONL is written (line ~1900 in unified_search.py), **before** return:

```python
# Auto-migrate JSONL → unified SQLite
unified_db_path = get_index_dir(self.project) / f"{self._path_hash()}_unified.db"

if not unified_db_path.exists() or force:
    print("Building unified SQLite database...")
    migration_result = subprocess.run([
        sys.executable,
        str(Path(__file__).parent / "migration.py"),
        "--jsonl-dir", str(get_index_dir(self.project)),
        "--output", str(unified_db_path),
        "--existing-db", str(self._get_symbol_db_path())  # if exists
    ], capture_output=True, text=True)

    if migration_result.returncode == 0:
        print(f"  Unified DB: {unified_db_path}")
    else:
        print(f"  Warning: Unified DB build failed: {migration_result.stderr}")
```

**Alternative**: Hook into `index` command handler (lines 2577-2650) after JSONL + SymbolGraph build.

### Config-Based Rollback (migration.py lines 36-45)

UnifiedQueryEngine already checks for `config.json` with `fallback_to_jsonl: true` flag:
```python
if config.get('fallback_to_jsonl', False):
    raise NotImplementedError("Config specifies fallback_to_jsonl=true")
```

This allows instant rollback by setting flag in `~/.something-wicked/wicked-search/config.json`.

---

## 5. JsonlSearcher Usage Sites

**All usage of JsonlSearcher class**:

1. **Definition**: unified_search.py line 67
2. **Instantiation**: unified_search.py line 2402 in `load_jsonl()`
3. **Storage**: unified_search.py line 1448 as class member `self.jsonl_searcher`
4. **Method Calls**:
   - `search_all()` → line 2709 (search command)
   - `search_code()` → line 2722 (code command)
   - `search_docs()` → line 2735 (docs command)
   - `find_references()` → line 2739 (refs command)
   - `blast_radius()` → line 2899 (blast-radius command without --use-graph)
   - `get_stats()` → line 2411 (stats command)

**Removal strategy**:
1. Replace JsonlSearcher instantiation with UnifiedQueryEngine
2. Update method calls to use query_builder methods
3. Remove JsonlSearcher class definition (lines 67-432)

**Note**: JsonlSearcher is ONLY used in unified_search.py, NOT in api.py.

---

## 6. _query_graph_dbs Usage Sites

**All 27 callsites in api.py**:

| Function | Lines | Query Type |
|----------|-------|------------|
| `cmd_list` | 375, 394, 398, 404 | SELECT from symbols, lineage_paths, service_nodes, service_connections |
| `cmd_get` | 446, 461, 475 | SELECT symbol + deps/dependents via refs |
| `cmd_search` | 534, 563 | WHERE name/qualified_name LIKE; lineage search |
| `cmd_traverse` | 630, 644, 663 | BFS: SELECT refs WHERE source_id/target_id; batch symbol fetch |
| `cmd_hotspots` | 728 | COUNT refs per symbol, JOIN for in/out counts |
| `cmd_categories` | 917, 928, 880, 884 | GROUP BY type/layer; cross-category refs |
| `cmd_impact` | 998, 1011, 1018, 1029 | Reverse lineage via maps_to → binds_to refs |

**Common patterns**:
- Most queries use `symbols` table
- Refs queried via `refs` table (not `symbol_refs` or `symbol_references`)
- Cross-DB merging happens in `_query_graph_dbs` (lines 216-238)

**Replacement strategy**:
1. Remove `_query_graph_dbs()` function
2. Replace with UnifiedQueryEngine method calls
3. Update SQL to use `symbol_refs` table (migration.py schema)
4. Remove multi-DB logic — single DB only

---

## 7. The Gap: Missing Methods in UnifiedQueryEngine

### Methods to Add

1. **`traverse(symbol_id, depth, direction)`**
   - BFS with configurable direction (in/out/both)
   - Returns `{root, nodes, edges}` structure
   - Based on api.py lines 586-691

2. **`hotspots(limit, offset, layer_filter, type_filter, category_filter)`**
   - Aggregate in/out ref counts
   - Sort by total_count DESC
   - Based on api.py lines 694-755

3. **`impact_analysis(column_id)`**
   - Reverse lineage for database columns
   - Follow maps_to → binds_to chains
   - Based on api.py lines 974-1045

4. **`list_lineage(limit, offset)`**
   - Query lineage_paths table
   - Based on api.py lines 393-394

5. **`search_lineage(query, limit, offset)`**
   - Search lineage_paths by source_id/sink_id
   - Based on api.py lines 557-566

6. **`list_services(limit, offset)`**
   - Query service_nodes + enrich with connections
   - Based on api.py lines 397-405

7. **`get_stats()`**
   - Aggregate counts by type, ref_type, layer, domain
   - Based on api.py lines 1121-1282

8. **`get_symbol_with_refs(symbol_id)`**
   - Get symbol + dependencies/dependents lists
   - Based on api.py lines 444-482

### Schema Extensions Needed

Migration.py already includes:
- `symbol_refs` table ✓
- `symbols` with layer/category/domain ✓
- `symbols_fts` FTS5 index ✓

**Missing tables for full parity**:
- `lineage_paths` (for lineage commands)
- `service_nodes` (for services commands)
- `service_connections` (for services commands)

These are currently in SymbolGraph exports but not in migration.py schema.

---

## 8. Recommended Migration Path

### Phase 1: Extend UnifiedQueryEngine

1. Add missing methods to query_builder.py:
   - `traverse()`, `hotspots()`, `impact_analysis()`
   - `list_lineage()`, `search_lineage()`
   - `list_services()`
   - `get_stats()`, `get_symbol_with_refs()`

2. Extend migration.py schema to include:
   - `lineage_paths` table
   - `service_nodes` table
   - `service_connections` table

### Phase 2: Wire in Auto-Migration

1. Add migration hook to `index` command flow (unified_search.py)
2. Auto-build unified DB after JSONL + SymbolGraph complete
3. Store unified DB as `*_unified.db`

### Phase 3: Update Commands

**unified_search.py**:
1. Replace JsonlSearcher with UnifiedQueryEngine in all commands
2. Remove JsonlSearcher class
3. Update method calls to match query_builder API

**api.py**:
1. Replace `_query_graph_dbs()` with UnifiedQueryEngine calls
2. Replace `_load_jsonl_index()` with UnifiedQueryEngine calls
3. Remove multi-DB logic
4. Update SQL to use migration.py schema (symbol_refs, not refs)

### Phase 4: Test + Rollback

1. Add `config.json` check in all commands
2. Test with `fallback_to_jsonl: true` to verify old path still works
3. Run acceptance tests against both backends
4. Document rollback procedure

---

## 9. Key Design Decisions

### Why Single DB?

**Current problems**:
- JsonlSearcher loads entire index into memory (no pagination)
- `_query_graph_dbs()` queries N databases and merges results (slow)
- Dual maintenance of JSONL + SQLite schemas
- No shared FTS index across formats

**Unified benefits**:
- Single source of truth
- SQL pagination + filtering at DB level
- FTS5 for fast text search
- Category + lineage + services in same DB
- Easier to extend (add tables, not new formats)

### Why Not Just Use SymbolGraph SQLite?

SymbolGraph DBs are language-specific:
- Each parser writes its own schema
- No unified layer/category/domain fields
- No FTS index
- No migration path from JSONL

Migration.py creates a **normalized** schema that works for all languages.

### Why Keep JSONL in Index Flow?

JSONL is the **intermediate format** from parallel indexing:
- `ParallelIndexer` streams JSONL as files are parsed
- Allows incremental updates (via `IncrementalUpdater`)
- Fast to write, easy to debug

Unified DB is built **from** JSONL, not instead of it.

---

## 10. File Locations

| File | Path | Lines |
|------|------|-------|
| api.py | `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/api.py` | 1358 |
| unified_search.py | `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/unified_search.py` | 2979 |
| query_builder.py | `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/query_builder.py` | 558 |
| migration.py | `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/migration.py` | 657 |
| indexer.py | `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-search/scripts/indexer.py` | 197 |

---

## End of Research Report

**Next Steps**: Use this report to build clarify phase deliverables (requirements, constraints, acceptance criteria).
