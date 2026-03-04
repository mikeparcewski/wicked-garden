# Release wicked-garden v1.12.1

**Date**: 2026-03-04
**Component**: wicked-garden

## Summary

Bug fix release resolving 7 issues (#191-#197) discovered during full 100-scenario acceptance test run. Fixes cover search indexing (doc-to-code cross-references), migration performance (incremental manifest-based tracking), thread safety (SqliteStore locking), and scenario reliability improvements.

## Changes

### Bug Fixes

- **search**: Add DocLinker for doc-to-code cross-reference edge generation (#191)
- **search**: Implement incremental migration with manifest tracking — 750x faster no-op (#192)
- **core**: Add per-path threading.Lock to SqliteStore for thread safety (#193)
- **scenarios**: Fix `end_session()` → `persist_session_meta()` in session-context-injection (#194)
- **scenarios**: Add mcp.json guard to 04-mcp-server-integration (#195)
- **scenarios**: Move `hey` from tools.required to tools.optional in perf-load-test (#196)
- **scenarios**: Reduce blast-radius-analysis from 209 to 126 lines (#197)

### Details

#### DocLinker (Pass 2b) — #191
New `DocLinker` class in `linker.py` scans doc nodes for CamelCase identifiers and backtick-quoted names, matching them against code symbols. Writes `metadata["documents"]` edges so migration creates `ref_type='documents'` relationships. Fixes cross-reference-detection, find-implementations, and document-extraction scenarios.

#### Incremental Migration — #192
Added `_migration_manifest` table tracking file hash (size+mtime) per JSONL. `import_jsonl_symbols_incremental()` skips unchanged files, re-processes only changed ones. Reduces no-op migration from >60s to 0.4s. Includes `--force-full` escape hatch.

#### SqliteStore Thread Safety — #193
Module-level lock registry with double-checked locking pattern. All read/write methods wrapped with `with self._lock:`. Inlined `self.get()` calls inside write methods to prevent deadlock.

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-garden@wicked-garden
```
