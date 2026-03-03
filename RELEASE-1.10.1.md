# wicked-garden v1.10.1

## Summary

Resolves 9 bugs discovered during a full 100-scenario test run, plus migrates all search commands to a local-first architecture.

## What Changed

### Bug Fixes (9 issues: #158-#168)

- **FTS5 integrity check** (#158) — New `integrity-check` subcommand on `unified_search.py` with `--repair` flag. Detects and rebuilds corrupted FTS5 indexes.
- **Python symbol extraction** (#159) — `python_adapter.py` now extracts classes, functions, and methods from any Python file via tree-sitter AST, not just ORM-specific patterns.
- **Multi-specialist schema** (#161) — `health_probe.py` now handles both the array format `{"specialists": [...]}` and legacy `{"specialist": {...}}` correctly.
- **Archetype false positive** (#162) — Removed "scoring" from infrastructure-framework keywords in `smart_decisioning.py` to prevent false positives.
- **Stale model ID** (#163) — Updated `anthropic/claude-3-5-sonnet` to `anthropic/claude-sonnet-4-6` in jam code review scenario.
- **Smaht scenarios** (#165) — Rewrote `fact-extraction`, `graceful-degradation`, and `01-fresh-install` with executable bash steps calling CLI scripts directly (no marketplace installation required).
- **Local-first search** (#166) — All 18 search commands now route through `unified_search.py` (local SQLite/FTS5) as primary path. CP is optional enhancement, not required.
- **Kanban comment routing** (#167) — Comments now route through local `kanban.py add-comment` instead of requiring CP.
- **Specialist role validation** (#168) — `specialist_discovery.py` now accepts role values (e.g., "brainstorming") not just category keys (e.g., "ideation").
- **KanbanStore import** — Fixed import shadowed by package `__init__.py`.

### Search Architecture: Local-First

All 18 search commands now use `unified_search.py` as their primary execution path:

| Subcommand | Status |
|-----------|--------|
| code, docs, search, refs, blast-radius, impl, lineage, stats, scout, index | Already local-first |
| hotspots, impact, categories, coverage, service-map, validate, quality | **Migrated in this release** |
| integrity-check | **New in this release** |

The control plane is now purely additive — search works fully offline with local SQLite.

### Documentation

- README: 125 commands, 79 agents, 71 skills, 48 personas (previously 116/78/70/47)
- CLAUDE.md: Updated persona count
- plugin.json/marketplace.json: Updated descriptions

## Upgrade Notes

No breaking changes. Search commands that previously required CP connectivity now work locally. CP integration remains available as an enhancement layer.
