---
description: Find the most-referenced symbols in the codebase — classes, functions, and modules with the highest connectivity
argument-hint: "[--limit <n>] [--layer <layer>] [--type <type>] [--category <dir>]"
---

# /wicked-garden:search:hotspots

Identify hotspot symbols ranked by total reference count (incoming + outgoing). Use this to find central coupling points, high-impact refactor targets, and architectural load-bearers.

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the hotspots query via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py hotspots --limit "${limit:-20}" ${layer:+--layer "${layer}"} --path "${PWD}"
   ```

   With no arguments, returns the top 20 most-connected symbols across the whole codebase.

   If the control plane is available, also query for enrichment:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph hotspots --limit "${limit:-20}" ${layer:+--layer "${layer}"} ${type:+--type "${type}"} ${category:+--category "${category}"}
   ```
   This step is optional — the local index is fully functional without CP.

3. Arguments (all optional):

   | Argument | Default | Description |
   |----------|---------|-------------|
   | `--limit N` | 20 | Number of results to return |
   | `--layer LAYER` | — | Filter to one architectural layer (`backend`, `frontend`, `database`, `view`) |
   | `--type TYPE` | — | Filter to one symbol type (`CLASS`, `FUNCTION`, `METHOD`, `TABLE`, etc.) |
   | `--category DIR` | — | Filter to one directory category (e.g., `controllers`, `services`, `api`) |

4. Present results as a ranked table:

   | Rank | Symbol | Type | Layer | In | Out | Total |
   |------|--------|------|-------|----|-----|-------|
   | 1 | `UserService` | CLASS | backend | 42 | 18 | 60 |
   | 2 | `db_session` | FUNCTION | database | 38 | 5 | 43 |
   | 3 | `AuthMiddleware` | CLASS | backend | 31 | 11 | 42 |

   Each row comes from `data[i]` with fields: `name`, `type`, `layer`, `in_count`, `out_count`, `total_count`, `file`.

5. Highlight:
   - The top 3-5 symbols and why they are hotspots (high in-count = shared dependency; high out-count = coordinator/orchestrator)
   - Any layer with a disproportionate share of hotspots (potential coupling concentration)
   - Symbols where `in_count` is very high relative to `out_count` (widely imported utilities)
   - Symbols where `out_count` is very high relative to `in_count` (orchestrators or god objects worth reviewing)

## Example

```
/wicked-garden:search:hotspots
/wicked-garden:search:hotspots --limit 10
/wicked-garden:search:hotspots --layer backend
/wicked-garden:search:hotspots --type CLASS --limit 15
/wicked-garden:search:hotspots --category services
```
