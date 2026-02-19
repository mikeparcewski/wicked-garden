# Release wicked-search v2.1.1

**Date**: 2026-02-19
**Component**: wicked-search

## Summary

Fixes lineage API returning empty results (`{data: [], meta: {...}}`) due to a schema mismatch between migration.py and lineage_tracer.py.

## Changes

### Bug Fixes

- fix: align lineage_paths schema across migration.py, symbol_graph.py, and lineage_tracer.py
  - migration.py defined `steps TEXT NOT NULL` but lineage_tracer.py wrote to `path_nodes` + `computed_at`
  - All INSERTs silently failed, leaving lineage_paths table permanently empty
  - Unified on `path_nodes TEXT` + `computed_at TEXT` (matching symbol_graph.py and lineage_tracer.py)
- fix: import_graph_extras now auto-detects source column names (`path_nodes` vs legacy `steps`)
- feat: add schema version check — warns users to reindex when DB schema is outdated
- chore: bump PRAGMA user_version 201 → 202

## Upgrade Notes

**Existing users must reindex** after upgrading to pick up the schema fix:

```
/wicked-search:index <project-path>
```

If you don't reindex, the API will print a warning to stderr on every query.

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-search@wicked-garden
```
